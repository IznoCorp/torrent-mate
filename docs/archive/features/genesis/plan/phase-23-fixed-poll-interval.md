# Phase 23 — Fixed poll interval (disable the idle backoff)

**Trigger (operator):** the adaptive poll interval (`core/interval.py`) backs off geometrically on
inactivity (`base=15s`, `backoff=2`, up to `idle_max=300s` = 5 min). After idle, a card move is
not detected for up to 5 minutes — "la reprise est trop longue". The interval is hardcoded (not
configurable), and the live `personal-scraper` daemon runs in registry mode (no `config.yml`), so
only changing the default affects it. The PoC used a FIXED-interval launchd reaper, so a fixed
cadence is also more PoC-conformant.

**Decision:** make the default poll cadence **fixed at 10s** — disable the idle backoff by default.
Keep the curve machinery in the pure function (so an explicit `idle_max > base` config could still
opt back in), but the shipped default is flat. No rate-limit concern (≈360 GraphQL probes/h ≪ limits).

## Sub-phase 23.1 — Fixed 10s default cadence

**Files (write):**

- `src/kanbanmate/core/interval.py` — defaults to a flat 10s cadence.
- `src/kanbanmate/daemon/loop.py` — docstrings (drop "adaptive sleep / backing off" wording → "fixed
  10s poll cadence (idle backoff disabled by default)"); confirm the live `LoopConfig.interval`
  uses the default `IntervalConfig()` (no override) so the change reaches the running daemon.
- `tests/core/test_interval.py` — keep the existing curve tests (they pass an EXPLICIT
  `IntervalConfig(base=15, idle_max=300, backoff=2)`, so they still exercise the backoff math);
  ADD a test asserting the DEFAULT `IntervalConfig()` is FLAT at 10s for any idle (e.g. idle of
  10×base still returns 10.0).
- `docs/features/genesis/DESIGN.md` §3.3 (and any H-row / §3 prose) — describe the fixed default
  cadence; note the backoff is opt-in only.

**Target state (`core/interval.py`):**

- `_DEFAULT_BASE = 10.0` and `_DEFAULT_IDLE_MAX = 10.0` (so `IntervalConfig()` → `next_sleep` returns
  a flat 10.0 for any idle; `backoff` becomes a no-op when `idle_max == base`). Keep `_DEFAULT_BACKOFF`
  defined (must stay > 1 so the `math.log(idle_max/base, backoff)` guard never divides by zero — with
  `idle_max == base`, `log(1, backoff) == 0`, fine).
- Update the module + `IntervalConfig` docstrings: the default cadence is a fixed 10s; the geometric
  backoff only engages if an operator explicitly sets `idle_max > base`.

**Guard / scope checks:**

- Grep `src/` and `tests/` for any assertion of the OLD defaults (`15.0` / `300.0` as the interval
  base/ceiling) and reconcile (e.g. a smoke/loop test asserting the default). Change only
  interval-default assertions, not unrelated 15/300 literals.
- Do NOT add config plumbing (out of scope; the live daemon is registry-mode — the fixed default is
  what reaches it). A future `poll_interval` config key is a separate enhancement.

**Acceptance:**

- `rm -rf .mypy_cache && make check` — green.
- `IntervalConfig().base == 10.0`; for the default config, `next_sleep(t0, t0 + 10*base, None) == 10.0`
  (no lengthening on long idle).
- The existing explicit-cfg curve tests still pass (backoff math intact for opt-in configs).
- `daemon/loop.py` docstrings no longer claim an adaptive/backoff default.

### Phase gate

`rm -rf .mypy_cache && make check` green; diff confined to the files above; `python -c "import
kanbanmate"` smoke. (Then: restart the live PM2 daemon so the 10s cadence goes live.)
