"""Verify JevClient caches by (model, state, questions) and replays recorded usage on a hit."""

import pytest
from tests.support import FakeTypeSafeClient

from sift.cache import Cache
from sift.jev import JevClient


@pytest.fixture
def cache(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as c:
        yield c


def test_first_call_hits_the_api_and_caches(cache):
    fake_client = FakeTypeSafeClient(input_tokens=42, output_tokens=3)
    jev = JevClient(fake_client, cache, model="jev-test")

    result = jev.ask_nouls("L001: hello", {"greeting": "Is this a greeting?"})

    assert fake_client.calls == 1
    assert result.answers == {"greeting": 0.9}
    assert result.usage == {"input_tokens": 42, "output_tokens": 3}
    assert result.cached is False


def test_identical_request_is_a_cache_hit(cache):
    fake_client = FakeTypeSafeClient(input_tokens=42, output_tokens=3, resolved_model="jev-1.13.0")
    jev = JevClient(fake_client, cache, model="jev-latest")

    jev.ask_nouls("L001: hello", {"greeting": "Is this a greeting?"})
    result = jev.ask_nouls("L001: hello", {"greeting": "Is this a greeting?"})

    assert fake_client.calls == 1  # no second API call
    assert result.answers == {"greeting": 0.9}
    assert result.usage == {"input_tokens": 42, "output_tokens": 3}
    assert result.resolved_model == "jev-1.13.0"  # replayed from cache, not just the requested alias
    assert result.cached is True


def test_different_state_is_a_cache_miss(cache):
    fake_client = FakeTypeSafeClient()
    jev = JevClient(fake_client, cache, model="jev-test")

    jev.ask_nouls("L001: hello", {"greeting": "Is this a greeting?"})
    jev.ask_nouls("L001: goodbye", {"greeting": "Is this a greeting?"})

    assert fake_client.calls == 2
