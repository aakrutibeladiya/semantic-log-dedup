"""Cost-at-scale demo: Q1 and Q4 on a real, larger OpenSSH slice (README §9.2, E3).

There's no ground truth at this scale -- only the curated 2k sample is hand-labeled
(E1). So this measures cost (tokens, lines judged, wall-clock time) and uses agreement
with the `none` baseline as the correctness proxy, instead of precision/recall/F1.

Usage: uv run python -m eval.run_scale_experiment [--limit N]
Expects data/raw/OpenSSH_full/OpenSSH_30k.log -- see data/README.md for how it's made.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from eval.metrics import agreement_with_baseline
from typesafe_sdk import TypeSafeClient

from sift import config
from sift.cache import Cache
from sift.grouping import STRATEGIES
from sift.grouping.refine import query_aware_groups
from sift.io import load_lines
from sift.jev import JevClient
from sift.pipeline import run_search
from sift.query_analysis import analyze_query

ROOT = Path(__file__).parent.parent
QUERIES_PATH = ROOT / "labels" / "queries.yaml"
LOG_PATH = ROOT / "data" / "raw" / "OpenSSH_full" / "OpenSSH_30k.log"
RESULTS_PATH = ROOT / "results" / "scale_experiment.csv"

STRATEGY_NAMES = ["none", "drain", "query-aware"]
QUERY_IDS = ["Q1", "Q4"]  # per README's E3 spec

FIELDNAMES = [
    "query_id",
    "query",
    "strategy",
    "refused",
    "lines_total",
    "lines_judged",
    "reduction_ratio",
    "input_tokens",
    "output_tokens",
    "resolved_model",
    "agreement_with_baseline",
    "wall_clock_seconds",
]


def _groups_for(strategy: str, lines: list[tuple[int, str]], jev: JevClient, query_text: str):
    if strategy == "query-aware":
        analysis = analyze_query(jev, query_text)
        if analysis.refuse:
            return None, True
        return query_aware_groups(lines, analysis.depends_on), False
    return STRATEGIES[strategy](lines), False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    load_dotenv()
    all_queries = {q["id"]: q for q in yaml.safe_load(QUERIES_PATH.read_text()) if q["dataset"] == "OpenSSH"}

    lines = load_lines(LOG_PATH)
    if args.limit is not None:
        lines = lines[: args.limit]

    rows = []
    with TypeSafeClient(model=config.MODEL) as client, Cache(config.CACHE_PATH) as cache:
        jev = JevClient(client, cache, model=config.MODEL)

        for query_id in QUERY_IDS:
            query = all_queries[query_id]
            print(f"{query_id}: {query['query']!r} ({len(lines)} lines)")
            baseline_predicted: dict[int, bool] = {}

            for strategy in STRATEGY_NAMES:
                start = time.monotonic()
                groups, refused = _groups_for(strategy, lines, jev, query["query"])
                row = {"query_id": query_id, "query": query["query"], "strategy": strategy, "refused": refused}

                if refused:
                    row["wall_clock_seconds"] = round(time.monotonic() - start, 1)
                    rows.append(row)
                    print(f"  {strategy:12} refused")
                    continue

                result = run_search(
                    jev,
                    lines,
                    query["query"],
                    groups=groups,
                    chunk_size=config.CHUNK_SIZE,
                    threshold=config.MATCH_THRESHOLD,
                )
                elapsed = time.monotonic() - start
                matched = {index for index, _ in result.matches}
                predicted = {index: (index in matched) for index in range(len(lines))}
                if strategy == "none":
                    baseline_predicted = predicted

                row.update(
                    {
                        "lines_total": result.stats.lines_total,
                        "lines_judged": result.stats.lines_judged,
                        "reduction_ratio": result.stats.reduction_ratio,
                        "input_tokens": result.stats.input_tokens,
                        "output_tokens": result.stats.output_tokens,
                        "resolved_model": result.stats.resolved_model,
                        "agreement_with_baseline": agreement_with_baseline(predicted, baseline_predicted or predicted),
                        "wall_clock_seconds": round(elapsed, 1),
                    }
                )
                rows.append(row)
                print(
                    f"  {strategy:12} lines_judged={row['lines_judged']}/{row['lines_total']} "
                    f"({row['reduction_ratio']:.1%}) tokens={row['input_tokens']} "
                    f"agreement={row['agreement_with_baseline']:.3f} time={row['wall_clock_seconds']}s"
                )

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {len(rows)} rows to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
