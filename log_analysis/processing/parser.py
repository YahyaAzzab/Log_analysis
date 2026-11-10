"""Transforme une ligne de auth.log en evenement, ou None."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from app_log import get_logger

logger = get_logger("processing")

# Le syslog n'a pas l'annee. On la fixe ici, comme dans les fichiers du TP.
LOG_YEAR = 2024

_TS_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\b"
)
_FAILED_RE = re.compile(
    r"Failed password for (?:(?P<invalid>invalid user) )?(?P<user>\S*) "
    r"from (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) port (?P<port>\d+)"
)
_INVALID_RE = re.compile(
    r"Invalid user (?P<user>\S*) from (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) "
    r"port (?P<port>\d+)"
)
_ACCEPTED_RE = re.compile(
    r"Accepted (?:password|publickey) for (?P<user>\S+) "
    r"from (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) port (?P<port>\d+)"
)
_AUTH_FAIL_RE = re.compile(
    r"authentication failure;.*?\brhost=(?P<ip>\d{1,3}(?:\.\d{1,3}){3})"
    r"(?:\s+user=(?P<user>\S+))?"
)


class AuthEvent:
    """Une tentative SSH retenue."""

    def __init__(
        self,
        timestamp: datetime,
        ip: str,
        username: str,
        event_type: str,
        invalid_user: bool,
        port: Optional[int],
        source_file: str,
    ) -> None:
        self.timestamp = timestamp
        self.ip = ip
        self.username = username
        self.event_type = event_type
        self.invalid_user = invalid_user
        self.port = port
        self.source_file = source_file
        self.country = ""
        self.is_bot = False


def _timestamp(line: str) -> Optional[datetime]:
    """Lit la date en debut de ligne. Retourne None si elle est absente."""
    match = _TS_RE.match(line)
    if not match:
        return None
    stamp = "{0} {1} {2} {3}".format(
        LOG_YEAR,
        match.group("month"),
        match.group("day"),
        match.group("time"),
    )
    try:
        return datetime.strptime(stamp, "%Y %b %d %H:%M:%S")
    except ValueError as exc:
        logger.error("Date illisible %r: %s", stamp, exc)
        return None


def parse_line(line: str, source_file: str) -> Optional[AuthEvent]:
    """Garde les echecs, les invalid user et les connexions reussies."""
    try:
        raw = line.rstrip("\n")
        timestamp = _timestamp(raw)
        if timestamp is None:
            return None

        failed = _FAILED_RE.search(raw)
        if failed:
            return AuthEvent(
                timestamp=timestamp,
                ip=failed.group("ip"),
                username=failed.group("user") or "",
                event_type="failed_password",
                invalid_user=failed.group("invalid") is not None,
                port=int(failed.group("port")),
                source_file=source_file,
            )

        invalid = _INVALID_RE.search(raw)
        if invalid:
            return AuthEvent(
                timestamp=timestamp,
                ip=invalid.group("ip"),
                username=invalid.group("user") or "",
                event_type="invalid_user",
                invalid_user=True,
                port=int(invalid.group("port")),
                source_file=source_file,
            )

        accepted = _ACCEPTED_RE.search(raw)
        if accepted:
            return AuthEvent(
                timestamp=timestamp,
                ip=accepted.group("ip"),
                username=accepted.group("user"),
                event_type="accepted",
                invalid_user=False,
                port=int(accepted.group("port")),
                source_file=source_file,
            )

        failure = _AUTH_FAIL_RE.search(raw)
        if failure:
            return AuthEvent(
                timestamp=timestamp,
                ip=failure.group("ip"),
                username=failure.group("user") or "",
                event_type="auth_failure",
                invalid_user=False,
                port=None,
                source_file=source_file,
            )
        return None
    except (TypeError, ValueError) as exc:
        logger.error("Ligne ignoree dans %s: %s | %s", source_file, exc, line[:160])
        return None
    except Exception as exc:
        logger.error("Erreur inattendue dans %s: %s", source_file, exc)
        return None
