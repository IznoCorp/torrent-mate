# Design — Architecture Cleanup Round 2 (Web-Facing Enablers)

> **Status**: Draft (brainstorm output) — pending user review then plan generation.
> **Date**: 2026-05-28
> **Codename**: `arch-cleanup-2`
> **Roadmap item**: P1 — Architecture Cleanup Round 2 (`ROADMAP.md:11`)
> **Source analysis**: `docs/analysis/05-architecture-improvement-roadmap.md`
> **Version bump target**: 0.16.0 → 0.17.0 (minor, Y+1)
> **Branch**: `feat/arch-cleanup-2`

---

## 1. Purpose & Motivation

The original `arch-cleanup` feature (shipped v0.9.0, archived) decomposed the
god-modules. This **second round** is a narrowly-scoped set of _enablers_ that
remove the architectural defects standing between the current pipeline and the
web-facing roadmap items (Web Management UI, Watcher Service, Auto-Download,
Web UI Registry Consumer). Three of those four roadmap items (`ROADMAP.md:83`,
`:105`, `:167`) explicitly list `arch-cleanup-2` as a **prerequisite**.

The codebase is structurally healthier than the legacy ROADMAP and
`docs/reference/architecture.md` claim (re-verified 2026-05-28 against HEAD on
`feat/registry`): `make check` is green, `python3 scripts/check-module-size.py`
exits 0 with only two advisory WARNs, `api/` has zero upward leaks, and the
`ProviderRegistry` is already shipped and consumed. The problem is _not_ a
rewrite — it is four concrete, low-risk defects:

1. **The 5 registry events bypass the `Event` contract.** They are bare
   `@dataclass(frozen=True)` classes that do not subclass `core.event_bus.Event`
   (`api/metadata/registry/_events.py:12,39,56,71,89`). They carry no
   `correlation_id`/`timestamp`/`event_id`, cannot round-trip through
   `event_to_envelope`/`event_from_envelope`, are not auto-registered in
   `_EVENT_CLASS_REGISTRY`, and are **dropped** by the base-`Event` subscriber
   (`subscribers/debug_log.py:25` subscribes to `Event`; the registry events'
   MRO is `[<dataclass>, object]`). This directly blocks the Web UI Registry
   Consumer's WebSocket streaming (`ROADMAP.md:167,171`).

2. **No `schema_version` on the `Event` envelope.** The first cross-process or
   persisted consumer (Watcher, Web UI) will silently break on the next
   event-shape change. The field must be added _before_ such a consumer exists.

