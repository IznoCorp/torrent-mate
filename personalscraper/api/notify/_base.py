"""Notify family base — re-exports of the Notifier and HealthChecker Protocols.

Implements DESIGN §7.1.

`PipelineReport` is the existing pipeline-run aggregator from
`personalscraper.models`; notifiers serialize it (typically to HTML) before
sending. Both Protocols are fail-soft contracts: implementations MUST NOT
raise on transport or API errors — they log and return `False` (or no-op,
for `HealthChecker`) so that notification failures never abort the pipeline.

As of the ``provider-ids`` feature (sub-phase 1.5), the canonical
definitions live in :mod:`personalscraper.api.notify._contracts` alongside
the other capability protocols (metadata, tracker, torrent). This module
re-exports them so existing imports from ``_base`` keep working without
churn during the migration.
"""

from personalscraper.api.notify._contracts import HealthChecker, Notifier

__all__ = ["Notifier", "HealthChecker"]
