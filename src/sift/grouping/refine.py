"""Split Drain groups by dependent parameter values (README D10, §5.3).

Splitting can only make a group purer: the worst case of an unnecessary split is extra
cost, never a wrong answer. So query-aware grouping starts from Drain's grouping (cheap)
and only un-merges where the query analysis says a masked field might matter.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from sift.grouping.drain import mine_templates

_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _parameter_kind(value: str) -> str | None:
    """Classify an extracted parameter value by the simple regexes in D10.

    Purely numeric values are never split on: numeric queries are refused upstream (D9),
    so no flag should ever ask for a split by number.
    """
    if _IP_RE.match(value):
        return "network"
    if "/" in value:
        return "paths"
    if value.isdigit():
        return None
    return "identity"


def query_aware_groups(lines: list[tuple[int, str]], depends_on: Iterable[str]) -> dict[int, list[int]]:
    """Drain groups, then split each group by parameter values whose kind is flagged (D10)."""
    depends_on = frozenset(depends_on)
    miner, members_by_cluster, template_by_cluster = mine_templates(lines)
    text_by_index = dict(lines)

    groups: dict[int, list[int]] = {}
    for cluster_id, members in members_by_cluster.items():
        template = template_by_cluster[cluster_id]
        subgroups: dict[tuple[str, ...], list[int]] = {}
        for index in members:
            params = miner.extract_parameters(template, text_by_index[index]) or []
            split_key = tuple(p.value for p in params if _parameter_kind(p.value) in depends_on)
            subgroups.setdefault(split_key, []).append(index)
        for sub_members in subgroups.values():
            representative = max(sub_members, key=lambda i: len(text_by_index[i]))
            groups[representative] = sub_members
    return groups
