"""Load-bearing STEP_REPORT_CONTRACT validation + typed Details producers.

Covers CROSS-CUTTING-01: the ``STEP_REPORT_CONTRACT`` validation in
``Pipeline._with_details_payload`` is load-bearing (a mistyped payload raises),
and the per-step ``run_*`` finalizers populate their typed ``Details`` payload
from data the step already computes.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from personalscraper.dispatch.run import _build_dispatch_details
from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline, StepReportContractError
from personalscraper.reports import STEP_REPORT_CONTRACT
from personalscraper.reports.dispatch import DispatchDetails
from personalscraper.reports.ingest import IngestDetails
from personalscraper.reports.scrape import ScrapeDetails
from personalscraper.reports.sort import SortDetails
from personalscraper.reports.verify import VerifyDetails
from personalscraper.scraper.run import _build_scrape_report
from personalscraper.sorter.run import _build_sort_details
from personalscraper.trailers.step import _build_trailers_details
from personalscraper.verify.run import _build_verify_details


def _bare_pipeline() -> Pipeline:
    """Return a Pipeline instance without running __init__ (validation is pure)."""
    return Pipeline.__new__(Pipeline)


class TestWithDetailsPayloadValidation:
    """``Pipeline._with_details_payload`` is a load-bearing contract check."""

    def test_none_payload_is_autofilled_with_empty_typed_dict(self) -> None:
        """A step with no per-item data gets the honest empty typed payload."""
        pipeline = _bare_pipeline()
        report = pipeline._with_details_payload("sort", StepReport(name="sort"))
        assert report.details_payload == dataclasses.asdict(SortDetails())

    def test_correct_dataclass_payload_is_flattened_to_dict(self) -> None:
        """A matching dataclass instance validates and is flattened via asdict."""
        pipeline = _bare_pipeline()
        report = StepReport(name="dispatch")
        # Assign post-construction so the payload stays a dataclass instance.
        report.details_payload = DispatchDetails(merged=["Show"])
        out = pipeline._with_details_payload("dispatch", report)
        assert out.details_payload == dataclasses.asdict(DispatchDetails(merged=["Show"]))

    def test_correct_dict_payload_passes_unchanged(self) -> None:
        """A pre-flattened dict with the declared field keys validates as-is."""
        pipeline = _bare_pipeline()
        payload = dataclasses.asdict(VerifyDetails(verified=["A"]))
        report = StepReport(name="verify", details_payload=payload)
        out = pipeline._with_details_payload("verify", report)
        assert out.details_payload == payload

    def test_wrong_dataclass_type_raises_with_step_name(self) -> None:
        """Attaching the wrong Details dataclass fails loud, naming the step."""
        pipeline = _bare_pipeline()
        report = StepReport(name="sort")
        report.details_payload = IngestDetails(copied=["oops"])  # wrong type for sort
        with pytest.raises(StepReportContractError, match="sort"):
            pipeline._with_details_payload("sort", report)

    def test_wrong_dict_keys_raise(self) -> None:
        """A dict whose keys don't match the declared dataclass fields raises."""
        pipeline = _bare_pipeline()
        report = StepReport(name="scrape", details_payload={"unexpected": 1})
        with pytest.raises(StepReportContractError, match="scrape"):
            pipeline._with_details_payload("scrape", report)

    def test_non_contract_step_is_untouched(self) -> None:
        """A step name absent from the contract is returned unchanged."""
        pipeline = _bare_pipeline()
        report = StepReport(name="not-a-step")
        out = pipeline._with_details_payload("not-a-step", report)
        assert out.details_payload is None

    def test_every_contract_step_autofills_a_matching_dict(self) -> None:
        """For all 9 declared steps a bare report gets a contract-shaped payload."""
        pipeline = _bare_pipeline()
        for name, payload_type in STEP_REPORT_CONTRACT.items():
            report = pipeline._with_details_payload(name, StepReport(name=name))
            assert report.details_payload == dataclasses.asdict(payload_type())


