"""Chunking, numbered-line state, and fan-out for judging representatives (README D5, D6)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sift.jev import JevClient


def _line_id(index: int, width: int) -> str:
    return f"L{index:0{width}d}"


def chunk_representatives(
    representatives: Sequence[tuple[int, str]], chunk_size: int
) -> list[list[tuple[int, str]]]:
    """Split representatives, kept in original file order, into fixed-size chunks (D6)."""
    return [list(representatives[i : i + chunk_size]) for i in range(0, len(representatives), chunk_size)]


def build_state(chunk: Sequence[tuple[int, str]], width: int) -> str:
    """Numbered-line state block, one line per representative (D5)."""
    return "\n".join(f"{_line_id(index, width)}: {text}" for index, text in chunk)


def build_questions(chunk: Sequence[tuple[int, str]], query: str, width: int) -> dict[str, str]:
    """One Noul per line, explicit about which line it's asking about, to counter literal reading (D5)."""
    questions = {}
    for index, _ in chunk:
        line_id = _line_id(index, width)
        questions[line_id] = f"Does line {line_id} match this description: {query}? Answer only about line {line_id}."
    return questions


def judge_representatives(
    jev: JevClient,
    representatives: Sequence[tuple[int, str]],
    query: str,
    chunk_size: int,
) -> dict[int, float]:
    """Judge each representative against `query`, one Noul per line, chunked (D5, D6).

    `representatives` is `(original_line_index, text)` pairs in original file order.
    Returns original line index -> match probability.
    """
    probabilities, _usage, _resolved_model = judge_representatives_with_usage(jev, representatives, query, chunk_size)
    return probabilities


def judge_representatives_with_usage(
    jev: JevClient,
    representatives: Sequence[tuple[int, str]],
    query: str,
    chunk_size: int,
) -> tuple[dict[int, float], dict[str, int], str | None]:
    """Like `judge_representatives`, but also returns total `input_tokens`/`output_tokens` (D12)
    and the last chunk's resolved model name (D2) -- the same for every chunk barring an
    alias moving mid-run, which is exactly the drift D2 wants visible."""
    total_usage = {"input_tokens": 0, "output_tokens": 0}
    if not representatives:
        return {}, total_usage, None
    width = max(3, len(str(max(index for index, _ in representatives))))
    probabilities: dict[int, float] = {}
    resolved_model: str | None = None
    for group in chunk_representatives(representatives, chunk_size):
        state = build_state(group, width)
        questions = build_questions(group, query, width)
        result = jev.ask_nouls(state, questions)
        resolved_model = result.resolved_model
        for key in total_usage:
            total_usage[key] += result.usage.get(key) or 0
        for index, _ in group:
            probabilities[index] = result.answers[_line_id(index, width)]
    return probabilities, total_usage, resolved_model


def fan_out(groups: Mapping[int, Sequence[int]], probabilities: Mapping[int, float]) -> dict[int, float]:
    """Copy each representative's probability to every member of its group (§5.2 step 7).

    `groups` maps representative index -> member indices (including the representative itself).
    """
    return {member: probabilities[representative] for representative, members in groups.items() for member in members}
