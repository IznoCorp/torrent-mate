"""Process phase modules — reclean, dedup, cleanup.

Phase 3 of the pipeline: re-clean raw folder names and deduplicate
fuzzy duplicates before scrape, then remove empty directories after
scrape. The 3 sub-steps run with individual error isolation.
"""
