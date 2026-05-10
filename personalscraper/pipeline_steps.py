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

        return run_ingest(ctx.settings, dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)


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

        return run_sort(
            ctx.settings,
            staging_dir=ctx.config.paths.staging_dir,
            dry_run=ctx.dry_run,
            config=ctx.config,
            observers=ctx.observers,
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

        return run_clean(ctx.settings, dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)


class ScrapeStep:
    """Adapter for the scrape step (``personalscraper.scraper.run.run_scrape``)."""

    name = "scrape"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the scrape step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` with per-item scrape outcomes and confidence scores.
        """
        from personalscraper.scraper.run import run_scrape

        return run_scrape(
            ctx.settings,
            config=ctx.config,
            dry_run=ctx.dry_run,
            interactive=ctx.interactive,
            observers=ctx.observers,
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

        return run_cleanup(ctx.settings, dry_run=ctx.dry_run, config=ctx.config)


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

        return run_enforce(ctx.settings, ctx.config, dry_run=ctx.dry_run, observers=ctx.observers)


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

        return run_verify(ctx.settings, ctx.config, dry_run=ctx.dry_run, fix=False, observers=ctx.observers)


class TrailersStep:
    """Adapter for the trailers step (``personalscraper.trailers.step.run_trailers``)."""

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
            ctx.config,
            staging_dir=ctx.config.paths.staging_dir,
            verified=ctx.extras.get("verified", []),
            skip_trailers=bool(ctx.extras.get("skip_trailers", False)),
            observers=ctx.observers,
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

        return run_dispatch(
            ctx.settings,
            config=ctx.config,
            dry_run=ctx.dry_run,
            verified=ctx.extras.get("verified"),
            observers=ctx.observers,
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
            return self._fn(ctx.settings, dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)
        if self.name == "sort":
            return self._fn(
                ctx.settings,
                staging_dir=ctx.config.paths.staging_dir,
                dry_run=ctx.dry_run,
                config=ctx.config,
                observers=ctx.observers,
            )
        if self.name in {"clean", "cleanup"}:
            return self._fn(ctx.settings, dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)
        if self.name == "scrape":
            return self._fn(
                ctx.settings,
                config=ctx.config,
                dry_run=ctx.dry_run,
                interactive=ctx.interactive,
                observers=ctx.observers,
            )
        if self.name == "enforce":
            return self._fn(ctx.settings, ctx.config, dry_run=ctx.dry_run, observers=ctx.observers)
        if self.name == "verify":
            return self._fn(ctx.settings, ctx.config, dry_run=ctx.dry_run, fix=False, observers=ctx.observers)
        if self.name == "trailers":
            return self._fn(
                ctx.config,
                staging_dir=ctx.config.paths.staging_dir,
                verified=ctx.extras.get("verified", []),
                skip_trailers=bool(ctx.extras.get("skip_trailers", False)),
                observers=ctx.observers,
            )
        if self.name == "dispatch":
            return self._fn(
                ctx.settings,
                config=ctx.config,
                dry_run=ctx.dry_run,
                verified=ctx.extras.get("verified"),
                observers=ctx.observers,
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
