"""Shared test doubles reused across test tiers (tests-arch consolidation).

Doubles here MUST have a single, tier-agnostic behavioural contract.  A double
whose contract genuinely differs between tiers (e.g. one that returns ``None``
on a miss for capability-semantics tests versus one that raises ``ApiError`` for
circuit-breaker resilience tests) stays local to its tier — parameterise or keep
separate, never blur the families.
"""
