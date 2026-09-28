"""SQLite cache keyed by SHA-256 of (model, state, questions) — see README D3.

Caching makes reruns free and instant and makes results reproducible from the cache
alone. Usage is stored alongside the answer from the *first* call, so cost reporting
reflects real recorded usage even on a cache hit (D3's consequence).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Self


def _key(model: str, state: str, questions: Mapping[str, str]) -> str:
    payload = json.dumps(
        {"model": model, "state": state, "questions": questions},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Cache:
    """A disk-backed cache of Noul answers, keyed by request content."""

    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "key TEXT PRIMARY KEY, answers TEXT NOT NULL, usage TEXT NOT NULL, resolved_model TEXT NOT NULL)"
        )
        self._conn.commit()

    def get(self, model: str, state: str, questions: Mapping[str, str]) -> dict | None:
        """Return `{"answers", "usage", "resolved_model"}` for a cached request, or `None` on a miss."""
        row = self._conn.execute(
            "SELECT answers, usage, resolved_model FROM responses WHERE key = ?", (_key(model, state, questions),)
        ).fetchone()
        if row is None:
            return None
        answers_json, usage_json, resolved_model = row
        return {"answers": json.loads(answers_json), "usage": json.loads(usage_json), "resolved_model": resolved_model}

    def put(
        self,
        model: str,
        state: str,
        questions: Mapping[str, str],
        *,
        answers: Mapping[str, float],
        usage: Mapping[str, int],
        resolved_model: str,
    ) -> None:
        """Record the answers, usage, and resolved model name for a request, keyed by its content.

        `resolved_model` is what the API actually used (`SystemOneResponse.model`), which can
        differ from an alias like "jev-latest" — the only way to see the alias's real target (D2).
        """
        self._conn.execute(
            "INSERT OR REPLACE INTO responses (key, answers, usage, resolved_model) VALUES (?, ?, ?, ?)",
            (_key(model, state, questions), json.dumps(dict(answers)), json.dumps(dict(usage)), resolved_model),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
