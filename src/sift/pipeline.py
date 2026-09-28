"""Glue: group -> judge -> fan-out -> threshold, returning matches + stats (README §5.2)."""

from __future__ import annotations

from dataclasses import dataclass

from sift.jev import JevClient
from sift.judge import fan_out, judge_representatives_with_usage


@dataclass(frozen=True)
class Stats:
    lines_total: int
    """Total lines in the log."""
    lines_judged: int
    """Representatives actually sent to the model — the "lines sent" side of the reduction ratio."""
    input_tokens: int
    output_tokens: int
    resolved_model: str | None
    """What the API actually used, e.g. the concrete version behind a "jev-latest" alias (D2)."""

    @property
    def reduction_ratio(self) -> float:
        """Fraction of lines that had to be judged directly, vs. inherited via fan-out."""
        return self.lines_judged / self.lines_total if self.lines_total else 0.0


@dataclass(frozen=True)
class SearchResult:
    matches: list[tuple[int, str]]
    """`(line_index, text)` pairs at or above threshold, sorted by original line index."""
    stats: Stats


def group_none(lines: list[tuple[int, str]]) -> dict[int, list[int]]:
    """Baseline grouping: every line is its own group (README §5.2 step 4)."""
    return {index: [index] for index, _ in lines}


def run_search(
    jev: JevClient,
    lines: list[tuple[int, str]],
    query: str,
    *,
    groups: dict[int, list[int]],
    chunk_size: int,
    threshold: float,
) -> SearchResult:
    """Judge one representative per group, fan out, and threshold (README §5.2 steps 5-8).

    `groups` maps a representative's line index to all member indices (including itself).
    """
    text_by_index = dict(lines)
    representatives = [(rep, text_by_index[rep]) for rep in sorted(groups)]

    probabilities, usage, resolved_model = judge_representatives_with_usage(jev, representatives, query, chunk_size)
    fanned = fan_out(groups, probabilities)

    matches = sorted((index, text_by_index[index]) for index, probability in fanned.items() if probability >= threshold)
    stats = Stats(
        lines_total=len(lines),
        lines_judged=len(representatives),
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        resolved_model=resolved_model,
    )
    return SearchResult(matches=matches, stats=stats)
