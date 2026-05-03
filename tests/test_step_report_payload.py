"""Tests for StepReport.details_payload."""

from __future__ import annotations

from dataclasses import dataclass

from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline
from personalscraper.reports.ingest import IngestDetails


def test_step_report_details_payload_defaults_to_none() -> None:
    """details_payload is additive and defaults to None."""
    report = StepReport(name="x")

    assert report.details_payload is None


def test_step_report_details_payload_accepts_arbitrary_object() -> None:
    """details_payload accepts any structured object."""

    @dataclass
    class FakeDetails:
        value: int

    report = StepReport(name="x", details_payload=FakeDetails(value=42))

    assert report.details_payload.value == 42


def test_step_report_legacy_details_field_still_exists() -> None:
    """The legacy string details remain unchanged."""
    report = StepReport(name="x", details=["one", "two"])

    assert report.details == ["one", "two"]
    assert report.details_payload is None


def test_pipeline_attaches_contract_payload_when_missing() -> None:
    """Pipeline execution attaches the contracted typed payload."""
    pipeline = Pipeline.__new__(Pipeline)
    report = pipeline._with_details_payload("ingest", StepReport(name="ingest"))

    assert isinstance(report.details_payload, IngestDetails)
