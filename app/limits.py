"""In-memory request limits for /api/ask, and when Gemini's daily quotas reset.

The counters live in the process, which is enough for the single uvicorn worker this demo
runs with; more workers would each keep their own counts. IP addresses are kept only as salted
hashes (the salt is random per process) and are never written to the database or the logs.
Behind a proxy the address comes from X-Forwarded-For, counted from the right by the number of
trusted proxies (app/ask.py: client_ip), so a client cannot pick it by sending the header.

"Day" means the Gemini quota day: it starts at midnight Pacific time, when the API's daily
quotas reset, so the app's daily limits and the provider's reset together.
"""

import hashlib
import secrets
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")
WINDOW_SECONDS = 60.0

Scope = Literal["ip_minute", "ip_day", "global_minute", "global_day"]


def next_daily_reset(now: datetime) -> datetime:
    """The next midnight in Pacific time, in UTC: when Gemini's daily quotas reset."""
    pacific = now.astimezone(PACIFIC)
    midnight = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(UTC)


@dataclass(frozen=True)
class Limits:
    global_per_minute: int
    global_per_day: int
    ip_per_minute: int
    ip_per_day: int


@dataclass(frozen=True)
class Refusal:
    scope: Scope
    limit: int
    retry_after: int  # seconds
    resets_at: datetime | None  # for the daily limits, in UTC


class RateLimiter:
    def __init__(self, limits: Limits, clock: Callable[[], float] = time.time):
        self.limits = limits
        self.clock = clock
        self._salt = secrets.token_bytes(16)
        self._day: date | None = None
        self._global_minute: deque[float] = deque()
        self._ip_minute: dict[str, deque[float]] = {}
        self._global_day = 0
        self._ip_day: dict[str, int] = {}

    def _key(self, ip: str) -> str:
        return hashlib.sha256(self._salt + ip.encode()).hexdigest()[:16]

    def _start_day_if_new(self, now: float) -> None:
        day = datetime.fromtimestamp(now, PACIFIC).date()
        if day != self._day:
            self._day = day
            self._global_day = 0
            self._ip_day.clear()

    def check(self, ip: str) -> Refusal | None:
        """Count one question from this IP, or return why it is refused (not counted)."""
        now = self.clock()
        self._start_day_if_new(now)
        key = self._key(ip)
        ip_minute = self._ip_minute.setdefault(key, deque())
        for window in (self._global_minute, ip_minute):
            while window and now - window[0] >= WINDOW_SECONDS:
                window.popleft()

        reset = next_daily_reset(datetime.fromtimestamp(now, UTC))
        until_reset = max(1, int(reset.timestamp() - now))
        limits = self.limits
        if self._global_day >= limits.global_per_day:
            return Refusal("global_day", limits.global_per_day, until_reset, reset)
        if self._ip_day.get(key, 0) >= limits.ip_per_day:
            return Refusal("ip_day", limits.ip_per_day, until_reset, reset)
        if len(self._global_minute) >= limits.global_per_minute:
            wait = WINDOW_SECONDS - (now - self._global_minute[0])
            return Refusal("global_minute", limits.global_per_minute, max(1, round(wait)), None)
        if len(ip_minute) >= limits.ip_per_minute:
            wait = WINDOW_SECONDS - (now - ip_minute[0])
            return Refusal("ip_minute", limits.ip_per_minute, max(1, round(wait)), None)

        self._global_minute.append(now)
        ip_minute.append(now)
        self._global_day += 1
        self._ip_day[key] = self._ip_day.get(key, 0) + 1
        self._forget_idle(now)
        return None

    def _forget_idle(self, now: float) -> None:
        """Drop per-IP minute windows with nothing in the last minute, so memory stays small."""
        if len(self._ip_minute) > 1000:
            for key in [k for k, w in self._ip_minute.items() if not w or now - w[-1] >= 60]:
                del self._ip_minute[key]
