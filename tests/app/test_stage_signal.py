"""Unit tests for the app-layer stage-sticky upsert (:mod:`kanbanmate.app.stage_signal`).

A fake :class:`~kanbanmate.ports.board.BoardWriter` records every comment-path call so
no test touches the network. The tests assert the §8.1 upsert contract (ported from the
PoC, adapted to NEW's repo-less client):

- FOUND: a single ``list_issue_comments`` call, the header is swapped, the body preserved,
  and the comment is PATCHed in place (the integer id is returned);
- ABSENT + a running header: a fresh sticky is CREATED (and the function returns ``None``);
- ABSENT + a terminal-only header (no append): a SILENT NO-OP — nothing is created;
- a GitHub error is swallowed (fail-soft): the upsert returns ``None`` and never raises.

A structural conformance check asserts the concrete ``GithubClient`` satisfies the widened
``BoardWriter`` port (``list_issue_comments`` + ``update_comment`` are no-cost additions).
"""

from __future__ import annotations

from typing import Any

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.types import CommentRef
from kanbanmate.app.stage_signal import _cancel_open_stickys, upsert_stage_comment
from kanbanmate.core.stage_comment import HeaderInfo, marker
from kanbanmate.ports.board import BoardWriter


class FakeWriter:
    """A :class:`BoardWriter` double recording every comment-path call.

    Replays a configured comment list for ``list_issue_comments`` and records the
    ``(method, *args)`` of every create/edit so a test can assert exactly which
    REST path the upsert exercised.
    """

    def __init__(self, comments: list[CommentRef] | None = None) -> None:
        """Seed the comment list and initialise an empty call log.

        Args:
            comments: The comments ``list_issue_comments`` should return.
        """
        self._comments = comments or []
        self.calls: list[tuple[Any, ...]] = []

    def move_card(self, item_id: str, column_key: str) -> None:
        """Record a (never-used here) move call to satisfy the port."""
        self.calls.append(("move", item_id, column_key))

    def comment(self, issue_number: int, body: str) -> None:
        """Record a fresh create (the CREATE / append path)."""
        self.calls.append(("create", issue_number, body))

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """Record the list call and return the seeded comments."""
        self.calls.append(("list", issue_number))
        return self._comments

    def update_comment(self, comment_id: int, body: str) -> None:
        """Record an in-place edit (the EDIT / PATCH path)."""
        self.calls.append(("update", comment_id, body))


class RaisingWriter(FakeWriter):
    """A writer whose ``list_issue_comments`` always raises (fail-soft probe)."""

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """Raise to exercise the fail-soft wrapper."""
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# FOUND: in-place PATCH (one list call, header swapped, body preserved)
# ---------------------------------------------------------------------------


def test_found_patches_in_place_swapping_header_preserving_body() -> None:
    """FOUND: the located sticky is PATCHed once — header swapped, progress kept."""
    body = (
        f"{marker('Design')}\n### 🟡 Design — in progress\n"
        "- session : `abc` · profile `docs` · mode `auto`\n\n"
        "**Progress**\n- 20:49 — first milestone"
    )
    writer = FakeWriter([CommentRef(comment_id=42, body=body)])

    new_header = HeaderInfo(stage="Design", status="done", finished="2026-06-05 14:30")
    cid = upsert_stage_comment(writer, 7, "Design", header=new_header, now=0.0)

    # The integer id round-trips back to the caller.
    assert cid == 42
    # Exactly one list call backs the locate + body read; then one PATCH.
    assert [c[0] for c in writer.calls] == ["list", "update"]
    assert writer.calls[0] == ("list", 7)
    method, comment_id, patched = writer.calls[1]
    assert method == "update"
    assert comment_id == 42
    # Header swapped to the terminal ✅ done badge…
    assert "### ✅ Design — done" in patched
    assert "- done : 2026-06-05 14:30" in patched
    # …and the BODY (the agent's progress zone) is preserved verbatim.
    assert "**Progress**" in patched
    assert "- 20:49 — first milestone" in patched
    # No fresh comment was created — the timeline keeps a single entry.
    assert not any(c[0] == "create" for c in writer.calls)


