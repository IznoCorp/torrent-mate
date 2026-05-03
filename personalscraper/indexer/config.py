"""Thin re-export of IndexerConfig for use within the indexer sub-package.

Importing directly from ``personalscraper.conf.models`` inside sub-modules of
this package would create a dependency chain that is harder to follow.  This
shim keeps the indexer package self-contained: internal modules import from
``personalscraper.indexer.config`` while the canonical definition stays in
``personalscraper.conf.models``.
"""

from personalscraper.conf.models.indexer import IndexerConfig

__all__ = ["IndexerConfig"]
