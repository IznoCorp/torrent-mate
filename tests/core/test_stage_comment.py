"""Pure unit tests for :mod:`kanbanmate.core.stage_comment` (NO I/O).

Covers marker, render, split, compose, find, stamp, header_from_state, and the
ENGLISH-only artifact guard per DESIGN §8.1 / phase-08 §8.1.a.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from kanbanmate.core.stage_comment import (
    BADGES,
    LABELS,
    CommentLike,
    HeaderInfo,
    StageStatus,
    _FINISHED_PREFIX,
    _stamp,
    compose,
    find_stage_comment_id,
    fmt_timestamp,
    header_from_state,
    marker,
    render_header,
    split_sticky,
)


# ── helpers ───────────────────────────────────────────────────────────────


@dataclass
class _FakeComment:
    """Minimal ``CommentLike`` for locate tests — non-frozen so the Protocol
    structural match passes mypy (Protocol attributes are writable by default,
    frozen dataclass attrs are read-only)."""

    id: int
    body: str


def _sticky_with_header(status: StageStatus, stage: str = "Design", **kw: str) -> str:
    """Build a full sticky body from a rendered header + a progress section."""
    info = HeaderInfo(
        stage=stage,
        status=status,
        session=kw.get("session", "abc123"),
        profile=kw.get("profile", "dev"),
        mode=kw.get("mode", "auto"),
        started=kw.get("started", "2026-06-05 14:00"),
        finished=kw.get("finished", ""),
        worktree=kw.get("worktree", "ticket-42"),
        log_hint=kw.get("log_hint", "kanban logs 42"),
    )
    header = render_header(info)
    return compose(header, ["- 14:30 — first milestone"])


# ── StageStatus ───────────────────────────────────────────────────────────


class TestStageStatus:
    """``StageStatus`` is the exact six-status literal (incl. ``waiting``, phase-27 §B)."""

    def test_all_statuses_present(self) -> None:
        expected: set[StageStatus] = {
            "running",
            "waiting",
            "done",
            "interrupted",
            "blocked",
            "cancelled",
        }
        # BADGES and LABELS cover exactly the six statuses (waiting added in §B).
        assert set(BADGES) == expected
        assert set(LABELS) == expected


# ── badges / labels — ENGLISH table ───────────────────────────────────────


class TestEnglishBadgeTable:
    """The badge→label table is EXACTLY the English spec (DESIGN §8.1)."""

    ENGLISH_TABLE: dict[StageStatus, tuple[str, str]] = {
        "running": ("\U0001f7e1", "in progress"),
        "done": ("✅", "done"),
        "interrupted": ("⚠️", "interrupted"),
        "blocked": ("⛔", "blocked"),
        "cancelled": ("❌", "cancelled"),
    }

    @pytest.mark.parametrize("status", list(ENGLISH_TABLE))
    def test_badge(self, status: StageStatus) -> None:
        badge, _label = self.ENGLISH_TABLE[status]
        assert BADGES[status] == badge

    @pytest.mark.parametrize("status", list(ENGLISH_TABLE))
    def test_label(self, status: StageStatus) -> None:
        _badge, label = self.ENGLISH_TABLE[status]
        assert LABELS[status] == label

    def test_finished_prefix_matches_label_for_terminal(self) -> None:
        """``_FINISHED_PREFIX`` uses the same English word as ``LABELS`` for
        each terminal status, and has no entry for ``running``."""
        assert "running" not in _FINISHED_PREFIX
        for status in ("done", "interrupted", "blocked", "cancelled"):
            assert _FINISHED_PREFIX[status] == LABELS[status]


class TestNoFrenchStrings:
    """ENGLISH-only artifact guard: no French label may appear anywhere in a
    rendered header (the user-facing GitHub sticky must be English)."""

    FRENCH_LABELS = [
        "en cours",
        "terminé",
        "interrompu",
        "bloqué",
        "annulé",
    ]

    @pytest.mark.parametrize("status", list(BADGES))
    def test_no_french_in_header(self, status: StageStatus) -> None:
        """Every rendered header is free of French label text."""
        hdr = render_header(
            HeaderInfo(
                stage="Design",
                status=status,
                session="abc",
                profile="dev",
                mode="auto",
                started="2026-06-05 12:00",
                finished="2026-06-05 14:00",
                worktree="ticket-42",
                log_hint="kanban logs 42",
            )
        )
        for french in self.FRENCH_LABELS:
            assert french not in hdr, (
                f"French label {french!r} found in rendered header for {status}"
            )

    def test_no_french_in_module_constants(self) -> None:
        """LABELS and _FINISHED_PREFIX contain no French strings."""
        for french in self.FRENCH_LABELS:
            assert french not in LABELS.values()
            assert french not in _FINISHED_PREFIX.values()


# ── marker ────────────────────────────────────────────────────────────────


class TestMarker:
    """``marker(stage)`` embeds the column key in NEW's prefix."""

    def test_marker_prefix(self) -> None:
        assert marker("Design") == "<!-- kanban:step=Design -->"

    def test_marker_with_spaces(self) -> None:
        """Spaces are valid inside HTML comments — the column key is embedded
        verbatim so ``PR Ready`` ≠ ``PR``."""
        assert marker("PR Ready") == "<!-- kanban:step=PR Ready -->"

    def test_marker_is_first_line_of_header(self) -> None:
        hdr = render_header(HeaderInfo(stage="Implement", status="running", started="…"))
        first, _, _ = hdr.partition("\n")
        assert first == marker("Implement")


