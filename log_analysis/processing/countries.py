"""Associe un pays a chaque adresse IP, avec un cache local."""

from __future__ import annotations

import ipaddress
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

from app_log import get_logger

logger = get_logger("processing")

_CACHE_PATH = Path(__file__).resolve().parents[1] / "storage" / "country_cache.json"
_BATCH_URL = "http://ip-api.com/batch"
_BATCH_SIZE = 100


def _load_cache() -> Dict[str, str]:
    """Lit le cache JSON. Un fichier absent ou casse donne un cache vide."""
    if not _CACHE_PATH.is_file():
        return {}
    try:
        raw = _CACHE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError as exc:
        logger.error("Impossible de lire le cache pays: %s", exc)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Cache pays illisible, il sera recree: %s", exc)
        return {}
    if not isinstance(data, dict):
        logger.error("Cache pays: format inattendu, il sera recree")
        return {}
    return {str(ip): str(country) for ip, country in data.items()}


def _save_cache(cache: Dict[str, str]) -> None:
    """Enregistre le cache. Une erreur ici n'arrete pas les graphiques."""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Impossible d'ecrire le cache pays: %s", exc)


def _is_private(ip: str) -> bool:
    """True pour une IP locale, privee ou mal formee."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        logger.error("Adresse IP invalide ignoree: %s", ip)
        return True
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )


def _lookup_batch(ips: List[str]) -> Dict[str, str]:
    """Interroge ip-api.com. En cas d'erreur, ces IP restent inconnues."""
    payload = json.dumps(
        [{"query": ip, "fields": "status,country,query,message"} for ip in ips]
    ).encode("utf-8")
    request = urllib.request.Request(
        _BATCH_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "pipeline-log-analyser",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        logger.error("ip-api HTTP %s pour %s IP", exc.code, len(ips))
        return {}
    except urllib.error.URLError as exc:
        logger.error("ip-api injoignable: %s", exc.reason)
        return {}
    except TimeoutError as exc:
        logger.error("ip-api timeout: %s", exc)
        return {}
    except OSError as exc:
        logger.error("Erreur reseau ip-api: %s", exc)
        return {}

    try:
        rows = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.error("Reponse ip-api illisible: %s", exc)
        return {}

    found: Dict[str, str] = {}
    if not isinstance(rows, list):
        logger.error("Reponse ip-api inattendue: %s", type(rows).__name__)
        return {}
    for row in rows:
        if not isinstance(row, dict):
            logger.error("Ligne ip-api ignoree: %s", row)
            continue
        ip = str(row.get("query") or "")
        if row.get("status") == "success" and row.get("country"):
            found[ip] = str(row["country"])
        else:
            logger.warning(
                "Pays introuvable pour %s: %s",
                ip,
                row.get("message") or row.get("status"),
            )
            found[ip] = "inconnu"
    return found


def countries_for(ips: List[str]) -> Dict[str, str]:
    """Retourne ip -> pays. Les IP deja vues ne sont pas redemandees."""
    cache = _load_cache()
    missing = []
    for ip in ips:
        if ip in cache:
            continue
        if _is_private(ip):
            cache[ip] = "prive ou local"
            continue
        missing.append(ip)

    unique_missing = []
    seen = set()
    for ip in missing:
        if ip not in seen:
            seen.add(ip)
            unique_missing.append(ip)

    logger.info("IP a geolocaliser: %s", len(unique_missing))
    for start in range(0, len(unique_missing), _BATCH_SIZE):
        chunk = unique_missing[start : start + _BATCH_SIZE]
        found = _lookup_batch(chunk)
        if not found:
            for ip in chunk:
                cache.setdefault(ip, "inconnu")
        else:
            cache.update(found)
        _save_cache(cache)
        if start + _BATCH_SIZE < len(unique_missing):
            time.sleep(1.5)

    logger.info("Pays connus en cache: %s", len(cache))
    return cache
