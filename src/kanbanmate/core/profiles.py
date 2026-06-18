"""Canonical permission-profile name set (DESIGN §13).

This module holds the single source of truth for the four supported profile
names. It lives in ``core`` (pure: no I/O) so the validator (``core/config_validate.py``)
can import it directly without violating the downward-only layering rule.
``adapters/perms.py`` imports from here and re-exports ``PROFILES`` so all
existing callers of ``perms.PROFILES`` are unaffected.
"""

from __future__ import annotations

# The four per-stage workflow profiles.  The PoC ``merge`` profile is
# deliberately absent — merge is human-only, not a launched-agent concern.
PROFILES: tuple[str, ...] = ("docs", "prepare", "dev", "check")
