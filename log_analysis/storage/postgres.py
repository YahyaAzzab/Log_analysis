"""Enregistre les tentatives et les IP malveillantes dans PostgreSQL."""

from __future__ import annotations

import os
from typing import Dict, List

from app_log import get_logger
from processing.parser import AuthEvent

logger = get_logger("storage")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cours_events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    ip INET NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    invalid_user BOOLEAN NOT NULL DEFAULT FALSE,
    port INTEGER,
    country TEXT,
    is_bot BOOLEAN NOT NULL DEFAULT FALSE,
    source_file TEXT NOT NULL DEFAULT '',
    UNIQUE (ts, ip, username, port, event_type)
);

CREATE TABLE IF NOT EXISTS cours_ip_intel (
    ip INET PRIMARY KEY,
    country TEXT,
    city TEXT,
    region TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    org TEXT,
    is_bot BOOLEAN NOT NULL DEFAULT FALSE,
    is_malicious BOOLEAN NOT NULL DEFAULT FALSE,
    failed_count INTEGER NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ
);
"""


def save_postgres(events: List[AuthEvent], intel: Dict[str, dict]) -> None:
    """Recharge les tables du cours. Une erreur SQL n'arrete pas les graphiques."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        logger.error("DATABASE_URL est vide. PostgreSQL ignore.")
        return
    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError as exc:
        logger.error("psycopg2 n'est pas installe: %s", exc)
        return

    try:
        connection = psycopg2.connect(url)
    except psycopg2.Error as exc:
        logger.error("Connexion PostgreSQL impossible: %s", exc)
        return

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(_SCHEMA)
                cursor.execute("TRUNCATE cours_events, cours_ip_intel")
                rows = [
                    (
                        event.timestamp,
                        event.ip,
                        event.username,
                        event.event_type,
                        event.invalid_user,
                        event.port,
                        event.country,
                        event.is_bot,
                        event.source_file,
                    )
                    for event in events
                ]
                execute_values(
                    cursor,
                    """
                    INSERT INTO cours_events (
                        ts, ip, username, event_type, invalid_user,
                        port, country, is_bot, source_file
                    ) VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    rows,
                    page_size=1000,
                )
                intel_rows = []
                for ip, info in intel.items():
                    geo = info.get("geo") or {}
                    intel_rows.append(
                        (
                            ip,
                            geo.get("country"),
                            geo.get("city"),
                            geo.get("region"),
                            geo.get("lat"),
                            geo.get("lon"),
                            geo.get("org"),
                            info["is_bot"],
                            info["is_malicious"],
                            info["failed_count"],
                            info["first_seen"],
                            info["last_seen"],
                        )
                    )
                if intel_rows:
                    execute_values(
                        cursor,
                        """
                        INSERT INTO cours_ip_intel (
                            ip, country, city, region, lat, lon, org,
                            is_bot, is_malicious, failed_count, first_seen, last_seen
                        ) VALUES %s
                        """,
                        intel_rows,
                        page_size=500,
                    )
        logger.info(
            "PostgreSQL: %s tentatives, %s IP malveillantes",
            len(events),
            len(intel),
        )
    except psycopg2.Error as exc:
        logger.error("Ecriture PostgreSQL impossible: %s", exc)
    finally:
        connection.close()