class TestSortDetailsProducer:
    """``run_sort`` populates a typed ``SortDetails`` payload."""

    def test_partitions_by_status_and_stringifies_paths(self) -> None:
        """moved/dry-run → moved, skipped → skipped, error → errored; Paths become str."""
        results = [
            SimpleNamespace(
                source=Path("/s/A"), destination=Path("/d/A"), status="moved", media_type="movie", message=None
            ),
            SimpleNamespace(
                source=Path("/s/B"), destination=Path("/d/B"), status="dry-run", media_type="movie", message=None
            ),
            SimpleNamespace(source=Path("/s/C"), destination=None, status="skipped", media_type="movie", message="dup"),
            SimpleNamespace(source=Path("/s/D"), destination=None, status="error", media_type="movie", message="boom"),
        ]
        details = _build_sort_details(results)  # type: ignore[arg-type]
        assert [r.source for r in details.moved] == ["A", "B"]
        assert details.moved[0].destination == "/d/A"
        assert [r.source for r in details.skipped] == ["C"]
        assert [r.source for r in details.errored] == ["D"]
        # A dataclass instance that validates against the contract.
        _bare_pipeline()._with_details_payload("sort", StepReport(name="sort", details_payload=details))


class TestDispatchDetailsProducer:
    """``run_dispatch`` populates a typed ``DispatchDetails`` payload."""

    def test_groups_moved_by_disk_and_partitions_actions(self) -> None:
        """Moved items group by disk; merged/replaced/error land in their buckets."""
        results = [
            SimpleNamespace(source=Path("/s/New"), action="moved", disk="disk2", reason=None),
            SimpleNamespace(source=Path("/s/New2"), action="moved", disk="disk2", reason=None),
            SimpleNamespace(source=Path("/s/Show"), action="merged", disk="disk1", reason=None),
            SimpleNamespace(source=Path("/s/Film"), action="replaced", disk="disk1", reason=None),
            SimpleNamespace(source=Path("/s/Bad"), action="error", disk=None, reason="no space"),
        ]
        details = _build_dispatch_details(results)  # type: ignore[arg-type]
        assert details.moved_to_disk == {"disk2": ["New", "New2"]}
        assert details.merged == ["Show"]
        assert details.replaced == ["Film"]
        assert details.failed == [("Bad", "no space")]


class TestVerifyDetailsProducer:
    """``run_verify`` populates a typed ``VerifyDetails`` payload."""

    def test_partitions_valid_fixed_blocked(self) -> None:
        """Valid → verified, fixed → fixed, blocked → one VerifyIssue per error."""
        results = [
            SimpleNamespace(media_path=Path("/m/A"), status="valid", errors=[]),
            SimpleNamespace(media_path=Path("/m/B"), status="fixed", errors=[]),
            SimpleNamespace(media_path=Path("/m/C"), status="blocked", errors=["no nfo", "no poster"]),
        ]
        details = _build_verify_details(results)  # type: ignore[arg-type]
        assert details.verified == ["A"]
        assert details.fixed == ["B"]
        assert [(i.path, i.message) for i in details.issues] == [("C", "no nfo"), ("C", "no poster")]