def test_found_identical_body_skips_patch() -> None:
    """#10: a re-upsert producing an IDENTICAL body skips the PATCH (no wasteful API call).

    The dashboard's per-tick ⏳ WAITING re-upsert (same header, no progress change) would otherwise
    PATCH every 10s. The body-diff guard returns the existing id WITHOUT calling update_comment.
    """
    from kanbanmate.core.stage_comment import compose, render_header

    # Build a sticky whose body is EXACTLY what re-rendering the same running header produces.
    header = HeaderInfo(stage="Design", status="running", session="abc", worktree="ticket-7")
    existing_body = compose(render_header(header), [])
    writer = FakeWriter([CommentRef(comment_id=42, body=existing_body)])

    # Re-upsert with the SAME header (no append) → the new body equals the existing one.
    cid = upsert_stage_comment(writer, 7, "Design", header=header, now=0.0)

    # The id still round-trips, but NO update_comment PATCH was issued (only the locate list).
    assert cid == 42
    assert [c[0] for c in writer.calls] == ["list"]
    assert not any(c[0] == "update" for c in writer.calls)


def test_found_changed_body_still_patches() -> None:
    """#10: the body-diff guard still PATCHes when the body genuinely changed (no false skip)."""
    body = f"{marker('Design')}\n### 🟡 Design — in progress"
    writer = FakeWriter([CommentRef(comment_id=42, body=body)])

    # A terminal header is a real change → must PATCH.
    new_header = HeaderInfo(stage="Design", status="done", finished="2026-06-05 14:30")
    cid = upsert_stage_comment(writer, 7, "Design", header=new_header, now=0.0)

    assert cid == 42
    assert any(c[0] == "update" for c in writer.calls)


def test_found_append_preserves_header_and_adds_stamped_line() -> None:
    """FOUND + append (no header): the running header is kept, a stamped line added."""
    body = f"{marker('Implement')}\n### 🟡 Implement — in progress"
    writer = FakeWriter([CommentRef(comment_id=5, body=body)])

    cid = upsert_stage_comment(writer, 7, "Implement", append="tests green", now=0.0)

    assert cid == 5
    method, comment_id, patched = writer.calls[1]
    assert method == "update"
    # The existing running header is preserved (no header arg → keep it).
    assert "### 🟡 Implement — in progress" in patched
    # The appended line is stamped and lives under the Progress heading.
    assert "**Progress**" in patched
    assert "tests green" in patched


# ---------------------------------------------------------------------------
# ABSENT + running header -> CREATE (returns None)
# ---------------------------------------------------------------------------


def test_absent_running_header_creates_and_returns_none() -> None:
    """ABSENT + a running header: a fresh sticky is created; the upsert returns None."""
    writer = FakeWriter([CommentRef(comment_id=1, body="unrelated note")])

    header = HeaderInfo(stage="Design", status="running", session="abc", worktree="ticket-7")
    cid = upsert_stage_comment(writer, 7, "Design", header=header, now=0.0)

    # NEW does NOT re-locate the just-created id — returns None after a create.
    assert cid is None
    assert [c[0] for c in writer.calls] == ["list", "create"]
    _, issue, created = writer.calls[1]
    assert issue == 7
    assert created.startswith(marker("Design"))
    assert "### 🟡 Design — in progress" in created
    assert not any(c[0] == "update" for c in writer.calls)


def test_absent_append_only_creates_with_minimal_running_header() -> None:
    """ABSENT + append (no header): create a minimal running sticky carrying the line."""
    writer = FakeWriter([])

    cid = upsert_stage_comment(writer, 7, "Implement", append="kicking off", now=0.0)

    assert cid is None
    assert [c[0] for c in writer.calls] == ["list", "create"]
    _, _issue, created = writer.calls[1]
    # A minimal running header is synthesised so the progress line has a home.
    assert "### 🟡 Implement — in progress" in created
    assert "kicking off" in created


# ---------------------------------------------------------------------------
# ABSENT + terminal-only header -> SILENT NO-OP (no create)
# ---------------------------------------------------------------------------


def test_absent_terminal_only_header_is_silent_noop() -> None:
    """ABSENT + a terminal header and NO append: nothing to finalize → no create."""
    writer = FakeWriter([CommentRef(comment_id=1, body="unrelated")])

    header = HeaderInfo(stage="Design", status="blocked", finished="2026-06-05 14:30")
    cid = upsert_stage_comment(writer, 7, "Design", header=header, now=0.0)

    assert cid is None
    # Only the locate ran — no create, no update (there was nothing to finalize).
    assert writer.calls == [("list", 7)]


# ---------------------------------------------------------------------------
# FAIL-SOFT: a GitHub error returns None and never raises
# ---------------------------------------------------------------------------


def test_github_error_is_swallowed_returns_none() -> None:
    """FAIL-SOFT: any GitHub error is logged + swallowed — returns None, never raises."""
    writer = RaisingWriter([])

    header = HeaderInfo(stage="Design", status="running")
    # Must NOT raise — the producer keeps going even when signaling fails.
    cid = upsert_stage_comment(writer, 7, "Design", header=header, now=0.0)

    assert cid is None


