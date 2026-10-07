from datetime import UTC, datetime

import pytest

from app.limits import Limits, RateLimiter, next_daily_reset

# 2026-10-07 12:00 UTC = 05:00 in California (PDT): the quota day started at 07:00 UTC.
NOON_UTC = datetime(2026, 10, 7, 12, 0, tzinfo=UTC).timestamp()


class Clock:
    def __init__(self, now: float = NOON_UTC):
        self.now = now

    def __call__(self) -> float:
        return self.now


def limiter(clock: Clock, **overrides) -> RateLimiter:
    values = {"global_per_minute": 12, "global_per_day": 300, "ip_per_minute": 3, "ip_per_day": 20}
    return RateLimiter(Limits(**{**values, **overrides}), clock=clock)


def test_ip_minute_limit_and_window():
    clock = Clock()
    rl = limiter(clock)

    assert [rl.check("1.1.1.1") for _ in range(3)] == [None, None, None]
    clock.now += 20
    refusal = rl.check("1.1.1.1")

    assert (refusal.scope, refusal.limit, refusal.retry_after) == ("ip_minute", 3, 40)
    assert rl.check("2.2.2.2") is None  # another address is not affected
    clock.now += 40
    assert rl.check("1.1.1.1") is None  # the first questions left the 60 s window


def test_global_minute_limit_across_addresses():
    clock = Clock()
    rl = limiter(clock, global_per_minute=4)

    results = [rl.check(f"10.0.0.{i}") for i in range(5)]

    assert results[:4] == [None] * 4
    assert results[4].scope == "global_minute"


def test_ip_day_limit_resets_at_pacific_midnight():
    clock = Clock()
    rl = limiter(clock, ip_per_day=2)
    rl.check("1.1.1.1")
    clock.now += 120
    rl.check("1.1.1.1")
    clock.now += 120

    refusal = rl.check("1.1.1.1")

    assert refusal.scope == "ip_day"
    assert refusal.resets_at == datetime(2026, 10, 8, 7, 0, tzinfo=UTC)
    assert refusal.retry_after == int(refusal.resets_at.timestamp() - clock.now)
    clock.now = datetime(2026, 10, 8, 7, 0, 1, tzinfo=UTC).timestamp()
    assert rl.check("1.1.1.1") is None


def test_global_day_limit_comes_first():
    clock = Clock()
    rl = limiter(clock, global_per_day=2)
    rl.check("1.1.1.1")
    rl.check("2.2.2.2")

    assert rl.check("3.3.3.3").scope == "global_day"


def test_refused_questions_are_not_counted():
    clock = Clock()
    rl = limiter(clock, ip_per_minute=1, ip_per_day=2)
    rl.check("1.1.1.1")
    for _ in range(5):
        assert rl.check("1.1.1.1").scope == "ip_minute"
    clock.now += 61

    assert rl.check("1.1.1.1") is None  # the 5 refusals did not use up the daily 2


def test_addresses_are_not_kept_in_clear():
    rl = limiter(Clock())
    rl.check("203.0.113.7")

    assert "203.0.113.7" not in repr(vars(rl))


@pytest.mark.parametrize(
    ("now", "reset"),
    [
        # 11:22 in California (PDT, UTC-7): next midnight is 07:00 UTC the next day.
        (datetime(2026, 10, 6, 18, 22, tzinfo=UTC), datetime(2026, 10, 7, 7, 0, tzinfo=UTC)),
        # In winter (PST, UTC-8) midnight is 08:00 UTC.
        (datetime(2026, 12, 1, 9, 0, tzinfo=UTC), datetime(2026, 12, 2, 8, 0, tzinfo=UTC)),
    ],
)
def test_next_daily_reset_is_midnight_pacific(now, reset):
    assert next_daily_reset(now) == reset
