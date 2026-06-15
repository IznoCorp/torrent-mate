"""Tests for :mod:`kanbanmate.cli.seed` — the per-repo ``kanban seed`` (DESIGN §4.3).

A :class:`FakeSeeder` records every create/add/patch call and assigns issue numbers
in creation order, so the tests can assert: issues are created in dependency order,
each is added to the project, and ``Depends on RPx`` references are rewritten to the
real ``#N`` numbers. No test touches the network; ``tmp_path`` holds the roadmap.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kanbanmate.cli.seed import parse_roadmap, seed, topo_order
from kanbanmate.core.body_edit import roadmap_marker

_ROADMAP = """\
# Roadmap

## [RP1] Bootstrap dispatcher
wave: 1
prio: P1
depends: RP2

The dispatcher wires the daemon.

## [RP2] Polling core
wave: 1
prio: P1

The cheap-probe + snapshot loop.

## [RP3] Installer
wave: 2
prio: P2
depends: RP1, RP2

The three-tier install model.
"""


class FakeSeeder:
    """A recording :class:`~kanbanmate.ports.board.Seeder` that numbers issues in order."""

    def __init__(self) -> None:
        """Initialise empty call logs and a monotonic issue counter."""
        self.created: list[tuple[str, str, str, list[str]]] = []
        self.added: list[tuple[str, str]] = []
        self.placed: list[tuple[str, str]] = []
        self.body_patches: list[tuple[str, str]] = []
        self._counter = 0

    def ensure_project(self, org: str, title: str) -> str:  # pragma: no cover - unused by seed
        """Unused by seed."""
        raise AssertionError("seed must not create projects")

    def ensure_columns(
        self, project_id: str, columns: list[str]
    ) -> dict[str, str]:  # pragma: no cover
        """Unused by seed."""
        raise AssertionError("seed must not ensure columns")

    def ensure_labels(self, repo: str, labels: list[str]) -> dict[str, str]:  # pragma: no cover
        """Unused by seed (create_issue ensures labels internally on the real client)."""
        return {name: f"lbl_{name}" for name in labels}

    def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> tuple[str, int]:
        """Record the create and assign the next monotonic issue number."""
        self._counter += 1
        self.created.append((repo, title, body, list(labels)))
        return f"NODE_{self._counter}", self._counter

    def update_issue_body(self, issue_node_id: str, body: str) -> None:
        """Record the body patch (the Depends-on rewrite)."""
        self.body_patches.append((issue_node_id, body))

    def add_to_project(self, project_id: str, issue_node_id: str) -> str:
        """Record the add and return a canned item id."""
        self.added.append((project_id, issue_node_id))
        return f"PVTI_{len(self.added)}"

    def move_card(self, item_id: str, column_key: str) -> None:
        """Record the Status placement (seed sets each item to Backlog explicitly)."""
        self.placed.append((item_id, column_key))

    def link_to_repo(self, project_id: str, repo: str) -> None:  # pragma: no cover - unused by seed
        """Unused by seed (only ``init`` links the project); satisfies the Seeder protocol."""

    def update_project_description(  # pragma: no cover - unused by seed
        self, project_id: str, short_description: str
    ) -> None:
        """Unused by seed (only ``init`` sets the description); satisfies the Seeder protocol."""


class FakeSeederWithOptions(FakeSeeder):
    """A :class:`FakeSeeder` that ALSO exposes the live ``status_options`` probe (#3).

    The seed landing pre-check reads the project's Status options through a
    ``getattr``-optional ``status_options(project_id)`` capability; a bare
    :class:`FakeSeeder` does not expose it (the check is then skipped), so this
    subclass lets a test drive the option set the guard validates against.
    """

    def __init__(self, options: dict[str, str]) -> None:
        """Record the canned Status options the guard will probe."""
        super().__init__()
        self._options = dict(options)

    def status_options(self, project_id: str) -> dict[str, str]:
        """Return the canned ``{column_name: option_id}`` Status option map."""
        return dict(self._options)


def _write_roadmap(tmp_path: Path, text: str = _ROADMAP) -> Path:
    """Write the roadmap text to a temp file and return its path."""
    path = tmp_path / "ROADMAP.md"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Pure roadmap parsing + ordering
# ---------------------------------------------------------------------------


def test_parse_roadmap_extracts_items_and_metadata() -> None:
    """``parse_roadmap`` reads codes, titles, labels, and dependencies."""
    items = parse_roadmap(_ROADMAP)
    by_code = {it.code: it for it in items}

    assert set(by_code) == {"RP1", "RP2", "RP3"}
    assert by_code["RP1"].title == "[RP1] Bootstrap dispatcher"
    assert by_code["RP1"].labels == ["wave:1", "prio:P1"]
    assert by_code["RP1"].depends == ["RP2"]
    assert "Depends on RP2" in by_code["RP1"].body
    assert by_code["RP2"].depends == []


def test_topo_order_places_dependencies_first() -> None:
    """``topo_order`` returns dependencies before dependents."""
    ordered = [it.code for it in topo_order(parse_roadmap(_ROADMAP))]

    assert ordered.index("RP2") < ordered.index("RP1")
    assert ordered.index("RP1") < ordered.index("RP3")
    assert ordered.index("RP2") < ordered.index("RP3")


def test_topo_order_detects_cycle() -> None:
    """A dependency cycle fails loud."""
    text = "## [A] a\ndepends: B\n\n## [B] b\ndepends: A\n"
    with pytest.raises(ValueError, match="cycle"):
        topo_order(parse_roadmap(text))


def test_topo_order_detects_unknown_dependency() -> None:
    """A reference to a non-existent code fails loud."""
    text = "## [A] a\ndepends: ZZ\n"
    with pytest.raises(ValueError, match="unknown dependency 'ZZ'"):
        topo_order(parse_roadmap(text))


# ---------------------------------------------------------------------------
# seed() orchestration
# ---------------------------------------------------------------------------


def test_seed_creates_issues_in_dependency_order(tmp_path: Path) -> None:
    """Issues are created dependency-first (RP2 before RP1 before RP3)."""
    seeder = FakeSeeder()
    seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )

    created_titles = [title for (_repo, title, _body, _labels) in seeder.created]
    assert created_titles == [
        "[RP2] Polling core",
        "[RP1] Bootstrap dispatcher",
        "[RP3] Installer",
    ]


def test_seed_adds_each_issue_to_project(tmp_path: Path) -> None:
    """Every created issue is added to the project."""
    seeder = FakeSeeder()
    seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )

    assert len(seeder.added) == 3
    assert all(project_id == "PVT" for (project_id, _node) in seeder.added)
    # The node ids added match the creation order (NODE_1=RP2, NODE_2=RP1, NODE_3=RP3).
    assert [node for (_p, node) in seeder.added] == ["NODE_1", "NODE_2", "NODE_3"]


def test_seed_places_each_issue_in_backlog(tmp_path: Path) -> None:
    """Each added item is set to Backlog explicitly.

    Projects v2 adds items with NO Status (no "default column on add"), so the seed
    must set it per item — otherwise cards land in "No Status" and the daemon logs
    "unknown column ''" for each.
    """
    seeder = FakeSeeder()
    seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )

    assert len(seeder.placed) == 3
    assert all(column == "Backlog" for (_item, column) in seeder.placed)
    # The item id returned by add_to_project is the one placed in Backlog.
    assert [item for (item, _c) in seeder.placed] == ["PVTI_1", "PVTI_2", "PVTI_3"]


def test_seed_rewrites_depends_on_to_real_numbers(tmp_path: Path) -> None:
    """``Depends on RPx`` references are rewritten to real ``#N`` after creation."""
    seeder = FakeSeeder()
    seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )

    # Creation order: RP2=#1, RP1=#2, RP3=#3. Only RP1 and RP3 carry dependencies.
    patched = dict(seeder.body_patches)
    # RP1 depends on RP2 (#1).
    assert "Depends on #1" in patched["NODE_2"]
    assert "RP2" not in patched["NODE_2"].split("Depends on", 1)[1]
    # RP3 depends on RP1 (#2) and RP2 (#1).
    assert "Depends on #2, #1" in patched["NODE_3"]
    # RP2 has no dependencies -> no patch issued for it.
    assert "NODE_1" not in patched