# ── fmt_timestamp ─────────────────────────────────────────────────────────


class TestFmtTimestamp:
    """``fmt_timestamp`` formats an epoch, returns ``""`` on falsy."""

    def test_format_valid_epoch(self) -> None:
        # 2026-06-05 14:30 UTC = 1751215800 (approx).  We freeze via
        # localtime override?  Can't easily — just assert the shape.
        ts = fmt_timestamp(1751215800.0)
        assert ts != ""
        assert len(ts) == 16  # "YYYY-MM-DD HH:MM"
        # Check pattern (digits, dashes, space, colon).
        parts = ts.split(" ")
        assert len(parts) == 2
        date_part, time_part = parts
        assert len(date_part.split("-")) == 3
        assert len(time_part.split(":")) == 2

    @pytest.mark.parametrize("falsy", [None, 0, 0.0, "", False])
    def test_falsy_returns_empty(self, falsy: object) -> None:
        assert fmt_timestamp(falsy) == ""


# ── render_header ─────────────────────────────────────────────────────────


class TestRenderHeader:
    """``render_header`` produces the two-zone header block (DESIGN §8.1)."""

    def test_marker_is_first_line(self) -> None:
        hdr = render_header(HeaderInfo(stage="Plan", status="running", session="s1"))
        lines = hdr.split("\n")
        assert lines[0] == marker("Plan")

    def test_running_has_no_finished_line(self) -> None:
        hdr = render_header(
            HeaderInfo(
                stage="Plan",
                status="running",
                session="s1",
                started="2026-06-05 12:00",
            )
        )
        assert "done :" not in hdr
        assert "interrupted :" not in hdr
        assert "blocked :" not in hdr
        assert "cancelled :" not in hdr

    def test_waiting_header_variant(self) -> None:
        """The WAITING header reads ``⏳ <stage> — waiting for your input`` (phase-27 §B).

        A non-terminal LIVE status: it shows the ⏳ badge + the "waiting for your input" label and
        carries NO finished-timestamp line (it is not terminal — like ``running``).
        """
        hdr = render_header(
            HeaderInfo(
                stage="Plan",
                status="waiting",
                session="s1",
                started="2026-06-05 12:00",
            )
        )
        assert "### ⏳ Plan — waiting for your input" in hdr
        # Non-terminal: no finished line is appended.
        assert "waiting :" not in hdr
        assert "done :" not in hdr
        assert "blocked :" not in hdr

    def test_waiting_header_renders_attach_hint(self) -> None:
        """31.2: the WAITING header carries a concrete tmux attach command so the operator can answer."""
        hdr = render_header(
            HeaderInfo(
                stage="Plan",
                status="waiting",
                session="s1",
                attach_hint="tmux attach -t ticket-42",
            )
        )
        assert "- answer : `tmux attach -t ticket-42`" in hdr

    def test_non_waiting_header_omits_attach_hint(self) -> None:
        """31.2: only the WAITING status renders the attach line — running/terminal never do."""
        running = render_header(
            HeaderInfo(stage="Plan", status="running", attach_hint="tmux attach -t ticket-42")
        )
        assert "answer :" not in running
        done = render_header(
            HeaderInfo(stage="Plan", status="done", attach_hint="tmux attach -t ticket-42")
        )
        assert "answer :" not in done

    @pytest.mark.parametrize(
        "status",
        ["done", "interrupted", "blocked", "cancelled"],
    )
    def test_terminal_status_has_finished_line(self, status: StageStatus) -> None:
        hdr = render_header(
            HeaderInfo(
                stage="Design",
                status=status,
                finished="2026-06-05 14:30",
                session="s1",
            )
        )
        # The finished line uses the English label as prefix.
        expected_prefix = _FINISHED_PREFIX[status]
        assert f"- {expected_prefix} : 2026-06-05 14:30" in hdr

    def test_terminal_with_empty_finished_omits_line(self) -> None:
        """Even a terminal status omits the finished line when ``finished`` is
        empty (the caller hasn't set it yet)."""
        hdr = render_header(
            HeaderInfo(
                stage="Design",
                status="done",
                finished="",
                session="s1",
            )
        )
        assert "done :" not in hdr

    def test_includes_badge_and_label(self) -> None:
        hdr = render_header(HeaderInfo(stage="Implement", status="running"))
        assert "🟡" in hdr
        assert "in progress" in hdr


