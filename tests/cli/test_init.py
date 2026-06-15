"""Tests for :mod:`kanbanmate.cli.init` — the per-repo ``kanban init`` (DESIGN §4.3).

Every test injects a :class:`FakeSeeder` (records calls, returns canned ids) so no
test touches the network. ``tmp_path`` stands in for both the kanban runtime root
(``projects.json``) and the clone (``.claude/kanban/columns.yml``). The assertions
pin the per-repo contract: a fresh project is ensured, the columns from the
template become the Status options, the ``wave:*``/``prio:*`` labels are ensured,
the template is copied into the clone, and the registry is written keyed by the
project node id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kanbanmate.cli import init as init_mod
from kanbanmate.cli.init import ProjectEntry, init


class FakeSeeder:
    """A :class:`~kanbanmate.ports.board.Seeder` that records calls and returns canned ids.

    Mirrors the production :class:`~kanbanmate.adapters.github.client.GithubClient`
    Seeder surface without any I/O. Also exposes ``status_field_node_id`` so ``init``
    can record the Status field id in the registry.
    """

    def __init__(self, *, project_id: str = "PVT_NEW") -> None:
        """Initialise empty call logs and the canned project id to return."""
        self.project_id = project_id
        self.ensure_project_calls: list[tuple[str, str]] = []
        self.linked: list[tuple[str, str]] = []
        self.described: list[tuple[str, str]] = []
        self.ensure_columns_calls: list[tuple[str, list[str]]] = []
        self.ensure_labels_calls: list[tuple[str, list[str]]] = []
        self.created_issues: list[tuple[str, str, str, list[str]]] = []
        self.added: list[tuple[str, str]] = []
        self.body_patches: list[tuple[str, str]] = []

    def ensure_project(self, org: str, title: str) -> str:
        """Record the call and return the canned project node id."""
        self.ensure_project_calls.append((org, title))
        return self.project_id

    def link_to_repo(self, project_id: str, repo: str) -> None:
        """Record the project↔repo link (init establishes it)."""
        self.linked.append((project_id, repo))

    def update_project_description(self, project_id: str, short_description: str) -> None:
        """Record the default-description set (init's phase-33 step)."""
        self.described.append((project_id, short_description))

    def ensure_columns(self, project_id: str, columns: list[str]) -> dict[str, str]:
        """Record the call and return an option-id map mirroring ``columns``."""
        self.ensure_columns_calls.append((project_id, list(columns)))
        return {name: f"opt_{i}" for i, name in enumerate(columns)}

    def ensure_labels(self, repo: str, labels: list[str]) -> dict[str, str]:
        """Record the call and return a label-id map mirroring ``labels``."""
        self.ensure_labels_calls.append((repo, list(labels)))
        return {name: f"lbl_{name}" for name in labels}

    def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> tuple[str, int]:
        """Record the call (unused by init) and return a canned issue."""
        self.created_issues.append((repo, title, body, list(labels)))
        return f"ISSUE_{len(self.created_issues)}", len(self.created_issues)

    def update_issue_body(self, issue_node_id: str, body: str) -> None:
        """Record the body patch (unused by init)."""
        self.body_patches.append((issue_node_id, body))

    def close_issue(self, issue_node_id: str) -> None:  # pragma: no cover - unused by init
        """Unused by init (cockpit ticket_close); satisfies the Seeder protocol."""

    def fetch_issue(self, issue_number: int):  # type: ignore[no-untyped-def]  # pragma: no cover
        """Unused by init (cockpit ticket_edit/close); satisfies the Seeder protocol."""
        from kanbanmate.adapters.github.types import IssueRef

        return IssueRef(node_id=f"NODE_{issue_number}", number=issue_number, title="", body="")

    def add_to_project(self, project_id: str, issue_node_id: str) -> str:
        """Record the add (unused by init) and return a canned item id."""
        self.added.append((project_id, issue_node_id))
        return f"PVTI_{len(self.added)}"

    def move_card(self, item_id: str, column_key: str) -> None:  # pragma: no cover - unused by init
        """Unused by init (only ``seed`` places cards); satisfies the Seeder protocol."""

    def status_field_node_id(self, project_id: str) -> str:
        """Return a canned Status field node id for the registry entry."""
        return "PVTSSF_STATUS"


class FakeEnsureClone:
    """An injectable ``ensure_clone`` fake that records its call (no real git).

    Records the ``repo_url`` + keyword args ``init`` passes so the tests can assert
    the tokenless URL and the ``<root>/token`` token path. ``record_columns_exists``
    snapshots whether the clone's ``columns.yml`` exists at call time, proving the
    bootstrap runs BEFORE the columns.yml write.
    """

    def __init__(self, *, columns_path: Path | None = None) -> None:
        """Initialise the recorder.

        Args:
            columns_path: When given, the clone's ``columns.yml`` path probed at
                call time so the test can assert the call-order (it must not exist
                yet when ``ensure_clone`` fires).
        """
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._columns_path = columns_path
        self.columns_existed_at_call: bool | None = None

    def __call__(self, repo_url: str, **kwargs: object) -> Path:
        """Record the call and snapshot the columns.yml existence."""
        if self._columns_path is not None:
            self.columns_existed_at_call = self._columns_path.exists()
        self.calls.append((repo_url, dict(kwargs)))
        return Path("/fake/clone")


def _run_init(
    tmp_path: Path,
    *,
    repo: str = "IznoCorp/demo",
    ensure_clone: FakeEnsureClone | None = None,
) -> tuple[FakeSeeder, ProjectEntry]:
    """Run ``init`` with a fake seeder, an isolated root, an isolated clone, and a
    fake ``ensure_clone`` (so the test never shells to git)."""
    seeder = FakeSeeder()
    root = tmp_path / "kanban"
    clone = tmp_path / "clone"
    entry = init(
        repo,
        root=root,
        clone=clone,
        seeder=seeder,
        ensure_clone=ensure_clone or FakeEnsureClone(),
    )
    return seeder, entry


def test_init_creates_project_and_returns_entry(tmp_path: Path) -> None:
    """``init`` ensures a fresh project and returns its registry entry."""
    seeder, entry = _run_init(tmp_path)

    assert seeder.ensure_project_calls == [("IznoCorp", "demo")]
    assert entry.project_id == "PVT_NEW"
    assert entry.repo == "IznoCorp/demo"
    assert entry.status_field_node_id == "PVTSSF_STATUS"


def test_init_sets_default_project_short_description(tmp_path: Path) -> None:
    """``init`` sets the default one-line project description on the fresh board (phase-33)."""
    seeder, _ = _run_init(tmp_path)

    assert seeder.described == [
        (
            "PVT_NEW",
            "Kanban orchestrated by KanbanMate — autonomous Claude agents "
            "launched per transition (IznoCorp/demo)",
        )
    ]


def test_init_ensures_template_columns_as_status_options(tmp_path: Path) -> None:
    """The Status options come from the bundled ``columns.yml`` template, in board order."""
    seeder, _ = _run_init(tmp_path)

    assert len(seeder.ensure_columns_calls) == 1
    project_id, columns = seeder.ensure_columns_calls[0]
    assert project_id == "PVT_NEW"
    # The 14-column default template (genesis phase 26), by human-readable name in
    # order — ``Brainstorming`` (interactive) sits after ``Backlog`` and ``Plan``
    # (autonomous) after ``Spec``; ``Prepare feature`` (the create-branch stage)
    # sits between ``Ready to dev`` and ``In Progress``.
    assert columns == [
        "Backlog",
        "Brainstorming",
        "Spec",
        "Plan",
        "Planned",
        "Ready to dev",
        "Prepare feature",
        "In Progress",
        "PR/CI",
        "Review",
        "Merge",
        "Cancel",
        "Done",
        "Blocked",
    ]


def test_init_ensures_wave_and_prio_labels(tmp_path: Path) -> None:
    """``init`` ensures the ``wave:*``/``prio:*`` routing labels on the repo."""
    seeder, _ = _run_init(tmp_path)

    assert len(seeder.ensure_labels_calls) == 1
    repo, labels = seeder.ensure_labels_calls[0]
    assert repo == "IznoCorp/demo"
    assert all(label.startswith(("wave:", "prio:")) for label in labels)
    assert "wave:1" in labels and "prio:P1" in labels


def test_init_writes_columns_yml_into_clone(tmp_path: Path) -> None:
    """The template is copied into ``<clone>/.claude/kanban/columns.yml`` verbatim."""
    _run_init(tmp_path)

    written = tmp_path / "clone" / ".claude" / "kanban" / "columns.yml"
    assert written.exists()
    source = init_mod._engine_assets_template()
    assert written.read_text(encoding="utf-8") == source


def test_init_registers_project_keyed_by_node_id(tmp_path: Path) -> None:
    """``projects.json`` is written keyed by the project node id with the option map."""
    seeder, entry = _run_init(tmp_path)

    projects = tmp_path / "kanban" / "projects.json"
    assert projects.exists()
    data = json.loads(projects.read_text(encoding="utf-8"))
    assert set(data) == {"PVT_NEW"}
    record = data["PVT_NEW"]
    assert record["repo"] == "IznoCorp/demo"
    assert record["project_id"] == "PVT_NEW"
    assert record["status_field_node_id"] == "PVTSSF_STATUS"
    # Option map mirrors the ensured columns.
    assert record["option_map"]["Backlog"] == "opt_0"


def test_init_is_idempotent_on_rerun(tmp_path: Path) -> None:
    """Re-running ``init`` overwrites the same registry key in place (no duplication)."""
    seeder, _ = _run_init(tmp_path)
    # Second run with a fresh seeder returning the SAME project id.
    second = FakeSeeder(project_id="PVT_NEW")
    init(
        "IznoCorp/demo",
        root=tmp_path / "kanban",
        clone=tmp_path / "clone",
        seeder=second,
        ensure_clone=FakeEnsureClone(),
    )

    data = json.loads((tmp_path / "kanban" / "projects.json").read_text(encoding="utf-8"))
    assert set(data) == {"PVT_NEW"}, "re-run must not create a second registry entry"


def test_init_rejects_bad_repo_slug(tmp_path: Path) -> None:
    """A ``repo`` without a slash fails loud before any network call."""
    with pytest.raises(ValueError, match="owner/name"):
        init("not-a-slug", root=tmp_path / "kanban", clone=tmp_path / "clone", seeder=FakeSeeder())


def test_init_links_project_to_repo(tmp_path: Path) -> None:
    """``init`` links the created project to the target repo (repo↔project association)."""
    seeder, _entry = _run_init(tmp_path, repo="IznoCorp/demo")
    assert seeder.linked == [("PVT_NEW", "IznoCorp/demo")]


# ── phase 12.7: transitions.yml renderer + writer + init emit ──────────────


def test_render_transitions_yaml_roundtrips() -> None:
    """``render_transitions_yaml`` output round-trips through ``load_transitions``."""
    from kanbanmate.core.transitions import load_transitions
    from kanbanmate.core.transitions_defaults import DEFAULT_TRANSITIONS, render_transitions_yaml

    yaml_text = render_transitions_yaml("owner/repo")
    config = load_transitions(yaml_text)

    assert config.project == "owner/repo"
    assert config.concurrency_cap == 3
    assert config.move_rate_limit_per_hour == 10

    # Explicit pair: PrepareFeature → InProgress carries _IMPLEMENT_PROMPT.
    t = config.get("PrepareFeature", "InProgress")
    assert t is not None
    assert t.prompt is not None
    assert "/implement:phase" in t.prompt
    assert t.advance == "auto:PRCI"

    # Same destination, different origin: PRCI → InProgress carries _FIXCI_PROMPT.
    t2 = config.get("PRCI", "InProgress")
    assert t2 is not None
    assert t2.prompt is not None
    assert "/implement:phase" not in t2.prompt  # fix-CI, not implement

    # Allowed no-op: Planned → ReadyToDev has no action.
    t3 = config.get("Planned", "ReadyToDev")
    assert t3 is not None
    assert not t3.has_action

    # Unlisted pair → None (caller rolls back).
    assert config.get("Backlog", "Merge") is None

    # Wildcard: any → Blocked.
    t4 = config.get("Spec", "Blocked")
    assert t4 is not None

    # Wildcard: Blocked → any.
    t5 = config.get("Blocked", "InProgress")
    assert t5 is not None

    # Script transition: InProgress → PRCI is a script-only gate.
    t6 = config.get("InProgress", "PRCI")
    assert t6 is not None
    assert t6.script == "bin/check-pr-ready.sh"
    assert t6.prompt is None
    assert t6.on_fail == "move:InProgress"

    # Every DEFAULT_TRANSITIONS entry is reachable via get(). A list-valued
    # ``from``/``to`` (the skip-to-Done sugar) cartesian-expands into concrete
    # edges at load, so expand it here too before resolving each concrete pair.
    for entry in DEFAULT_TRANSITIONS:
        raw_from = entry.get("from", "")
        raw_to = entry.get("to", "")
        from_cols = raw_from if isinstance(raw_from, list) else [raw_from]
        to_cols = raw_to if isinstance(raw_to, list) else [raw_to]
        for from_col in from_cols:
            for to_col in to_cols:
                resolved = config.get(from_col, to_col)
                assert resolved is not None, f"({from_col!r}, {to_col!r}) not found"


def test_render_transitions_yaml_has_permission_mode_header() -> None:
    """The rendered YAML starts with the permission_mode documentation header."""
    from kanbanmate.core.transitions_defaults import render_transitions_yaml

    yaml_text = render_transitions_yaml("owner/repo")
    assert yaml_text.startswith("# permission_mode")
    assert "bypassPermissions is NOT allowed" in yaml_text
    assert "default | acceptEdits | auto | dontAsk | plan" in yaml_text


def test_write_transitions_yml_writes_file(tmp_path: Path) -> None:
    """``write_transitions_yml`` writes ``<clone>/.claude/kanban/transitions.yml``."""
    from kanbanmate.cli.init import write_transitions_yml

    clone = tmp_path / "clone"
    dest = write_transitions_yml(clone, "owner/repo")

    expected = clone / ".claude" / "kanban" / "transitions.yml"
    assert dest == expected
    assert expected.exists()
    content = expected.read_text(encoding="utf-8")
    assert content.startswith("# permission_mode")
    assert "owner/repo" in content


def test_write_transitions_yml_is_idempotent(tmp_path: Path) -> None:
    """Re-writing transitions.yml overwrites in place (no duplication, no error)."""
    from kanbanmate.cli.init import write_transitions_yml

    clone = tmp_path / "clone"
    first = write_transitions_yml(clone, "owner/repo")
    second = write_transitions_yml(clone, "owner/repo")

    assert first == second
    # Only one file in the kanban dir, not directory-bloat.
    parent = clone / ".claude" / "kanban"
    assert len(list(parent.iterdir())) == 1


def test_init_emits_transitions_yml_beside_columns_yml(tmp_path: Path) -> None:
    """``kanban init`` writes transitions.yml beside columns.yml in the clone."""
    seeder = FakeSeeder()
    root = tmp_path / "kanban"
    clone = tmp_path / "clone"
    init("IznoCorp/demo", root=root, clone=clone, seeder=seeder, ensure_clone=FakeEnsureClone())

    columns_yml = clone / ".claude" / "kanban" / "columns.yml"
    transitions_yml = clone / ".claude" / "kanban" / "transitions.yml"
    assert columns_yml.exists(), "columns.yml must exist after init"
    assert transitions_yml.exists(), "transitions.yml must exist after init"
    # transitions.yml carries the project slug (rendered, not a static copy).
    content = transitions_yml.read_text(encoding="utf-8")
    assert "IznoCorp/demo" in content


# ── phase 14.6: registry config_dir/dev_repo_path + init ensure_clone ──────────


def test_project_entry_roundtrips_config_dir_and_dev_repo_path(tmp_path: Path) -> None:
    """``config_dir`` + ``dev_repo_path`` round-trip through ``_upsert_project`` →
    ``_load_registry`` (``asdict`` serialises them; ``.get`` reads them back)."""
    path = tmp_path / "projects.json"
    entry = ProjectEntry(
        repo="IznoCorp/demo",
        clone="/tmp/clone",
        project_id="PVT_NEW",
        status_field_node_id="PVTSSF_x",
        config_dir="/tmp/clone/.claude",
        dev_repo_path="/home/dev/demo",
    )
    init_mod._upsert_project(path, "PVT_NEW", entry)

    loaded = init_mod._load_registry(path)
    assert loaded["PVT_NEW"].config_dir == "/tmp/clone/.claude"
    assert loaded["PVT_NEW"].dev_repo_path == "/home/dev/demo"


def test_load_registry_loads_old_shaped_entry_without_new_fields(tmp_path: Path) -> None:
    """An OLD-shaped ``projects.json`` (no ``config_dir``/``dev_repo_path`` keys) still loads,
    with the new fields defaulted to ``""`` (registry format stays backward-compatible)."""
    path = tmp_path / "projects.json"
    path.write_text(
        json.dumps(
            {
                "PVT_OLD": {
                    "repo": "IznoCorp/demo",
                    "clone": "/tmp/clone",
                    "project_id": "PVT_OLD",
                    "status_field_node_id": "PVTSSF_x",
                    "option_map": {"Backlog": "opt0"},
                    # NO config_dir / dev_repo_path keys — the pre-phase-14 shape.
                }
            }
        ),
        encoding="utf-8",
    )

    loaded = init_mod._load_registry(path)
    assert set(loaded) == {"PVT_OLD"}
    assert loaded["PVT_OLD"].config_dir == ""
    assert loaded["PVT_OLD"].dev_repo_path == ""


def test_init_persists_dev_repo_path(tmp_path: Path) -> None:
    """``init(..., dev_repo_path=...)`` persists the field on the entry + in projects.json."""
    seeder = FakeSeeder()
    entry = init(
        "IznoCorp/demo",
        root=tmp_path / "kanban",
        clone=tmp_path / "clone",
        seeder=seeder,
        dev_repo_path="/home/dev/demo",
        ensure_clone=FakeEnsureClone(),
    )

    assert entry.dev_repo_path == "/home/dev/demo"
    data = json.loads((tmp_path / "kanban" / "projects.json").read_text(encoding="utf-8"))
    assert data["PVT_NEW"]["dev_repo_path"] == "/home/dev/demo"


def test_init_defaults_config_dir_to_clone_dot_claude(tmp_path: Path) -> None:
    """``init`` defaults ``config_dir`` to ``<clone>/.claude`` when not overridden."""
    clone = tmp_path / "clone"
    _, entry = _run_init(tmp_path)

    assert entry.config_dir == str(clone / ".claude")


def test_init_runs_ensure_clone_before_columns_yml_with_tokenless_url(tmp_path: Path) -> None:
    """``init`` calls the injected ``ensure_clone`` with the TOKENLESS repo URL + the
    ``<root>/token`` token path, and does so BEFORE writing the clone's columns.yml."""
    root = tmp_path / "kanban"
    clone = tmp_path / "clone"
    columns_yml = clone / ".claude" / "kanban" / "columns.yml"
    fake = FakeEnsureClone(columns_path=columns_yml)

    init("IznoCorp/demo", root=root, clone=clone, seeder=FakeSeeder(), ensure_clone=fake)

    assert len(fake.calls) == 1, "ensure_clone runs exactly once at init"
    repo_url, kwargs = fake.calls[0]
    # TOKENLESS public URL — no x-access-token:<tok>@ embedded.
    assert repo_url == "https://github.com/IznoCorp/demo.git"
    # token_path is the 600-mode <root>/token so the credential helper is installed at init.
    assert kwargs["token_path"] == str(root / "token")
    assert kwargs["base"] == "main"
    # Call-order proof: columns.yml did NOT exist yet when ensure_clone fired (it is written
    # AFTER the bootstrap so the clone exists to write into).
    assert fake.columns_existed_at_call is False
    # And it does exist after init completes.
    assert columns_yml.exists()
