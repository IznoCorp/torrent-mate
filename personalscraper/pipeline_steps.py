"""Pipeline step adapters and default registry.

Each adapter class wraps a domain-level ``run_*`` function so that the
pipeline orchestrator can call every step through the uniform
:class:`PipelineStep` protocol.  The lazy imports inside ``__call__``
avoid pulling in the entire project at module-load time.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from personalscraper.models import StepReport
from personalscraper.pipeline_protocol import PipelineStep, StepContext
from personalscraper.reports import (
    STEP_REPORT_CONTRACT,
    CleanDetails,
    CleanupDetails,
    DispatchDetails,
    EnforceDetails,
    IngestDetails,
    ScrapeDetails,
    SortDetails,
    TrailersDetails,
    VerifyDetails,
)

if TYPE_CHECKING:
    from personalscraper.core.delete_permit import DeletePermit, SeedObligationRecorder


class DispatchAuthorityKW(TypedDict, total=False):
    """Resolved delete-permit kwargs forwarded to ``run_dispatch``.

    Empty when no acquire ``delete_authority`` is configured, so
    ``run_dispatch``'s library-level ``AllowAllPermit`` defaults apply.
    """

    permit: DeletePermit
    recorder: SeedObligationRecorder


def resolve_dispatch_authority(app: Any) -> DispatchAuthorityKW:  # noqa: ANN401
    """Resolve the delete permit + seed-obligation recorder for a dispatch call.

    Single owner of the acquire→dispatch injection so BOTH the full-run
    :class:`DispatchStep` and the standalone ``personalscraper dispatch`` CLI
    command forward the SAME ``permit``/``recorder`` to
    :func:`~personalscraper.dispatch.run.run_dispatch`. Reads the borrowed
    ``DeleteAuthority`` off ``app.acquire.delete_authority`` by duck-typing — the
    engine never imports ``acquire/`` (layering rule, DESIGN §9). When no
    authority is configured the mapping is empty, so ``run_dispatch``'s
    library-level ``AllowAllPermit`` defaults apply — byte-identical to the
    pre-resolution behaviour tests rely on.

    Args:
        app: The process-scoped :class:`~personalscraper.core.app_context.AppContext`
            (or any object exposing ``acquire.delete_authority``).

    Returns:
        ``{"permit": authority, "recorder": authority}`` when an authority is
        configured, else an empty mapping.
    """
    acquire = getattr(app, "acquire", None)
    authority = getattr(acquire, "delete_authority", None)
    if authority is None:
        return {}
    return {"permit": authority, "recorder": authority}


class IngestStep:
    """Adapter for the ingest step (``personalscraper.ingest.ingest.run_ingest``)."""

    name = "ingest"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the ingest step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` summarising copied, skipped, and failed torrents.
        """
        from personalscraper.ingest.ingest import run_ingest

        # Inject the seed-obligation checker (fail-safe copy-vs-move, §7 HnR)
        # from the acquire context via the core port — ingest never imports
        # acquire/ (layering rule). None ⇒ ingest relies on the live seeding
        # probe alone (byte-identical to the pre-E4 behaviour).
        acquire = getattr(ctx.app, "acquire", None)
        seed_checker = getattr(acquire, "delete_authority", None)

        return run_ingest(
            ctx.app.settings,
            dry_run=ctx.dry_run,
            config=ctx.app.config,
            event_bus=ctx.app.event_bus,
            torrent_client=ctx.app.torrent_client,
            seed_checker=seed_checker,
            # Boot's _recover_from_previous_run owns the once-per-run orphan
            # sweep (PIPELINE-CORE-07) — don't sweep again here.
            recover_orphans=False,
        )


