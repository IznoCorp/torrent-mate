"""Unit tests for the pure read-only monitoring builders."""

from types import SimpleNamespace

from kanbanmate.app.monitor import (
    build_agents,
    build_board,
    build_ticket_detail,
    derive_state,
)


def test_derive_state_maps_status() -> None:
    assert derive_state("RUNNING") == "running"
    assert derive_state("WAITING") == "waiting"
    assert derive_state("BLOCKED") == "blocked"
    assert derive_state("IDLE") == "idle"


def test_build_board_groups_and_summarises() -> None:
    columns = [("Backlog", "Backlog", "inert"), ("InProgress", "In Progress", "inert")]
    tickets = [(1, "First", "Backlog"), (2, "Second", "InProgress")]
    board = build_board(columns, tickets, running_by_issue={2: "running"})
    assert board["columns"][0] == {"key": "Backlog", "name": "Backlog", "column_class": "inert"}
    by_num = {t["number"]: t for t in board["tickets"]}
    assert by_num[1]["agent_state"] is None
    assert by_num[2]["agent_state"] == "running"
    assert board["agents_summary"] == {"running": 1, "waiting": 0, "blocked": 0}


def test_build_board_maps_snapshot_column_name_to_config_key() -> None:
    """A ticket whose snapshot column is the GitHub option NAME resolves to the config KEY.

    Regression: a card in a multi-word column ("Ready to dev" / key "ReadyToDev") rendered nowhere
    because the UI groups by key and the snapshot column is the option name.
    """
    columns = [("ReadyToDev", "Ready to dev", "inert")]
    tickets = [(43, "anchor", "Ready to dev")]  # snapshot carries the NAME
    board = build_board(columns, tickets, running_by_issue={})
    assert board["tickets"][0]["column_key"] == "ReadyToDev"  # mapped to the key the UI groups on


def test_build_agents_computes_age_and_duration() -> None:
    states = [
        SimpleNamespace(
            issue_number=7,
            status="running",
            heartbeat=1000.0,
            stage="InProgress",
            started=900.0,
            worktree="/wt/kanban/ticket-7",
            title="Build it",
        )
    ]
    agents = build_agents(states, alive_by_issue={7: True}, now=1010.0)
    a = agents[0]
    assert a["issue"] == 7
    assert a["state"] == "running"
    assert a["heartbeat_age"] == 10.0
    assert a["duration_s"] == 110.0
    assert a["session_alive"] is True
    assert a["branch"] == "ticket-7"  # basename of the worktree path


def test_build_ticket_detail_markers_and_timeline() -> None:
    comments = ["hello"]  # the engine's IssueContext.comments are plain strings
    comment_dates = ["2026-06-20T11:30:00Z"]
    progress = [{"at": "2026-06-20T11:00:00Z", "text": "phase 1 done"}]
    body = "**codename**: monitoring\n**design**: docs/d.md\n**plans**: docs/p.md\nbody text"
    d = build_ticket_detail(
        7, "Build it", "InProgress", body, comments, progress, comment_dates=comment_dates
    )
    assert d["markers"]["codename"] == "monitoring"
    assert d["markers"]["design"] == "docs/d.md"
    assert d["comments"] == ["hello"]
    # timeline: progress milestones first, then chronological comments
    kinds = [e["kind"] for e in d["timeline"]]
    assert kinds == ["progress", "comment"]
    assert d["timeline"][0]["at"] == "2026-06-20T11:00:00Z"  # progress timestamp
    assert d["timeline"][1]["at"] == "2026-06-20T11:30:00Z"  # comment createdAt
    assert d["timeline"][1]["text"] == "hello"


def test_build_ticket_detail_comment_dates_defaults_empty() -> None:
    """Without comment_dates kwarg, comment entries have empty ``at``."""
    comments = ["one", "two"]
    d = build_ticket_detail(7, "T", "Backlog", "body", comments, [])
    comment_entries = [e for e in d["timeline"] if e["kind"] == "comment"]
    assert comment_entries == [
        {"kind": "comment", "at": "", "text": "one"},
        {"kind": "comment", "at": "", "text": "two"},
    ]


def test_build_ticket_detail_track_and_labels() -> None:
    """A ``track:*`` label is parsed into ``track``; raw label names pass through as ``labels``."""
    d = build_ticket_detail(7, "T", "Backlog", "body", [], [], labels=("bug", "track:express"))
    assert d["track"] == "express"
    assert d["labels"] == ["bug", "track:express"]


def test_build_ticket_detail_track_none_when_absent() -> None:
    """No ``track:*`` label → ``track`` is None; default (None) labels → empty list."""
    with_labels = build_ticket_detail(7, "T", "Backlog", "body", [], [], labels=["bug"])
    assert with_labels["track"] is None
    assert with_labels["labels"] == ["bug"]
    default = build_ticket_detail(7, "T", "Backlog", "body", [], [])
    assert default["track"] is None
    assert default["labels"] == []
