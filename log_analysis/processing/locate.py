"""Pays et position des IP malveillantes via la bibliotheque ipinfo."""

from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from app_log import get_logger

logger = get_logger("processing")

_CACHE_PATH = Path(__file__).resolve().parents[1] / "storage" / "ipinfo_cache.json"


def _empty(ip: str) -> dict:
    """Resultat vide quand on ne peut pas localiser l'adresse."""
    return {
        "ip": ip,
        "country": None,
        "city": None,
        "region": None,
        "lat": None,
        "lon": None,
        "org": None,
    }


def _is_private(ip: str) -> bool:
    """True pour une IP locale ou mal formee."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        logger.error("IP invalide ignoree: %s", ip)
        return True
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )


def _load_cache() -> Dict[str, dict]:
    """Lit le cache ipinfo. Un fichier casse est ignore."""
    if not _CACHE_PATH.is_file():
        return {}
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.error("Impossible de lire le cache ipinfo: %s", exc)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Cache ipinfo illisible: %s", exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save_cache(cache: Dict[str, dict]) -> None:
    """Enregistre le cache. Le jeton n'y est jamais ecrit."""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Impossible d'ecrire le cache ipinfo: %s", exc)


def _parse_loc(loc: Optional[str]) -> tuple:
    """Separe 'lat,lon' en deux nombres."""
    if not loc or "," not in loc:
        return None, None
    try:
        lat_text, lon_text = loc.split(",", 1)
        return float(lat_text), float(lon_text)
    except ValueError:
        logger.error("Coordonnees ipinfo illisibles")
        return None, None


def _lookup(ip: str) -> dict:
    """Appelle ipinfo une fois. Ne leve pas d'exception."""
    import ipinfo
    from ipinfo.error import APIError
    from ipinfo.exceptions import RequestQuotaExceededError, TimeoutExceededError

    token = os.getenv("IPINFO_TOKEN") or None
    if not token:
        logger.error("IPINFO_TOKEN est vide. Localisation ipinfo ignoree.")
        return _empty(ip)
    try:
        handler = ipinfo.getHandler(token, request_options={"timeout": 5})
        details = handler.getDetails(ip, timeout=5)
    except RequestQuotaExceededError:
        logger.error("Quota ipinfo depasse pour %s", ip)
        return _empty(ip)
    except (APIError, TimeoutExceededError, OSError) as exc:
        logger.error("ipinfo a echoue pour %s: %s", ip, type(exc).__name__)
        return _empty(ip)
    except Exception as exc:
        logger.error("Erreur ipinfo pour %s: %s", ip, type(exc).__name__)
        return _empty(ip)

    data = details.all if hasattr(details, "all") else {}
    if data.get("bogon"):
        return _empty(ip)
    lat, lon = _parse_loc(data.get("loc"))
    return {
        "ip": ip,
        "country": data.get("country_name") or data.get("country"),
        "city": data.get("city"),
        "region": data.get("region"),
        "lat": lat,
        "lon": lon,
        "org": data.get("org"),
    }


def locate_ips(ips: List[str]) -> Dict[str, dict]:
    """Localise chaque IP une seule fois, puis reutilise le cache."""
    cache = _load_cache()
    unique = []
    seen = set()
    for ip in ips:
        if ip and ip not in seen:
            seen.add(ip)
            unique.append(ip)

    missing = []
    for ip in unique:
        if ip in cache:
            continue
        if _is_private(ip):
            cache[ip] = _empty(ip)
            cache[ip]["country"] = "prive ou local"
            continue
        missing.append(ip)

    logger.info("IP a envoyer a ipinfo: %s", len(missing))
    for index, ip in enumerate(missing, start=1):
        cache[ip] = _lookup(ip)
        if index % 20 == 0:
            _save_cache(cache)
            logger.info("ipinfo: %s / %s", index, len(missing))
    _save_cache(cache)
    return {ip: cache.get(ip, _empty(ip)) for ip in unique}