class SortStep:
    """Adapter for the sort step (``personalscraper.sorter.run.run_sort``)."""

    name = "sort"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the sort step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` with per-item sort outcomes.
        """
        from personalscraper.sorter.run import run_sort

        # Pass the torrent client only when the opt-in seed-pure sort guard is
        # enabled; otherwise leave it None so run_sort never queries the client.
        sort_cfg = getattr(ctx.app.config, "sort", None)
        torrent_client = ctx.app.torrent_client if sort_cfg is not None and sort_cfg.verify_seed_pure else None

        return run_sort(
            ctx.app.settings,
            staging_dir=ctx.app.config.paths.staging_dir,
            dry_run=ctx.dry_run,
            config=ctx.app.config,
            event_bus=ctx.app.event_bus,
            torrent_client=torrent_client,
        )


class CleanStep:
    """Adapter for the clean process sub-step (``personalscraper.process.run.run_clean``)."""

    name = "clean"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the clean sub-step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` with per-item cleaning outcomes.
        """
        from personalscraper.process.run import run_clean

        return run_clean(
            ctx.app.settings,
            dry_run=ctx.dry_run,
            config=ctx.app.config,
            event_bus=ctx.app.event_bus,
        )


class ScrapeStep:
    """Adapter for the scrape step (``personalscraper.scraper.run.run_scrape``).

    The pipeline boot sequence (sub-phase 1.1) parks the
    :class:`ProviderRegistry` instance under ``ctx.extras["registry"]`` so each
    step adapter that needs it can pick it up without widening
    :class:`AppContext` (the boundary-only rule keeps the bundle minimal —
    DESIGN §Architecture).
    """

    name = "scrape"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the scrape step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` with per-item scrape outcomes and confidence scores.

        Raises:
            RuntimeError: If ``ctx.extras["registry"]`` is missing. The
                Pipeline always seeds it (see ``Pipeline.run``); a missing
                entry is a wiring bug, not a recoverable runtime condition.
        """
        from personalscraper.scraper.run import run_scrape

        registry = ctx.extras.get("registry")
        if registry is None:
            raise RuntimeError(
                "ScrapeStep requires a ProviderRegistry in ctx.extras['registry']. "
                "Pipeline.run seeds it at boot; running the step adapter outside the "
                "Pipeline must provide it explicitly."
            )

        return run_scrape(
            ctx.app.settings,
            config=ctx.app.config,
            dry_run=ctx.dry_run,
            interactive=ctx.interactive,
            event_bus=ctx.app.event_bus,
            registry=registry,
        )


class CleanupStep:
    """Adapter for the cleanup process sub-step (``personalscraper.process.run.run_cleanup``)."""

    name = "cleanup"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the cleanup sub-step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` with per-item cleanup outcomes.
        """
        from personalscraper.process.run import run_cleanup

        return run_cleanup(
            ctx.app.settings,
            dry_run=ctx.dry_run,
            config=ctx.app.config,
            event_bus=ctx.app.event_bus,
        )


class EnforceStep:
    """Adapter for the enforce step (``personalscraper.enforce.run.run_enforce``)."""

    name = "enforce"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the enforce step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` with enforcement outcomes (structure, naming, coherence).
        """
        from personalscraper.enforce.run import run_enforce

        return run_enforce(ctx.app.settings, ctx.app.config, dry_run=ctx.dry_run, event_bus=ctx.app.event_bus)


class VerifyStep:
    """Adapter for the verify step (``personalscraper.verify.run.run_verify``).

    Returns a ``(StepReport, verified_paths)`` tuple so the pipeline
    can forward the verified-path list to downstream steps (trailers).
    """

    name = "verify"

    def __call__(self, ctx: StepContext) -> tuple[StepReport, Any]:
        """Execute the verify step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``(StepReport, list[Path])`` tuple of verification results
            and the list of verified media paths.
        """
        from personalscraper.verify.run import run_verify

        return run_verify(
            ctx.app.settings,
            ctx.app.config,
            dry_run=ctx.dry_run,
            fix=False,
            event_bus=ctx.app.event_bus,
        )


class TrailersStep:
    """Adapter for the trailers step (``personalscraper.trailers.step.run_trailers``).

    The :class:`ProviderRegistry` is forwarded from ``ctx.app.provider_registry``
    so the orchestrator's ``VideoProvider`` resolution shares the
    process-scoped registry (feat/registry §5.2 / sub-phase 3.1).
    """

    name = "trailers"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the trailers step.

        Args:
            ctx: Pipeline step context with config, flags, and extras
                (``verified`` paths, ``skip_trailers`` toggle).

        Returns:
            A ``StepReport`` with per-item trailer download outcomes.
        """
        from personalscraper.trailers.step import run_trailers

        return run_trailers(
            ctx.app.config,
            staging_dir=ctx.app.config.paths.staging_dir,
            verified=ctx.extras.get("verified", []),
            skip_trailers=bool(ctx.extras.get("skip_trailers", False)),
            event_bus=ctx.app.event_bus,
            registry=ctx.app.provider_registry,
        )


