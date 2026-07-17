"""Indexer scenario integration tests (real sqlite + tmp_path FS, no live disks).

Relocated from tests/e2e/ (phase 12 tests-arch): these are pyfakefs/tmp_path
mocked-filesystem integration tests, not manual live-disk E2E — they always ran
in the default suite, so they belong under tests/integration/ per
docs/reference/testing.md.
"""
