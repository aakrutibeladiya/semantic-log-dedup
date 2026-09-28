"""Four-Noul query dependency check + numeric refusal (README D8, D9).

State = the query text. One cheap call, four Nouls answered in parallel, decides what
the query depends on before any line is judged.
"""

from __future__ import annotations

from dataclasses import dataclass

from sift import config
from sift.jev import JevClient

QUESTIONS = {
    "identity": (
        "To decide whether a log line matches this search, would you need to know exactly "
        "which user, account, or host name it names — as opposed to just whether some user, "
        "account, or host name is involved at all?"
    ),
    "network": (
        "To decide whether a log line matches this search, would you need to know exactly "
        "which IP address or network address it names — as opposed to just whether an "
        "address is involved at all?"
    ),
    "paths": (
        "To decide whether a log line matches this search, would you need to know exactly "
        "which file or directory path it names — as opposed to just whether a path is "
        "involved at all?"
    ),
    "numbers": (
        "Does this search require comparing a numeric value, such as a port, count, size, "
        "duration, or status code, against a specific number or threshold — as opposed to "
        "just detecting that some event happened?"
    ),
}

REFUSAL_MESSAGE = (
    "sift refuses queries that depend on numeric comparison: numeric reasoning is a "
    "documented weakness of the judgment model, and a regex or awk filter does exact "
    "numeric comparison perfectly. Try something like: grep -E or awk on the relevant field."
)


@dataclass(frozen=True)
class QueryAnalysis:
    """Which fields a query depends on, per D8's asymmetric-threshold Noul check."""

    probabilities: dict[str, float]
    """Raw probability per flag (identity, network, paths, numbers), 0-1."""
    depends_on: frozenset[str]
    """Flags at or above the dependency threshold."""

    @property
    def refuse(self) -> bool:
        """Numeric queries are refused by design (D9)."""
        return "numbers" in self.depends_on


def analyze_query(jev: JevClient, query: str, threshold: float = config.DEPENDENCY_THRESHOLD) -> QueryAnalysis:
    """Ask whether `query` depends on identity, network, paths, or numbers (D8)."""
    result = jev.ask_nouls(query, QUESTIONS)
    depends_on = frozenset(name for name, probability in result.answers.items() if probability >= threshold)
    return QueryAnalysis(probabilities=result.answers, depends_on=depends_on)
