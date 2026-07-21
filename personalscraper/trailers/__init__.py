"""Trailers sub-package for PersonalScraper.

Provides trailer placement path computation, existence checks, and NFO
trailer-tag population. No network I/O or media downloads -- download is
owned by ``personalscraper.trailers.discovery.ytdlp_downloader.YtdlpDownloader`` and
the full pipeline is orchestrated by
``personalscraper.trailers.orchestrator.TrailersOrchestrator``.
"""
