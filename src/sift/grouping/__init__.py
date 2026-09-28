"""Grouping strategy registry: `none` | `drain` | `query-aware`.

`none` and `drain` only need the log lines. `query-aware` (D10) additionally needs the
query's dependency flags from `query_analysis.analyze_query`, so it doesn't fit the same
`Callable[[lines], groups]` shape and is wired up separately in `cli.py`.
"""

from __future__ import annotations

from collections.abc import Callable

from sift.grouping.drain import group_by_template
from sift.pipeline import group_none

Strategy = Callable[[list[tuple[int, str]]], dict[int, list[int]]]

STRATEGIES: dict[str, Strategy] = {
    "none": group_none,
    "drain": group_by_template,
}

ALL_STRATEGY_NAMES = (*STRATEGIES, "query-aware")
