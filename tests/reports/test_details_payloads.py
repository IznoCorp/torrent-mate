"""Tests for typed report payload dataclasses."""

from __future__ import annotations

from dataclasses import asdict

from personalscraper.reports.clean import CleanDetails
from personalscraper.reports.cleanup import CleanupDetails
from personalscraper.reports.dispatch import DispatchDetails
from personalscraper.reports.enforce import EnforceDetails
from personalscraper.reports.ingest import IngestDetails
from personalscraper.reports.scrape import ScrapeDetails
from personalscraper.reports.sort import SortDetails, SortResult
from personalscraper.reports.trailers import TrailersDetails
from personalscraper.reports.verify import VerifyDetails, VerifyIssue


def test_payload_defaults_are_independent() -> None:
    """Default mutable containers are not shared between instances."""
    one = TrailersDetails()
    two = TrailersDetails()

    one.downloaded.append("movie")

    assert two.downloaded == []


def test_payloads_are_serialisable_to_dict() -> None:
    """Payloads can be converted with dataclasses.asdict."""
    payloads = [
        IngestDetails(copied=["a"]),
        SortDetails(moved=[SortResult(source="a", destination="b", status="moved")]),
        CleanDetails(removed_dirs=["empty"]),
        ScrapeDetails(scraped=["movie"], unmatched_paths=["raw"]),
        CleanupDetails(removed=["empty"]),
        EnforceDetails(corrected=["movie"]),
        VerifyDetails(verified=["movie"], issues=[VerifyIssue(path="p", code="missing-nfo")]),
        TrailersDetails(downloaded=["movie"], bot_detected=["other"]),
        DispatchDetails(moved_to_disk={"/disk1": ["movie"]}, merged=["existing"]),
    ]

    for payload in payloads:
        assert isinstance(asdict(payload), dict)
