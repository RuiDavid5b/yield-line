"""
Fixtures shared by every test under tests/integration/.
"""

from __future__ import annotations

import os

import pytest

ALWAYS_REQUIRED_ENV_VARS = ["DATABASE_URL"]


@pytest.fixture(autouse=True)
def _skip_if_missing_env(request):
    required = list(ALWAYS_REQUIRED_ENV_VARS)

    marker = request.node.get_closest_marker("requires_env")
    if marker:
        required += list(marker.args)

    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        pytest.skip(f"Missing required env var(s): {', '.join(missing)}")