# ---------------------------------------------------------------------------
# Port conformance: the concrete GithubClient satisfies the widened BoardWriter
# ---------------------------------------------------------------------------


def test_github_client_satisfies_widened_board_writer() -> None:
    """The concrete ``GithubClient`` structurally satisfies the widened port.

    Widening ``BoardWriter`` with ``list_issue_comments`` + ``update_comment`` is a
    no-cost port change because the client already implements both — assert that
    statically (a typed binding mypy must accept) and at runtime (the methods exist
    and are callable with the port signatures).
    """
    client = GithubClient("tok", project_id="PVT", repo="IznoCorp/demo")
    # A typed binding: if the client did not satisfy the widened port, mypy fails here.
    writer: BoardWriter = client
    assert callable(writer.list_issue_comments)
    assert callable(writer.update_comment)
    assert callable(writer.move_card)
    assert callable(writer.comment)


# ---------------------------------------------------------------------------
# _cancel_open_stickys — flip open stickies to ❌ cancelled on teardown (DESIGN §8.2.c)
# ---------------------------------------------------------------------------


def test_cancel_flips_running_sticky_to_cancelled() -> None:
    """A RUNNING sticky (header has "in progress") → flipped to ❌ cancelled with finished ts."""
    body = (
        f"{marker('Design')}\n### 🟡 Design — in progress\n"
        "- session : `abc` · profile `docs` · mode `auto`\n\n"
        "**Progress**\n- 20:49 — first milestone"
    )
    writer = FakeWriter([CommentRef(comment_id=42, body=body)])

    _cancel_open_stickys(writer, 7, now=1_700_000_000.0)

    # The flip happens via upsert → it lists then updates in place.
    assert any(c[0] == "update" for c in writer.calls)
    update_call = next(c for c in writer.calls if c[0] == "update")
    _, cid, patched = update_call
    assert cid == 42
    assert "### ❌ Design — cancelled" in patched
    assert "- cancelled :" in patched


def test_cancel_leaves_terminal_done_sticky_untouched() -> None:
    """A terminal ✅ done sticky → UNTOUCHED (header lacks "in progress")."""
    body = (
        f"{marker('Design')}\n### ✅ Design — done\n"
        "- session : `abc` · profile `docs` · mode `auto`\n"
        "- done : 2026-06-05 14:30"
    )
    writer = FakeWriter([CommentRef(comment_id=42, body=body)])

    _cancel_open_stickys(writer, 7, now=1_700_000_000.0)

    # No update — the terminal sticky was skipped.
    assert not any(c[0] == "update" for c in writer.calls)


def test_cancel_leaves_terminal_blocked_sticky_untouched() -> None:
    """A terminal ⛔ blocked sticky → UNTOUCHED."""
    body = f"{marker('Implement')}\n### ⛔ Implement — blocked\n- blocked : 2026-06-05 12:00"
    writer = FakeWriter([CommentRef(comment_id=99, body=body)])

    _cancel_open_stickys(writer, 7, now=1_700_000_000.0)

    assert not any(c[0] == "update" for c in writer.calls)


def test_cancel_header_only_check_ignores_body_in_progress() -> None:
    """Body whose ONLY "in progress" is in the **Progress** zone → UNTOUCHED (header-only check)."""
    body = (
        f"{marker('Design')}\n### ✅ Design — done\n"
        "- session : `abc` · profile `docs` · mode `auto`\n"
        "- done : 2026-06-05 14:30\n\n"
        "**Progress**\n- 20:49 — moved to in progress state"
    )
    writer = FakeWriter([CommentRef(comment_id=42, body=body)])

    _cancel_open_stickys(writer, 7, now=1_700_000_000.0)

    # No update — the "in progress" was in the body only, not the header.
    assert not any(c[0] == "update" for c in writer.calls)


def test_cancel_ignores_non_stage_comments() -> None:
    """A non-stage comment (no "kanban:step=") → ignored entirely."""
    body = "just a regular comment about the ticket"
    writer = FakeWriter([CommentRef(comment_id=1, body=body)])

    _cancel_open_stickys(writer, 7, now=1_700_000_000.0)

    # Only the list call from cancel — pre-filter skipped, no upsert invoked.
    assert writer.calls == [("list", 7)]


def test_cancel_swallows_github_error_on_list() -> None:
    """A GitHub error during listing → swallowed (no raise)."""
    writer = RaisingWriter([])

    # Must NOT raise.
    _cancel_open_stickys(writer, 7, now=1_700_000_000.0)
