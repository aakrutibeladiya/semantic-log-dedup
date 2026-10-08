"""Shared fakes for exercising JevClient/pipeline/cli without hitting the real API."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class FakeNoulAnswer:
    noul: float


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    nouls: dict[str, FakeNoulAnswer]
    usage: FakeUsage
    model: str


class FakeTypeSafeClient:
    """Stands in for `TypeSafeClient.system_one`.

    `answer_fn(line_text) -> float` decides each line's noul; defaults to always "yes".
    """

    def __init__(
        self,
        answer_fn: Callable[[str], float] = lambda _text: 0.9,
        *,
        input_tokens: int = 10,
        output_tokens: int = 1,
        resolved_model: str = "jev-test-resolved",
    ) -> None:
        self.answer_fn = answer_fn
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.resolved_model = resolved_model
        self.calls = 0

    def system_one(self, *, state, questions, model):
        self.calls += 1
        # Judge-style state is "L001: text" per line, keyed by line id (matching question names);
        # anything else falls back to the whole state, so simpler cache-only tests still work.
        lines = dict(line.split(": ", 1) for line in state.splitlines() if ": " in line)
        return FakeResponse(
            nouls={name: FakeNoulAnswer(noul=self.answer_fn(lines.get(name, state))) for name in questions},
            usage=FakeUsage(input_tokens=self.input_tokens, output_tokens=self.output_tokens),
            model=self.resolved_model,
        )

    def close(self) -> None:
        pass
