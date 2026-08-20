"""
Lightweight in-process memory guard for the batch processing tabs.

Streamlit Cloud's free tier caps a running app around ~1GB of RSS. Rather
than let a big batch silently blow past that and crash the whole session
(losing everything already processed), each batch loop checks actual
process memory as it goes and stops early - keeping whatever was already
built so it can still be downloaded, instead of a hard crash that loses
the entire batch.

Budget is tracked per-batch (growth since the batch started), not as a
flat ceiling on total process memory - a long-running session naturally
accumulates baseline memory from Streamlit itself and earlier tabs, and
that shouldn't count against a fresh, small batch. A flat ceiling alone
was tripping on batches that hadn't actually used much memory themselves,
just because the session had been running a while.
"""

import psutil

# Absolute safety net regardless of how the session got here. Streamlit
# Community Cloud's per-app limit is roughly 1GB; this leaves headroom for
# whatever still needs to be built after a loop stops (a ZIP or PDF from
# what's already processed).
HARD_LIMIT_MB = 900

# How much RSS a single batch run is allowed to add on top of wherever
# memory already was when it started. This is what governs normal
# operation.
BATCH_GROWTH_BUDGET_MB = 500

_process = psutil.Process()


def current_rss_mb():
    return _process.memory_info().rss / 1e6


class BatchBudget:
    """Tracks memory growth for one batch run. Create one right before a
    processing loop starts, then check .over_limit() each iteration."""

    def __init__(self):
        self.baseline_mb = current_rss_mb()

    def over_limit(self):
        current = current_rss_mb()
        if current > HARD_LIMIT_MB:
            return True
        return (current - self.baseline_mb) > BATCH_GROWTH_BUDGET_MB
