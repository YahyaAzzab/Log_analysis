"""Enregistre les evenements dans un fichier CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from app_log import get_logger
from processing.parser import AuthEvent

logger = get_logger("storage")

_CSV_PATH = Path(__file__).resolve().parent / "evenements.csv"

_COLUMNS = [
    "timestamp",
    "ip",
    "username",
    "event_type",
    "invalid_user",
    "port",
    "country",
    "source_file",
]


def save_events(events: Iterable[AuthEvent]) -> Path:
    """Ecrit le CSV et retourne son chemin. Leve rien vers l'appelant."""
    rows = list(events)
    try:
        _CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
            writer.writeheader()
            for event in rows:
                writer.writerow(
                    {
                        "timestamp": event.timestamp.isoformat(sep=" "),
                        "ip": event.ip,
                        "username": event.username,
                        "event_type": event.event_type,
                        "invalid_user": event.invalid_user,
                        "port": "" if event.port is None else event.port,
                        "country": event.country,
                        "source_file": event.source_file,
                    }
                )
    except OSError as exc:
        logger.error("Impossible d'ecrire %s: %s", _CSV_PATH, exc)
        return _CSV_PATH
    except csv.Error as exc:
        logger.error("Erreur CSV: %s", exc)
        return _CSV_PATH

    logger.info("CSV ecrit: %s (%s lignes)", _CSV_PATH, len(rows))
    return _CSV_PATH