def test_seed_returns_created_in_order(tmp_path: Path) -> None:
    """``seed`` returns the created issues in dependency order with their numbers."""
    seeder = FakeSeeder()
    created = seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )

    assert [(c.code, c.issue_number) for c in created] == [("RP2", 1), ("RP1", 2), ("RP3", 3)]


# ---------------------------------------------------------------------------
# §29.2 — durable **roadmap** marker + persisted code→issue map
# ---------------------------------------------------------------------------


def test_roadmap_marker_is_first_body_line_and_parser_compatible() -> None:
    """``_flush`` prepends ``**roadmap**: <CODE>`` as the FIRST body element (parser-visible)."""
    items = parse_roadmap(_ROADMAP)
    by_code = {it.code: it for it in items}
    # First line of each body is the roadmap marker (its own paragraph).
    assert by_code["RP1"].body.splitlines()[0] == "**roadmap**: RP1"
    assert by_code["RP2"].body.splitlines()[0] == "**roadmap**: RP2"
    # The ticket_fields regex recovers the codename-style marker… here the roadmap value.
    assert "RP1" == roadmap_marker(by_code["RP1"].body)
    # The Depends-on line is preserved byte-identical (so _rewrite_depends still matches).
    assert "Depends on RP2" in by_code["RP1"].body


