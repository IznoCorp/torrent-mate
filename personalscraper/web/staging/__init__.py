"""Staging read-model helpers for the web API (webui-overhaul OBJ2A).

Pure, read-only functions that scan the configured staging tree and turn each
media folder into a :class:`~personalscraper.web.models.staging.StagingMediaItem`
— NFO metadata, matching state, trailer/poster presence, and the per-media
pipeline timeline. Kept out of the route module so it stays unit-testable
without a FastAPI app.
"""
