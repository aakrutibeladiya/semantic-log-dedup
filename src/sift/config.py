"""Single place for model id, chunk size, thresholds, and prices (see README D2, D6, D12)."""

import os

# D2: pin an exact model name, never an alias -- an alias can move to a new model and
# silently change results. `client.models.list()` only exposes aliases (jev-latest,
# jev-preview), but a live call's `SystemOneResponse.model` revealed jev-latest's actual
# resolved version, and the API accepts that exact name back as the `model` field. That's
# the real pin (re-check it periodically; the alias can still move to a new version).
MODEL = os.environ.get("SIFT_MODEL", "jev-1.13.0")

# Representatives per chunk sent to a single system_one call, fixed across all grouping
# strategies so comparisons aren't confounded by neighbor effects (D6).
CHUNK_SIZE = 30

# Asymmetric threshold for query-analysis dependency flags (D8): biased toward "depends"
# because a false "doesn't depend" costs correctness, a false "depends" only costs money.
DEPENDENCY_THRESHOLD = 0.3

# Match threshold for the final per-line noul score.
MATCH_THRESHOLD = 0.5

# $ per token, read from the TypeSafe pricing page (D12) — fill in before reporting cost.
PRICE_PER_INPUT_TOKEN = 0.0
PRICE_PER_OUTPUT_TOKEN = 0.0

CACHE_PATH = os.environ.get("SIFT_CACHE_PATH", ".cache/sift.sqlite3")
