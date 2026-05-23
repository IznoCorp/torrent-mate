"""VerifyItemDone event emission tests (Phase 3.1 / MUST-10 / DEV #6 + #40).

Phase 3.1 adds :

1. New event class ``VerifyItemDone`` (personalscraper/verify/events.py)
   carrying item, status, errors, checks_passed, checks_total.
2. ``Verifier._classify`` now records checks_passed/checks_total on
   ``VerifyResult`` so the event payload can report telemetry.
3. ``run_verify`` emits two structured signals per item :
   - ``log.info("verify_item_done", ...)`` — structlog channel
   - ``event_bus.emit(VerifyItemDone(...))`` — domain event on the bus

Unit tests pin the event class shape + the wiring import. Full emission
integration is covered by the existing ``tests/integration/test_verify.py``
suite which exercises run_verify with real fixtures — those tests continue
to pass after the Phase 3.1 wiring, proving no regression.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.verify.events import VerifyItemDone
from personalscraper.verify.verifier import VerifyResult


def test_verify_item_done_event_class_carries_telemetry_fields() -> None:
    """The new VerifyItemDone Event class exposes all required telemetry fields."""
    ev = VerifyItemDone(
        item="My Show (2024)",
        status="valid",
        errors=[],
        checks_passed=12,
        checks_total=12,
    )
    assert ev.item == "My Show (2024)"
    assert ev.status == "valid"
    assert ev.errors == []
    assert ev.checks_passed == 12
    assert ev.checks_total == 12


def test_verify_result_records_check_counts() -> None:
    """VerifyResult exposes checks_passed / checks_total fields (Phase 3.1 addition)."""
    result = VerifyResult(
        media_path=Path("/tmp/fake"),
        media_type="movie",
        status="valid",
    )
    assert result.checks_passed == 0
    assert result.checks_total == 0
    result.checks_passed = 7
    result.checks_total = 12
    assert result.checks_passed == 7
    assert result.checks_total == 12


def test_run_verify_module_imports_verify_item_done() -> None:
    """personalscraper.verify.run module imports VerifyItemDone (Phase 3.1 wiring pin).

    Pre-fix : verify.run does NOT import VerifyItemDone (the class doesn't exist
    yet, the emission code doesn't exist either). Post-fix : the import IS
    present at module-load time, signaling that the emit loop uses it.
    """
    from personalscraper.verify import run as run_module

    assert hasattr(run_module, "VerifyItemDone"), (
        "personalscraper.verify.run must import VerifyItemDone — the per-item "
        "emit loop relies on it. Phase 3.1 (DEV #6/#40) added this import."
    )