class DispatchStep:
    """Adapter for the dispatch step (``personalscraper.dispatch.run.run_dispatch``)."""

    name = "dispatch"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the dispatch step.

        Args:
            ctx: Pipeline step context with config, settings, and extras
                (``verified`` paths for trailer-aware placement).

        Returns:
            A ``StepReport`` with per-item move/merge/replace outcomes.
        """
        from personalscraper.dispatch.run import run_dispatch

        # Permit/recorder resolution is the shared single owner (F2 parity with
        # the standalone ``personalscraper dispatch`` CLI command).
        report, results = run_dispatch(
            ctx.app.settings,
            config=ctx.app.config,
            dry_run=ctx.dry_run,
            verified=ctx.extras.get("verified"),
            event_bus=ctx.app.event_bus,
            # Boot's _recover_from_previous_run owns the once-per-run orphan
            # sweep (PIPELINE-CORE-07) — don't sweep again here.
            recover_orphans=False,
            **resolve_dispatch_authority(ctx.app),
        )

        # Post-dispatch index maintenance (DESIGN index-sync) is triggered
        # through the single owner shared with the standalone
        # ``personalscraper dispatch`` CLI command (PIPELINE-CORE-01): the
        # enablement resolution, touched-disk collection, and dry-run guard live
        # in one place so both entry points behave identically.
        from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

        maybe_run_post_dispatch_maintenance(
            ctx.app.config,
            results,
            dry_run=ctx.dry_run,
            no_post_maintenance=bool(ctx.extras.get("no_post_maintenance", False)),
        )

        return report


class LegacyCallableStep:
    """Adapter that preserves the historical ``step_overrides`` callable API.

    Wraps a bare callable (old-style override) so it can be called through
    the :class:`PipelineStep` protocol with a :class:`StepContext`.  Each
    known step name unpacks the context into the positional signature that
    the legacy function expects.
    """

    def __init__(self, name: str, fn: Callable[..., Any]) -> None:
        """Initialize the legacy adapter.

        Args:
            name: Step name matching a key in ``DEFAULT_STEPS``.
            fn: Legacy callable with a step-specific positional signature.
        """
        self.name = name
        self._fn = fn

    def __call__(self, ctx: StepContext) -> Any:  # noqa: ANN401
        """Execute the legacy step, unpacking context to positional args.

        Args:
            ctx: Pipeline step context.

        Returns:
            The return value of the wrapped legacy callable.
        """
        if self.name == "ingest":
            return self._fn(
                ctx.app.settings,
                dry_run=ctx.dry_run,
                config=ctx.app.config,
                event_bus=ctx.app.event_bus,
                torrent_client=ctx.app.torrent_client,
            )
        if self.name == "sort":
            return self._fn(
                ctx.app.settings,
                staging_dir=ctx.app.config.paths.staging_dir,
                dry_run=ctx.dry_run,
                config=ctx.app.config,
                event_bus=ctx.app.event_bus,
            )
        if self.name in {"clean", "cleanup"}:
            return self._fn(
                ctx.app.settings,
                dry_run=ctx.dry_run,
                config=ctx.app.config,
                event_bus=ctx.app.event_bus,
            )
        if self.name == "scrape":
            return self._fn(
                ctx.app.settings,
                config=ctx.app.config,
                dry_run=ctx.dry_run,
                interactive=ctx.interactive,
                event_bus=ctx.app.event_bus,
            )
        if self.name == "enforce":
            return self._fn(
                ctx.app.settings,
                ctx.app.config,
                dry_run=ctx.dry_run,
                event_bus=ctx.app.event_bus,
            )
        if self.name == "verify":
            return self._fn(
                ctx.app.settings,
                ctx.app.config,
                dry_run=ctx.dry_run,
                fix=False,
                event_bus=ctx.app.event_bus,
            )
        if self.name == "trailers":
            return self._fn(
                ctx.app.config,
                staging_dir=ctx.app.config.paths.staging_dir,
                verified=ctx.extras.get("verified", []),
                skip_trailers=bool(ctx.extras.get("skip_trailers", False)),
                event_bus=ctx.app.event_bus,
                registry=ctx.app.provider_registry,
            )
        if self.name == "dispatch":
            return self._fn(
                ctx.app.settings,
                config=ctx.app.config,
                dry_run=ctx.dry_run,
                verified=ctx.extras.get("verified"),
                event_bus=ctx.app.event_bus,
            )
        return self._fn(ctx)


DEFAULT_STEPS: dict[str, PipelineStep] = {
    "ingest": IngestStep(),
    "sort": SortStep(),
    "clean": CleanStep(),
    "scrape": ScrapeStep(),
    "cleanup": CleanupStep(),
    "enforce": EnforceStep(),
    "verify": VerifyStep(),
    "trailers": TrailersStep(),
    "dispatch": DispatchStep(),
}


class StepSpecError(Exception):
    """Raised at import when :data:`STEP_SPECS` disagrees with its sources of truth.

    The spec list is validated against the step registry (:data:`DEFAULT_STEPS`)
    and the typed report contract (:data:`STEP_REPORT_CONTRACT`). Agreement with
    the web stage catalog (``STEP_TO_STAGE``) is enforced at test tier — the
    engine must never import ``personalscraper.web`` (layering rule, DESIGN §9).
    A drift — a typo'd step name, a wrong payload type, a spec/registry mismatch
    — fails loud at module load rather than at the first pipeline run.
    """


@dataclass(frozen=True)
class StepSkip:
    """A skip predicate paired with the operator-facing reason it reports.

    ``StepSpec.skip_when`` is typed as a plain ``Callable[[StepContext], bool]``;
    this small wrapper lets a spec carry the human reason surfaced in the
    synthesised skip report (``StepReport.details``) alongside the boolean
    predicate. The reason therefore travels WITH the spec (open/closed: adding a
    skippable step touches only its spec entry) instead of being special-cased
    in the orchestrator. The instance is itself callable and returns the
    predicate's verdict, so it satisfies the ``skip_when`` field type.

    Attributes:
        predicate: Returns True when the step must be skipped for this run.
        reason: Operator-facing phrase recorded as ``"Skipped: {reason}"``.
    """

    predicate: Callable[[StepContext], bool]
    reason: str

    def __call__(self, ctx: StepContext) -> bool:
        """Return the predicate's verdict for *ctx* (skip when True)."""
        return self.predicate(ctx)


