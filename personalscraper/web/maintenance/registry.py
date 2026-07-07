"""Maintenance action registry — typed models for the 25 ``library-*`` CLI commands.

Each :class:`MaintenanceAction` entry models a single Typer-registered
``library-*`` command with its risk classification, dry-run capability,
long-running flag, and curated targeting options for the S3 web UI.

Category mapping (from module to registry category):

* ``query.py`` (status/search/show) → ``"query"``
* ``scan.py`` (index/init-canonical/scan/backfill-ids) → ``"scan"``
* ``maintenance.py`` (verify/repair) → ``"repair"``
* ``maintenance.py`` (clean/validate) → ``"clean"``
* ``analyze.py`` (analyze/recommend/rescrape/report) → ``"analyze"``
* ``audit.py`` (reconcile/ghost-audit/relink) → ``"fix"`` (reconcile and relink
  are mutating repairs; ghost-audit is ro diagnostics mapped to ``"query"``)
* ``doctor.py`` → ``"query"`` (read-only health diagnostics)
* ``gc.py`` → ``"fix"`` (mutating cleanup of ``index_outbox``)
* ``fix_canonical_provider.py`` → ``"fix"``
* ``fix_nfo.py`` → ``"fix"``
* ``fix_orphan_files.py`` → ``"fix"``
* ``fix_season_counts.py`` → ``"fix"``
* ``dedup_titles.py`` → ``"fix"``
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ActionOption(BaseModel):
    """A single targeting option for a maintenance action.

    Models one CLI flag or positional argument. The ``type`` field drives
    the form control rendered in the web UI (text input, number input,
    checkbox, or dropdown). Enum values are the valid choices for a
    ``select`` / dropdown control.

    Attributes:
        name: CLI-facing name (flag name without leading dashes, or
            positional arg name). Used as the JSON key in ``options_json``.
        type: Form-control type — ``"str"`` for text, ``"int"`` for number,
            ``"bool"`` for checkbox, ``"enum"`` for dropdown.
        enum_values: Valid choices when ``type="enum"``. ``None`` otherwise.
        default: Default value matching the CLI default. ``None`` when the
            CLI has no default (optional flags) or when the value is a
            required positional.
        required: ``True`` for mandatory positional arguments (e.g.
            ``library-search``'s ``query``). ``False`` for optional flags.
        label: French label for the web UI form field.
        help: French help text / placeholder for the web UI form field.
    """

    name: str
    type: Literal["str", "int", "bool", "enum"]
    enum_values: list[str] | None = None
    default: str | int | bool | None = None
    required: bool = False
    label: str
    help: str


class MaintenanceAction(BaseModel):
    """A single maintenance action backed by a ``library-*`` CLI command.

    Each entry in :data:`REGISTRY` maps 1:1 to a Typer-registered
    ``library-*`` command. The web UI reads the registry to render the
    action panels and the ``POST /api/maintenance/run`` endpoint uses it
    to validate incoming requests and build the subprocess invocation.

    Attributes:
        id: Kebab-case CLI command name (e.g. ``"library-index"``).
        title: Short French label for the web UI action card / button.
        description: One-line French description of what the command does.
        category: UI grouping — ``"query"`` (read-only info), ``"scan"``
            (indexer scans), ``"repair"`` (repair-queue based fixes),
            ``"clean"`` (filesystem cleanup), ``"analyze"`` (insights),
            ``"fix"`` (targeted DB/filesystem repairs).
        risk: Write-impact classification — ``"ro"`` (read-only, safe to
            run anytime), ``"write"`` (mutates DB or filesystem but is
            reversible / non-destructive), ``"destructive"`` (deletes files,
            drops rows, or truncates data — needs confirmation UI).
        long_running: ``True`` when the command walks disks, makes network
            calls, or processes the full library. The web UI uses this to
            route execution through the S2 subprocess + lock path and show
            a progress indicator.
        dry_run: ``"supported"`` when the CLI exposes ``--dry-run`` or an
            ``--apply`` flag whose absence means dry-run. ``"unsupported"``
            otherwise. The web UI sends ``dry_run`` separately; this field
            tells it whether to show the toggle.
        options: Curated list of high-value targeting flags/arguments.
            Plumbing flags (``--config``, ``--db``, ``--wait-for-lock``,
            ``--confirm-bulk-change``, ``--list-checks``, ``--export``,
            ``--backfill-streams``, ``--rebuild``, ``--no-enqueue``,
            ``--interactive``, ``--read-only``, ``--enqueue-repairs``,
            ``--clean-fk-orphans``, ``--purge-unrecoverable``,
            ``--purge-release-orphans``, ``--from-index``, ``--fix``) are
            excluded — the web layer handles them separately or they are
            irrelevant outside a terminal.
    """

    id: str
    title: str
    description: str
    category: Literal["query", "scan", "repair", "clean", "analyze", "fix"]
    risk: Literal["ro", "write", "destructive"]
    long_running: bool
    dry_run: Literal["unsupported", "supported"]
    options: list[ActionOption]


# ---------------------------------------------------------------------------
# Registry — 25 library-* commands registered on the Typer app.
# Ground truth: @app.command decorators in personalscraper/commands/library/*.py
# (NOT __all__, which is stale at 23 entries).
# ---------------------------------------------------------------------------

REGISTRY: list[MaintenanceAction] = []
