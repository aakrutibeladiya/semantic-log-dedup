"""`none` strategy end to end: group_none -> judge -> fan-out -> threshold, with real stats."""

from pathlib import Path

import pytest
from tests.support import FakeTypeSafeClient

from sift.cache import Cache
from sift.io import load_lines
from sift.jev import JevClient
from sift.pipeline import group_none, run_search

FIXTURE = Path(__file__).parent / "fixtures" / "sample.log"


@pytest.fixture
def jev(tmp_path):
    fake_client = FakeTypeSafeClient(
        answer_fn=lambda text: 1.0 if "Invalid user" in text else 0.0,
        input_tokens=5,
        output_tokens=1,
    )
    with Cache(tmp_path / "cache.sqlite3") as cache:
        yield JevClient(fake_client, cache, model="jev-test")


def test_group_none_makes_every_line_its_own_group():
    lines = load_lines(FIXTURE)
    groups = group_none(lines)
    assert groups == {i: [i] for i in range(5)}


def test_run_search_returns_matches_and_stats(jev):
    lines = load_lines(FIXTURE)
    groups = group_none(lines)

    result = run_search(jev, lines, "failed login attempts", groups=groups, chunk_size=30, threshold=0.5)

    assert [index for index, _ in result.matches] == [0, 1, 3]  # the three "Invalid user" lines
    assert result.stats.lines_total == 5
    assert result.stats.lines_judged == 5  # every line is its own representative under `none`
    assert result.stats.input_tokens == 5  # one chunk (chunk_size=30 >= 5 lines) -> one call
    assert result.stats.output_tokens == 1


def test_run_search_chunking_produces_multiple_calls_but_same_matches(jev):
    lines = load_lines(FIXTURE)
    groups = group_none(lines)

    result = run_search(jev, lines, "failed login attempts", groups=groups, chunk_size=2, threshold=0.5)

    assert [index for index, _ in result.matches] == [0, 1, 3]
    assert result.stats.input_tokens == 5 * 3  # 5 lines / chunk_size 2 -> 3 chunks
