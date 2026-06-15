"""``kanban poll --once`` — run exactly one reconciliation tick and exit (DESIGN §3.1 / §5).

``kanban poll --once`` is the debugging counterpart to the long-running ``kanban run`` daemon: it
loads the same :class:`~kanbanmate.app.wiring.WiringConfig` from ``~/.kanban/config.yml`` and runs a
**single** :func:`~kanbanmate.app.wiring.run_one_tick`, then returns — no loop, no adaptive sleep, no
single-instance lock to acquire. It is what an operator reaches for to see one probe → snapshot →
diff → decide → execute pass without leaving a daemon running.

Both seams are injectable: ``load_config`` (the daemon's YAML loader by default) and ``run_tick``
(:func:`~kanbanmate.app.wiring.run_one_tick` by default), so tests assert "exactly one tick ran" and
"the result is returned" without touching the real network/tmux/filesystem config.

Layering: ``cli`` is an entrypoint at the top of the import hierarchy (DESIGN §3.2); it may import
``app`` (the tick result types + ``run_one_tick``) and ``daemon`` (the config loader) freely.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from kanbanmate.app.tick import PersistedState, TickResult
from kanbanmate.app.wiring import WiringConfig, run_one_tick
from kanbanmate.daemon.loop import CONFIG_FILENAME, DEFAULT_KANBAN_ROOT, _load_wiring_config

# A config loader: maps a config-file path to the wiring inputs. The daemon's loader by default; a
# test injects a stub returning a canned :class:`WiringConfig` so no YAML/columns file is read.
ConfigLoader = Callable[[Path], WiringConfig]

# A single-tick runner mirroring :func:`~kanbanmate.app.wiring.run_one_tick`. Injected so tests
# assert it is called exactly once and never wire real adapters.
TickRunner = Callable[[WiringConfig, PersistedState | None], "tuple[TickResult, PersistedState]"]


def poll_once(
    *,
    root: Path | str | None = None,
    load_config: ConfigLoader = _load_wiring_config,
    run_tick: TickRunner = run_one_tick,
) -> TickResult:
    """Run exactly one reconciliation tick and return its result (DESIGN §3.1).

    Loads the wiring config from ``<root>/config.yml`` and runs a **single** tick from a fresh
    :class:`~kanbanmate.app.tick.PersistedState` baseline (a one-shot dry run carries no cross-tick
    state). Unlike :func:`~kanbanmate.daemon.loop.run_loop` this acquires no daemon lock and never
    sleeps or loops — it ticks once and returns.

    Args:
        root: The kanban runtime root holding ``config.yml``; defaults to ``~/.kanban``. Pass a
            ``tmp_path`` in tests.
        load_config: The config loader (injected for tests); defaults to the daemon's YAML loader.
        run_tick: The single-tick runner (injected for tests); defaults to
            :func:`~kanbanmate.app.wiring.run_one_tick`.

    Returns:
        The :class:`~kanbanmate.app.tick.TickResult` summarising the one cycle that ran.
    """
    resolved_root = DEFAULT_KANBAN_ROOT if root is None else Path(root)
    config = load_config(resolved_root / CONFIG_FILENAME)
    # A one-shot poll starts from a cold baseline: no carry-over PersistedState exists across a
    # single CLI invocation, so the diff compares the live board against an empty prior.
    result, _next_state = run_tick(config, PersistedState())
    return result


def render_poll(result: TickResult) -> str:
    """Render a one-tick :class:`~kanbanmate.app.tick.TickResult` as an operator summary line.

    Args:
        result: The tick result to describe.

    Returns:
        A human-readable one-line summary of the cycle.
    """
    return (
        "kanban poll --once: "
        f"snapshot={result.snapshot_taken} "
        f"actions={result.actions_executed} "
        f"reaped={result.reaped} "
        f"errors={result.errors}"
    )
