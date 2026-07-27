"""Per-step typed details payloads for StepReport.details_payload."""

from __future__ import annotations

from personalscraper.reports._validate import StepReportContractError, validate_details_payload
from personalscraper.reports.clean import CleanDetails
from personalscraper.reports.cleanup import CleanupDetails
from personalscraper.reports.dispatch import DispatchDetails
from personalscraper.reports.enforce import EnforceDetails
from personalscraper.reports.ingest import IngestDetails
from personalscraper.reports.scrape import ScrapeDetails
from personalscraper.reports.sort import SortDetails
from personalscraper.reports.trailers import TrailersDetails
from personalscraper.reports.verify import VerifyDetails

STEP_REPORT_CONTRACT: dict[str, type] = {
    "ingest": IngestDetails,
    "sort": SortDetails,
    "clean": CleanDetails,
    "scrape": ScrapeDetails,
    "cleanup": CleanupDetails,
    "enforce": EnforceDetails,
    "verify": VerifyDetails,
    "trailers": TrailersDetails,
    "dispatch": DispatchDetails,
}

__all__ = [
    "STEP_REPORT_CONTRACT",
    "StepReportContractError",
    "validate_details_payload",
    "CleanDetails",
    "CleanupDetails",
    "DispatchDetails",
    "EnforceDetails",
    "IngestDetails",
    "ScrapeDetails",
    "SortDetails",
    "TrailersDetails",
    "VerifyDetails",
]
