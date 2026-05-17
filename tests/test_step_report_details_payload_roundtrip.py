"""Regression test — Sub-phase 3.1 pre-investigation.

``StepReport.details_payload`` was typed ``Any | None``. The bus decoder
cannot reconstruct a typed dataclass from ``Any`` (no discriminator), so the
envelope round-trip in Sub-phase 3.1 would mutate a typed payload (e.g.
``IngestDetails(...)``) into a bare ``dict`` and break equality on the
enclosing event.

The field is now ``dict[str, Any] | None`` with ``__post_init__`` flattening
typed dataclass instances via :func:`dataclasses.asdict`. The dict form is
fully JSON-safe and survives encode → json.dumps → json.loads → decode
with equality preserved.
"""

from __future__ import annotations

import dataclasses
import json
import typing

from personalscraper.core.event_bus import _decode_field_value, event_to_dict
from personalscraper.models import StepReport
from personalscraper.reports.ingest import IngestDetails


def test_details_payload_flattens_typed_dataclass_to_dict() -> None:
    """Constructing with a typed dataclass coerces to its ``asdict`` form."""
    report = StepReport(name="ingest", details_payload=IngestDetails())
    assert isinstance(report.details_payload, dict)
    assert report.details_payload == dataclasses.asdict(IngestDetails())


def test_details_payload_none_is_preserved() -> None:
    """``None`` is a valid value (default) and not coerced."""
    report = StepReport(name="x")
    assert report.details_payload is None


def test_details_payload_envelope_roundtrip() -> None:
    """A populated payload survives encode / json / decode unchanged.

    Exercises the decoder's ``dict`` branch (now reachable thanks to the
    ``dict[str, Any] | None`` annotation).
    """
    typed = IngestDetails()
    report = StepReport(name="ingest", details_payload=typed)
    encoded = event_to_dict(report)
    raw = json.loads(json.dumps(encoded))

    hints = typing.get_type_hints(StepReport)
    decoded = _decode_field_value(raw["details_payload"], hints["details_payload"])

    assert decoded == dataclasses.asdict(typed)
    assert decoded == report.details_payload
