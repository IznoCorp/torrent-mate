"""Canonical permission-profile name set (DESIGN §13).

This module holds the single source of truth for the supported profile names. It lives in
``core`` (pure: no I/O) so the validator (``core/config_validate.py``) can import it directly
without violating the downward-only layering rule. ``adapters/perms.py`` imports from here and
re-exports ``PROFILES`` so all existing callers of ``perms.PROFILES`` are unaffected.
"""

from __future__ import annotations

# The per-stage workflow profiles. ``merge`` is the autonomous Review→Merge stage (operator
# decision — it supersedes the historical merge=human-only floor for THAT stage only): it is the
# SOLE profile whose deny-list lifts ``gh pr merge`` (``adapters/perms.py``), and the SOLE profile a
# prompt-bearing transition into the ``Merge`` column may carry (validator V7 carve-out). Every
# other profile still bans all merge paths.
PROFILES: tuple[str, ...] = ("docs", "prepare", "dev", "check", "merge")

# Profiles an AD-HOC launch may use (the operator "launch an agent on this ticket" path). This is
# ``PROFILES`` minus ``merge`` ON PURPOSE: ``merge`` lifts the ``gh pr merge`` ban and is reachable
# ONLY through the engine-gated Review→Merge stage (validator V7), NEVER via an ad-hoc launch — which
# would attach merge capability to any ticket in any column and, because authority is DERIVED per
# issue (a ``launch`` intent for a non-running target resolves to operator authority), be reachable
# by a bridled agent. Excluding ``merge`` here keeps merge=human-only intact. Enforced server-side in
# ``app/intents._execute_launch`` AND the ``launch_agent`` HTTP endpoint (never trust the UI select).
SAFE_LAUNCH_PROFILES: frozenset[str] = frozenset({"docs", "prepare", "dev", "check"})
