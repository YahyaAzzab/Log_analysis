"""Tests for sshd auth line parsing."""

from __future__ import annotations

from datetime import datetime

from processing.extract_transform import parse_line

YEAR = 2024


def test_failed_password_valid_user() -> None:
    line = (
        "May 24 01:14:01 ns sshd[1351821]: "
        "Failed password for root from 45.148.10.147 port 8868 ssh2"
    )
    event = parse_line(line, YEAR)
    assert event is not None
    assert event.event_type == "failed_password"
    assert event.username == "root"
    assert event.ip == "45.148.10.147"
    assert event.port == 8868
    assert event.is_invalid_user is False
    assert event.timestamp == datetime(2024, 5, 24, 1, 14, 1)


def test_failed_password_invalid_user() -> None:
    line = (
        "May 24 00:28:00 ns sshd[1351222]: "
        "Failed password for invalid user test from 45.156.87.204 port 41740 ssh2"
    )
    event = parse_line(line, YEAR)
    assert event is not None
    assert event.event_type == "failed_password"
    assert event.username == "test"
    assert event.is_invalid_user is True
    assert event.ip == "45.156.87.204"
    assert event.port == 41740


def test_invalid_user_with_name() -> None:
    line = (
        "May 24 00:27:57 ns sshd[1351222]: "
        "Invalid user test from 45.156.87.204 port 41740"
    )
    event = parse_line(line, YEAR)
    assert event is not None
    assert event.event_type == "invalid_user"
    assert event.username == "test"
    assert event.is_invalid_user is True
    assert event.port == 41740


def test_invalid_user_empty_name() -> None:
    line = (
        "May 24 00:26:51 ns sshd[1351208]: "
        "Invalid user  from 45.156.87.204 port 35940"
    )
    event = parse_line(line, YEAR)
    assert event is not None
    assert event.event_type == "invalid_user"
    assert event.username == ""
    assert event.is_invalid_user is True
    assert event.ip == "45.156.87.204"


def test_accepted_password() -> None:
    line = (
        "May 19 08:49:50 ns sshd[1257866]: "
        "Accepted password for adminesisa from 10.10.33.81 port 59176 ssh2"
    )
    event = parse_line(line, YEAR)
    assert event is not None
    assert event.event_type == "accepted"
    assert event.username == "adminesisa"
    assert event.ip == "10.10.33.81"
    assert event.port == 59176
    assert event.is_invalid_user is False


def test_accepted_publickey() -> None:
    line = (
        "May 19 09:00:00 ns sshd[1]: "
        "Accepted publickey for deploy from 203.0.113.10 port 2222 ssh2"
    )
    event = parse_line(line, YEAR)
    assert event is not None
    assert event.event_type == "accepted"
    assert event.username == "deploy"
    assert event.port == 2222


def test_auth_failure_with_user() -> None:
    line = (
        "May 24 01:13:59 ns sshd[1351821]: "
        "pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 "
        "tty=ssh ruser= rhost=45.148.10.147  user=root"
    )
    event = parse_line(line, YEAR)
    assert event is not None
    assert event.event_type == "auth_failure"
    assert event.ip == "45.148.10.147"
    assert event.username == "root"
    assert event.port is None


def test_auth_failure_without_user() -> None:
    line = (
        "May 24 00:27:58 ns sshd[1351222]: "
        "pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 "
        "tty=ssh ruser= rhost=45.156.87.204 "
    )
    event = parse_line(line, YEAR)
    assert event is not None
    assert event.event_type == "auth_failure"
    assert event.ip == "45.156.87.204"
    assert event.username == ""
    assert event.port is None


def test_ignored_unrelated_line() -> None:
    line = "May 24 00:26:59 ns sshd[1351208]: Connection closed by invalid user"
    assert parse_line(line, YEAR) is None
