"""Wrap Drain3 template mining into the `groups` shape the pipeline expects (README §5.2 step 4)."""

from __future__ import annotations

from drain3 import TemplateMiner


def mine_templates(lines: list[tuple[int, str]]) -> tuple[TemplateMiner, dict[int, list[int]], dict[int, str]]:
    """Run Drain3 once over `lines`.

    Returns the miner (needed for `extract_parameters` in `refine.py`, D10), each cluster's
    member line indices, and each cluster's mined template text.
    """
    miner = TemplateMiner()
    members_by_cluster: dict[int, list[int]] = {}
    template_by_cluster: dict[int, str] = {}
    for index, text in lines:
        result = miner.add_log_message(text)
        cluster_id = result["cluster_id"]
        members_by_cluster.setdefault(cluster_id, []).append(index)
        template_by_cluster[cluster_id] = result["template_mined"]
    return miner, members_by_cluster, template_by_cluster


def group_by_template(lines: list[tuple[int, str]]) -> dict[int, list[int]]:
    """Group lines by Drain3 template, representative = longest member of each group (D7).

    Longest is deterministic (reproducible results) and loses the least if lines are
    ever truncated to fit a state limit.
    """
    _miner, members_by_cluster, _templates = mine_templates(lines)
    text_by_index = dict(lines)
    return {
        max(members, key=lambda i: len(text_by_index[i])): members for members in members_by_cluster.values()
    }