@dataclass(frozen=True)
class StepSpec:
    """Declarative specification of one pipeline step.

    ``Pipeline.run()`` iterates :data:`STEP_SPECS` and drives each step purely
    from its spec — no per-step branching in the orchestrator. Adding a
    hypothetical step touches ONLY three seams: its adapter class, one entry
    here, and its ``reports/*Details`` dataclass (the operator-owned web stage
    catalog gains the matching key separately).

    Attributes:
        name: Step identifier; must be a key of :data:`DEFAULT_STEPS`, of
            :data:`STEP_REPORT_CONTRACT`, and of the web stage catalog.
        adapter: The default adapter instance bound to this step (identical to
            ``DEFAULT_STEPS[name]``; per-run overrides are resolved separately
            by :func:`apply_step_overrides`).
        critical: When True, a fatal crash aborts the whole pipeline (the
            downstream steps depend on this step's output — ingest, sort).
        extras_key: When set, the step's extra return value is stored under this
            key in the shared ``extras`` mapping for downstream steps (``verify``
            exposes its verified-path list as ``"verified"``).
        skip_when: Optional predicate; when it returns True the orchestrator
            synthesises a symmetric skip report through the normal step path
            instead of invoking the adapter (dispatch skips when nothing passed
            verify). A :class:`StepSkip` also carries the reported reason.
        payload_type: The typed ``reports.*Details`` dataclass declared for this
            step in :data:`STEP_REPORT_CONTRACT`.
    """

    name: str
    adapter: PipelineStep
    critical: bool = False
    extras_key: str | None = None
    skip_when: Callable[[StepContext], bool] | None = None
    payload_type: type | None = None


def _no_verified_items(ctx: StepContext) -> bool:
    """Return True when verify produced no dispatchable items.

    Drives the dispatch step's ``skip_when``: with an empty ``verified`` list
    the move phase has nothing to place, so the step is skipped (the old inline
    ``Pipeline.run`` no-verified-items synthesis, now declarative).

    Args:
        ctx: The dispatch step's context; reads ``extras['verified']``.

    Returns:
        True when there are no verified items to dispatch.
    """
    return not ctx.extras.get("verified")


