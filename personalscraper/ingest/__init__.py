"""V1 — Ingest: copy/move completed torrents from qBittorrent to staging.

Modules:
    qbit_client: Wrapper around qbittorrent-api for torrent status and file listing.
    tracker: JSON-based tracker for already-ingested torrents.
    ingest: Main orchestrator (run_ingest entry point).
"""