class TestScrapeDetailsProducer:
    """``_build_scrape_report`` populates a typed ``ScrapeDetails`` payload."""

    def _result(self, name: str, action: str, **kw: object) -> SimpleNamespace:
        """Build a minimal ScrapeResult-like fake for the given name/action."""
        base = dict(
            media_path=Path(f"/staging/{name}"),
            action=action,
            error=None,
            nfo_written=False,
            artwork_downloaded=[],
            episodes_renamed=0,
            decision_trigger=None,
            decision_candidates=None,
            media_type="movie",
            match=None,
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_populates_scraped_skipped_failed_existing(self) -> None:
        """scraped/existing/low-confidence/error map to the matching ScrapeDetails fields."""
        results = [
            self._result("Ok", "scraped"),
            self._result("Existing", "skipped_already_done"),
            self._result("Low", "skipped_low_confidence"),
            self._result("Boom", "error", error="tmdb down"),
        ]
        report = _build_scrape_report(results)  # type: ignore[arg-type]
        payload = report.details_payload
        assert isinstance(payload, dict)  # flattened by StepReport.__post_init__
        assert payload["scraped"] == ["Ok"]
        assert payload["existing_validated"] == ["Existing"]
        assert payload["skipped_low_confidence"] == ["Low"]
        assert payload["failed"] == [("Boom", "tmdb down")]
        assert payload["unmatched_paths"] == ["Low"]
        # Round-trips through the load-bearing validator without raising.
        _bare_pipeline()._with_details_payload("scrape", report)

    def test_empty_scrape_yields_empty_but_valid_payload(self) -> None:
        """An empty result set still produces a contract-shaped (empty) payload."""
        report = _build_scrape_report([])
        assert report.details_payload == dataclasses.asdict(ScrapeDetails())


class TestTrailersDetailsProducer:
    """``run_trailers`` populates a typed ``TrailersDetails`` payload."""

    def test_partitions_by_status_excluding_bot_from_failed(self) -> None:
        """downloaded/bot/skipped partition; failed excludes bot_detected duplicates."""
        item_results = [
            ("/m/A", "downloaded", "downloaded"),
            ("/m/B", "bot_detected", "bot_detected"),
            ("/m/C", "already_present", "already_present"),
            ("/m/D", "skipped", "skipped_by_state"),
        ]
        failed_items = [
            ("/m/B", "bot_detected", "captcha"),  # excluded from `failed`
            ("/m/E", "no_trailer", ""),
        ]
        details = _build_trailers_details(item_results, failed_items)
        assert details.downloaded == ["/m/A"]
        assert details.bot_detected == ["/m/B"]
        assert details.skipped_existing == ["/m/C", "/m/D"]
        assert details.failed == [("/m/E", "no_trailer")]


class TestEnforceDetailsProducer:
    """``run_enforce`` populates a typed ``EnforceDetails`` payload."""

    def test_partitions_corrected_compliant_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sanitize/structure outcomes map to corrected/already_compliant/failed."""
        from personalscraper.core.event_bus import EventBus
        from personalscraper.enforce import run as enforce_run

        sanitize = [
            SimpleNamespace(action="renamed", old_name="dirty.mkv", new_name="clean.mkv"),
            SimpleNamespace(action="skipped", old_name="ok.mkv", new_name=None),
            SimpleNamespace(action="error", old_name="bad.mkv", new_name=None),
        ]
        structure = [
            SimpleNamespace(path=Path("/m/Repaired"), action="repaired", fixes=["added nfo"], warnings=[]),
            SimpleNamespace(path=Path("/m/Valid"), action="validated", fixes=[], warnings=[]),
            SimpleNamespace(path=Path("/m/Broken"), action="error", fixes=[], warnings=["boom"]),
        ]
        monkeypatch.setattr(enforce_run, "sanitize_files", lambda *a, **k: sanitize)
        monkeypatch.setattr(enforce_run, "validate_structure", lambda *a, **k: structure)
        monkeypatch.setattr(enforce_run, "check_coherence", lambda *a, **k: [])

        report = enforce_run.run_enforce(MagicMock(), MagicMock(), dry_run=True, event_bus=EventBus())
        payload = report.details_payload
        assert isinstance(payload, dict)  # flattened by StepReport.__post_init__
        assert payload["corrected"] == ["dirty.mkv", "Repaired"]
        assert payload["already_compliant"] == ["ok.mkv", "Valid"]
        assert payload["failed"] == [("bad.mkv", "error"), ("Broken", "error")]
        # Round-trips through the load-bearing validator without raising.
        _bare_pipeline()._with_details_payload("enforce", report)
