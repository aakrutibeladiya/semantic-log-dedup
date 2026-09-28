"""Template labels -> line labels, or code-based extraction for parameter-dependent
queries (README D11).

Template labels only work when the query doesn't depend on what Drain masks out (D11's
catch). Q4 (default account names) and Q5 (root login) do depend on the username, so
their ground truth comes from extracting it directly out of each line's raw text and
checking it, not from a per-template table.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

_USERNAME_PATTERNS = [
    re.compile(r"invalid user\s+(\S+)", re.IGNORECASE),  # some real lines have a double space
    re.compile(r"authentication failures for (\S+) \[preauth\]", re.IGNORECASE),
    re.compile(r"message repeated \d+ times: \[ Failed password for (\S+) from", re.IGNORECASE),
    re.compile(r"Failed password for (\S+) from", re.IGNORECASE),
    re.compile(r"Accepted password for (\S+) from", re.IGNORECASE),
    re.compile(r"session opened for user (\S+) by", re.IGNORECASE),
    re.compile(r"session closed for user (\S+)", re.IGNORECASE),
    re.compile(r"user=(\S+)\s*$", re.IGNORECASE),
]

DEFAULT_ACCOUNTS = frozenset({"admin", "oracle", "test", "postgres"})


def extract_username(content: str) -> str | None:
    """Best-effort username extraction from a raw OpenSSH log line (D11's "code" labels).

    Patterns are ordered specific-to-general (e.g. "invalid user X" before the plainer
    "Failed password for X from") so a line only ever matches the pattern that actually
    names its subject.
    """
    for pattern in _USERNAME_PATTERNS:
        match = pattern.search(content)
        if match:
            return match.group(1)
    return None


def load_structured(structured_csv: str | Path) -> pd.DataFrame:
    """Load a Loghub structured CSV, re-indexed 0-based to match `sift.io.load_lines`."""
    df = pd.read_csv(structured_csv)
    df.index = df["LineId"] - 1
    return df


def template_labels(structured: pd.DataFrame, template_labels_csv: str | Path, query_id: str) -> dict[int, int]:
    """Line index -> 0/1, via each line's EventId and a hand-labeled per-template column (D11)."""
    labels_by_event = pd.read_csv(template_labels_csv).set_index("EventId")[query_id]
    return {index: int(labels_by_event[event_id]) for index, event_id in structured["EventId"].items()}


def default_account_labels(structured: pd.DataFrame, accounts: frozenset[str] = DEFAULT_ACCOUNTS) -> dict[int, int]:
    """Line index -> 1 if the line names a default/service account (Q4)."""
    labels = {}
    for index, content in structured["Content"].items():
        username = extract_username(content)
        labels[index] = int(username is not None and username.lower() in accounts)
    return labels


def root_login_labels(structured: pd.DataFrame) -> dict[int, int]:
    """Line index -> 1 if the line names the root account (Q5)."""
    labels = {}
    for index, content in structured["Content"].items():
        username = extract_username(content)
        labels[index] = int(username is not None and username.lower() == "root")
    return labels
