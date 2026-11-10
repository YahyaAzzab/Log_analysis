"""Geolocate IP addresses with the official ipinfo client."""

from __future__ import annotations

import ipaddress
import os
import time
from typing import Dict, Iterable, List, Optional

import ipinfo
import requests
from dotenv import load_dotenv
from ipinfo.error import APIError
from ipinfo.exceptions import RequestQuotaExceededError, TimeoutExceededError

load_dotenv()

_CACHE: Dict[str, dict] = {}
_HANDLER: Optional[ipinfo.handler.Handler] = None
_TIMEOUT_SECONDS = 5
_MAX_ATTEMPTS = 2
_RETRY_SLEEP_SECONDS = 1.0


def _get_handler() -> ipinfo.handler.Handler:
    """Build a shared ipinfo handler (token never logged)."""
    global _HANDLER
    if _HANDLER is None:
        token = os.getenv("IPINFO_TOKEN") or None
        _HANDLER = ipinfo.getHandler(
            token,
            request_options={"timeout": _TIMEOUT_SECONDS},
        )
    return _HANDLER


def _is_private_ip(ip: str) -> bool:
    """Return True for private, loopback, or otherwise non-public IPs."""
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return True
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _empty_result(ip: str) -> dict:
    """Placeholder result when lookup is skipped or fails."""
    return {
        "ip": ip,
        "country": None,
        "country_code": None,
        "city": None,
        "region": None,
        "loc": None,
        "org": None,
        "timezone": None,
    }


def _parse_loc(loc: Optional[str]) -> Optional[Dict[str, float]]:
    """Split an ipinfo loc string into lat/lon floats."""
    if not loc or "," not in loc:
        return None
    try:
        lat_s, lon_s = loc.split(",", 1)
        return {"lat": float(lat_s.strip()), "lon": float(lon_s.strip())}
    except ValueError:
        return None


def _from_details(ip: str, details: object) -> dict:
    """Map an ipinfo Details object to the project geo dict."""
    data = details.all if hasattr(details, "all") else {}
    country_code = data.get("country")
    return {
        "ip": data.get("ip") or ip,
        "country": data.get("country_name") or country_code,
        "country_code": country_code,
        "city": data.get("city"),
        "region": data.get("region"),
        "loc": _parse_loc(data.get("loc")),
        "org": data.get("org"),
        "timezone": data.get("timezone"),
    }


def _lookup_remote(ip: str) -> Optional[object]:
    """Call ipinfo with timeout and one retry. Never raises."""
    handler = _get_handler()
    last_error: Optional[BaseException] = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return handler.getDetails(ip, timeout=_TIMEOUT_SECONDS)
        except RequestQuotaExceededError as exc:
            last_error = exc
        except APIError as exc:
            last_error = exc
            if getattr(exc, "error_code", None) != 429 and attempt >= _MAX_ATTEMPTS:
                break
        except (requests.RequestException, TimeoutExceededError, OSError) as exc:
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - keep pipeline running
            last_error = exc
            break

        if attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_SLEEP_SECONDS)

    if last_error is not None:
        # Do not include request headers or token in any message.
        print(f"geolocate failed for {ip}: {type(last_error).__name__}")
    return None


def geolocate(ip: str) -> dict:
    """Return geo fields for one IP, using cache and skipping private IPs."""
    ip = (ip or "").strip()
    if not ip:
        return _empty_result(ip)

    if ip in _CACHE:
        return _CACHE[ip]

    if _is_private_ip(ip):
        result = _empty_result(ip)
        _CACHE[ip] = result
        return result

    details = _lookup_remote(ip)
    if details is None:
        result = _empty_result(ip)
        # Do not cache hard failures forever? Cache to avoid hammering on 429.
        _CACHE[ip] = result
        return result

    # Bogon responses from ipinfo have no useful geo fields.
    data = details.all if hasattr(details, "all") else {}
    if data.get("bogon"):
        result = _empty_result(ip)
        _CACHE[ip] = result
        return result

    result = _from_details(ip, details)
    _CACHE[ip] = result
    return result


def geolocate_many(ips: Iterable[str]) -> Dict[str, dict]:
    """Geolocate many IPs after deduplicating, reusing the memory cache."""
    unique: List[str] = []
    seen = set()
    for raw in ips:
        ip = (raw or "").strip()
        if not ip or ip in seen:
            continue
        seen.add(ip)
        unique.append(ip)

    return {ip: geolocate(ip) for ip in unique}
