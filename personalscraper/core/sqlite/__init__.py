# personalscraper/core/sqlite/__init__.py
"""Neutral SQLite machinery shared by indexer/ and acquire/.

Event-free: no EventBus import, no event emission.
"""

from __future__ import annotations
