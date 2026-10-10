"""The client address used by the per-IP limits, directly or behind trusted proxies."""

import pytest
from starlette.requests import Request

from app.ask import client_ip
from app.limits import Limits, RateLimiter
from tests.conftest import make_settings
from tests.fakes import FakeLLM
from tests.test_ask import ask, ask_client

PEER = "10.0.0.9"  # the proxy, as the app sees it


def request(*forwarded: str) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
    return Request({"type": "http", "headers": headers, "client": (PEER, 50000)})


@pytest.mark.parametrize(
    ("forwarded", "hops", "expected"),
    [
        ((), 0, PEER),  # no proxy: the direct peer
        (("198.51.100.4",), 0, PEER),  # header ignored without trusted proxies
        ((), 1, PEER),  # no header: the direct peer
        (("198.51.100.4",), 1, "198.51.100.4"),  # one proxy appended the client
        (("203.0.113.7, 198.51.100.4",), 1, "198.51.100.4"),  # forged value on the left
        (("203.0.113.7, 198.51.100.4, 10.1.2.3",), 2, "198.51.100.4"),  # two proxies
        (("198.51.100.4",), 2, PEER),  # fewer values than trusted proxies
        ((" 2001:db8::5 ,  198.51.100.4 ",), 2, "2001:db8::5"),  # spaces, IPv6
        (("2001:db8::5",), 1, "2001:db8::5"),
        (("203.0.113.7", "198.51.100.4"), 1, "198.51.100.4"),  # two header lines, in order
        ((", ,198.51.100.4",), 1, "198.51.100.4"),  # empty entries skipped
    ],
)
def test_client_ip(forwarded, hops, expected):
    assert client_ip(request(*forwarded), hops) == expected


def test_no_client_at_all():
    assert client_ip(Request({"type": "http", "headers": []}), 1) == "unknown"


@pytest.mark.anyio
async def test_forged_header_does_not_get_round_the_per_ip_limit(db, loaded):
    limiter = RateLimiter(
        Limits(global_per_minute=100, global_per_day=100, ip_per_minute=1, ip_per_day=100)
    )
    settings = make_settings(forwarded_trusted_hops=1)

    async with ask_client(FakeLLM(), limiter=limiter, settings=settings, ip=PEER) as client:
        first = await client.post(
            "/api/ask",
            json={"question": "Gece uçuşu?", "lang": "tr"},
            headers={"X-Forwarded-For": "198.51.100.4"},
        )
        forged = await client.post(
            "/api/ask",
            json={"question": "Gece uçuşu?", "lang": "tr"},
            headers={"X-Forwarded-For": "203.0.113.7, 198.51.100.4"},
        )
        other = await ask(client, "Gece uçuşu?")  # another client: no header, so the peer

    assert first.status_code == 200
    assert forged.status_code == 429
    assert other.status_code == 200
