"""Main ingest orchestrator — run_ingest() entry point.

Coordinates qBitClient, IngestTracker, and atomic file transfers
to move completed torrents from torrents/complete to staging.
Implemented in V1 phase 4.
"""
