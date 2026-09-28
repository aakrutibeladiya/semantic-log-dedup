"""`sift search` end to end via `cli.run`, with a fake JevClient injected (no API key needed)."""

from pathlib import Path

from tests.support import FakeNoulAnswer, FakeResponse, FakeTypeSafeClient, FakeUsage

from sift.cache import Cache
from sift.cli import build_parser, run
from sift.jev import JevClient

FIXTURE = Path(__file__).parent / "fixtures" / "sample.log"

_ANALYSIS_FLAGS = {"identity", "network", "paths", "numbers"}


class _QueryAwareFakeClient(FakeTypeSafeClient):
    """Answers query-analysis flags by name (fixed probabilities); answers line judgments
    by whether "Invalid user" appears, same as the other CLI tests."""

    def __init__(self, flag_probabilities: dict[str, float]) -> None:
        super().__init__()
        self._flag_probabilities = flag_probabilities

    def system_one(self, *, state, questions, model):
        self.calls += 1
        if set(questions) <= _ANALYSIS_FLAGS:
            nouls = {name: FakeNoulAnswer(noul=self._flag_probabilities[name]) for name in questions}
        else:
            lines = dict(line.split(": ", 1) for line in state.splitlines() if ": " in line)
            nouls = {name: FakeNoulAnswer(noul=1.0 if "Invalid user" in lines.get(name, state) else 0.0) for name in questions}
        return FakeResponse(
            nouls=nouls,
            usage=FakeUsage(input_tokens=self.input_tokens, output_tokens=self.output_tokens),
            model=self.resolved_model,
        )


def test_build_parser_parses_search_args():
    args = build_parser().parse_args(["search", "some.log", "-q", "a query", "--threshold", "0.7"])
    assert args.command == "search"
    assert args.log_file == "some.log"
    assert args.query == "a query"
    assert args.strategy == "none"
    assert args.threshold == 0.7


def test_run_prints_matches_and_stats(tmp_path, capsys):
    def jev_factory() -> JevClient:
        fake_client = FakeTypeSafeClient(answer_fn=lambda text: 1.0 if "Invalid user" in text else 0.0)
        return JevClient(fake_client, Cache(tmp_path / "cache.sqlite3"), model="jev-test")

    exit_code = run(["search", str(FIXTURE), "-q", "failed login attempts"], jev_factory=jev_factory)

    assert exit_code == 0
    out = capsys.readouterr()
    assert "Invalid user admin" in out.out
    assert "Invalid user jsmith" in out.out
    assert "Invalid user oracle" in out.out
    assert "Accepted password" not in out.out
    assert "lines_judged=5/5" in out.err


def test_run_with_drain_strategy_matches_all_three_invalid_user_lines(tmp_path, capsys):
    """Drain merges all 3 "Invalid user" lines into one group; safe for a query that
    doesn't depend on usernames (README §5.3), so all 3 should still match via fan-out."""

    def jev_factory() -> JevClient:
        fake_client = FakeTypeSafeClient(answer_fn=lambda text: 1.0 if "Invalid user" in text else 0.0)
        return JevClient(fake_client, Cache(tmp_path / "cache.sqlite3"), model="jev-test")

    exit_code = run(
        ["search", str(FIXTURE), "-q", "failed login attempts", "--strategy", "drain"], jev_factory=jev_factory
    )

    assert exit_code == 0
    out = capsys.readouterr()
    assert "Invalid user admin" in out.out
    assert "Invalid user jsmith" in out.out
    assert "Invalid user oracle" in out.out
    assert "Accepted password" not in out.out
    # only 2 representatives sent to the model: one "Invalid user" group + one "Accepted password" group
    assert "lines_judged=2/5" in out.err


def test_run_with_query_aware_strategy_splits_by_identity_when_flagged(tmp_path, capsys):
    def jev_factory() -> JevClient:
        fake_client = _QueryAwareFakeClient(
            {"identity": 0.8, "network": 0.1, "paths": 0.1, "numbers": 0.1}
        )
        return JevClient(fake_client, Cache(tmp_path / "cache.sqlite3"), model="jev-test")

    exit_code = run(
        ["search", str(FIXTURE), "-q", "logins using default account names", "--strategy", "query-aware"],
        jev_factory=jev_factory,
    )

    assert exit_code == 0
    out = capsys.readouterr()
    assert "Invalid user admin" in out.out
    assert "Invalid user jsmith" in out.out
    assert "Invalid user oracle" in out.out
    assert "Accepted password" not in out.out
    # identity flagged -> every group with a username parameter is split, so all 5 lines are
    # their own representative (no cost savings here, but still correct -- README §5.3)
    assert "lines_judged=5/5" in out.err


def test_run_with_query_aware_strategy_refuses_numeric_queries(tmp_path, capsys):
    fake_client_holder = {}

    def tracking_jev_factory() -> JevClient:
        client = _QueryAwareFakeClient({"identity": 0.1, "network": 0.1, "paths": 0.1, "numbers": 0.9})
        fake_client_holder["client"] = client
        return JevClient(client, Cache(tmp_path / "cache.sqlite3"), model="jev-test")

    exit_code = run(
        ["search", str(FIXTURE), "-q", "connections on ports above 50000", "--strategy", "query-aware"],
        jev_factory=tracking_jev_factory,
    )

    assert exit_code == 1
    out = capsys.readouterr()
    assert out.out == ""  # no matches printed
    assert "refuse" in out.err.lower()
    assert fake_client_holder["client"].calls == 1  # only the analysis call -- no line-level calls (D9)
