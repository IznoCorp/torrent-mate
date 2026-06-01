"""Check plugin package — importing this module registers all check plugins."""

from personalscraper.verify.checks import (  # noqa: F401
    artwork,
    category,
    dedup,
    naming,
    nfo,
    ntfs,
    provider_ids,
    streams,
    structure,
)
from personalscraper.verify.checks.registry import registry  # noqa: F401

__all__ = ["registry"]
