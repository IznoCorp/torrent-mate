"""Tests for the skiff route breadcrumb on the filesystem state store.

The route breadcrumb (``route/<issue>`` = ``{"ts", "lane"}``) mirrors the boolean
``done``/``advance`` breadcrumbs (same issue-keyed path, same :data:`_DONE_TTL` recency horizon,
same poison-file degrade) but carries a PAYLOAD — the lane the triage stage chose. Task 3's
``kanban-route`` helper writes it; Task 4's session-end backstop reads it to move the card to the
lane's entry column.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from kanbanmate.adapters.store.fs_store import FsStateStore


def test_route_breadcrumb_roundtrips_the_lane(tmp_path: Path) -> None:
    """record_agent_route writes the lane; recent_agent_route reads it back within TTL."""
    store = FsStateStore(tmp_path)
    now = time.time()
    assert store.recent_agent_route(7, now=now) == ""  # absent → empty
    store.record_agent_route(7, "express", now=now)
    assert store.recent_agent_route(7, now=now) == "express"


def test_route_breadcrumb_expires_after_ttl(tmp_path: Path) -> None:
    """An aged route breadcrumb reads as empty (mirrors the done TTL horizon)."""
    store = FsStateStore(tmp_path)
    store.record_agent_route(7, "lite", now=1000.0)
    assert store.recent_agent_route(7, now=1000.0 + 1801.0) == ""


def test_clear_agent_route_is_idempotent(tmp_path: Path) -> None:
    """clear_agent_route removes the marker and never raises when absent."""
    store = FsStateStore(tmp_path)
    store.record_agent_route(7, "full", now=500.0)
    store.clear_agent_route(7)
    store.clear_agent_route(7)  # no-op, no raise
    assert store.recent_agent_route(7, now=500.0) == ""


# ---------------------------------------------------------------------------
# Poison-file degrade: a WELL-FORMED-JSON-but-WRONG-SHAPE file must degrade to the
# reader's safe default, NEVER raise (the AttributeError/KeyError guard). These reads
# run BEFORE purge_ticket in session-end, so an escaping exception would strand the
# slot — every reader must absorb a wrong-shape marker. The finding hardens the
# pre-existing genesis advance/done/end_attempts readers too (not just skiff's route).
# ---------------------------------------------------------------------------

# Wrong-SHAPE bodies: valid JSON, but not the ``{"<key>": ...}`` object the readers
# expect. The non-dict shapes (list / bare string / int / bool / null) all lack ``.get``,
# so without the guard ``data.get(...)`` raises AttributeError; the dict-missing-key shape
# exercises the ``.get(..., default)`` branch (which must NOT raise either). ``now`` is
# pushed far beyond both TTL horizons so a defaulted ``ts=0.0`` reads as EXPIRED, making the
# safe default (False / "") observable uniformly across every shape.
_WRONG_SHAPE = ("[1, 2, 3]", '"x"', "42", "true", "null", '{"unexpected": 1}')
_FAR_FUTURE = 1_000_000.0  # >> _ADVANCE_TTL (300) and _DONE_TTL (1800)


@pytest.mark.parametrize("body", _WRONG_SHAPE)
def test_recent_agent_advance_degrades_on_wrong_shape(tmp_path: Path, body: str) -> None:
    """A wrong-shape advance file reads as False (no AttributeError/KeyError escape)."""
    store = FsStateStore(tmp_path)
    store._advance_path(7).write_text(body)
    assert store.recent_agent_advance(7, now=_FAR_FUTURE) is False


@pytest.mark.parametrize("body", _WRONG_SHAPE)
def test_recent_agent_done_degrades_on_wrong_shape(tmp_path: Path, body: str) -> None:
    """A wrong-shape done file reads as False (no AttributeError/KeyError escape)."""
    store = FsStateStore(tmp_path)
    store._done_path(7).write_text(body)
    assert store.recent_agent_done(7, now=_FAR_FUTURE) is False


@pytest.mark.parametrize("body", _WRONG_SHAPE)
def test_recent_agent_route_degrades_on_wrong_shape(tmp_path: Path, body: str) -> None:
    """A wrong-shape route file reads as "" (no AttributeError/KeyError escape)."""
    store = FsStateStore(tmp_path)
    store._route_path(7).write_text(body)
    assert store.recent_agent_route(7, now=_FAR_FUTURE) == ""


@pytest.mark.parametrize("body", _WRONG_SHAPE)
def test_get_end_attempts_degrades_on_wrong_shape(tmp_path: Path, body: str) -> None:
    """A wrong-shape end_attempts file reads as 0 (no AttributeError/KeyError escape)."""
    store = FsStateStore(tmp_path)
    store._end_attempts_path(7).write_text(body)
    assert store.get_end_attempts(7) == 0
