"""Drain3 grouping: same template -> same group; representative = longest member (D7).

Also covers query-aware splitting (D10): splitting never merges, and only the flagged
parameter kinds affect the split.
"""

from sift.grouping.drain import group_by_template
from sift.grouping.refine import query_aware_groups


def test_lines_with_same_template_are_grouped_together():
    lines = [
        (0, "Invalid user admin from 173.234.31.186"),
        (1, "Invalid user jsmith from 52.80.34.196"),
        (2, "Accepted password for alice from 10.0.0.5 port 22 ssh2"),
    ]

    groups = group_by_template(lines)

    member_lists = sorted(groups.values(), key=len)
    assert member_lists == [[2], [0, 1]]


def test_representative_is_the_longest_member():
    lines = [
        (0, "Invalid user admin from 173.234.31.186"),
        (1, "Invalid user jsmith-the-really-long-username from 52.80.34.196"),
    ]

    groups = group_by_template(lines)

    assert list(groups.keys()) == [1]
    assert groups[1] == [0, 1]


def test_splitting_never_merges_groups_from_different_templates():
    lines = [
        (0, "Invalid user admin from 173.234.31.186"),
        (1, "Accepted password for alice from 10.0.0.5 port 22 ssh2"),
    ]

    groups = group_by_template(lines)

    all_members = [member for members in groups.values() for member in members]
    assert sorted(all_members) == [0, 1]
    assert len(groups) == 2


def test_query_aware_with_no_dependencies_matches_plain_drain():
    lines = [
        (0, "Invalid user admin from 173.234.31.186"),
        (1, "Invalid user jsmith from 52.80.34.196"),
        (2, "Accepted password for alice from 10.0.0.5 port 22 ssh2"),
    ]

    plain = group_by_template(lines)
    aware = query_aware_groups(lines, depends_on=[])

    assert sorted(plain.values(), key=sorted) == sorted(aware.values(), key=sorted)


def test_query_aware_only_splits_on_flagged_parameter_kinds():
    # same IP, different usernames
    lines = [
        (0, "Invalid user admin from 10.0.0.1"),
        (1, "Invalid user jsmith from 10.0.0.1"),
    ]

    # flagging "network" alone shouldn't split: both lines share the same IP value
    by_network = query_aware_groups(lines, depends_on=["network"])
    assert sorted(by_network.values()) == [[0, 1]]

    # flagging "identity" splits: usernames differ
    by_identity = query_aware_groups(lines, depends_on=["identity"])
    assert sorted(by_identity.values()) == [[0], [1]]


def test_query_aware_splitting_never_merges_lines_from_different_templates():
    lines = [
        (0, "Invalid user admin from 173.234.31.186"),
        (1, "Accepted password for alice from 10.0.0.5 port 22 ssh2"),
    ]

    groups = query_aware_groups(lines, depends_on=["identity"])

    all_members = sorted(member for members in groups.values() for member in members)
    assert all_members == [0, 1]
    assert len(groups) == 2