#: Ordered pipeline step specifications — the single declarative driver for
#: ``Pipeline.run()``. Order mirrors :data:`DEFAULT_STEPS` (INGEST → SORT →
#: CLEAN → SCRAPE → CLEANUP → ENFORCE → VERIFY → TRAILERS → DISPATCH) and is
#: asserted against it at import.
STEP_SPECS: tuple[StepSpec, ...] = (
    StepSpec("ingest", DEFAULT_STEPS["ingest"], critical=True, payload_type=IngestDetails),
    StepSpec("sort", DEFAULT_STEPS["sort"], critical=True, payload_type=SortDetails),
    StepSpec("clean", DEFAULT_STEPS["clean"], payload_type=CleanDetails),
    StepSpec("scrape", DEFAULT_STEPS["scrape"], payload_type=ScrapeDetails),
    StepSpec("cleanup", DEFAULT_STEPS["cleanup"], payload_type=CleanupDetails),
    StepSpec("enforce", DEFAULT_STEPS["enforce"], payload_type=EnforceDetails),
    StepSpec("verify", DEFAULT_STEPS["verify"], extras_key="verified", payload_type=VerifyDetails),
    StepSpec("trailers", DEFAULT_STEPS["trailers"], payload_type=TrailersDetails),
    StepSpec(
        "dispatch",
        DEFAULT_STEPS["dispatch"],
        skip_when=StepSkip(predicate=_no_verified_items, reason="no verified items"),
        payload_type=DispatchDetails,
    ),
)


def _validate_step_specs(
    specs: Sequence[StepSpec],
    steps: Mapping[str, PipelineStep],
    contract: Mapping[str, type],
) -> None:
    """Validate :data:`STEP_SPECS` against its two engine-internal sources of truth.

    Invoked once at import so a malformed spec list fails loud at module load.
    Checks: no duplicate names; the spec order/set equals the step registry;
    every spec name is in the typed report contract; the declared
    ``payload_type`` matches the contract; the ``adapter`` is the registry's.

    Agreement with the web stage catalog (``STEP_TO_STAGE``) is enforced at
    test tier, not at import time — the engine must never import
    ``personalscraper.web`` (layering rule, DESIGN §9).

    Args:
        specs: The ordered spec list (normally :data:`STEP_SPECS`).
        steps: The step registry (normally :data:`DEFAULT_STEPS`).
        contract: The typed report contract (:data:`STEP_REPORT_CONTRACT`).

    Raises:
        StepSpecError: On any disagreement between the sources.
    """
    names = [spec.name for spec in specs]
    if len(names) != len(set(names)):
        raise StepSpecError(f"STEP_SPECS has duplicate step names: {names}")
    if names != list(steps):
        raise StepSpecError(f"STEP_SPECS must mirror DEFAULT_STEPS order/set: specs={names}, registry={list(steps)}")
    for spec in specs:
        if spec.name not in contract:
            raise StepSpecError(f"step {spec.name!r} is not in STEP_REPORT_CONTRACT")
        if spec.payload_type is not contract[spec.name]:
            raise StepSpecError(
                f"step {spec.name!r}: StepSpec.payload_type {spec.payload_type!r} "
                f"!= STEP_REPORT_CONTRACT {contract[spec.name]!r}"
            )
        if spec.adapter is not steps[spec.name]:
            raise StepSpecError(f"step {spec.name!r}: StepSpec.adapter is not DEFAULT_STEPS[{spec.name!r}]")


_validate_step_specs(STEP_SPECS, DEFAULT_STEPS, STEP_REPORT_CONTRACT)


def apply_step_overrides(
    steps: Mapping[str, PipelineStep],
    overrides: Mapping[str, Callable[..., Any]] | None,
) -> dict[str, PipelineStep]:
    """Return a step registry with legacy callable overrides adapted.

    Args:
        steps: Base step registry (typically ``DEFAULT_STEPS``).
        overrides: Optional mapping of step name to legacy callable.
            Each callable is wrapped in a :class:`LegacyCallableStep`.

    Returns:
        A new dict with overridden steps replaced by adapters.
    """
    resolved = dict(steps)
    for name, fn in dict(overrides or {}).items():
        resolved[name] = LegacyCallableStep(name, fn)
    return resolved


__all__ = [
    "DEFAULT_STEPS",
    "STEP_SPECS",
    "CleanupStep",
    "CleanStep",
    "DispatchAuthorityKW",
    "DispatchStep",
    "EnforceStep",
    "IngestStep",
    "LegacyCallableStep",
    "ScrapeStep",
    "SortStep",
    "StepSkip",
    "StepSpec",
    "StepSpecError",
    "TrailersStep",
    "VerifyStep",
    "apply_step_overrides",
    "resolve_dispatch_authority",
]