def test_seed_rewrites_depends_with_marker_present(tmp_path: Path) -> None:
    """With the marker prepended, the Depends-on rewrite still produces ``#N`` references."""
    seeder = FakeSeeder()
    seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )
    patched = dict(seeder.body_patches)
    # RP1 depends on RP2 (#1); the marker line coexists with the rewritten Depends-on.
    assert "**roadmap**: RP1" in patched["NODE_2"]
    assert "Depends on #1" in patched["NODE_2"]


def test_seed_writes_code_to_issue_map(tmp_path: Path) -> None:
    """``seed`` persists ``<root>/seed-map/<owner>-<repo>.json`` with the code→issue mapping."""
    seeder = FakeSeeder()
    seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )

    map_path = tmp_path / "seed-map" / "IznoCorp-demo.json"
    assert map_path.is_file()
    payload = json.loads(map_path.read_text(encoding="utf-8"))
    assert payload["repo"] == "IznoCorp/demo"
    # Creation order: RP2=#1, RP1=#2, RP3=#3.
    assert payload["issues"]["RP2"]["issue_number"] == 1
    assert payload["issues"]["RP1"]["issue_number"] == 2
    assert payload["issues"]["RP3"]["issue_number"] == 3
    assert payload["issues"]["RP2"]["issue_node_id"] == "NODE_1"


# ---------------------------------------------------------------------------
# #12 — registry auto-resolve of --project-id (PoC init→seed handoff)
# ---------------------------------------------------------------------------


def _write_registry(root: Path, repo: str, project_id: str = "PVT_registered") -> None:
    """Write a minimal ``projects.json`` registering ``repo`` under ``project_id``."""
    entry = {
        "repo": repo,
        "clone": str(root / "clone"),
        "project_id": project_id,
        "status_field_node_id": "FIELD_x",
        "option_map": {"Backlog": "opt1"},
        "config_dir": "",
        "dev_repo_path": "",
    }
    (root / "projects.json").write_text(json.dumps({project_id: entry}), encoding="utf-8")


def test_seed_resolves_project_id_from_registry_when_omitted(tmp_path: Path) -> None:
    """#12: with no ``--project-id``, the project node id is resolved from ``projects.json`` by repo."""
    _write_registry(tmp_path, repo="IznoCorp/demo", project_id="PVT_registered")
    seeder = FakeSeeder()

    seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id=None,  # omitted → registry resolve
        root=tmp_path,
        seeder=seeder,
    )

    # Every issue was added under the project id resolved from the registry.
    assert seeder.added, "no issues were added"
    assert all(project_id == "PVT_registered" for (project_id, _node) in seeder.added)


def test_seed_errors_run_init_first_when_repo_unregistered(tmp_path: Path) -> None:
    """#12: an unregistered repo (no ``--project-id``) fails loud with the run-init-first message."""
    # No projects.json written → the repo is unregistered.
    seeder = FakeSeeder()

    with pytest.raises(
        ValueError, match=r"no project registered for IznoCorp/demo — run `kanban init` first"
    ):
        seed(
            _write_roadmap(tmp_path),
            repo="IznoCorp/demo",
            project_id=None,
            root=tmp_path,
            seeder=seeder,
        )
    # Fails BEFORE creating any issue (clean, not mid-seed).
    assert seeder.created == []


def test_seed_explicit_project_id_overrides_registry(tmp_path: Path) -> None:
    """#12: an explicit ``--project-id`` wins over the registry (the override is preserved)."""
    # Registry maps the repo to PVT_registered, but the caller passes an explicit override.
    _write_registry(tmp_path, repo="IznoCorp/demo", project_id="PVT_registered")
    seeder = FakeSeeder()

    seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT_explicit",  # explicit override
        root=tmp_path,
        seeder=seeder,
    )

    # The explicit id is used, NOT the registered one.
    assert all(project_id == "PVT_explicit" for (project_id, _node) in seeder.added)


# ---------------------------------------------------------------------------
# #3 — landing-column ("Backlog") pre-check (PoC parity, no half-seed)
# ---------------------------------------------------------------------------


