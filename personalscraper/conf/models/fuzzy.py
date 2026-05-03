"""Fuzzy matching threshold config model."""

from pydantic import Field

from personalscraper.conf.models._base import _StrictModel


class FuzzyMatchConfig(_StrictModel):
    """Thresholds for ``text_utils.fuzzy_match_score``.

    All fields are exposed in ``config.json5`` under the ``fuzzy_match`` key
    so the anti-false-positive guards can be tuned without touching code.

    Attributes:
        min_length_ratio: ``len(shorter) / len(longer)`` guard. Strings
            whose length ratio is below this are rejected before scoring.
            Range: (0.0, 1.0]. Default 0.67.
        short_title_length: Inclusive length boundary (processed string
            length) separating short and long titles for the adaptive
            threshold. Default 10.
        short_title_threshold: WRatio score required when the processed
            length is ≤ ``short_title_length``. Default 95.0.
        long_title_threshold: WRatio score required when the processed
            length is > ``short_title_length``. Default 90.0.
    """

    min_length_ratio: float = Field(default=0.67, gt=0.0, le=1.0)
    short_title_length: int = Field(default=10, ge=1)
    short_title_threshold: float = Field(default=95.0, ge=0.0, le=100.0)
    long_title_threshold: float = Field(default=90.0, ge=0.0, le=100.0)