# ── find_stage_comment_id ─────────────────────────────────────────────────


class TestFindStageCommentId:
    """``find_stage_comment_id`` returns ``int | None``, exact marker match."""

    def test_finds_matching_comment(self) -> None:
        comments: list[CommentLike] = [
            _FakeComment(id=1, body="nothing"),
            _FakeComment(id=2, body=f"{marker('Design')}\n### …"),
            _FakeComment(id=3, body="other"),
        ]
        assert find_stage_comment_id(comments, "Design") == 2

    def test_returns_none_when_no_match(self) -> None:
        comments: list[CommentLike] = [
            _FakeComment(id=1, body="nothing"),
        ]
        assert find_stage_comment_id(comments, "Design") is None

    def test_pr_ready_does_not_match_pr(self) -> None:
        """Exact match: ``"PR Ready"`` ≠ ``"PR"`` (spaces matter)."""
        comments: list[CommentLike] = [
            _FakeComment(id=1, body=marker("PR Ready") + "\nbody"),
        ]
        assert find_stage_comment_id(comments, "PR") is None
        assert find_stage_comment_id(comments, "PR Ready") == 1

    def test_returns_int_not_str(self) -> None:
        comments: list[CommentLike] = [
            _FakeComment(id=42, body=marker("Design")),
        ]
        result = find_stage_comment_id(comments, "Design")
        assert isinstance(result, int)
        assert result == 42

    def test_empty_body_treated_as_no_match(self) -> None:
        comments: list[CommentLike] = [
            _FakeComment(id=1, body=""),
        ]
        assert find_stage_comment_id(comments, "Design") is None


# ── split_sticky / compose ────────────────────────────────────────────────


