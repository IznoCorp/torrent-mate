"""Read-only insights layer over the indexer DB.

Provides analysis, reporting, and recommendation functions that consume
the ``media_item`` / ``media_stream`` tables written by
``indexer.scanner``. Intended for CLI commands and the future Web UI.

This package never walks the filesystem and never runs ffprobe: the
stream-level data it surfaces (codec / audio / subtitle / HDR / Atmos)
is read exclusively from the rows the enrich pass persisted into
``media_stream`` (see ``indexer.scanner._modes.enrich``). The dropped
``analyzer.analyze_library`` ffprobe re-scan has no successor here.
"""
