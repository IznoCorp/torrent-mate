"""Pipeline step adapters and default registry."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from personalscraper.models import StepReport
from personalscraper.pipeline_protocol import PipelineStep, StepContext


class IngestStep:
    """Adapter for the ingest step."""

    name = "ingest"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.ingest.ingest import run_ingest

        return run_ingest(ctx.settings, dry_run=ctx.dry_run, config=ctx.config)


class SortStep:
    """Adapter for the sort step."""

    name = "sort"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.sorter.run import run_sort

        return run_sort(
            ctx.settings,
            staging_dir=ctx.config.paths.staging_dir,
            dry_run=ctx.dry_run,
            config=ctx.config,
        )


class CleanStep:
    """Adapter for the clean process sub-step."""

    name = "clean"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.process.run import run_clean

        return run_clean(ctx.settings, dry_run=ctx.dry_run, config=ctx.config)


class ScrapeStep:
    """Adapter for the scrape process sub-step."""

    name = "scrape"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.scraper.run import run_scrape

        return run_scrape(
            ctx.settings,
            config=ctx.config,
            dry_run=ctx.dry_run,
            interactive=ctx.interactive,
        )


class CleanupStep:
    """Adapter for the cleanup process sub-step."""

    name = "cleanup"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.process.run import run_cleanup

        return run_cleanup(ctx.settings, dry_run=ctx.dry_run, config=ctx.config)


class EnforceStep:
    """Adapter for the enforce step."""

    name = "enforce"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.enforce.run import run_enforce

        return run_enforce(ctx.settings, ctx.config, dry_run=ctx.dry_run)


class VerifyStep:
    """Adapter for the verify step."""

    name = "verify"

    def __call__(self, ctx: StepContext) -> tuple[StepReport, Any]:
        from personalscraper.verify.run import run_verify

        return run_verify(ctx.settings, ctx.config, dry_run=ctx.dry_run, fix=False)


class TrailersStep:
    """Adapter for the trailers step."""

    name = "trailers"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.trailers.step import run_trailers

        return run_trailers(
            ctx.config,
            staging_dir=ctx.config.paths.staging_dir,
            verified=ctx.extras.get("verified", []),
            skip_trailers=bool(ctx.extras.get("skip_trailers", False)),
        )


class DispatchStep:
    """Adapter for the dispatch step."""

    name = "dispatch"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.dispatch.run import run_dispatch

        return run_dispatch(
            ctx.settings,
            config=ctx.config,
            dry_run=ctx.dry_run,
            verified=ctx.extras.get("verified"),
        )


class LegacyCallableStep:
    """Adapter that preserves the historical ``step_overrides`` callable API."""

    def __init__(self, name: str, fn: Callable[..., Any]) -> None:
        self.name = name
        self._fn = fn

    def __call__(self, ctx: StepContext) -> StepReport | tuple[StepReport, Any]:
        if self.name == "ingest":
            return self._fn(ctx.settings, dry_run=ctx.dry_run, config=ctx.config)
        if self.name == "sort":
            return self._fn(
                ctx.settings,
                staging_dir=ctx.config.paths.staging_dir,
                dry_run=ctx.dry_run,
                config=ctx.config,
            )
        if self.name in {"clean", "cleanup"}:
            return self._fn(ctx.settings, dry_run=ctx.dry_run, config=ctx.config)
        if self.name == "scrape":
            return self._fn(ctx.settings, config=ctx.config, dry_run=ctx.dry_run, interactive=ctx.interactive)
        if self.name == "enforce":
            return self._fn(ctx.settings, ctx.config, dry_run=ctx.dry_run)
        if self.name == "verify":
            return self._fn(ctx.settings, ctx.config, dry_run=ctx.dry_run, fix=False)
        if self.name == "trailers":
            return self._fn(
                ctx.config,
                staging_dir=ctx.config.paths.staging_dir,
                verified=ctx.extras.get("verified", []),
                skip_trailers=bool(ctx.extras.get("skip_trailers", False)),
            )
        if self.name == "dispatch":
            return self._fn(ctx.settings, config=ctx.config, dry_run=ctx.dry_run, verified=ctx.extras.get("verified"))
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
    """Return a step registry with legacy callable overrides adapted."""
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
