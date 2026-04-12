"""Process phase modules — reclean, dedup, cleanup.

Phase 3 of the pipeline: re-clean raw folder names, deduplicate fuzzy
duplicates, and remove empty directories. Runs after sort and before
scrape in the sequential pipeline.
"""
