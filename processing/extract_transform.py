"""Parse sshd auth log lines into structured AuthEvent objects."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Syslog timestamp without year: "May 24 00:26:51"
_TS_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\b"
)

# Failed password for [invalid user] <user> from <ip> port <p> ssh2
_FAILED_RE = re.compile(
    r"Failed password for (?:(?P<invalid>invalid user) )?(?P<user>\S*) "
    r"from (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) port (?P<port>\d+)"
)

# Invalid user <user> from <ip> port <p>  (user may be empty)
_INVALID_RE = re.compile(
    r"Invalid user (?P<user>\S*) from (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) "
    r"port (?P<port>\d+)"
)

# Accepted password|publickey for <user> from <ip> port <p>
_ACCEPTED_RE = re.compile(
    r"Accepted (?:password|publickey) for (?P<user>\S+) "
    r"from (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) port (?P<port>\d+)"
)

# authentication failure ... rhost=<ip> [user=<user>]
_AUTH_FAIL_RE = re.compile(
    r"authentication failure;.*?\brhost=(?P<ip>\d{1,3}(?:\.\d{1,3}){3})"
    r"(?:\s+user=(?P<user>\S+))?"
)


@dataclass
class AuthEvent:
    """One recognized sshd authentication event."""

    timestamp: datetime
    ip: str
    username: str
    event_type: str
    is_invalid_user: bool
    port: Optional[int]
    raw_line: str
    source_file: str


def _parse_timestamp(line: str, year: int) -> Optional[datetime]:
    """Build a datetime from the syslog prefix and LOG_YEAR."""
    match = _TS_RE.match(line)
    if not match:
        return None
    stamp = (
        f"{year} {match.group('month')} {match.group('day')} "
        f"{match.group('time')}"
    )
    try:
        return datetime.strptime(stamp, "%Y %b %d %H:%M:%S")
    except ValueError:
        return None


def parse_line(line: str, year: int) -> Optional[AuthEvent]:
    """Parse one auth log line into an AuthEvent, or None if ignored."""
    raw_line = line.rstrip("\n")
    timestamp = _parse_timestamp(raw_line, year)
    if timestamp is None:
        return None

    match = _FAILED_RE.search(raw_line)
    if match:
        return AuthEvent(
            timestamp=timestamp,
            ip=match.group("ip"),
            username=match.group("user") or "",
            event_type="failed_password",
            is_invalid_user=match.group("invalid") is not None,
            port=int(match.group("port")),
            raw_line=raw_line,
            source_file="",
        )

    match = _INVALID_RE.search(raw_line)
    if match:
        return AuthEvent(
            timestamp=timestamp,
            ip=match.group("ip"),
            username=match.group("user") or "",
            event_type="invalid_user",
            is_invalid_user=True,
            port=int(match.group("port")),
            raw_line=raw_line,
            source_file="",
        )

    match = _ACCEPTED_RE.search(raw_line)
    if match:
        return AuthEvent(
            timestamp=timestamp,
            ip=match.group("ip"),
            username=match.group("user"),
            event_type="accepted",
            is_invalid_user=False,
            port=int(match.group("port")),
            raw_line=raw_line,
            source_file="",
        )

    match = _AUTH_FAIL_RE.search(raw_line)
    if match:
        return AuthEvent(
            timestamp=timestamp,
            ip=match.group("ip"),
            username=match.group("user") or "",
            event_type="auth_failure",
            is_invalid_user=False,
            port=None,
            raw_line=raw_line,
            source_file="",
        )

    return None


if __name__ == "__main__":
    year = int(os.getenv("LOG_YEAR", "2024"))

    # Five representative lines from data/auth.log.1
    samples = [
        "May 24 00:26:51 ns sshd[1351208]: Invalid user  from 45.156.87.204 port 35940",
        "May 24 00:27:57 ns sshd[1351222]: Invalid user test from 45.156.87.204 port 41740",
        "May 24 00:27:58 ns sshd[1351222]: pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=45.156.87.204 ",
        "May 24 00:28:00 ns sshd[1351222]: Failed password for invalid user test from 45.156.87.204 port 41740 ssh2",
        "May 24 01:14:01 ns sshd[1351821]: Failed password for root from 45.148.10.147 port 8868 ssh2",
    ]

    read_count = 0
    parsed_count = 0
    ignored_count = 0

    for sample in samples:
        read_count += 1
        event = parse_line(sample, year)
        if event is None:
            ignored_count += 1
            print("IGNORED:", sample)
            continue
        parsed_count += 1
        print(event)

    print("---")
    print(f"lines read: {read_count}")
    print(f"events recognized: {parsed_count}")
    print(f"ignored: {ignored_count}")
