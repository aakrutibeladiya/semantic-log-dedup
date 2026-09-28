"""Load raw log files, keeping each line's original index (README §5.2 step 1).

Loghub structured-CSV loading (for `EventId` ground truth) is deferred until eval work
starts — not needed for the CLI's search path.
"""

from __future__ import annotations

from pathlib import Path


def load_lines(path: str | Path) -> list[tuple[int, str]]:
    """Read a log file, stripping trailing newlines, pairing each line with its 0-based index."""
    with open(path, encoding="utf-8") as f:
        return [(index, line.rstrip("\n")) for index, line in enumerate(f)]
