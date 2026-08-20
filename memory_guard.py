"""
Lightweight in-process memory guard for the batch processing tabs.

Streamlit Cloud's free tier caps a running app around ~1GB of RSS. Rather
than let a big batch silently blow past that and crash the whole session
(losing everything already processed), each batch loop checks actual
process memory as it goes and stops early - keeping whatever was already
built so it can still be downloaded, instead of a hard crash that loses
the entire batch.
"""

import psutil

# Conservative on purpose: leaves headroom below Streamlit Community
# Cloud's ~1GB per-app limit for Streamlit's own baseline overhead and
# whatever ZIP/PDF still needs to be built from what's processed so far.
# Raise this if you know your plan has more memory available.
SOFT_LIMIT_MB = 700

_process = psutil.Process()


def current_rss_mb():
    return _process.memory_info().rss / 1e6


def over_limit():
    return current_rss_mb() > SOFT_LIMIT_MB
