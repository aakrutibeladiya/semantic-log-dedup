"""Chunk construction, L00N <-> original-index mapping, fan-out, and cache-hit behavior."""

import pytest
from tests.support import FakeTypeSafeClient

from sift.cache import Cache
from sift.jev import JevClient
from sift.judge import build_questions, build_state, chunk_representatives, fan_out, judge_representatives


@pytest.fixture
def jev(tmp_path):
    fake_client = FakeTypeSafeClient(answer_fn=lambda text: 1.0 if "match" in text else 0.0)
    with Cache(tmp_path / "cache.sqlite3") as cache:
        yield JevClient(fake_client, cache, model="jev-test"), fake_client


def test_chunk_representatives_splits_and_preserves_order():
    reps = [(i, f"line {i}") for i in range(7)]
    chunks = chunk_representatives(reps, chunk_size=3)
    assert chunks == [reps[0:3], reps[3:6], reps[6:7]]


def test_build_state_and_questions_use_zero_padded_ids_matching_original_index():
    chunk = [(1, "hello"), (42, "world")]
    state = build_state(chunk, width=3)
    assert state == "L001: hello\nL042: world"

    questions = build_questions(chunk, "a greeting", width=3)
    assert set(questions) == {"L001", "L042"}
    assert questions["L042"] == "Does line L042 match this description: a greeting? Answer only about line L042."


def test_judge_representatives_maps_answers_back_to_original_indices(jev):
    client, _ = jev
    representatives = [(0, "nothing relevant here"), (1, "this is a match"), (35, "another match")]

    probabilities = judge_representatives(client, representatives, query="irrelevant", chunk_size=2)

    assert probabilities == {0: 0.0, 1: 1.0, 35: 1.0}


def test_judge_representatives_reruns_are_cache_hits(jev):
    client, fake_client = jev
    representatives = [(0, "a match"), (1, "no")]

    judge_representatives(client, representatives, query="q", chunk_size=10)
    judge_representatives(client, representatives, query="q", chunk_size=10)

    assert fake_client.calls == 1


def test_fan_out_preserves_indices_and_copies_representative_probability():
    groups = {0: [0, 2, 3], 1: [1]}
    probabilities = {0: 0.9, 1: 0.1}

    result = fan_out(groups, probabilities)

    assert result == {0: 0.9, 2: 0.9, 3: 0.9, 1: 0.1}
