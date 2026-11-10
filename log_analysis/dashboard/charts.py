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


def _ready(labels: List[str], values: List[int], title: str) -> Tuple[List[str], List[int]]:
    """Remplace une serie vide par une mention explicite."""
    if labels:
        return labels, values
    logger.warning("Graphique vide: %s", title)
    return ["aucune donnee"], [0]


def _draw(axis: object, labels: List[str], values: List[int], title: str, color: str) -> None:
    """Dessine un graphique en barres horizontales sur un axe."""
    labels, values = _ready(labels, values, title)
    shown_labels = list(reversed(labels))
    shown_values = list(reversed(values))
    bars = axis.barh(shown_labels, shown_values, color=color, height=0.55)
    for bar, value in zip(bars, shown_values):
        axis.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            " {0}".format(value),
            va="center",
            fontsize=8,
        )
    axis.set_title(title)
    axis.set_xlabel("Nombre de tentatives")
    peak = max(shown_values) if shown_values else 1
    axis.set_xlim(0, max(peak * 1.18, 1))
    if len(labels) == 1:
        axis.set_ylim(-1.2, 1.2)


def _save_barh(labels: List[str], values: List[int], title: str, filename: str, color: str) -> Path:
    """Enregistre un graphique seul, en plus de la fenetre commune."""
    import matplotlib.pyplot as plt

    path = _REPORTS / filename
    try:
        _REPORTS.mkdir(parents=True, exist_ok=True)
        height = 3.4 if len(labels) < 3 else max(4.0, 0.42 * max(len(labels), 1) + 1.4)
        fig, axis = plt.subplots(figsize=(10, height))
        _draw(axis, labels, values, title, color)
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


def _show_dashboard(fig: object) -> None:
    """Ouvre la fenetre. Sans ecran, les fichiers PNG restent dans reports/."""
    import matplotlib
    import matplotlib.pyplot as plt

    backend = matplotlib.get_backend().lower()
    if backend == "agg":
        plt.close(fig)
        logger.info("Pas d'ecran : les graphiques sont dans reports/")
        return
    logger.info("Dashboard ouvert. Fermer la fenetre pour terminer.")
    try:
        plt.show()
    except Exception as exc:
        logger.error("Impossible d'ouvrir la fenetre matplotlib: %s", exc)
        plt.close(fig)


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
    panels = [
        (
            country_labels,
            country_values,
            "Tentatives echouees par pays (top 15)",
            "echecs_par_pays.png",
            "#c0392b",
        ),
        (
            success_labels,
            success_values,
            "Tentatives reussies par utilisateur",
            "reussites_par_utilisateur.png",
            "#1e8449",
        ),
        (
            invalid_labels,
            invalid_values,
            "Echecs invalid user par nom (total {0})".format(invalid_total),
            "echecs_invalid_user.png",
            "#b9770e",
        ),
    ]
    paths = [
        _save_barh(labels, values, title, filename, color)
        for labels, values, title, filename, color in panels
    ]
    _open_dashboard(panels)
    return paths


def _open_dashboard(panels: List[tuple]) -> None:
    """Affiche les trois graphiques dans une seule fenetre."""
    import matplotlib.pyplot as plt

    try:
        _REPORTS.mkdir(parents=True, exist_ok=True)
        fig, axes = plt.subplots(3, 1, figsize=(11, 14))
        for axis, panel in zip(axes, panels):
            labels, values, title, _filename, color = panel
            _draw(axis, labels, values, title, color)
        fig.suptitle("Dashboard des tentatives SSH")
        fig.tight_layout()
        dashboard_path = _REPORTS / "dashboard.png"
        fig.savefig(dashboard_path, dpi=120)
        logger.info("Dashboard ecrit: %s", dashboard_path)
    except OSError as exc:
        logger.error("Impossible d'enregistrer le dashboard: %s", exc)
        return
    except Exception as exc:
        logger.error("Impossible de preparer le dashboard: %s", exc)
        return
    _show_dashboard(fig)
