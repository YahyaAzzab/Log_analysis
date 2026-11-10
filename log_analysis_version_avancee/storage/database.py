"""PostgreSQL access layer for STRIX auth events and IP intel."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor, execute_values

load_dotenv()

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _database_url() -> str:
    """Return DATABASE_URL or raise a clear error."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is missing in the environment (.env)")
    return url


@contextmanager
def get_connection() -> Iterator[Any]:
    """Yield a psycopg2 connection and always close it."""
    conn = psycopg2.connect(_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes from schema.sql."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def _event_row(event: Any) -> Tuple[Any, ...]:
    """Map an AuthEvent-like object to an insert tuple."""
    return (
        event.timestamp,
        event.ip,
        event.username or "",
        event.event_type,
        bool(event.is_invalid_user),
        event.port,
        getattr(event, "source_file", "") or "",
    )


def insert_events(events: Iterable[Any]) -> int:
    """Batch-insert auth events; duplicates are ignored."""
    rows = [_event_row(event) for event in events]
    if not rows:
        return 0

    query = """
        INSERT INTO auth_events (
            ts, ip, username, event_type, is_invalid_user, port, source_file
        ) VALUES %s
        ON CONFLICT (ts, ip, username, port, event_type) DO NOTHING
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, query, rows, page_size=500)
            return cur.rowcount if cur.rowcount is not None else 0


def upsert_ip_intel(rows: Sequence[Dict[str, Any]]) -> int:
    """Insert or update IP intelligence rows."""
    if not rows:
        return 0

    values = [
        (
            row["ip"],
            row.get("country"),
            row.get("country_code"),
            row.get("city"),
            row.get("region"),
            row.get("lat"),
            row.get("lon"),
            row.get("org"),
            bool(row.get("is_malicious", False)),
            int(row.get("failed_count", 0)),
            row.get("first_seen"),
            row.get("last_seen"),
            bool(row.get("is_bot", False)),
        )
        for row in rows
    ]

    query = """
        INSERT INTO ip_intel (
            ip, country, country_code, city, region, lat, lon, org,
            is_malicious, failed_count, first_seen, last_seen, is_bot
        ) VALUES %s
        ON CONFLICT (ip) DO UPDATE SET
            country = EXCLUDED.country,
            country_code = EXCLUDED.country_code,
            city = EXCLUDED.city,
            region = EXCLUDED.region,
            lat = EXCLUDED.lat,
            lon = EXCLUDED.lon,
            org = EXCLUDED.org,
            is_malicious = EXCLUDED.is_malicious,
            failed_count = EXCLUDED.failed_count,
            first_seen = LEAST(ip_intel.first_seen, EXCLUDED.first_seen),
            last_seen = GREATEST(ip_intel.last_seen, EXCLUDED.last_seen),
            is_bot = EXCLUDED.is_bot
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, query, values, page_size=500)
            return cur.rowcount if cur.rowcount is not None else 0


def _fetch_all(query: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
    """Run a read query and return dict rows."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            return [dict(row) for row in cur.fetchall()]


def failures_by_hour(limit_hours: int = 168) -> List[Dict[str, Any]]:
    """Count failed auth events grouped by hour."""
    return _fetch_all(
        """
        SELECT date_trunc('hour', ts) AS hour, COUNT(*) AS failures
        FROM auth_events
        WHERE event_type IN ('failed_password', 'invalid_user', 'auth_failure')
          AND ts >= NOW() - (%s || ' hours')::interval
        GROUP BY 1
        ORDER BY 1
        """,
        (limit_hours,),
    )


def top_ips(limit: int = 20) -> List[Dict[str, Any]]:
    """Return IPs with the most failed auth events."""
    return _fetch_all(
        """
        SELECT ip::text AS ip, COUNT(*) AS failures
        FROM auth_events
        WHERE event_type IN ('failed_password', 'invalid_user', 'auth_failure')
        GROUP BY ip
        ORDER BY failures DESC
        LIMIT %s
        """,
        (limit,),
    )


def top_users(limit: int = 20) -> List[Dict[str, Any]]:
    """Return usernames most often targeted by failed auth."""
    return _fetch_all(
        """
        SELECT username, COUNT(*) AS failures
        FROM auth_events
        WHERE event_type IN ('failed_password', 'invalid_user', 'auth_failure')
          AND username <> ''
        GROUP BY username
        ORDER BY failures DESC
        LIMIT %s
        """,
        (limit,),
    )


def events_by_country(limit: int = 20) -> List[Dict[str, Any]]:
    """Aggregate failed events by country using ip_intel."""
    return _fetch_all(
        """
        SELECT
            COALESCE(i.country, 'Unknown') AS country,
            COALESCE(i.country_code, '??') AS country_code,
            COUNT(*) AS failures
        FROM auth_events e
        LEFT JOIN ip_intel i ON e.ip = i.ip
        WHERE e.event_type IN ('failed_password', 'invalid_user', 'auth_failure')
        GROUP BY 1, 2
        ORDER BY failures DESC
        LIMIT %s
        """,
        (limit,),
    )


def event_type_counts() -> List[Dict[str, Any]]:
    """Count rows per event_type."""
    return _fetch_all(
        """
        SELECT event_type, COUNT(*) AS total
        FROM auth_events
        GROUP BY event_type
        ORDER BY total DESC
        """
    )


def malicious_ips(limit: int = 50) -> List[Dict[str, Any]]:
    """List flagged IPs ordered by failed_count."""
    return _fetch_all(
        """
        SELECT
            ip::text AS ip,
            country,
            country_code,
            city,
            org,
            failed_count,
            is_malicious,
            is_bot,
            first_seen,
            last_seen
        FROM ip_intel
        WHERE is_malicious = TRUE OR failed_count > 0
        ORDER BY failed_count DESC, last_seen DESC NULLS LAST
        LIMIT %s
        """,
        (limit,),
    )


def recent_events(limit: int = 100) -> List[Dict[str, Any]]:
    """Return the most recent auth events."""
    return _fetch_all(
        """
        SELECT
            id,
            ts,
            ip::text AS ip,
            username,
            event_type,
            is_invalid_user,
            port,
            source_file
        FROM auth_events
        ORDER BY ts DESC
        LIMIT %s
        """,
        (limit,),
    )
