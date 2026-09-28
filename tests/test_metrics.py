"""precision/recall/F1, baseline agreement, and label-impurity on tiny hand-made fixtures (D13)."""

from eval.metrics import agreement_with_baseline, label_impure_groups, precision_recall_f1


def test_precision_recall_f1_perfect_prediction():
    predicted = {0: True, 1: False, 2: True}
    ground_truth = {0: 1, 1: 0, 2: 1}

    precision, recall, f1 = precision_recall_f1(predicted, ground_truth)

    assert (precision, recall, f1) == (1.0, 1.0, 1.0)


def test_precision_recall_f1_with_false_positive_and_false_negative():
    predicted = {0: True, 1: True, 2: False}  # 0: TP, 1: FP, 2: FN
    ground_truth = {0: 1, 1: 0, 2: 1}

    precision, recall, f1 = precision_recall_f1(predicted, ground_truth)

    assert precision == 0.5  # 1 TP / (1 TP + 1 FP)
    assert recall == 0.5  # 1 TP / (1 TP + 1 FN)
    assert round(f1, 4) == 0.5


def test_precision_recall_f1_no_positives_predicted_or_true():
    predicted = {0: False, 1: False}
    ground_truth = {0: 0, 1: 0}

    assert precision_recall_f1(predicted, ground_truth) == (0.0, 0.0, 0.0)


def test_agreement_with_baseline_all_agree():
    predicted = {0: True, 1: False, 2: True}
    baseline = {0: True, 1: False, 2: True}

    assert agreement_with_baseline(predicted, baseline) == 1.0


def test_agreement_with_baseline_partial_disagreement():
    predicted = {0: True, 1: True, 2: False}
    baseline = {0: True, 1: False, 2: False}  # disagree on index 1

    assert agreement_with_baseline(predicted, baseline) == 2 / 3


def test_label_impure_groups_counts_groups_with_mixed_labels():
    groups = {
        0: [0, 1, 2],  # all label 1 -> pure
        3: [3, 4],  # labels 1 and 0 -> impure
        5: [5],  # single member -> pure
    }
    ground_truth = {0: 1, 1: 1, 2: 1, 3: 1, 4: 0, 5: 0}

    assert label_impure_groups(groups, ground_truth) == 1
