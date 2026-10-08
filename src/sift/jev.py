"""Cache-first wrapper around `TypeSafeClient.system_one`, Noul-only (see README D4).

Retries and backoff are handled by the SDK's own `RetryPolicy` (passed through the
`TypeSafeClient` constructor by the caller); this module only adds the caching layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

from typesafe_sdk import Noul, TypeSafeClient

from sift.cache import Cache


@dataclass(frozen=True)
class NoulResult:
    """Answers to a batch of Noul questions about one state, plus the usage that produced them."""

    answers: dict[str, float]
    """Question name -> probability of yes/true, 0-1."""
    usage: dict[str, int]
    """`input_tokens` / `output_tokens`, recorded at first call (D3) and replayed on cache hits."""
    resolved_model: str
    """What the API actually used, e.g. the concrete version behind a "jev-latest" alias (D2)."""
    cached: bool
    """Whether this result came from the cache rather than a live API call."""


class JevClient:
    """Asks named yes/no questions about a state, caching by (model, state, questions)."""

    def __init__(self, client: TypeSafeClient, cache: Cache, model: str) -> None:
        self._client = client
        self._cache = cache
        self._model = model

    def ask_nouls(self, state: str, questions: Mapping[str, str]) -> NoulResult:
        """Ask yes/no questions about `state`.

        Args:
            state: The text to judge.
            questions: Question name -> instructions (the yes/no statement or question).
        """
        cached = self._cache.get(self._model, state, questions)
        if cached is not None:
            return NoulResult(
                answers=cached["answers"], usage=cached["usage"], resolved_model=cached["resolved_model"], cached=True
            )

        response = self._client.system_one(
            state=state,
            questions={name: Noul(instructions=instructions) for name, instructions in questions.items()},
            model=self._model,
        )
        answers = {name: answer.noul for name, answer in response.nouls.items()}
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        self._cache.put(self._model, state, questions, answers=answers, usage=usage, resolved_model=response.model)
        return NoulResult(answers=answers, usage=usage, resolved_model=response.model, cached=False)

    def close(self) -> None:
        """Close the underlying TypeSafe client and cache connection.

        The SDK's own usage docs are explicit that `TypeSafeClient` should be used via
        a context manager for proper connection cleanup -- this delegates that through.
        """
        self._client.close()
        self._cache.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
