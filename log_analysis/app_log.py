"""Ouvre un fichier de log different pour chaque module."""

from __future__ import annotations

import logging
from pathlib import Path


def get_logger(module_name: str) -> logging.Logger:
    """Retourne un logger qui ecrit dans logs/<module>.log."""
    logger = logging.getLogger(module_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log_dir = Path(__file__).resolve().parent / "logs"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / "{0}.log".format(module_name),
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.addHandler(logging.StreamHandler())
        logger.error("Impossible de creer le fichier de log: %s", exc)
        return logger

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(console)
    return logger
