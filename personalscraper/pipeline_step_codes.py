"""The closed set of pipeline step identifiers, the code set behind ``cli_core.step``.

Lives beside ``pipeline_steps.py`` (which registers one adapter per step in
``DEFAULT_STEPS``) the way ``RefusalCode`` lives in ``app/errors.py``; a test ties
the two so a step added to one cannot be missing from the other. Kept free of
imports so the console subscriber can use it without loading the step adapters.
"""

from __future__ import annotations

from enum import StrEnum


class StepCode(StrEnum):
    """The nine pipeline steps, the closed code set behind ``cli_core.step`` (their words in the catalogue)."""

    INGEST = "ingest"
    SORT = "sort"
    CLEAN = "clean"
    SCRAPE = "scrape"
    CLEANUP = "cleanup"
    ENFORCE = "enforce"
    VERIFY = "verify"
    TRAILERS = "trailers"
    DISPATCH = "dispatch"