class TestSplitSticky:
    """``split_sticky`` splits at ``**Progress**``."""

    def test_header_only(self) -> None:
        body = marker("Design") + "\n### …"
        hdr, prog = split_sticky(body)
        assert hdr == body
        assert prog == []

    def test_header_and_progress(self) -> None:
        body = (
            marker("Design")
            + "\n### 🟡 Design — in progress\n\n**Progress**\n"
            + "- 14:30 — first step\n"
            + "- 14:45 — second step\n"
        )
        hdr, prog = split_sticky(body)
        assert marker("Design") in hdr
        assert "**Progress**" not in hdr
        assert len(prog) == 2
        assert prog[0] == "- 14:30 — first step"
        assert prog[1] == "- 14:45 — second step"

    def test_no_heading_returns_full_body(self) -> None:
        body = "just some random text\nwithout a heading"
        hdr, prog = split_sticky(body)
        assert hdr == body
        assert prog == []

    def test_trailing_blank_lines_trimmed_from_header(self) -> None:
        body = "header text\n\n\n\n**Progress**\n- item"
        hdr, prog = split_sticky(body)
        assert hdr == "header text"
        assert prog == ["- item"]


class TestCompose:
    """``compose`` assembles header + progress, round-trips through split."""

    def test_header_only(self) -> None:
        hdr = marker("Plan") + "\n### …"
        assert compose(hdr, []) == hdr

    def test_header_and_progress(self) -> None:
        hdr = marker("Design") + "\n### …"
        prog = ["- 14:30 — a", "- 15:00 — b"]
        body = compose(hdr, prog)
        assert hdr in body
        assert "**Progress**" in body
        assert "- 14:30 — a" in body
        assert "- 15:00 — b" in body

    def test_round_trip(self) -> None:
        """``split_sticky(compose(hdr, prog))`` recovers the originals."""
        hdr = marker("Review") + "\n### ✅ Review — done"
        prog = ["- 15:00 — approved"]
        body = compose(hdr, prog)
        hdr2, prog2 = split_sticky(body)
        assert hdr2 == hdr
        assert prog2 == prog

    def test_round_trip_header_only(self) -> None:
        hdr = marker("Backlog") + "\nno progress yet"
        body = compose(hdr, [])
        hdr2, prog2 = split_sticky(body)
        assert hdr2 == hdr
        assert prog2 == []


# ── _stamp ────────────────────────────────────────────────────────────────


class TestStamp:
    """``_stamp`` prefixes a line with ``HH:MM``."""

    def test_stamp_format(self) -> None:
        # Use a fixed epoch: 2026-06-05 14:30 UTC.
        # We only check the HH:MM prefix shape, not the exact value
        # (localtime depends on the test runner's timezone).
        stamped = _stamp("hello world", now=1751215800.0)
        # Pattern: "- HH:MM — hello world"
        assert stamped.startswith("- ")
        assert " — hello world" in stamped

    def test_stamp_uses_now(self) -> None:
        """Without ``now``, it uses ``time.time()``."""
        stamped = _stamp("test")
        assert stamped.startswith("- ")
        assert " — test" in stamped


# ── header_from_state ─────────────────────────────────────────────────────


