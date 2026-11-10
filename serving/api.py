"""STRIX FastAPI: JSON analytics API + static frontend."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from psycopg2.extras import RealDictCursor

from storage.database import get_connection

WEB_DIR = Path(__file__).resolve().parent / "web"
FAIL_TYPES = ("failed_password", "invalid_user", "auth_failure")

app = FastAPI(title="STRIX API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _jsonable(value: Any) -> Any:
    """Convert DB values into plain JSON types."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _fetch(query: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    """Run a read-only SQL query and return JSON-ready dict rows."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [_jsonable(dict(row)) for row in cur.fetchall()]


def _fetch_one(query: str, params: Sequence[Any] = ()) -> Dict[str, Any]:
    """Run a query expected to return a single row."""
    rows = _fetch(query, params)
    return rows[0] if rows else {}


def _event_filters(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    country: Optional[str],
    ip: Optional[str],
    username: Optional[str],
    bots_only: bool,
    min_attempts: Optional[int],
    alias: str = "e",
) -> Tuple[str, List[Any]]:
    """Build WHERE clause fragments for auth_events (+ optional ip_intel)."""
    clauses = [f"{alias}.event_type IN %s"]
    params: List[Any] = [FAIL_TYPES]

    if date_from is not None:
        clauses.append(f"{alias}.ts >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append(f"{alias}.ts <= %s")
        params.append(date_to)
    if ip:
        clauses.append(f"{alias}.ip = %s::inet")
        params.append(ip)
    if username:
        clauses.append(f"{alias}.username ILIKE %s")
        params.append(f"%{username}%")
    if country:
        clauses.append("i.country_code ILIKE %s OR i.country ILIKE %s")
        params.extend([country, f"%{country}%"])
    if bots_only:
        clauses.append("i.is_bot = TRUE")
    if min_attempts is not None:
        clauses.append("COALESCE(i.failed_count, 0) >= %s")
        params.append(min_attempts)

    return " AND ".join(clauses), params


def _needs_intel(
    country: Optional[str],
    bots_only: bool,
    min_attempts: Optional[int],
) -> bool:
    """True when filters require a join on ip_intel."""
    return bool(country or bots_only or min_attempts is not None)


@app.get("/api/kpis")
def api_kpis(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    country: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    bots_only: bool = False,
    min_attempts: Optional[int] = Query(default=None, ge=0),
) -> Dict[str, Any]:
    """Return high-level KPIs for the filtered failure set."""
    where, params = _event_filters(
        date_from, date_to, country, ip, username, bots_only, min_attempts
    )
    join = "LEFT JOIN ip_intel i ON e.ip = i.ip" if _needs_intel(
        country, bots_only, min_attempts
    ) else "LEFT JOIN ip_intel i ON e.ip = i.ip"

    summary = _fetch_one(
        f"""
        SELECT
            COUNT(*)::int AS total_failures,
            COUNT(DISTINCT e.ip)::int AS unique_ips,
            COUNT(DISTINCT CASE WHEN i.is_bot THEN e.ip END)::int AS bots_detected,
            COUNT(DISTINCT i.country_code)::int AS countries
        FROM auth_events e
        {join}
        WHERE {where}
        """,
        params,
    )

    peak = _fetch_one(
        f"""
        SELECT date_trunc('hour', e.ts) AS hour, COUNT(*)::int AS failures
        FROM auth_events e
        {join}
        WHERE {where}
        GROUP BY 1
        ORDER BY failures DESC, hour DESC
        LIMIT 1
        """,
        params,
    )

    return {
        "total_failures": summary.get("total_failures", 0),
        "unique_ips": summary.get("unique_ips", 0),
        "bots_detected": summary.get("bots_detected", 0),
        "countries": summary.get("countries", 0),
        "peak_hour": peak.get("hour"),
        "peak_hour_failures": peak.get("failures", 0),
    }


@app.get("/api/timeline")
def api_timeline(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    country: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    bots_only: bool = False,
    min_attempts: Optional[int] = Query(default=None, ge=0),
    granularity: str = Query(default="hour", pattern="^(hour|day)$"),
) -> List[Dict[str, Any]]:
    """Return failures grouped by hour or day."""
    where, params = _event_filters(
        date_from, date_to, country, ip, username, bots_only, min_attempts
    )
    return _fetch(
        f"""
        SELECT date_trunc(%s, e.ts) AS bucket, COUNT(*)::int AS failures
        FROM auth_events e
        LEFT JOIN ip_intel i ON e.ip = i.ip
        WHERE {where}
        GROUP BY 1
        ORDER BY 1
        """,
        [granularity, *params],
    )


@app.get("/api/top-ips")
def api_top_ips(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    country: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    bots_only: bool = False,
    min_attempts: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Return IPs with the most failures."""
    where, params = _event_filters(
        date_from, date_to, country, ip, username, bots_only, min_attempts
    )
    return _fetch(
        f"""
        SELECT
            e.ip::text AS ip,
            COUNT(*)::int AS failures,
            BOOL_OR(COALESCE(i.is_bot, FALSE)) AS is_bot,
            BOOL_OR(COALESCE(i.is_malicious, FALSE)) AS is_malicious,
            MAX(i.country) AS country,
            MAX(i.country_code) AS country_code
        FROM auth_events e
        LEFT JOIN ip_intel i ON e.ip = i.ip
        WHERE {where}
        GROUP BY e.ip
        ORDER BY failures DESC
        LIMIT %s
        """,
        [*params, limit],
    )


@app.get("/api/top-users")
def api_top_users(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    country: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    bots_only: bool = False,
    min_attempts: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Return usernames most often targeted."""
    where, params = _event_filters(
        date_from, date_to, country, ip, username, bots_only, min_attempts
    )
    return _fetch(
        f"""
        SELECT e.username, COUNT(*)::int AS failures
        FROM auth_events e
        LEFT JOIN ip_intel i ON e.ip = i.ip
        WHERE {where}
          AND e.username <> ''
        GROUP BY e.username
        ORDER BY failures DESC
        LIMIT %s
        """,
        [*params, limit],
    )


@app.get("/api/countries")
def api_countries(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    country: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    bots_only: bool = False,
    min_attempts: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=300),
) -> List[Dict[str, Any]]:
    """Aggregate failures by country."""
    where, params = _event_filters(
        date_from, date_to, country, ip, username, bots_only, min_attempts
    )
    return _fetch(
        f"""
        SELECT
            COALESCE(i.country, 'Unknown') AS country,
            COALESCE(i.country_code, '??') AS country_code,
            COUNT(*)::int AS failures
        FROM auth_events e
        LEFT JOIN ip_intel i ON e.ip = i.ip
        WHERE {where}
        GROUP BY 1, 2
        ORDER BY failures DESC
        LIMIT %s
        """,
        [*params, limit],
    )


@app.get("/api/map")
def api_map(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    country: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    bots_only: bool = False,
    min_attempts: Optional[int] = Query(default=None, ge=0),
) -> List[Dict[str, Any]]:
    """Return lat/lon points with failure counts for the map."""
    where, params = _event_filters(
        date_from, date_to, country, ip, username, bots_only, min_attempts
    )
    return _fetch(
        f"""
        SELECT
            i.lat,
            i.lon,
            e.ip::text AS ip,
            COUNT(*)::int AS failures,
            MAX(i.country) AS country,
            MAX(i.city) AS city,
            BOOL_OR(COALESCE(i.is_bot, FALSE)) AS is_bot
        FROM auth_events e
        INNER JOIN ip_intel i ON e.ip = i.ip
        WHERE {where}
          AND i.lat IS NOT NULL
          AND i.lon IS NOT NULL
        GROUP BY e.ip, i.lat, i.lon
        ORDER BY failures DESC
        """,
        params,
    )


@app.get("/api/bots")
def api_bots(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    country: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    bots_only: bool = True,
    min_attempts: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """List bot / malicious IPs with intel fields."""
    # Force bot filter unless explicitly disabled.
    where, params = _event_filters(
        date_from, date_to, country, ip, username, bots_only, min_attempts
    )
    return _fetch(
        f"""
        SELECT
            i.ip::text AS ip,
            i.country,
            i.country_code,
            i.city,
            i.org,
            i.failed_count,
            i.is_bot,
            i.is_malicious,
            i.first_seen,
            i.last_seen,
            COUNT(e.id)::int AS failures_in_range
        FROM ip_intel i
        INNER JOIN auth_events e ON e.ip = i.ip
        WHERE {where}
          AND i.is_bot = TRUE
        GROUP BY
            i.ip, i.country, i.country_code, i.city, i.org,
            i.failed_count, i.is_bot, i.is_malicious, i.first_seen, i.last_seen
        ORDER BY i.failed_count DESC, failures_in_range DESC
        LIMIT %s
        """,
        [*params, limit],
    )


@app.get("/api/events")
def api_events(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    country: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    bots_only: bool = False,
    min_attempts: Optional[int] = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort: str = Query(default="ts", pattern="^(ts|ip|username|event_type)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> Dict[str, Any]:
    """Paginated auth events with sorting."""
    where, params = _event_filters(
        date_from, date_to, country, ip, username, bots_only, min_attempts
    )
    offset = (page - 1) * page_size
    sort_col = {
        "ts": "e.ts",
        "ip": "e.ip",
        "username": "e.username",
        "event_type": "e.event_type",
    }[sort]
    order_sql = "ASC" if order.lower() == "asc" else "DESC"

    total_row = _fetch_one(
        f"""
        SELECT COUNT(*)::int AS total
        FROM auth_events e
        LEFT JOIN ip_intel i ON e.ip = i.ip
        WHERE {where}
        """,
        params,
    )
    items = _fetch(
        f"""
        SELECT
            e.id,
            e.ts,
            e.ip::text AS ip,
            e.username,
            e.event_type,
            e.is_invalid_user,
            e.port,
            e.source_file,
            i.country,
            i.country_code,
            i.is_bot,
            i.is_malicious
        FROM auth_events e
        LEFT JOIN ip_intel i ON e.ip = i.ip
        WHERE {where}
        ORDER BY {sort_col} {order_sql}, e.id DESC
        LIMIT %s OFFSET %s
        """,
        [*params, page_size, offset],
    )
    total = int(total_row.get("total", 0))
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
    }


@app.get("/api/health")
def api_health() -> Dict[str, str]:
    """Simple health check."""
    try:
        _fetch_one("SELECT 1 AS ok")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}


# Serve the frontend after API routes are registered.
WEB_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