def test_seed_fails_clean_when_backlog_option_missing(tmp_path: Path) -> None:
    """#3: a project whose Status field lacks 'Backlog' fails BEFORE any issue is created.

    Without the up-front guard the seed would create issue 1, then crash on its
    ``move_card(item, "Backlog")`` — a half-seed leaving orphaned issues. The guard reads
    the live ``status_options`` probe, finds no 'Backlog' option, and fails clean.
    """
    seeder = FakeSeederWithOptions({"Todo": "opt_todo", "Done": "opt_done"})  # no Backlog

    with pytest.raises(ValueError, match=r"has no 'Backlog' Status option"):
        seed(
            _write_roadmap(tmp_path),
            repo="IznoCorp/demo",
            project_id="PVT",
            root=tmp_path,
            seeder=seeder,
        )

    # Fails BEFORE creating / adding / placing any issue (clean, not mid-seed).
    assert seeder.created == []
    assert seeder.added == []
    assert seeder.placed == []


def test_seed_proceeds_when_backlog_option_present(tmp_path: Path) -> None:
    """#3: a project whose Status field has 'Backlog' seeds normally (the guard passes)."""
    seeder = FakeSeederWithOptions({"Backlog": "opt_backlog", "Done": "opt_done"})

    created = seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )

    # All three issues created + each placed in Backlog (the guard did not block).
    assert len(created) == 3
    assert all(column == "Backlog" for (_item, column) in seeder.placed)


def test_seed_skips_landing_check_without_options(tmp_path: Path) -> None:
    """#3 back-compat: a bare Seeder (no ``status_options``, explicit --project-id) is not blocked.

    When neither a live probe nor a registry ``option_map`` can name the options, the
    pre-check cannot decide and is skipped — exactly the pre-guard behaviour.
    """
    seeder = FakeSeeder()  # no status_options capability

    created = seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT",
        root=tmp_path,
        seeder=seeder,
    )

    assert len(created) == 3  # the seed ran (the check was skipped, not failed)


def test_seed_landing_check_uses_registry_option_map(tmp_path: Path) -> None:
    """#3: the registry ``option_map`` is the fallback source when no live probe exists.

    The PoC's source of truth for the landing option was ``entry.option_map`` recorded by
    ``kanban init``; a registry entry WITHOUT 'Backlog' must fail clean even with a bare fake.
    """
    # Registry entry whose option_map lacks Backlog.
    entry = {
        "repo": "IznoCorp/demo",
        "clone": str(tmp_path / "clone"),
        "project_id": "PVT_registered",
        "status_field_node_id": "FIELD_x",
        "option_map": {"Todo": "opt_todo"},  # no Backlog
        "config_dir": "",
        "dev_repo_path": "",
    }
    (tmp_path / "projects.json").write_text(json.dumps({"PVT_registered": entry}), encoding="utf-8")
    seeder = FakeSeeder()  # no live probe → falls back to the registry option_map

    with pytest.raises(ValueError, match=r"has no 'Backlog' Status option"):
        seed(
            _write_roadmap(tmp_path),
            repo="IznoCorp/demo",
            project_id=None,  # registry resolve → entry.option_map consulted
            root=tmp_path,
            seeder=seeder,
        )
    assert seeder.created == []


def test_seed_explicit_project_id_path_is_guarded_no_half_seed(tmp_path: Path) -> None:
    """#3 regression-vs-PoC: the explicit ``--project-id`` path is now guarded (no half-seed).

    On the explicit ``--project-id`` override NO registry entry is resolved, so the
    registry ``option_map`` fallback is unavailable — the guard relies SOLELY on the
    live ``status_options`` probe. In production that probe resolves because the real
    ``GithubClient`` now exposes ``status_options`` (phase 19.2). With a board lacking
    'Backlog' the seed must fail clean BEFORE any ``create_issue`` — closing the
    previously-unguarded ``--project-id`` half-seed path the PoC never had.
    """
    seeder = FakeSeederWithOptions({"Todo": "opt_todo", "Done": "opt_done"})  # no Backlog

    with pytest.raises(ValueError, match=r"has no 'Backlog' Status option"):
        seed(
            _write_roadmap(tmp_path),
            repo="IznoCorp/demo",
            project_id="PVT_explicit",  # explicit override → NO registry lookup at all
            seeder=seeder,
        )

    # Guard fired up front: not a single issue was created/added/placed (no half-seed).
    assert seeder.created == []
    assert seeder.added == []
    assert seeder.placed == []


def test_seed_explicit_project_id_path_proceeds_when_backlog_present(tmp_path: Path) -> None:
    """#3 companion: the same explicit ``--project-id`` path seeds normally when 'Backlog' exists."""
    seeder = FakeSeederWithOptions({"Backlog": "opt_backlog", "Done": "opt_done"})

    created = seed(
        _write_roadmap(tmp_path),
        repo="IznoCorp/demo",
        project_id="PVT_explicit",  # explicit override → NO registry lookup at all
        seeder=seeder,
    )

    # The guard passed: all three issues created and each placed in Backlog.
    assert len(created) == 3
    assert all(column == "Backlog" for (_item, column) in seeder.placed)
