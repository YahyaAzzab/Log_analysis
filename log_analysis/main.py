"""Pipeline : lire les logs, compter, enregistrer, dessiner."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from app_log import get_logger
from dashboard.charts import build_charts
from ingestion.reader import iter_log_lines
from processing.bots import detect_bots
from processing.countries import countries_for
from processing.locate import locate_ips
from processing.parser import LOG_YEAR, AuthEvent, parse_line
from settings import load_local_env
from storage.postgres import save_postgres
from storage.save_csv import save_events

logger = get_logger("main")

_FAIL_TYPES = {"failed_password", "invalid_user", "auth_failure"}
_COUNTRY_NAMES = {"The Netherlands": "Netherlands"}


def resolve_data_dir(given: Optional[str]) -> Path:
    """Choisit le dossier des logs."""
    if given:
        return Path(given)
    here = Path(__file__).resolve().parent
    local = here / "data"
    shared = here.parent / "log_analysis_version_avancee" / "data"
    if local.is_dir() and any(local.iterdir()):
        return local
    if shared.is_dir():
        return shared
    return local


def run(data_dir: Path) -> None:
    """Enchaine lecture, bots, ipinfo, PostgreSQL et graphiques."""
    load_local_env()
    logger.info("Annee ajoutee aux dates syslog: %s", LOG_YEAR)
    logger.info("Dossier des logs: %s", data_dir)

    events: List[AuthEvent] = []
    lines_read = 0
    try:
        source = iter_log_lines(str(data_dir))
    except Exception as exc:
        logger.error("Lecture impossible: %s", exc)
        return

    for source_file, line in source:
        lines_read += 1
        event = parse_line(line, source_file)
        if event is not None:
            events.append(event)

    logger.info("Lignes lues: %s", lines_read)
    logger.info("Evenements SSH retenus: %s", len(events))
    if lines_read == 0:
        logger.error("Aucune ligne lue. Verifiez le dossier data.")
        return
    if not events:
        logger.error("Aucune tentative SSH reconnue dans les fichiers.")
        return

    try:
        scores = detect_bots(events)
    except Exception as exc:
        logger.error("Detection des bots interrompue: %s", exc)
        scores = {}

    malicious_ips = [ip for ip, info in scores.items() if info["is_malicious"]]
    logger.info(
        "Bots: %s, IP malveillantes: %s",
        sum(1 for info in scores.values() if info["is_bot"]),
        len(malicious_ips),
    )
    try:
        country_by_ip = countries_for([event.ip for event in events])
    except Exception as exc:
        logger.error("Geolocalisation de secours interrompue: %s", exc)
        country_by_ip = {}

    try:
        located = locate_ips(malicious_ips)
    except Exception as exc:
        logger.error("ipinfo interrompu: %s", exc)
        located = {}

    for event in events:
        geo = located.get(event.ip) or {}
        country = geo.get("country") or country_by_ip.get(event.ip, "inconnu")
        event.country = _COUNTRY_NAMES.get(country, country)
        event.is_bot = bool(scores.get(event.ip, {}).get("is_bot"))

    intel = {}
    for ip in malicious_ips:
        info = dict(scores[ip])
        info["geo"] = located.get(ip) or {}
        intel[ip] = info

    csv_path = save_events(events)
    save_postgres(events, intel)
    try:
        charts = build_charts(events)
    except ImportError as exc:
        logger.error("matplotlib n'est pas installe: %s", exc)
        charts = []
    except Exception as exc:
        logger.error("Dashboard interrompu: %s", exc)
        charts = []

    failures = sum(1 for event in events if event.event_type in _FAIL_TYPES)
    success = sum(1 for event in events if event.event_type == "accepted")
    invalid_user = sum(1 for event in events if event.invalid_user)
    logger.info("Echecs: %s", failures)
    logger.info("Reussites: %s", success)
    logger.info("Lignes invalid user: %s", invalid_user)
    logger.info("CSV: %s", csv_path)
    for path in charts:
        logger.info("Graphique: %s", path)


def main() -> None:
    """Point d'entree du script."""
    parser = argparse.ArgumentParser(
        description="Analyse des logs SSH et creation des graphiques."
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Dossier des auth.log. Par defaut: data/ ou le dossier de la version avancee.",
    )
    args = parser.parse_args()
    try:
        run(resolve_data_dir(args.data_dir))
    except Exception as exc:
        logger.error("Le pipeline s'est arrete: %s", exc)


if __name__ == "__main__":
    main()
