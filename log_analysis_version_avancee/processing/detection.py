"""Detect aggressive / bot-like IPs from failed auth events."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Set

from dotenv import load_dotenv

# Tunable thresholds (defaults: 5 failures in 30 seconds)
BOT_MIN_ATTEMPTS = 5
BOT_WINDOW_SECONDS = 30
MALICIOUS_MIN_FAILURES = 20

_FAIL_TYPES = frozenset({"failed_password", "invalid_user", "auth_failure"})

load_dotenv()


def _max_burst(timestamps: List[datetime], window_seconds: int) -> int:
    """Largest number of failures inside any sliding time window."""
    if not timestamps:
        return 0
    ordered = sorted(timestamps)
    left = 0
    best = 0
    for right, current in enumerate(ordered):
        while (current - ordered[left]).total_seconds() > window_seconds:
            left += 1
        best = max(best, right - left + 1)
    return best


def detect_bots(events: Iterable[object]) -> Dict[str, dict]:
    """Score each IP for burst failures and mark bots/malicious hosts.

    Returns a dict keyed by IP with:
    failed_count, max_burst, burst_window_seconds, is_bot,
    first_seen, last_seen, nb_usernames_distincts, is_malicious.
    """
    times: DefaultDict[str, List[datetime]] = defaultdict(list)
    users: DefaultDict[str, Set[str]] = defaultdict(set)

    for event in events:
        if getattr(event, "event_type", None) not in _FAIL_TYPES:
            continue
        ip = getattr(event, "ip", "") or ""
        if not ip:
            continue
        times[ip].append(event.timestamp)
        username = getattr(event, "username", "") or ""
        if username:
            users[ip].add(username)

    results: Dict[str, dict] = {}
    for ip, stamps in times.items():
        failed_count = len(stamps)
        max_burst = _max_burst(stamps, BOT_WINDOW_SECONDS)
        is_bot = max_burst >= BOT_MIN_ATTEMPTS
        is_malicious = is_bot or failed_count >= MALICIOUS_MIN_FAILURES
        results[ip] = {
            "failed_count": failed_count,
            "max_burst": max_burst,
            "burst_window_seconds": BOT_WINDOW_SECONDS,
            "is_bot": is_bot,
            "first_seen": min(stamps),
            "last_seen": max(stamps),
            "nb_usernames_distincts": len(users[ip]),
            "is_malicious": is_malicious,
        }
    return results


def analyze_logs(data_dir: str = "./data") -> Dict[str, dict]:
    """Run ingestion + parsing + bot detection on a log directory."""
    # Local imports keep module import light for reuse.
    from ingestion.read import iter_log_lines
    from processing.extract_transform import parse_line

    year = int(os.getenv("LOG_YEAR", "2024"))
    events = []
    for source_file, line in iter_log_lines(data_dir):
        event = parse_line(line, year)
        if event is None:
            continue
        event.source_file = source_file
        events.append(event)
    return detect_bots(events)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    scores = analyze_logs(str(root / "data"))
    ranked = sorted(
        scores.items(),
        key=lambda item: (item[1]["max_burst"], item[1]["failed_count"]),
        reverse=True,
    )

    print(
        f"IPs scored: {len(ranked)} "
        f"(bot if >= {BOT_MIN_ATTEMPTS} fails in {BOT_WINDOW_SECONDS}s)"
    )
    print("Top 10 most aggressive IPs:")
    for ip, info in ranked[:10]:
        print(
            f"{ip}: failed={info['failed_count']} "
            f"max_burst={info['max_burst']} "
            f"users={info['nb_usernames_distincts']} "
            f"bot={info['is_bot']} malicious={info['is_malicious']} "
            f"first={info['first_seen']} last={info['last_seen']}"
        )
