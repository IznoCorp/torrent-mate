"""Library tooling — scanner, analyzer, rescraper, and reconciliation helpers.

Tools that read or repair the on-disk media library outside the regular
ingest/sort/scrape/dispatch pipeline. Used by the indexer (full / quick /
enrich scans), the rescraper (drift fixups against TMDB/TVDB), and the
analyzer (size and quality stats reported by ``library-status``).
"""
