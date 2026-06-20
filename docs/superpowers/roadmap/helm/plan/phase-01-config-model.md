# Phase 1 — Editable config model + definition/binding split

**Goal:** introduce a mutable, JSON-serializable **draft model** of the pipeline in `core/`
(pure), with the backend-neutral **`definition`** isolated from the GitHub **`binding`**
(DESIGN §4). No behavior change to the runtime loaders; this is additive.

**Files:** `src/kanbanmate/core/config_model.py` (new), `tests/core/test_config_model.py`
(new). Read-only references: `core/transitions.py`, `core/columns.py`, `core/domain.py`,
`core/transitions_defaults.py`.

### 1.1 — Draft dataclasses

Define mutable dataclasses mirroring the YAML 1:1:

- `ColumnDef(key: str, column_class: str = "inert")` — `column_class` is a **string** mirroring
  `core/domain.ColumnClass` values (`"reactive"` ⇔ `action: teardown`, else `"inert"`), NOT a
  bool. This keeps the draft 1:1 with the enum so a third class never forces a model migration.
  The `Column.name` produced by `load_columns` projects into `binding.column_names[key]`, NOT
  into `ColumnDef` (the name is a binding concern).
- `TransitionDef(from_: str | list[str], to: str | list[str], profile: str = "",
prompt: str | None = None, script: str | None = None, advance: str = "stop",
on_fail: str = "", permission_mode: str = "auto")`.
- `Defaults(concurrency_cap: int, move_rate_limit_per_hour: int)`.
- `GithubBinding(project: str, column_names: dict[str, str])` — `key → "GitHub label"`.
- `PipelineDefinition(columns: list[ColumnDef], transitions: list[TransitionDef],
defaults: Defaults)`.
- `PipelineConfig(definition: PipelineDefinition, binding: GithubBinding)`.

**Acceptance:** dataclasses construct; `mypy` clean; a transition with a `prompt` reports
`is_launch` (a derived property `bool(prompt)`); a `from_`/`to` accepts `str | list | "*"`.
Tests cover construction + the derived `is_launch`/`has_action` properties.

### 1.2 — `from_loaded` builder (YAML → draft)

`PipelineConfig.from_loaded(transitions_yaml: str | None, columns_yaml: str)` builds the draft.
**Critical (HEAD-verified):** `TransitionConfig` exposes **no transition list** — only `get()`,
`launch_target_columns()`, and private `_explicit`/`_wild_to`/`_wild_from` tables — so the draft
CANNOT be reconstructed from a `TransitionConfig`. Instead `from_loaded`:

- **re-parses the RAW `transitions.yml` string** (`yaml.safe_load` of the `transitions:`
  sequence, the `project:` header, the `defaults:` block) to populate the ordered, list-shape-
  preserving `TransitionDef` rows and split `project` into `binding.github` / the rest into
  `definition`;
- calls `load_transitions(transitions_yaml)` / `load_columns(columns_yaml)` purely to
  **validate** (the oracle) — never as a serialization source;
- reads each `ColumnDef.column_class` from the same `action:` flag `load_columns` uses, and
  projects each `Column.name` into `binding.column_names`.

A `None` transitions YAML uses the built-in default — call `render_transitions_yaml("")` and
re-parse that string (parity with `default_transition_config()`, which itself round-trips the
rendered default).

**Acceptance:** building from the shipped default template yields a `PipelineConfig` whose
`definition.transitions` rows match the rendered default's `transitions:` sequence (the default
`DEFAULT_TRANSITIONS` list is **20 raw entries**, some list-expanded) and whose
`binding.column_names` has all **14** columns. The round-trip is asserted as **semantic
equivalence** (`load(render(from_loaded(X))) == load(X)`), NOT byte/field-for-field, against a
**purpose-built** fixture (§ phase-02 2.2) — the live `personal-scraper` config currently equals
the shipped default, so it exercises no non-default shape. Tests assert no GitHub-ism leaks into
`definition`.

### 1.3 — JSON boundary (`to_dict`/`from_dict`)

Symmetric `to_dict()` / `from_dict(d)` for the HTTP boundary (plain JSON: lists, dicts, str,
int, bool, None). `from_` serializes as `"from"` in the dict (Python keyword avoidance).

**Acceptance:** `from_dict(to_dict(cfg)) == cfg` for the default and the fixture. Tests assert
the dict is JSON-serializable (`json.dumps` succeeds) and the `from`/`from_` key mapping.

### Phase gate

`rm -rf .mypy_cache && make check` green; `import kanbanmate` smoke test; no residual imports.
