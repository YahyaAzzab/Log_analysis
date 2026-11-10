"""Tests for burst / bot detection."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import List

from processing.detection import (
    BOT_MIN_ATTEMPTS,
    BOT_WINDOW_SECONDS,
    MALICIOUS_MIN_FAILURES,
    detect_bots,
)


def _fail(
    ip: str,
    ts: datetime,
    username: str = "root",
    event_type: str = "failed_password",
) -> SimpleNamespace:
    return SimpleNamespace(
        ip=ip,
        timestamp=ts,
        username=username,
        event_type=event_type,
    )


def test_bot_burst_within_window() -> None:
    """>= BOT_MIN_ATTEMPTS failures inside BOT_WINDOW_SECONDS => bot."""
    start = datetime(2024, 5, 1, 12, 0, 0)
    events = [
        _fail("1.1.1.1", start + timedelta(seconds=i), username=f"u{i}")
        for i in range(BOT_MIN_ATTEMPTS)
    ]
    scores = detect_bots(events)
    info = scores["1.1.1.1"]
    assert info["is_bot"] is True
    assert info["is_malicious"] is True
    assert info["max_burst"] >= BOT_MIN_ATTEMPTS
    assert info["failed_count"] == BOT_MIN_ATTEMPTS
    assert info["burst_window_seconds"] == BOT_WINDOW_SECONDS
    assert info["nb_usernames_distincts"] == BOT_MIN_ATTEMPTS


def test_human_sparse_failures() -> None:
    """Failures spaced beyond the window should not mark a bot."""
    start = datetime(2024, 5, 1, 12, 0, 0)
    events = [
        _fail("2.2.2.2", start + timedelta(seconds=i * (BOT_WINDOW_SECONDS + 1)))
        for i in range(BOT_MIN_ATTEMPTS)
    ]
    scores = detect_bots(events)
    info = scores["2.2.2.2"]
    assert info["is_bot"] is False
    assert info["max_burst"] == 1
    assert info["failed_count"] == BOT_MIN_ATTEMPTS
    # Not malicious unless volume threshold reached
    assert info["is_malicious"] is (BOT_MIN_ATTEMPTS >= MALICIOUS_MIN_FAILURES)


def test_boundary_exactly_min_attempts_in_window() -> None:
    """Exactly BOT_MIN_ATTEMPTS events spanning exactly the window => bot."""
    start = datetime(2024, 5, 1, 12, 0, 0)
    # N events from t=0 to t=window inclusive -> all within <= window seconds
    events: List[SimpleNamespace] = []
    for i in range(BOT_MIN_ATTEMPTS):
        offset = 0 if BOT_MIN_ATTEMPTS == 1 else int(
            i * BOT_WINDOW_SECONDS / (BOT_MIN_ATTEMPTS - 1)
        )
        events.append(_fail("3.3.3.3", start + timedelta(seconds=offset)))

    scores = detect_bots(events)
    info = scores["3.3.3.3"]
    assert info["max_burst"] == BOT_MIN_ATTEMPTS
    assert info["is_bot"] is True


def test_boundary_just_under_bot_threshold() -> None:
    """BOT_MIN_ATTEMPTS - 1 failures in the window => not a bot."""
    start = datetime(2024, 5, 1, 12, 0, 0)
    n = BOT_MIN_ATTEMPTS - 1
    events = [
        _fail("4.4.4.4", start + timedelta(seconds=i))
        for i in range(n)
    ]
    scores = detect_bots(events)
    info = scores["4.4.4.4"]
    assert info["max_burst"] == n
    assert info["is_bot"] is False


def test_malicious_by_volume_without_burst() -> None:
    """High volume spaced out => malicious, but not bot."""
    start = datetime(2024, 5, 1, 12, 0, 0)
    events = [
        _fail("5.5.5.5", start + timedelta(seconds=i * (BOT_WINDOW_SECONDS + 5)))
        for i in range(MALICIOUS_MIN_FAILURES)
    ]
    scores = detect_bots(events)
    info = scores["5.5.5.5"]
    assert info["is_bot"] is False
    assert info["failed_count"] == MALICIOUS_MIN_FAILURES
    assert info["is_malicious"] is True


def test_ignores_accepted_events() -> None:
    start = datetime(2024, 5, 1, 12, 0, 0)
    events = [
        _fail("6.6.6.6", start, event_type="accepted"),
        _fail("6.6.6.6", start + timedelta(seconds=1), event_type="accepted"),
    ]
    assert detect_bots(events) == {}
