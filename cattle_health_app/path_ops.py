"""Bounded filesystem operations for transient Windows path contention."""

from __future__ import annotations

import os
import time


REPLACE_ATTEMPTS = 6
INITIAL_RETRY_DELAY_SECONDS = 0.05


def replace_path_with_retry(source, destination) -> None:
    """Atomically replace a path, retrying only transient permission failures."""
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt + 1 == REPLACE_ATTEMPTS:
                raise
            time.sleep(INITIAL_RETRY_DELAY_SECONDS * (2 ** attempt))
