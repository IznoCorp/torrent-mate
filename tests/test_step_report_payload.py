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


def test_step_report_details_payload_accepts_dataclass_and_flattens_to_dict() -> None:
    """Dataclass payloads are flattened to a JSON-safe ``dict`` via ``__post_init__``.

    Sub-phase 3.1: the field annotation moved from ``Any | None`` to
    ``dict[str, Any] | None`` so the value round-trips through
    ``event_to_envelope`` / ``event_from_envelope``. Producers may still pass
    a typed dataclass — the coercion runs automatically.
    """

    @dataclass
    class FakeDetails:
        value: int

    report = StepReport(name="x", details_payload=FakeDetails(value=42))

    assert report.details_payload == {"value": 42}


def test_step_report_details_payload_accepts_plain_dict_unchanged() -> None:
    """A pre-flattened dict is stored as-is (no double-coercion)."""
    report = StepReport(name="x", details_payload={"already": "dict"})

    assert report.details_payload == {"already": "dict"}


def test_step_report_legacy_details_field_still_exists() -> None:
    """The legacy string details remain unchanged."""
    report = StepReport(name="x", details=["one", "two"])

    assert report.details == ["one", "two"]
    assert report.details_payload is None


def test_pipeline_attaches_contract_payload_when_missing() -> None:
    """Pipeline execution attaches the contracted typed payload (flattened to dict)."""
    pipeline = Pipeline.__new__(Pipeline)
    report = pipeline._with_details_payload("ingest", StepReport(name="ingest"))

    # Sub-phase 3.1: the typed dataclass is coerced to a dict so the field
    # is JSON-safe for envelope round-trip. The contract is preserved at the
    # construction boundary (``_with_details_payload`` instantiates the
    # typed dataclass), but the field stores the flattened view.
    import dataclasses

    assert report.details_payload == dataclasses.asdict(IngestDetails())
