"""Repere les IP qui enchainent les echecs trop vite."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from app_log import get_logger
from processing.parser import AuthEvent

logger = get_logger("processing")

BOT_MIN_ATTEMPTS = 5
BOT_WINDOW_SECONDS = 30
MALICIOUS_MIN_FAILURES = 20
_FAIL_TYPES = {"failed_password", "invalid_user", "auth_failure"}


def _max_burst(stamps: List[datetime]) -> int:
    """Plus grand nombre d'echecs dans une fenetre de 30 secondes."""
    ordered = sorted(stamps)
    left = 0
    best = 0
    for right, current in enumerate(ordered):
        while (current - ordered[left]).total_seconds() > BOT_WINDOW_SECONDS:
            left += 1
        best = max(best, right - left + 1)
    return best


def detect_bots(events: List[AuthEvent]) -> Dict[str, dict]:
    """Marque une IP bot si elle fait 5 echecs en 30 secondes."""
    times = defaultdict(list)
    for event in events:
        if event.event_type not in _FAIL_TYPES or not event.ip:
            continue
        times[event.ip].append(event.timestamp)

    scores: Dict[str, dict] = {}
    try:
        for ip, stamps in times.items():
            burst = _max_burst(stamps)
            failed_count = len(stamps)
            is_bot = burst >= BOT_MIN_ATTEMPTS
            scores[ip] = {
                "failed_count": failed_count,
                "max_burst": burst,
                "is_bot": is_bot,
                "is_malicious": is_bot or failed_count >= MALICIOUS_MIN_FAILURES,
                "first_seen": min(stamps),
                "last_seen": max(stamps),
            }
    except (TypeError, ValueError) as exc:
        logger.error("Detection des bots interrompue: %s", exc)
        return scores

    bots = sum(1 for info in scores.values() if info["is_bot"])
    malicious = sum(1 for info in scores.values() if info["is_malicious"])
    logger.info("IP notees: %s, bots: %s, malveillantes: %s", len(scores), bots, malicious)
    return scores
