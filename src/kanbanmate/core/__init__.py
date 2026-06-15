"""Functional core: pure domain logic with zero I/O and zero upward imports.

This layer holds the domain model, the board diff, the decision rules, and
other side-effect-free strategies. It is the innermost hexagonal layer and
must depend on nothing from ``ports``, ``adapters``, ``app``, ``daemon``,
``cli``, or ``bin`` (DESIGN §3.2 downward-only import rule).
"""
