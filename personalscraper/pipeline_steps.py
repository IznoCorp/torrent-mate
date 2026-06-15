"""Pipeline step adapters and default registry.

Each adapter class wraps a domain-level ``run_*`` function so that the
pipeline orchestrator can call every step through the uniform
:class:`PipelineStep` protocol.  The lazy imports inside ``__call__``
avoid pulling in the entire project at module-load time.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from personalscraper.models import StepReport
from personalscraper.pipeline_protocol import PipelineStep, StepContext


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

        return run_ingest(
            ctx.app.settings,
            dry_run=ctx.dry_run,
            config=ctx.app.config,
            event_bus=ctx.app.event_bus,
            torrent_client=ctx.app.torrent_client,
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
        from typing import TypedDict

        from personalscraper.core.delete_permit import DeletePermit, SeedObligationRecorder
        from personalscraper.dispatch.run import run_dispatch

        class _DispatchKW(TypedDict, total=False):
            permit: DeletePermit
            recorder: SeedObligationRecorder

        acquire = getattr(ctx.app, "acquire", None)
        authority = getattr(acquire, "delete_authority", None)
        kw: _DispatchKW = {}
        if authority is not None:
            kw = {"permit": authority, "recorder": authority}

        return run_dispatch(
            ctx.app.settings,
            config=ctx.app.config,
            dry_run=ctx.dry_run,
            verified=ctx.extras.get("verified"),
            event_bus=ctx.app.event_bus,
            **kw,
        )


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
    "CleanupStep",
    "CleanStep",
    "DEFAULT_STEPS",
    "DispatchStep",
    "EnforceStep",
    "IngestStep",
    "LegacyCallableStep",
    "ScrapeStep",
    "SortStep",
    "TrailersStep",
    "VerifyStep",
    "apply_step_overrides",
]