class TestHeaderFromState:
    """``header_from_state`` builds ``HeaderInfo`` from a ``Mapping``."""

    def test_fills_all_fields_from_state(self) -> None:
        state: Mapping[str, object] = {
            "session_uuid": "sess-abc",
            "profile": "dev",
            "permission_mode": "auto",
            "started_at": 1751215800.0,
            "worktree": "/tmp/worktrees/ticket-42",
        }
        hdr = header_from_state(state, issue=42, stage="Design", status="running")
        assert hdr.stage == "Design"
        assert hdr.status == "running"
        assert hdr.session == "sess-abc"
        assert hdr.profile == "dev"
        assert hdr.mode == "auto"
        assert hdr.started == fmt_timestamp(1751215800.0)
        assert hdr.worktree == "ticket-42"
        assert hdr.log_hint == "kanban logs 42"
        assert hdr.finished == ""

    def test_session_id_fallback(self) -> None:
        """When ``session_uuid`` is absent, ``session_id`` is used."""
        state: Mapping[str, object] = {"session_id": "sid-xyz"}
        hdr = header_from_state(state, issue=1, stage="Plan", status="done")
        assert hdr.session == "sid-xyz"

    def test_mode_fallback(self) -> None:
        """When ``permission_mode`` is absent, ``mode`` is used."""
        state: Mapping[str, object] = {"mode": "safe"}
        hdr = header_from_state(state, issue=1, stage="Plan", status="running")
        assert hdr.mode == "safe"

    def test_started_fallback(self) -> None:
        """When ``started_at`` is absent, ``started`` is used."""
        state: Mapping[str, object] = {"started": 1751215800.0}
        hdr = header_from_state(state, issue=1, stage="Plan", status="running")
        assert hdr.started == fmt_timestamp(1751215800.0)

    def test_session_uuid_wins_over_session_id(self) -> None:
        """``session_uuid`` takes precedence over ``session_id`` when both
        are present."""
        state: Mapping[str, object] = {
            "session_uuid": "uuid-preferred",
            "session_id": "sid-fallback",
        }
        hdr = header_from_state(state, issue=1, stage="Plan", status="running")
        assert hdr.session == "uuid-preferred"

    def test_all_missing_fields_graceful_degradation(self) -> None:
        """An empty state produces a header with all metadata blank (not
        a crash)."""
        state: Mapping[str, object] = {}
        hdr = header_from_state(state, issue=99, stage="Review", status="blocked")
        assert hdr.stage == "Review"
        assert hdr.status == "blocked"
        assert hdr.session == ""
        assert hdr.profile == ""
        assert hdr.mode == ""
        assert hdr.started == ""
        assert hdr.worktree == ""  # Path("").name == ""
        assert hdr.log_hint == "kanban logs 99"

    def test_finished_passed_through(self) -> None:
        state: Mapping[str, object] = {}
        hdr = header_from_state(
            state,
            issue=1,
            stage="Merge",
            status="done",
            finished="2026-06-05 15:00",
        )
        assert hdr.finished == "2026-06-05 15:00"

    def test_empty_string_value_skipped_for_fallback(self) -> None:
        """An empty-string value does NOT satisfy the fallback — the next
        key is tried instead."""
        state: Mapping[str, object] = {
            "session_uuid": "",
            "session_id": "sid-real",
        }
        hdr = header_from_state(state, issue=1, stage="Plan", status="running")
        assert hdr.session == "sid-real"

    def test_none_value_skipped(self) -> None:
        """A ``None`` value is treated as absent."""
        state: Mapping[str, object] = {
            "session_uuid": None,
            "session_id": "sid-from-none",
        }
        hdr = header_from_state(state, issue=1, stage="Plan", status="running")
        assert hdr.session == "sid-from-none"


# ── full sticky lifecycle smoke-test ──────────────────────────────────────


class TestFullStickyLifecycle:
    """A header update preserves the body; a progress append preserves the
    header."""

    def test_header_update_preserves_body(self) -> None:
        """When the reaper flips running → blocked, the progress lines are
        kept intact."""
        body = _sticky_with_header("running", stage="Implement")
        hdr_old, prog = split_sticky(body)
        assert len(prog) == 1
        # Build a new (blocked) header and recompose.
        new_hdr = render_header(
            HeaderInfo(
                stage="Implement",
                status="blocked",
                session="abc123",
                profile="dev",
                mode="auto",
                started="2026-06-05 14:00",
                finished="2026-06-05 15:00",
                worktree="ticket-42",
                log_hint="kanban logs 42",
            )
        )
        new_body = compose(new_hdr, prog)
        assert "blocked" in new_body
        assert "- 14:30 — first milestone" in new_body

    def test_progress_append_preserves_header(self) -> None:
        """When the agent appends a line, the header is untouched."""
        body = _sticky_with_header("running")
        hdr_old, prog_old = split_sticky(body)
        prog_new = prog_old + ["- 15:00 — second milestone"]
        new_body = compose(hdr_old, prog_new)
        hdr_check, prog_check = split_sticky(new_body)
        assert hdr_check == hdr_old
        assert len(prog_check) == 2
