"""Application layer: orchestration and the composition root.

This layer wires adapters into the unified poll loop (``tick``), drives the
command-pattern actions, and builds dependencies in ``wiring``. The app may
import ``core``, ``ports``, and ``adapters`` but must not import ``cli`` or
``daemon`` (DESIGN §3.2 downward-only import rule).
"""
