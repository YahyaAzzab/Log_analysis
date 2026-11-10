"""Read rotated auth log files line by line."""

from __future__ import annotations

import gzip
import os
import re
from typing import Iterator, List, Tuple


_ROTATION_RE = re.compile(r"\.(\d+)(?:\.gz)?$")


def _rotation_number(filename: str) -> int:
    """Return the rotation index from a log filename, or -1 if absent."""
    match = _ROTATION_RE.search(filename)
    if match:
        return int(match.group(1))
    return -1


def _list_log_files(path: str) -> List[str]:
    """List log files sorted by rotation number descending (oldest first)."""
    names = [
        name
        for name in os.listdir(path)
        if name != ".DS_Store" and os.path.isfile(os.path.join(path, name))
    ]
    names.sort(key=_rotation_number, reverse=True)
    return names


def iter_log_lines(path: str) -> Iterator[Tuple[str, str]]:
    """Yield (source_file, line) for every line in data/ log files.

    Files are read in chronological order: highest rotation number first.
    Gzipped files are opened in text mode. Errors on one file are logged
    and skipped so the rest keep processing.
    """
    try:
        files = _list_log_files(path)
    except OSError as exc:
        print(f"Cannot list directory {path!r}: {exc}")
        return

    for name in files:
        file_path = os.path.join(path, name)
        try:
            if name.endswith(".gz"):
                opener = gzip.open(file_path, mode="rt", errors="replace")
            else:
                opener = open(file_path, mode="r", errors="replace")
            with opener as handle:
                for line in handle:
                    yield name, line
        except OSError as exc:
            print(f"Skip {file_path!r}: {exc}")
            continue


if __name__ == "__main__":
    counts: dict = {}
    for source_file, _line in iter_log_lines("./data"):
        counts[source_file] = counts.get(source_file, 0) + 1
    for source_file, total in counts.items():
        print(f"{source_file}: {total}")
    print(f"total files: {len(counts)}")
    print(f"total lines: {sum(counts.values())}")
