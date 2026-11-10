"""Charge le fichier .env sans afficher les secrets."""

from __future__ import annotations

import os
from pathlib import Path

from app_log import get_logger

logger = get_logger("main")


def load_local_env() -> None:
    """Lit .env du cours, sinon celui de la version avancee."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / ".env",
        here.parent / "log_analysis_version_avancee" / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logger.error("Impossible de lire %s: %s", path, exc)
            continue
        for line in lines:
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        logger.info("Configuration chargee depuis %s", path.name)
        return
    logger.error("Aucun fichier .env trouve. IPINFO_TOKEN et DATABASE_URL manquent.")