3. **`core/` and `conf/` leak upward imports**, inverting the documented acyclic
   direction (`docs/reference/architecture.md` asserts `core/`+`conf/` "depend
   on nothing in the project"). A clean service/HTTP facade would transitively
   re-pull these inverted edges.

4. **`sorter.file_type` is a misplaced shared constant.** `VIDEO_EXTENSIONS` /
   `FileType` / `is_trailer_filename` are imported by **10 non-`sorter`
   subpackages across 23 import lines** — turning a pipeline-step package into
   an undeclared utility dependency of nearly the whole system.

These are the prerequisite enablers; report 05 sequences them **first**, before
`FilesystemCapability` (sibling `multi-filesystem`), before the heavy
`lib-fold`, and before any Web UI.

---

## 2. Goals / Non-goals

### Goals

- Bring the 5 registry events (`ProviderFallbackTriggered`,
  `ProviderExhaustedEvent`, `LockedCapabilityUnresolved`,
  `RegistryFanOutCompleted`, `RegistryBootValidated`) onto the base `Event`
  contract: frozen `kw_only` subclasses, auto-registered, envelope-round-trippable,
  delivered to base-`Event` subscribers.
- Add a `schema_version: int` field to the `Event` base, threaded through
  `event_to_envelope` / `event_from_envelope`.
- Remove the upward import leaks from `core/` and `conf/` by relocating the
  shared primitives (`CircuitOpenError`, `ApiError`, `MediaType`, the four
  `Ranking*` config models) **down** into a neutral home, with re-exports that
  preserve every existing public import path.
- Promote `VIDEO_EXTENSIONS` / `FileType` / `is_trailer_filename` out of
  `sorter` into a neutral shared module, rewriting all 23 non-`sorter` import
  lines and dropping the cross-package dependency on `sorter`.
- Add architecture-guardrail tests (AST-based) that lock in the layering and
  the event-contract invariants so they cannot silently regress.

### Non-goals

- The heavy library/indexer fold (separate `lib-fold` feature — `ROADMAP.md:32`).
- `FilesystemCapability` / mount-parser consolidation (separate
  `multi-filesystem` feature — `ROADMAP.md:136`).
- A full DI container / `ServiceContainer`. The orchestrator self-instantiation
  (`scraper/orchestrator.py:101,103,113`) and `commands/info.py:59-83`
  registry-rebuild are **noted** (P3 DI Container, `ROADMAP.md:236`) but **not
  fixed here**. See §8 Open Questions for the overlap decision.
- Any Web UI / FastAPI / Flask code, or reversing the `architecture.md` "no web
  UI" anti-decision. This feature only _unblocks_ those.
- Migration scripts. Pre-1.0, single mono-user instance, not in production —
  config/DB/event shapes evolve in place (`feedback_no_backcompat_before_v1`).
- Runtime hot-swap, health scoring, or any registry behaviour change. The
  registry's runtime semantics are untouched; only its event-emission substrate
  changes.

---

## 3. Current state (evidence-backed, verified 2026-05-28 @ HEAD `1c4636eb`)

### 3.1 The 5 registry events bypass `Event`

`api/metadata/registry/_events.py` defines five bare frozen dataclasses:

| Class                        | Anchor          | Subclasses `Event`? |
| ---------------------------- | --------------- | ------------------- |
| `ProviderFallbackTriggered`  | `_events.py:12` | **No**              |
| `ProviderExhaustedEvent`     | `_events.py:39` | **No**              |
| `LockedCapabilityUnresolved` | `_events.py:56` | **No**              |
| `RegistryFanOutCompleted`    | `_events.py:71` | **No**              |
| `RegistryBootValidated`      | `_events.py:89` | **No**              |

Consequences, all verified:

- They are emitted via `ProviderRegistry._event_bus_safe_emit` →
  `self._event_bus.emit(event)  # type: ignore[arg-type]`
  (`api/metadata/registry/__init__.py:699,706`). The `type: ignore[arg-type]`
  exists precisely because `emit()` expects an `Event`.
- They are **not** registered in `_EVENT_CLASS_REGISTRY`
  (`Event.__init_subclass__`, `core/event_bus.py:242`, only fires for `Event`
  subclasses), so `event_from_envelope` cannot reconstruct them
  (`event_from_envelope` raises `KeyError` on unknown `_type`,
  `core/event_bus.py:108`).
- `events/__init__.py` eager-imports every producer module **except** `_events`
  (it imports `pipeline_events`, `core.circuit`, `dispatch.events`,
  `indexer.events`, `trailers.events` — confirmed, no `registry._events`).
- The base-`Event` subscriber `subscribers/debug_log.py:25`
  (`bus.subscribe(Event, self.on_event)`) **never receives them** — MRO walk in
  the bus dispatch only matches base classes that are actually in the MRO.

The 18 production `Event` subclasses (`indexer.events` 6, `pipeline_events` 6,
`core.circuit` 3, `trailers.events` 1, `verify.events` 1, `dispatch.events` 1)
all behave correctly. The registry's 5 are the only outliers.

### 3.2 The `Event` base has no `schema_version`

`core/event_bus.py:204-229` defines `@dataclass(frozen=True, kw_only=True) class
Event` with exactly four fields: `timestamp`, `source`, `event_id`,
`correlation_id`. There is **no** `version` / `schema_version` field.
`event_to_envelope` (`:96`) emits `{"_type", "data"}` with no version tag.

**Re-verified correction to report 05 §D caveat**: the base-`Event` envelope
serialization (`event_to_envelope` / `event_from_envelope`) is referenced only
in docstrings within production code — it is **not** wired into any persistence
path today. The `index_outbox` table stores an `OutboxPayload`-shaped
`payload_json` (`indexer/schema.py:416-433,605`), serialized at
`indexer/outbox/_drain.py:146` (`json.dumps(event_payload)`) — a domain dict,
**not** a base-`Event` envelope. Therefore adding `schema_version` is purely
additive and carries **no** stored-row-rewrite risk at present. (The Watcher /
Web UI will be the first true cross-process envelope consumers; that is exactly
why the version field must land before them.)

### 3.3 `core/` and `conf/` upward import leaks

`docs/reference/architecture.md` documents `core/`+`conf/` as dependency-free.
Verified false:

| Leak                        | Anchor | Target                                                                                                                                   |
| --------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `core/circuit.py`           | `:35`  | `from personalscraper.api._contracts import CircuitOpenError`                                                                            |
| `core/circuit.py`           | `:37`  | `from personalscraper.logger import get_logger`                                                                                          |
| `core/circuit.py`           | `:332` | `from personalscraper.api._contracts import ApiError` (local)                                                                            |
| `core/event_bus.py`         | `:32`  | `from personalscraper.logger import get_logger`                                                                                          |
| `conf/classifier.py`        | `:22`  | `from personalscraper.api._contracts import MediaType`                                                                                   |
| `conf/classifier.py`        | `:25`  | `from personalscraper.logger import get_logger`                                                                                          |
| `conf/models/api_config.py` | `:11`  | `from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry`                       |
| `conf/loader.py`            | `:36`  | `from personalscraper.logger import get_logger`                                                                                          |
| `conf/loader.py`            | `:361` | `from personalscraper.indexer.db import _apply_pragmas` (local)                                                                          |
| `core/app_context.py`       | `:28`  | `from personalscraper.api.metadata.registry import ProviderRegistry` (TYPE_CHECKING only — the documented AppContext boundary, **kept**) |

The structural inversion is in `api/` ↔ `core/`: `api/` consumes `core/`'s
`CircuitBreaker`, yet `core/circuit.py` imports `api/`'s `CircuitOpenError` /
`ApiError`. Symbol definitions:

- `MediaType` — `api/_contracts.py:13`
- `ApiError` — `api/_contracts.py:103`
- `CircuitOpenError` — `api/_contracts.py:156`
- `ThresholdEntry` / `RankingCriterion` / `RankingBonuses` / `RankingConfig` —
  `api/tracker/_ranking.py:18,39,57,69`

**35 files** import from `personalscraper.api._contracts` — moving symbols out of
it **without** a re-export would churn all 35. Re-exports are mandatory.

The `conf/loader.py:361` → `indexer.db._apply_pragmas` and the two `logger`
edges are separate, lower-severity leaks (a config layer reaching into the
indexer DB internals, and the logger being above `core`/`conf`). Scope decision:
see §8 Open Questions Q3 — the **primary** fix is the `api/_contracts` /
`_ranking` inversion; the logger and pragma edges may be deferred or fixed
opportunistically.

### 3.4 The `sorter.file_type` horizontal-coupling edge

`sorter/file_type.py` (183 LOC) exports `VIDEO_EXTENSIONS` (`:16`),
`AUDIO_EXTENSIONS`, `EBOOK_EXTENSIONS`, the `FileType` enum (`:96`),
`is_trailer_filename` (`:128`), and the detection functions `detect_file_type`
(`:162`) / `detect_dir_type` (`:191`).

Verified imports from **outside** `sorter/`: **23 import lines across 10
subpackages** (the report's "11 subpackages" counts the
`library/scanner.py:152` re-export _comment_ line; the live import count is 23):

```
scraper (7):   run.py, movie_service.py, tv_service.py, rename_service.py,
               existing_validator.py, existing_validator_drift.py, _shared.py
enforce (3):   structure_validator.py, coherence_checker.py, file_sanitizer.py
library (3):   analyzer.py, rescraper.py, scanner.py
conf (2):      staging.py, models/staging.py
indexer (2):   scanner/_modes/backfill.py, scanner/_modes/enrich.py
verify (2):    checker.py, run.py
dispatch (1):  run.py
ingest (1):    ingest.py
process (1):   run.py
trailers (1):  scanner.py
```

Most import only the data constants (`VIDEO_EXTENSIONS`, `FileType`,
`is_trailer_filename`); the detection _functions_ (`detect_file_type`,
`detect_dir_type`) are sorter-internal pipeline logic and stay in `sorter`.

### 3.5 Module-size ground truth

`python3 scripts/check-module-size.py` exits 0, two WARN lines only:
`scraper/movie_service.py` **954** non-blank, `library/scanner.py` **855**.
`WARN_LOC = 800`, `BLOCK_LOC = 1000`, `EXCLUDED_FILENAMES = {"__init__.py"}`
(`scripts/check-module-size.py:19,20,22`). The `__init__.py` blanket exclusion
hides `api/metadata/registry/__init__.py` and `indexer/scanner/__init__.py`.
`verify/checker.py` is 713 non-blank (822 total) — near the ceiling; **do not
inline new logic into it**. `scraper/tmdb_client.py` no longer exists (split to
`api/metadata/tmdb.py` + `_tmdb_parsers.py`).

This feature is **net-neutral to slightly-negative** on module size: it
relocates symbols and rewrites imports; no module is expected to grow toward the
ceiling. New modules are small (see §4).

---

## 4. Proposed design

### 4.1 New / modified module map

```
personalscraper/
├── core/
│   ├── event_bus.py         (MODIFY — add schema_version to Event + envelope)
│   ├── circuit.py           (MODIFY — import from core._contracts, not api)
│   ├── _contracts.py        (NEW — neutral home for CircuitOpenError, ApiError, MediaType)
│   └── media_types.py       (NEW — neutral home for VIDEO_EXTENSIONS, FileType, is_trailer_filename)
├── conf/
│   ├── classifier.py        (MODIFY — MediaType from core._contracts)
│   ├── models/api_config.py (MODIFY — Ranking* from core._contracts.ranking or new home)
│   └── models/_ranking.py   (NEW — Ranking* config models relocated DOWN; OR keep in api and re-export — see §4.4)
├── api/
│   ├── _contracts.py        (MODIFY — re-export CircuitOpenError, ApiError, MediaType from core._contracts)
│   └── tracker/_ranking.py  (MODIFY — re-export Ranking* from the new home)
├── sorter/
│   └── file_type.py         (MODIFY — re-export VIDEO_EXTENSIONS/FileType/is_trailer_filename from core.media_types; keep detection funcs)
├── api/metadata/registry/
│   ├── _events.py           (MODIFY — 5 classes become Event subclasses)
│   └── __init__.py          (MODIFY — drop `type: ignore[arg-type]` at :706)
└── events/__init__.py       (MODIFY — eager-import registry._events for auto-registration)

tests/architecture/
├── test_layering.py         (NEW — AST guard: core/ and conf/ never import api/scraper/pipeline/...)
├── test_registry_events_contract.py  (NEW — all _events.py classes subclass Event; envelope round-trip)
└── test_event_schema_version.py      (NEW — Event has schema_version; envelope carries it)
```

### 4.2 Registry events onto the `Event` contract

Rebase the 5 classes in `_events.py` onto `Event`. They become
`@dataclass(frozen=True, kw_only=True)` subclasses (kw_only is required because
`Event`'s inherited fields have defaults and subclass fields must follow the
dataclass field-ordering rule — `kw_only` sidesteps it entirely, matching every
other production event subclass).

```python
# api/metadata/registry/_events.py  (after)
from personalscraper.core.event_bus import Event

@dataclass(frozen=True, kw_only=True)
class ProviderFallbackTriggered(Event):
    capability: str
    from_provider: str
    to_provider: str
    reason: Literal["circuit_open", "network", "empty_result", "other"]
    exc_type: str | None
    item: dict[str, Any]
# ... and the other four, unchanged payload fields, now Event-inheriting.
```

Field payloads are unchanged (`tuple` fields stay tuples — they already satisfy
the frozen invariant per PR cycle-4 finding I5). The emit call at
`registry/__init__.py:706` drops its `# type: ignore[arg-type]` because the
argument is now a real `Event`. `events/__init__.py` adds
`from personalscraper.api.metadata.registry import \_events as \_registry_events

# noqa: F401`so`Event.**init_subclass**` registers them at catalog import.

**Public-path preservation**: the import path
`from personalscraper.api.metadata.registry import ProviderFallbackTriggered`
(and the four siblings) MUST remain valid — `registry/__init__.py` already
re-exports them; verify and keep the re-export.

### 4.3 `schema_version` on the `Event` base

Add a fifth inherited field:

```python
# core/event_bus.py  (Event base)
schema_version: int = 1
```

`event_to_envelope` gains the field automatically (it serializes all dataclass
fields via `event_to_dict`); `event_from_envelope` reconstructs it via
`fields(cls)` (`:115`). No envelope-format change is needed beyond the field
itself appearing inside `"data"`. Decision (per report 05 trade-off): the
version lives **on the `Event` base with a default**, so all 18+5 events inherit
it uniformly and in-process subscribers can reason about event shape — _not_ a
separate envelope-only field. A bump of `schema_version` is reserved for the
first breaking event-shape change after a cross-process consumer exists.

### 4.4 Layering: move shared primitives DOWN

Create `core/_contracts.py` housing the canonical definitions of
`CircuitOpenError`, `ApiError`, and `MediaType`. Re-point:

- `core/circuit.py:35,332` → `from personalscraper.core._contracts import ...`
- `conf/classifier.py:22` → `from personalscraper.core._contracts import MediaType`

Then `api/_contracts.py` **re-exports** the three symbols from
`core._contracts` so all 35 downstream `api._contracts` importers keep working
unchanged:

```python
# api/_contracts.py  (after)
from personalscraper.core._contracts import ApiError, CircuitOpenError, MediaType  # re-export
```

For the `Ranking*` config models (`conf/models/api_config.py:11` →
`api/tracker/_ranking.py`): these are Pydantic config models, conceptually
config-layer, not API-layer. Two options (§8 Q2):

- **(A)** Relocate them to `conf/models/_ranking.py` (their natural home — they
  are parsed from config), and have `api/tracker/_ranking.py` re-export them.
- **(B)** Relocate to `core/_contracts` alongside the others.

Recommended: **(A)** — `Ranking*` are config models; moving them into `conf/`
removes the leak in the correct direction and keeps `core/_contracts` focused on
cross-cutting primitives. `api/tracker/_ranking.py` re-exports for its own
consumers.

`core/_contracts.py` must import **nothing** from `api/`, `conf/`, or any
sibling above `core`. It may import stdlib and `enum`.

**Logger and pragma edges (lower severity)**: `core/event_bus.py:32`,
`core/circuit.py:37`, `conf/*:get_logger`, and `conf/loader.py:361` →
`indexer.db._apply_pragmas`. These are out of the _primary_ scope. The layering
AST guard (§4.6) will treat `personalscraper.logger` as an allowed dependency of
`core`/`conf` (logger is a leaf utility), and will flag the `indexer.db` edge —
see §8 Q3 for whether to fix the pragma edge in this feature.

### 4.5 `media_types` promotion

Create `core/media_types.py` holding `VIDEO_EXTENSIONS`, `FileType`, and
`is_trailer_filename` (and, for completeness, `AUDIO_EXTENSIONS` /
`EBOOK_EXTENSIONS` if any consumer needs them — verify). `core/` is chosen over
`text_utils`/`naming_patterns` because (a) it is the lowest layer, (b) it sits
next to the future capability work, and (c) it has no upward dependencies.

`sorter/file_type.py` keeps `detect_file_type` / `detect_dir_type` /
`_has_tvshow_markers` / `_extension_of` (pipeline-internal detection logic) and
**re-exports** the moved symbols for one transitional state, then the 23
non-`sorter` import lines are rewritten to import from `core.media_types`.
Decision (per report 05): the re-export from `sorter.file_type` is dropped at
the end so `sorter` no longer re-exports shared constants — the acceptance grep
(ACC) asserts zero non-`sorter` imports of `sorter.file_type`.

The detection functions themselves import `VIDEO_EXTENSIONS`/`FileType` from
`core.media_types` (intra-package becomes a downward import — fine).

### 4.6 Architecture guardrail tests

`tests/architecture/test_layering.py` — AST-based (like the existing
`tests/architecture/test_app_context_boundary.py`): parse every module under
`personalscraper/core/` and `personalscraper/conf/`, assert no `import` /
`from ... import` targets `personalscraper.{api,scraper,pipeline,dispatch,verify,library,indexer,trailers}`.
`personalscraper.logger` is allow-listed (leaf utility). The `core/app_context.py`
TYPE_CHECKING registry import is allow-listed (documented boundary). The
`conf/loader.py:361` indexer-db edge is asserted-absent only if §8 Q3 decides to
fix it; otherwise documented as a known exception in the test.

`tests/architecture/test_registry_events_contract.py` — assert each class in
`_events.py` is an `Event` subclass; assert `ProviderFallbackTriggered` (and
each sibling) is in `_EVENT_CLASS_REGISTRY` after `import personalscraper.events`;
assert `event_from_envelope(event_to_envelope(e)) == e` for a constructed
instance of each.

`tests/architecture/test_event_schema_version.py` — assert `hasattr(Event,
"schema_version")`; assert a fresh `Event` subclass instance has
`schema_version == 1`; assert the envelope `"data"` carries the field.

---

## 5. Phasing

Lifecycle: `/implement:feature` → branch `feat/arch-cleanup-2`, SemVer **minor**
(0.16.0 → 0.17.0). Conventional Commits scoped `(arch-cleanup-2)`. Every phase
gate runs **`make lint` + `make test` + `make check`** all green. Every phase
that moves or deletes a symbol runs the **mandatory residual-import grep across
BOTH `personalscraper/` AND `tests/`**. Regression-test-per-bug applies: any bug
surfaced gets a reproducer landed with the fix. No migration scripts.

Phases are independently small; B/C/D can be implemented in any order after A.
Ordering below is the recommended execution order.

### Phase 1 — Event contract: schema_version + registry events (codename scope `arch-cleanup-2`)

- **Objective**: unify the event substrate. Add `schema_version`; bring the 5
  registry events onto `Event`.
- **Modify**: `core/event_bus.py` (add `schema_version: int = 1` to `Event`);
  `api/metadata/registry/_events.py` (5 classes → `Event` subclasses,
  `frozen=True, kw_only=True`); `api/metadata/registry/__init__.py` (drop
  `# type: ignore[arg-type]` at `:706`); `events/__init__.py` (eager-import
  `registry._events`).
- **Create**: `tests/architecture/test_event_schema_version.py`,
  `tests/architecture/test_registry_events_contract.py`.
- **Sub-tasks**: (1) add `schema_version`; (2) rebase the 5 events; (3) register
  in catalog; (4) remove the `type: ignore`; (5) write the two architecture
  tests (one per invariant); (6) residual grep for any code that constructed the
  events positionally (now kw_only) in `personalscraper/` AND `tests/`; fix
  call sites; (7) regression test for any positional-construction breakage
  surfaced.
- **Effort**: M · **Risk**: medium (kw_only flip may break positional
  constructions; the catalog-size invariant test in
  `tests/event_bus/` may need its expected count bumped from 18 to 23 —
  verify and update). · **Dependencies**: none.
- **Gate**: `make lint` + `make test` + `make check` green;
  `python -c "import personalscraper.events"` succeeds;
  `rg -t py 'type: ignore\[arg-type\]' personalscraper/api/metadata/registry/__init__.py`
  returns nothing.

### Phase 2 — Layering: relocate shared primitives down (`(arch-cleanup-2)`)

- **Objective**: remove the `core`/`conf` → `api` inversion.
- **Create**: `core/_contracts.py` (canonical `CircuitOpenError`, `ApiError`,
  `MediaType`); `conf/models/_ranking.py` (relocated `Ranking*` models — Option
  A); `tests/architecture/test_layering.py`.
- **Modify**: `core/circuit.py:35,332` → import from `core._contracts`;
  `conf/classifier.py:22` → import `MediaType` from `core._contracts`;
  `conf/models/api_config.py:11` → import `Ranking*` from `conf/models/_ranking`;
  `api/_contracts.py` → re-export `CircuitOpenError`/`ApiError`/`MediaType` from
  `core._contracts`; `api/tracker/_ranking.py` → re-export `Ranking*` from
  `conf/models/_ranking`.
- **Sub-tasks**: (1) move definitions down; (2) re-point `core`+`conf`
  importers; (3) add `api/` re-exports to preserve all 35 `api._contracts`
  importers + `api.tracker._ranking` importers; (4) write the layering AST guard;
  (5) **check for any existing test that encodes the false acyclic invariant** —
  if a passing layering test already exists it must be updated, not duplicated;
  (6) residual grep across `personalscraper/` AND `tests/` for the moved
  definitions' old anchors.
- **Effort**: M · **Risk**: low (re-exports keep all downstream paths working;
  the only behavioural surface is import resolution — caught by collection).
  · **Dependencies**: none.
- **Gate**: `make lint` + `make test` + `make check` green;
  `rg -t py '^from personalscraper\.(api|scraper|pipeline|dispatch|verify|library|indexer|trailers)' personalscraper/core/ personalscraper/conf/`
  returns nothing (modulo the allow-listed TYPE_CHECKING + logger lines);
  `python -m pytest tests/architecture/test_layering.py -q` passes.

### Phase 3 — `media_types` promotion (`(arch-cleanup-2)`)

- **Objective**: turn `sorter` back into a pure pipeline step.
- **Create**: `core/media_types.py` (`VIDEO_EXTENSIONS`, `FileType`,
  `is_trailer_filename`, plus `AUDIO_EXTENSIONS`/`EBOOK_EXTENSIONS` if needed).
- **Modify**: `sorter/file_type.py` (detection funcs import the moved symbols
  from `core.media_types`; drop the re-export at the end of the phase); the **23
  non-`sorter` import lines** across 10 subpackages → import from
  `core.media_types`.
- **Sub-tasks**: (1) create `core/media_types.py` + move symbols; (2) rewrite
  the 23 import lines (`scraper` 7, `enforce` 3, `library` 3, `conf` 2, `indexer`
  2, `verify` 2, `dispatch` 1, `ingest` 1, `process` 1, `trailers` 1); (3)
  rewrite `sorter/file_type.py` detection funcs to import from the new home; (4)
  drop the transitional re-export; (5) residual grep across `personalscraper/`
  AND `tests/` for `sorter.file_type` imports of the moved symbols — update test
  fixtures/mocks; (6) regression/identity test asserting `VIDEO_EXTENSIONS`
  resolves to the same `frozenset` from `core.media_types`.
- **Effort**: M (S logic, M test-fixture churn) · **Risk**: low ·
  **Dependencies**: none (parallel-able with Phase 1/2).
- **Gate**: `make lint` + `make test` + `make check` green;
  `rg -t py 'from personalscraper.sorter.file_type import' personalscraper/ | rg -v 'personalscraper/sorter/'`
  returns nothing (exit 1).

### Phase 4 — Docs + feature PR (`(arch-cleanup-2)`)

- **Objective**: correct stale docs the enablers touch; finalize.
- **Modify**: `docs/reference/architecture.md` (correct the `core/`+`conf/`
  "depend on nothing" claim — now enforced by `test_layering.py`; add the
  registry-events-on-`Event` note; document `schema_version`);
  `docs/reference/event-bus.md` (registry events now in the catalog;
  `schema_version` field); `CHANGELOG.md` 0.17.0 entry; `ROADMAP.md`
  (mark `arch-cleanup-2` prerequisites satisfied where applicable).
- **Effort**: S · **Risk**: low · **Dependencies**: Phases 1-3.
- **Gate**: `make check` green; all ACCEPTANCE criteria PASS.
- **Auto-invoked**: `/implement:feature-pr` then `/implement:pr-review`
  (squash merge).

### 5.1 Phase / risk matrix

| Phase | Objective                       | Effort | Risk   | LOC delta (est.) |
| ----- | ------------------------------- | ------ | ------ | ---------------- |
| 1     | Event contract + schema_version | M      | medium | +90 / -8         |
| 2     | Layering relocation             | M      | low    | +120 / -20       |
| 3     | media_types promotion           | M      | low    | +90 / -40        |
| 4     | Docs + PR                       | S      | low    | +60 / -20        |

No module is expected to cross 800 LOC; the new modules are small
(`core/_contracts.py` ~60 LOC, `core/media_types.py` ~70 LOC,
`conf/models/_ranking.py` ~70 LOC moved). The `__init__.py` size blind spot is
irrelevant here — nothing is added to a package `__init__.py`.

---

## 6. Acceptance criteria (SH-16 — executable, with expected output)

```bash
# ACC-01 — global gate green
make check
# EXPECT: exit 0

# ACC-02 — Event base carries schema_version
python -c "from personalscraper.core.event_bus import Event; assert hasattr(Event, 'schema_version'); print('ok')"
# EXPECT: exit 0; stdout: ok

# ACC-03 — all 5 registry events are real Events
python -c "
import personalscraper.events  # noqa
from personalscraper.core.event_bus import Event
from personalscraper.api.metadata.registry import _events as e
names = ['ProviderFallbackTriggered','ProviderExhaustedEvent','LockedCapabilityUnresolved','RegistryFanOutCompleted','RegistryBootValidated']
assert all(issubclass(getattr(e, n), Event) for n in names)
print('ok')
"
# EXPECT: exit 0; stdout: ok

# ACC-04 — registry events round-trip through the envelope + are catalog-registered
python -c "
import personalscraper.events  # noqa
from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
assert 'ProviderFallbackTriggered' in _EVENT_CLASS_REGISTRY
print('ok')
"
# EXPECT: exit 0; stdout: ok

# ACC-05 — the emit type:ignore is gone
rg -t py 'type: ignore\[arg-type\]' personalscraper/api/metadata/registry/__init__.py
# EXPECT: no output, exit 1

# ACC-06 — registry events public import path preserved
python -c "from personalscraper.api.metadata.registry import ProviderFallbackTriggered, RegistryBootValidated; print('ok')"
# EXPECT: exit 0; stdout: ok

# ACC-07 — core/ and conf/ no longer import upward (logger + TYPE_CHECKING boundary allow-listed)
rg -t py '^from personalscraper\.(api|scraper|pipeline|dispatch|verify|library|indexer|trailers)' personalscraper/core/ personalscraper/conf/ | rg -v 'app_context.py' | rg -v 'TYPE_CHECKING'
# EXPECT: no output, exit 1

# ACC-08 — layering guard test passes
python -m pytest tests/architecture/test_layering.py -q
# EXPECT: exit 0; "passed" in output

# ACC-09 — api._contracts re-export keeps the legacy path working
python -c "from personalscraper.api._contracts import CircuitOpenError, ApiError, MediaType; print('ok')"
# EXPECT: exit 0; stdout: ok

# ACC-10 — Ranking* re-export keeps the legacy api path working
python -c "from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry; print('ok')"
# EXPECT: exit 0; stdout: ok

# ACC-11 — sorter.file_type no longer imported outside sorter/
rg -t py 'from personalscraper.sorter.file_type import' personalscraper/ | rg -v 'personalscraper/sorter/'
# EXPECT: no output, exit 1

# ACC-12 — media_types is the new home and VIDEO_EXTENSIONS is identical
python -c "
from personalscraper.core.media_types import VIDEO_EXTENSIONS, FileType, is_trailer_filename
assert isinstance(VIDEO_EXTENSIONS, frozenset) and 'mkv' in VIDEO_EXTENSIONS
print('ok')
"
# EXPECT: exit 0; stdout: ok

# ACC-13 — architecture contract tests pass
python -m pytest tests/architecture/test_registry_events_contract.py tests/architecture/test_event_schema_version.py -q
# EXPECT: exit 0; "passed" in output

# ACC-14 — module-size guardrail unchanged (still only the two known WARNs, exit 0)
python3 scripts/check-module-size.py
# EXPECT: exit 0; exactly two WARN lines (movie_service.py, library/scanner.py)

# ACC-15 — version bump
cat VERSION
# EXPECT: exit 0; stdout: 0.17.0

# ACC-16 — CHANGELOG entry
grep -c '^## \[0.17.0\]' CHANGELOG.md
# EXPECT: exit 0; stdout: 1

# ACC-17 — smoke import
python -c "import personalscraper; print('ok')"
# EXPECT: exit 0; stdout: ok
```

---

## 7. Risks & mitigations

| #   | Risk                                                                                                                        | Mitigation                                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-1 | `kw_only` flip on the 5 registry events breaks any positional construction in tests/prod.                                   | Residual grep for positional construction across `personalscraper/` AND `tests/`; the emit sites already use kwargs. Regression test per breakage. |
| R-2 | The event-catalog-size invariant test (`tests/event_bus/`) hard-codes 18 production events; adding 5 makes it 23 and fails. | Phase 1 sub-task explicitly locates and updates the expected count. This is an expected, not surprising, change.                                   |
| R-3 | Moving `CircuitOpenError`/`MediaType` out of `api._contracts` breaks one of the 35 importers if a re-export is missed.      | Re-export is mandatory and asserted by ACC-09. `make test` collection catches any missed path immediately (ERROR, not FAILED).                     |
| R-4 | A pre-existing test encodes the _false_ acyclic invariant and contradicts the new `test_layering.py`.                       | Phase 2 sub-task (5) greps for existing layering tests and updates rather than duplicates.                                                         |
| R-5 | `core/_contracts.py` accidentally imports something above `core` (re-introducing a cycle).                                  | `test_layering.py` covers `core/` including `_contracts.py`; ACC-08 enforces.                                                                      |
| R-6 | The `sorter.file_type` 23-line rewrite churns many test mocks/fixtures.                                                     | Effort estimate accounts for M-level fixture churn; residual grep in `tests/` is mandatory (Phase 3 sub-task 5).                                   |
| R-7 | `schema_version` default value chosen wrong (0 vs 1).                                                                       | Default `1` (events are version 1 today). Documented; bumped only on the first breaking shape change after a cross-process consumer exists.        |
| R-8 | Scope creep into `lib-fold` / `multi-filesystem` / DI container.                                                            | Hard non-goals (§2). The orchestrator/`info.py` DI debt is noted, not touched.                                                                     |

---

## 8. Open questions (decisions for the user)

1. **`schema_version` default**: confirm `1` (recommended) vs `0`. The field is
   additive; the value only matters at the first future bump.

2. **`Ranking*` relocation target** (§4.4): Option A — move to
   `conf/models/_ranking.py` (config-model home, recommended) — vs Option B —
   `core/_contracts.py`. Which home?

3. **Lower-severity leak scope**: do we fix the `conf/loader.py:361` →
   `indexer.db._apply_pragmas` edge in this feature (it inverts config→indexer),
   or defer it? The `personalscraper.logger` edges (`core`/`conf` importing the
   logger) are proposed as **allow-listed** (logger is a leaf utility) rather
   than fixed — confirm this is acceptable, or specify a logger relocation.

4. **`media_types` home**: `core/media_types.py` (recommended — lowest layer,
   next to future capability work) vs folding into an existing shared family
   (`text_utils` / `naming_patterns`). Either satisfies ACC-11/ACC-12.

5. **DI container overlap**: report 05 and `ROADMAP.md:236` note a
   `ServiceContainer` _could_ land in `arch-cleanup-2`. This DESIGN **excludes**
   it (keeps the feature small and low-risk). Confirm DI stays a separate P3
   feature, or expand scope to include the orchestrator-injection + `info.py`
   fix.

---

## 9. References

- **Source analysis**: `docs/analysis/05-architecture-improvement-roadmap.md`
  (the foundation — §2.2 layering, §2.3 sorter edge, §2.4 registry events, §2.8
  module size; problem table P-1…P-4; Features A–H sequencing). This DESIGN
  scopes `arch-cleanup-2` to report 05's Features B (media-types), C
  (layer-contracts), and D (event-unify) — the prerequisite enablers — and
  explicitly excludes E (`lib-fold`), F (`fs-capability`), G
  (`service-container`), and H (`service-api`/`web-ui`).
- **ROADMAP entry**: `ROADMAP.md:11` (P1 — Architecture Cleanup Round 2). Sibling
  prerequisites: `ROADMAP.md:83` (Web Management UI), `:105` (Watcher Service),
  `:167` (Web UI Registry Consumer), `:236` (P3 DI Container overlap).
- **Sibling feature designs** (separate features, depend on this one):
  `docs/features/lib-fold/DESIGN.md` (to be written —
  `docs/analysis/01-library-indexer-consolidation.md`),
  `docs/features/multi-filesystem/DESIGN.md` (to be written —
  `docs/analysis/04-filesystem-decoupling-macfuse-ntfs.md`).
- **Structural template**: `docs/features/registry/DESIGN.md` (the shipped
  Provider Registry design; the 5 events being unified here were introduced by
  that feature, §7.4).
- **Code anchors** (verified 2026-05-28 @ HEAD `1c4636eb`):
  `api/metadata/registry/_events.py:12,39,56,71,89`;
  `api/metadata/registry/__init__.py:699,706`;
  `core/event_bus.py:96,101,204-229,242`;
  `subscribers/debug_log.py:25`; `events/__init__.py`;
  `core/circuit.py:35,37,332`; `conf/classifier.py:22,25`;
  `conf/models/api_config.py:11`; `conf/loader.py:361`;
  `api/_contracts.py:13,103,156`; `api/tracker/_ranking.py:18,39,57,69`;
  `sorter/file_type.py:16,96,128,162,191`;
  `scripts/check-module-size.py:19,20,22`;
  `indexer/schema.py:416,605`; `indexer/outbox/_drain.py:146`.
- **Project rules** (CLAUDE.md): SH-16 (executable ACCEPTANCE criteria);
  module-size soft 800 / hard 1000 with `__init__.py` exclusion;
  `feedback_no_backcompat_before_v1` (no migration scripts pre-1.0);
  `feedback_regression_test_per_bug` (reproducer per bug);
  `feedback_rg_type_filter_mandatory` (every `rg` carries a type/glob filter).
- **Reference docs**: `docs/reference/event-bus.md` (Event/envelope contract,
  fail-soft emit); `docs/reference/architecture.md` (layering — to be corrected
  in Phase 4); `docs/reference/logging.md` (logger conventions).
