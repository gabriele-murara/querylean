"""Pytest configuration: Qt runs offscreen during tests."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
