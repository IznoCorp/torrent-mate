"""Verify pipeline step — quality gate run before dispatch.

Checks each scraped media directory for the dispatch contract: NFO present
and parseable, required artwork files exist, no NTFS-illegal filenames,
episode files conform to the canonical naming pattern.  Items that fail
the gate are reported as ``blocked`` and skipped by the subsequent
dispatch step.
"""
