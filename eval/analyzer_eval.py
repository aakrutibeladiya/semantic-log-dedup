"""Evaluate query_analysis.py's four flags against labels/analyzer_testset.yaml (D8, §9.1).

Run with: uv run python eval/analyzer_eval.py
Needs TYPESAFE_API_KEY (loaded from .env). Uses the same on-disk cache as `sift search`,
so reruns while tuning wording are free once a query's flags have been asked once —
delete .cache/sift.sqlite3 (or bump SIFT_MODEL) to force fresh answers after an edit.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv
from typesafe_sdk import TypeSafeClient

from sift import config
from sift.cache import Cache
from sift.jev import JevClient
from sift.query_analysis import QUESTIONS, analyze_query

TESTSET_PATH = Path(__file__).parent.parent / "labels" / "analyzer_testset.yaml"


def main() -> None:
    load_dotenv()
    testset = yaml.safe_load(TESTSET_PATH.read_text())
    flags = list(QUESTIONS)

    correct = dict.fromkeys(flags, 0)
    mismatches = []
    with TypeSafeClient(model=config.MODEL) as client, Cache(config.CACHE_PATH) as cache:
        jev = JevClient(client, cache, model=config.MODEL)
        for case in testset:
            result = analyze_query(jev, case["query"])
            expected = frozenset(case["expected_flags"])
            for flag in flags:
                if (flag in expected) == (flag in result.depends_on):
                    correct[flag] += 1
            if result.depends_on != expected:
                mismatches.append((case, expected, result))

    total = len(testset)
    print(f"{total} queries\n")
    for flag in flags:
        print(f"{flag:10} accuracy: {correct[flag] / total:.0%} ({correct[flag]}/{total})")

    if mismatches:
        print(f"\n{len(mismatches)} mismatch(es):")
        for case, expected, result in mismatches:
            print(f"  {case['id']}: {case['query']!r}")
            print(f"      expected={sorted(expected)} got={sorted(result.depends_on)} probs={result.probabilities}")


if __name__ == "__main__":
    main()
