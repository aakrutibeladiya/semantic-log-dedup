"""Metrics for one (dataset, query, strategy) run (README §9.1, D13)."""

from __future__ import annotations

from collections.abc import Mapping


def precision_recall_f1(predicted: Mapping[int, bool], ground_truth: Mapping[int, int]) -> tuple[float, float, float]:
    """Standard precision/recall/F1 of `predicted` against `ground_truth`, at whatever
    threshold `predicted` was already computed at."""
    tp = sum(1 for index, hit in predicted.items() if hit and ground_truth.get(index, 0))
    fp = sum(1 for index, hit in predicted.items() if hit and not ground_truth.get(index, 0))
    fn = sum(1 for index, hit in predicted.items() if not hit and ground_truth.get(index, 0))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def agreement_with_baseline(predicted: Mapping[int, bool], baseline: Mapping[int, bool]) -> float:
    """Fraction of lines where `predicted` and the `none`-strategy baseline agree (§9.1):
    does dedup change the answer, independent of whether either is actually correct?"""
    if not predicted:
        return 1.0
    agree = sum(1 for index, hit in predicted.items() if hit == baseline.get(index, hit))
    return agree / len(predicted)


def label_impure_groups(groups: Mapping[int, list[int]], ground_truth: Mapping[int, int]) -> int:
    """Count groups whose members have different ground-truth labels for this query (D13).

    This -- not template purity -- is what actually causes a wrong answer: merging two
    lines from different true templates is harmless if the query's answer agrees on both.
    """
    return sum(1 for members in groups.values() if len({ground_truth.get(index, 0) for index in members}) > 1)
