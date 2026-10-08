"""`sift search FILE -q QUERY [--strategy none] [--threshold T]` (README §5, §10)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from dotenv import load_dotenv
from typesafe_sdk import TypeSafeClient

from sift import config
from sift.cache import Cache
from sift.grouping import ALL_STRATEGY_NAMES, STRATEGIES
from sift.grouping.refine import query_aware_groups
from sift.io import load_lines
from sift.jev import JevClient
from sift.pipeline import run_search
from sift.query_analysis import REFUSAL_MESSAGE, analyze_query


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sift")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search a log file for lines matching a query.")
    search.add_argument("log_file")
    search.add_argument("-q", "--query", required=True)
    search.add_argument("--strategy", choices=list(ALL_STRATEGY_NAMES), default="none")
    search.add_argument("--chunk-size", type=int, default=config.CHUNK_SIZE)
    search.add_argument("--threshold", type=float, default=config.MATCH_THRESHOLD)
    return parser


def _default_jev_factory() -> JevClient:
    client = TypeSafeClient(model=config.MODEL)
    cache = Cache(config.CACHE_PATH)
    return JevClient(client, cache, model=config.MODEL)


def run(argv: list[str], jev_factory: Callable[[], JevClient] = _default_jev_factory) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    lines = load_lines(args.log_file)

    with jev_factory() as jev:
        if args.strategy == "query-aware":
            analysis = analyze_query(jev, args.query)
            if analysis.refuse:
                print(REFUSAL_MESSAGE, file=sys.stderr)
                return 1
            groups = query_aware_groups(lines, analysis.depends_on)
        else:
            groups = STRATEGIES[args.strategy](lines)

        result = run_search(jev, lines, args.query, groups=groups, chunk_size=args.chunk_size, threshold=args.threshold)

        for index, text in result.matches:
            print(f"{index}: {text}")

        stats = result.stats
        print(
            f"lines_judged={stats.lines_judged}/{stats.lines_total} "
            f"input_tokens={stats.input_tokens} output_tokens={stats.output_tokens} "
            f"model={stats.resolved_model}",
            file=sys.stderr,
        )
    return 0


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
