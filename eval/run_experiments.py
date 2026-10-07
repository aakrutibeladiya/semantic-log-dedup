"""Run every (dataset, query, strategy) combination and write results/summary.csv (README §9.2, E1).

Usage: uv run python eval/run_experiments.py [--dataset OpenSSH] [--limit N]

`--limit` truncates the log to its first N lines -- use it for a fast, cheap smoke test
before committing to a full run (OpenSSH_2k is 2000 lines, so the `none` baseline alone
is ~67 API calls per query at the default chunk size).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import yaml
from dotenv import load_dotenv
from eval.ground_truth import default_account_labels, load_structured, root_login_labels, template_labels
from eval.metrics import agreement_with_baseline, label_impure_groups, precision_recall_f1
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
TEMPLATE_LABELS_BY_DATASET = {
    "OpenSSH": ROOT / "labels" / "openssh_template_labels.csv",
    "Apache": ROOT / "labels" / "apache_template_labels.csv",
    "Linux": ROOT / "labels" / "linux_template_labels.csv",
}
SUMMARY_PATH = ROOT / "results" / "summary.csv"

STRATEGY_NAMES = ["none", "drain", "query-aware"]

FIELDNAMES = [
    "dataset",
    "query_id",
    "query",
    "strategy",
    "refused",
    "precision",
    "recall",
    "f1",
    "agreement_with_baseline",
    "label_impure_groups",
    "lines_total",
    "lines_judged",
    "reduction_ratio",
    "input_tokens",
    "output_tokens",
    "resolved_model",
    "model_requested",
    "chunk_size",
    "threshold",
]


def _ground_truth_for(query: dict, structured) -> dict[int, int] | None:
    """`None` for a "refused" query (Q6): there's no correctness metric to compute --
    the interesting fact is just whether `query-aware` refuses while `none`/`drain` don't."""
    method = query["label_method"]
    if method == "refused":
        return None
    if method == "template":
        return template_labels(structured, TEMPLATE_LABELS_BY_DATASET[query["dataset"]], query["id"])
    if method == "code:default_accounts":
        return default_account_labels(structured)
    if method == "code:root_login":
        return root_login_labels(structured)
    raise ValueError(f"unsupported label_method for E1: {method!r}")


def _groups_for(strategy: str, lines: list[tuple[int, str]], jev: JevClient, query_text: str):
    """Returns `(groups, refused)`. Only `query-aware` can refuse (D9)."""
    if strategy == "query-aware":
        analysis = analyze_query(jev, query_text)
        if analysis.refuse:
            return None, True
        return query_aware_groups(lines, analysis.depends_on), False
    return STRATEGIES[strategy](lines), False


def run_query(
    query: dict,
    lines: list[tuple[int, str]],
    structured,
    jev: JevClient,
    chunk_size: int,
    threshold: float,
) -> list[dict]:
    ground_truth = _ground_truth_for(query, structured)
    baseline_predicted: dict[int, bool] = {}
    rows = []

    for strategy in STRATEGY_NAMES:
        groups, refused = _groups_for(strategy, lines, jev, query["query"])
        row = {
            "dataset": query["dataset"],
            "query_id": query["id"],
            "query": query["query"],
            "strategy": strategy,
            "refused": refused,
            "chunk_size": chunk_size,
            "threshold": threshold,
            "model_requested": config.MODEL,
        }
        if refused:
            rows.append(row)
            continue

        result = run_search(jev, lines, query["query"], groups=groups, chunk_size=chunk_size, threshold=threshold)
        matched = {index for index, _ in result.matches}
        predicted = {index: (index in matched) for index in range(len(lines))}
        if strategy == "none":
            baseline_predicted = predicted

        if ground_truth is None:
            precision = recall = f1 = label_impure = ""
        else:
            precision, recall, f1 = precision_recall_f1(predicted, ground_truth)
            label_impure = label_impure_groups(groups, ground_truth)
        row.update(
            {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "agreement_with_baseline": agreement_with_baseline(predicted, baseline_predicted or predicted),
                "label_impure_groups": label_impure,
                "lines_total": result.stats.lines_total,
                "lines_judged": result.stats.lines_judged,
                "reduction_ratio": result.stats.reduction_ratio,
                "input_tokens": result.stats.input_tokens,
                "output_tokens": result.stats.output_tokens,
                "resolved_model": result.stats.resolved_model,
            }
        )
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="OpenSSH")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    load_dotenv()
    queries = [q for q in yaml.safe_load(QUERIES_PATH.read_text()) if q["dataset"] == args.dataset]

    client = TypeSafeClient(model=config.MODEL)
    cache = Cache(config.CACHE_PATH)
    jev = JevClient(client, cache, model=config.MODEL)

    log_path = ROOT / "data" / "raw" / args.dataset / f"{args.dataset}_2k.log"
    structured_path = ROOT / "data" / "raw" / args.dataset / f"{args.dataset}_2k.log_structured.csv"
    lines = load_lines(log_path)
    structured = load_structured(structured_path)
    if args.limit is not None:
        lines = lines[: args.limit]
        structured = structured.loc[structured.index < args.limit]

    all_rows = []
    for query in queries:
        print(f"{query['id']}: {query['query']!r}")
        rows = run_query(query, lines, structured, jev, config.CHUNK_SIZE, config.MATCH_THRESHOLD)
        all_rows.extend(rows)
        for row in rows:
            if row["refused"]:
                print(f"  {row['strategy']:12} refused")
            else:
                f1_display = f"{row['f1']:.2f}" if row["f1"] != "" else "n/a"
                print(
                    f"  {row['strategy']:12} f1={f1_display} lines_judged={row['lines_judged']}/{row['lines_total']} "
                    f"tokens={row['input_tokens']}"
                )

    existing_rows = []
    if SUMMARY_PATH.exists():
        with open(SUMMARY_PATH, newline="") as f:
            existing_rows = [row for row in csv.DictReader(f) if row["dataset"] != args.dataset]

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(existing_rows + all_rows)
    print(f"\nwrote {len(all_rows)} rows for {args.dataset} to {SUMMARY_PATH} ({len(existing_rows) + len(all_rows)} total)")


if __name__ == "__main__":
    main()
