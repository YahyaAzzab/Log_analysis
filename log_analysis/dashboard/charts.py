"""Cree les trois graphiques demandes avec matplotlib."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import List, Tuple

from app_log import get_logger
from processing.parser import AuthEvent

logger = get_logger("dashboard")

_REPORTS = Path(__file__).resolve().parents[1] / "reports"
_FAIL_TYPES = {"failed_password", "invalid_user", "auth_failure"}


def _top(counter: Counter, limit: int) -> Tuple[List[str], List[int]]:
    """Retourne les labels et les valeurs, du plus grand au plus petit."""
    pairs = counter.most_common(limit)
    labels = []
    values = []
    for label, value in pairs:
        text = label.strip() if isinstance(label, str) else str(label)
        labels.append(text or "(vide)")
        values.append(value)
    return labels, values


def _save_barh(labels: List[str], values: List[int], title: str, filename: str, color: str) -> Path:
    """Enregistre un graphique en barres horizontales."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = _REPORTS / filename
    try:
        _REPORTS.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("Impossible de creer le dossier reports: %s", exc)
        return path

    if not labels:
        labels = ["aucune donnee"]
        values = [0]
        logger.warning("Graphique vide: %s", title)

    try:
        height = 3.4 if len(labels) < 3 else max(4.0, 0.42 * len(labels) + 1.4)
        fig, axis = plt.subplots(figsize=(10, height))
        shown_labels = list(reversed(labels))
        shown_values = list(reversed(values))
        bars = axis.barh(shown_labels, shown_values, color=color, height=0.45)
        for bar, value in zip(bars, shown_values):
            axis.text(
                bar.get_width(),
                bar.get_y() + bar.get_height() / 2,
                " {0}".format(value),
                va="center",
            )
        axis.set_title(title)
        axis.set_xlabel("Nombre de tentatives")
        peak = max(shown_values) if shown_values else 1
        axis.set_xlim(0, max(peak * 1.12, 1))
        if len(labels) == 1:
            axis.set_ylim(-1.2, 1.2)
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
    except OSError as exc:
        logger.error("Impossible d'enregistrer %s: %s", path, exc)
    except ValueError as exc:
        logger.error("Graphique invalide %s: %s", filename, exc)
    except Exception as exc:
        logger.error("Erreur matplotlib sur %s: %s", filename, exc)
    else:
        logger.info("Graphique ecrit: %s", path)
    return path


def build_charts(events: List[AuthEvent]) -> List[Path]:
    """Produit les trois images du dashboard et retourne leurs chemins."""
    failures_by_country: Counter = Counter()
    success_by_user: Counter = Counter()
    invalid_by_user: Counter = Counter()

    for event in events:
        if event.event_type in _FAIL_TYPES:
            country = event.country or "inconnu"
            failures_by_country[country] += 1
        if event.event_type == "accepted":
            success_by_user[event.username or "(vide)"] += 1
        if event.invalid_user:
            invalid_by_user[event.username or "(vide)"] += 1

    country_labels, country_values = _top(failures_by_country, 15)
    success_labels, success_values = _top(success_by_user, 15)
    invalid_labels, invalid_values = _top(invalid_by_user, 15)

    invalid_total = sum(invalid_by_user.values())
    paths = [
        _save_barh(
            country_labels,
            country_values,
            "Tentatives echouees par pays (top 15)",
            "echecs_par_pays.png",
            "#c0392b",
        ),
        _save_barh(
            success_labels,
            success_values,
            "Tentatives reussies par utilisateur",
            "reussites_par_utilisateur.png",
            "#1e8449",
        ),
        _save_barh(
            invalid_labels,
            invalid_values,
            "Echecs invalid user par nom (total {0})".format(invalid_total),
            "echecs_invalid_user.png",
            "#b9770e",
        ),
    ]
    return paths
