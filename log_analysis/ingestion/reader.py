"""Lit les journaux SSH tournes, y compris les fichiers .gz."""

from __future__ import annotations

import gzip
import os
import re
from typing import Iterator, List, Tuple

from app_log import get_logger

logger = get_logger("ingestion")

# auth.log.4.gz -> 4. Le plus grand numero est le plus ancien.
_ROTATION_RE = re.compile(r"\.(\d+)(?:\.gz)?$")


def _rotation_number(filename: str) -> int:
    """Retourne le numero de rotation, ou -1 s'il n'y en a pas."""
    match = _ROTATION_RE.search(filename)
    if match:
        return int(match.group(1))
    return -1


def list_log_files(path: str) -> List[str]:
    """Liste les fichiers du dossier, du plus ancien au plus recent."""
    try:
        names = os.listdir(path)
    except FileNotFoundError:
        logger.error("Dossier introuvable: %s", path)
        return []
    except NotADirectoryError:
        logger.error("Ce chemin n'est pas un dossier: %s", path)
        return []
    except PermissionError:
        logger.error("Permission refusee sur le dossier: %s", path)
        return []
    except OSError as exc:
        logger.error("Impossible de lister %s: %s", path, exc)
        return []

    files = []
    for name in names:
        if name == ".DS_Store" or name.startswith("."):
            continue
        full_path = os.path.join(path, name)
        if not os.path.isfile(full_path):
            logger.warning("Ignore, ce n'est pas un fichier: %s", full_path)
            continue
        files.append(name)

    files.sort(key=_rotation_number, reverse=True)
    if not files:
        logger.error("Aucun fichier de log dans %s", path)
    else:
        logger.info("Fichiers a lire: %s", ", ".join(files))
    return files


def iter_log_lines(path: str) -> Iterator[Tuple[str, str]]:
    """Donne (nom_du_fichier, ligne) pour chaque ligne lue."""
    for name in list_log_files(path):
        file_path = os.path.join(path, name)
        try:
            if name.endswith(".gz"):
                handle = gzip.open(file_path, mode="rt", errors="replace")
            else:
                handle = open(file_path, mode="r", errors="replace")
        except gzip.BadGzipFile as exc:
            logger.error("Fichier gzip illisible %s: %s", file_path, exc)
            continue
        except PermissionError:
            logger.error("Permission refusee: %s", file_path)
            continue
        except OSError as exc:
            logger.error("Impossible d'ouvrir %s: %s", file_path, exc)
            continue

        count = 0
        try:
            with handle:
                for line in handle:
                    count += 1
                    yield name, line
        except EOFError as exc:
            logger.error("Fin de fichier inattendue %s: %s", file_path, exc)
        except gzip.BadGzipFile as exc:
            logger.error("Erreur gzip pendant la lecture %s: %s", file_path, exc)
        except UnicodeError as exc:
            logger.error("Encodage illisible %s: %s", file_path, exc)
        except OSError as exc:
            logger.error("Erreur de lecture %s: %s", file_path, exc)
        else:
            if count == 0:
                logger.warning("Fichier vide: %s", file_path)
            else:
                logger.info("%s: %s lignes", name, count)
