"""Threshold logic and numeric refusal for the four-Noul query analyzer (D8, D9)."""

import pytest
from tests.support import FakeNoulAnswer, FakeResponse, FakeTypeSafeClient, FakeUsage

from sift.cache import Cache
from sift.jev import JevClient
from sift.query_analysis import QUESTIONS, analyze_query


class _NameKeyedClient(FakeTypeSafeClient):
    """Answers by question NAME rather than by state content.

    query_analysis asks all four questions about the same state (the query text), so they
    can only be told apart by name — unlike judge.py's per-line questions.
    """

    def __init__(self, probabilities: dict[str, float]) -> None:
        super().__init__()
        self._probabilities = probabilities

    def system_one(self, *, state, questions, model):
        self.calls += 1
        return FakeResponse(
            nouls={name: FakeNoulAnswer(noul=self._probabilities[name]) for name in questions},
            usage=FakeUsage(input_tokens=self.input_tokens, output_tokens=self.output_tokens),
            model=self.resolved_model,
        )


@pytest.fixture
def cache(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as c:
        yield c


def _jev_returning(probabilities: dict[str, float], cache) -> JevClient:
    return JevClient(_NameKeyedClient(probabilities), cache, model="jev-test")


def test_asks_all_four_questions():
    assert set(QUESTIONS) == {"identity", "network", "paths", "numbers"}


def test_query_with_no_dependencies(cache):
    jev = _jev_returning({"identity": 0.1, "network": 0.1, "paths": 0.1, "numbers": 0.1}, cache)

    result = analyze_query(jev, "authentication failures or break-in attempts")

    assert result.depends_on == frozenset()
    assert result.refuse is False


def test_asymmetric_threshold_biases_toward_depends(cache):
    """0.35 is well below 0.5 but still above threshold -> counts as "depends" (D8)."""
    jev = _jev_returning({"identity": 0.35, "network": 0.1, "paths": 0.1, "numbers": 0.1}, cache)

    result = analyze_query(jev, "login attempts using default account names")

    assert result.depends_on == frozenset({"identity"})


def test_numeric_dependency_triggers_refusal(cache):
    jev = _jev_returning({"identity": 0.1, "network": 0.1, "paths": 0.1, "numbers": 0.9}, cache)

    result = analyze_query(jev, "connections on ports above 50000")

    assert result.depends_on == frozenset({"numbers"})
    assert result.refuse is True


def test_multiple_dependencies_can_be_flagged_at_once(cache):
    jev = _jev_returning({"identity": 0.8, "network": 0.7, "paths": 0.1, "numbers": 0.1}, cache)

    result = analyze_query(jev, "root logins from a specific external IP")

    assert result.depends_on == frozenset({"identity", "network"})
    assert result.refuse is False
