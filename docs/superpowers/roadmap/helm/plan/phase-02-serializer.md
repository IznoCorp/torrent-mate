# Phase 2 — Serializer (`render_pipeline`) + authoritative `transitions.yml` defaults

**Goal:** serialize an arbitrary `PipelineConfig` draft back to valid `transitions.yml` +
`columns.yml` (DESIGN §6), generalizing today's `render_transitions_yaml` (which only renders
the default flow — `DEFAULT_TRANSITIONS`, 20 raw entries, for the fixed 14-column board).
Establish the round-trip idempotence property.

**Files:** `src/kanbanmate/core/config_serialize.py` (new),
`tests/core/test_config_serialize.py` (new). Read-only refs: `core/transitions_defaults.py`
(`render_transitions_yaml`), `assets/columns.yml.tmpl`.

### 2.1 — `render_pipeline`

`render_pipeline(cfg: PipelineConfig) -> tuple[str, str]` returning `(transitions_yaml,
columns_yaml)`:

- `transitions.yml`: the 3-line `# permission_mode …` comment header, `project:` (from
  `binding.github`), an **authoritative** `defaults:` block (the home the daemon reads — see
  2.3), and the transition list. Emit via
  `yaml.safe_dump(sort_keys=False, allow_unicode=True, width=120)`; prompts as block scalars.
  Omit fields equal to their default (`advance: stop`, empty `on_fail`, `permission_mode:
auto` on non-launch rows) to keep the file lean — matching the live file's shape.
- `columns.yml`: bare set (`key` + `name` from `binding.column_names`) + `action: teardown`
  on the reactive column. Preserve document order. Do NOT emit an active `defaults:` block here
  (leave the template's commented-out fallback — the daemon reads defaults from `transitions.yml`,
  see 2.3).

**Acceptance:** rendering the default `PipelineConfig` produces a `transitions.yml` that
`load_transitions` accepts and whose parsed result equals `default_transition_config()`. The
rendered `columns.yml` parses via `load_columns` to the **14-column** set.

### 2.2 — Round-trip idempotence tests

Assert **semantic** idempotence (not byte equality): `load(render(load(X))) == load(X)` for
(a) the shipped default and (b) a **PURPOSE-BUILT** fixture, for both transitions and columns.
Do NOT use the live `personal-scraper` config as the non-default fixture — it currently _equals_
`default_transition_config()`, so it exercises no non-default shape. The purpose-built fixture
must include the round-trip's hard cases:

- a **list-expansion** row (`[a, b] → c`) — assert it round-trips (preserved OR cartesian-
  expanded, as long as the parsed result is equal);
- **two prompt-bearing rows landing in the same column** with different prompts (e.g.
  `PrepareFeature→InProgress` vs `PRCI→InProgress`) — the per-`(from,to)` discriminator;
- a **wildcard-shadowing** case (an explicit `(from,to)` row plus a `(*,to)` the explicit row
  shadows) — precedence preserved post-render.

**Acceptance:** both round-trips pass; the reordered/wildcard fixture resolves identically
post-render (precedence preserved) — equality is on the parsed `TransitionConfig` via `get()`
across all column pairs, since `TransitionConfig` has no public row list to compare directly.

### 2.3 — Defaults home (transitions.yml is authoritative — HEAD reality)

**Reality (genesis phase 30 / #4):** `app/wiring.build_tick_config` reads `concurrency_cap` /
`move_rate_limit_per_hour` from the parsed `TransitionConfig` (i.e. `transitions.yml`'s
`defaults:`), the loader fallback is **3** (aligned with the template — no 2/3 asymmetry), and
the `columns.yml` `defaults:` block is **demoted to a commented-out fallback** in the template
(`load_board_defaults` still parses it but the daemon does not read it). So `transitions.yml` is
the single authoritative home — the OPPOSITE of this prep's earlier draft.

On render, write `definition.defaults` into the `transitions.yml` `defaults:` block
(authoritative) and do NOT emit an active `columns.yml` `defaults:` block (leave the commented
fallback). The validator (phase-03) may **warn** if a hand-edited `columns.yml` carries an
_uncommented_ `defaults:` that disagrees (dead config), but `transitions.yml` always wins.

**Acceptance:** rendering a draft produces a `transitions.yml` whose `defaults:` carries
`definition.defaults`; a test asserts `build_tick_config` reads those exact values back from the
rendered `transitions.yml` unchanged (no behavior change). The rendered `columns.yml` has no
active `defaults:` block.

### Phase gate

`rm -rf .mypy_cache && make check` green; round-trip tests pass; no residual imports.
