# Phase 4 — Docs + feature PR

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> or `superpowers:executing-plans` to implement this phase step-by-step.

**Goal:** Correct the stale documentation that the earlier phases invalidated, bump the
version to 0.17.0, write the CHANGELOG entry, and fire the feature PR flow.

**Architecture:** Documentation-only changes plus VERSION and CHANGELOG. No source code
touched. After the gate passes, `/implement:feature-pr` is auto-invoked to push the branch,
create the PR, and poll CI; then `/implement:pr-review` runs the review + squash merge cycle.

**Tech Stack:** Markdown, grep, make.

---

## Gate (pre-conditions — all of Phases 1–3 must be complete)

```bash
# Phase 1 gate
python -c "from personalscraper.core.event_bus import Event; assert hasattr(Event, 'schema_version')"
python -m pytest tests/architecture/test_event_schema_version.py tests/architecture/test_registry_events_contract.py -q
# EXPECT: passed

# Phase 2 gate
python -m pytest tests/architecture/test_layering.py -q
# EXPECT: passed

# Phase 3 gate
rg -t py "from personalscraper.sorter.file_type import" personalscraper/ | rg -v 'personalscraper/sorter/'
# EXPECT: no output (exit 1)

# Overall
make check
# EXPECT: exit 0
```

---

## Files

| Action | Path                             |
| ------ | -------------------------------- |
| Modify | `docs/reference/architecture.md` |
| Modify | `docs/reference/event-bus.md`    |
| Modify | `CHANGELOG.md`                   |
| Modify | `ROADMAP.md`                     |
| Modify | `VERSION`                        |

---

## Sub-phase 4.1 — Update `docs/reference/architecture.md`

- [ ] **Step 4.1.1: Locate the stale claims in `architecture.md`**

```bash
grep -n "depend on nothing\|core.*depend\|conf.*depend\|no.*dependency\|sorter.*file_type\|file_type.*sorter" \
    docs/reference/architecture.md | head -20
```

- [ ] **Step 4.1.2: Correct the `core/`+`conf/` "depend on nothing" claim**

Find the section that asserts `core/` and `conf/` have no internal project dependencies.
Replace with wording that reflects the enforced invariant:

```markdown
<!-- BEFORE (approximate — match the exact text found in Step 4.1.1): -->

`core/` and `conf/` depend on nothing in the project.

<!-- AFTER: -->

`core/` and `conf/` are the lowest layers and must not import from `api/`,
`scraper/`, `pipeline/`, `dispatch/`, `verify/`, `library/`, `indexer/`, or
`trailers/` at runtime. `personalscraper.logger` is allow-listed as a leaf
utility. The `core/app_context.py` TYPE_CHECKING import of `ProviderRegistry`
is the documented AppContext boundary (tested separately). This invariant is
enforced by `tests/architecture/test_layering.py` (arch-cleanup-2, Phase 2).
```

- [ ] **Step 4.1.3: Add the registry events note**

Find the section describing the event catalog or registry. Add:

```markdown
### Registry events on the `Event` contract

The five provider-registry events (`ProviderFallbackTriggered`,
`ProviderExhaustedEvent`, `LockedCapabilityUnresolved`,
`RegistryFanOutCompleted`, `RegistryBootValidated`) are full `Event`
subclasses as of arch-cleanup-2 (v0.17.0). They are auto-registered in
`_EVENT_CLASS_REGISTRY`, envelope-round-trippable, and delivered to
base-`Event` subscribers. The event catalog count is 23.
```

- [ ] **Step 4.1.4: Document `core/media_types.py` in the module map**

Find the module map table or list that describes `core/` contents. Add an entry:

```markdown
| `core/media_types.py` | Shared media-type constants (`VIDEO_EXTENSIONS`, `FileType`, `is_trailer_filename`). Canonical home — promoted from `sorter/file_type.py` in arch-cleanup-2. |
```

And update the `sorter/` entry to note that `sorter/file_type.py` now contains only
detection functions (`detect_file_type`, `detect_dir_type`) and imports shared
constants from `core.media_types`.

- [ ] **Step 4.1.5: Document `core/_contracts.py` in the module map**

```markdown
| `core/_contracts.py` | Core-layer primitive contracts: `MediaType`, `ApiError`, `CircuitOpenError`. Re-exported from `api/_contracts.py` for backward compatibility. |
```

- [ ] **Step 4.1.6: Commit architecture.md changes**

```bash
git add -f docs/reference/architecture.md
git commit -m "docs(arch-cleanup-2): update architecture.md — layering invariant enforced, schema_version, media_types"
```

---

## Sub-phase 4.2 — Update `docs/reference/event-bus.md`

- [ ] **Step 4.2.1: Locate stale event catalog table in `event-bus.md`**

```bash
grep -n "registry\|ProviderFallback\|schema_version\|catalog\|18\b" docs/reference/event-bus.md | head -20
```

- [ ] **Step 4.2.2: Add the 5 registry events to the catalog table**

Find the event catalog table (listing the 18 production events). Add 5 new rows:

```markdown
| `ProviderFallbackTriggered` | `api.metadata.registry._events` | Chain moved to next provider |
| `ProviderExhaustedEvent` | `api.metadata.registry._events` | All chain providers failed |
| `LockedCapabilityUnresolved` | `api.metadata.registry._events` | `locked()` cannot bind via IDCrossRef |
| `RegistryFanOutCompleted` | `api.metadata.registry._events` | `fan_out` returned (success or failure) |
| `RegistryBootValidated` | `api.metadata.registry._events` | Registry boot completed successfully |
```

Update any catalog-count reference from 18 to 23.

- [ ] **Step 4.2.3: Document `schema_version`**

Find the `Event` base field table or description. Add:

```markdown
| `schema_version` | `int` | `1` | Schema version — bumped on the first breaking event-shape change after a cross-process consumer exists. Default `1` for all events in v0.17.0. |
```

- [ ] **Step 4.2.4: Commit event-bus.md changes**

```bash
git add -f docs/reference/event-bus.md
git commit -m "docs(arch-cleanup-2): update event-bus.md — 5 registry events in catalog, schema_version field"
```

---

## Sub-phase 4.3 — VERSION bump + CHANGELOG entry

- [ ] **Step 4.3.1: Bump VERSION to 0.17.0**

```bash
# Read the current content first, then write:
cat VERSION   # should show 0.16.0
```

Write `0.17.0\n` to `VERSION`.

- [ ] **Step 4.3.2: Verify the bump**

```bash
cat VERSION
# EXPECT: 0.17.0
```

- [ ] **Step 4.3.3: Add the CHANGELOG entry**

Find the top of `CHANGELOG.md` (after the header). Add a new section before the
existing latest entry:

```markdown
## [0.17.0] — 2026-05-29

### Added

- `core/_contracts.py`: canonical home for `CircuitOpenError`, `ApiError`, `MediaType`
  (re-exported from `api/_contracts.py` for backward compatibility).
- `conf/models/_ranking.py`: canonical home for `ThresholdEntry`, `RankingCriterion`,
  `RankingBonuses`, `RankingConfig` (re-exported from `api/tracker/_ranking.py`).
- `core/media_types.py`: canonical home for `VIDEO_EXTENSIONS`, `FileType`,
  `is_trailer_filename` (promoted from `sorter/file_type.py`).
- `schema_version: int = 1` field on the `Event` base class — threads through
  `event_to_envelope` / `event_from_envelope`.
- `tests/architecture/test_layering.py`: AST-based guard enforcing that `core/`
  and `conf/` do not import upward into `api/` or upper layers.
- `tests/architecture/test_event_schema_version.py`: invariant tests for `schema_version`.
- `tests/architecture/test_registry_events_contract.py`: invariant tests asserting all
  5 registry events subclass `Event` and are envelope-round-trippable.

### Changed

- 5 provider-registry events (`ProviderFallbackTriggered`, `ProviderExhaustedEvent`,
  `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated`)
  now subclass `Event` (`frozen=True, kw_only=True`); auto-registered in
  `_EVENT_CLASS_REGISTRY`; production event catalog grows from 18 to 23.
- `sorter/file_type.py` no longer exports shared constants — `detect_file_type` and
  `detect_dir_type` remain; 23 non-`sorter` import lines rewritten to `core.media_types`.
- `core/circuit.py` and `conf/classifier.py` import from `core._contracts` instead of
  `api._contracts`; `conf/models/api_config.py` imports from `conf/models/_ranking`.

### Fixed

- Removed `# type: ignore[arg-type]` suppression on registry event `emit()` call
  (`api/metadata/registry/__init__.py`) — no longer needed now that events subclass `Event`.

### Architecture

- Closes P1 roadmap prerequisite for Web Management UI (`ROADMAP.md:83`),
  Watcher Service (`:105`), and Web UI Registry Consumer (`:167`).
```

- [ ] **Step 4.3.4: Commit version bump + CHANGELOG**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore(arch-cleanup-2): bump version to 0.17.0; add CHANGELOG entry"
```

---

## Sub-phase 4.4 — ROADMAP.md update

- [ ] **Step 4.4.1: Mark arch-cleanup-2 prerequisites satisfied**

```bash
grep -n "arch-cleanup-2\|Architecture Cleanup Round 2\|0.17.0" ROADMAP.md | head -20
```

Find the `arch-cleanup-2` entry (around `ROADMAP.md:11`) and the three roadmap items
that list it as a prerequisite (`:83`, `:105`, `:167`). Update their status or
prerequisite notation to indicate the prerequisite is now satisfied.

- [ ] **Step 4.4.2: Commit ROADMAP.md**

```bash
git add -f ROADMAP.md
git commit -m "docs(arch-cleanup-2): mark arch-cleanup-2 prerequisites satisfied in ROADMAP.md"
```

---

## Sub-phase 4.5 — Full acceptance suite and PR

- [ ] **Step 4.5.1: Run the full acceptance suite**

```bash
# ACC-01
make check
# EXPECT: exit 0

# ACC-02
python -c "from personalscraper.core.event_bus import Event; assert hasattr(Event, 'schema_version'); print('ok')"
# EXPECT: ok

# ACC-03
python -c "
import personalscraper.events
from personalscraper.core.event_bus import Event
from personalscraper.api.metadata.registry import _events as e
names = ['ProviderFallbackTriggered','ProviderExhaustedEvent','LockedCapabilityUnresolved','RegistryFanOutCompleted','RegistryBootValidated']
assert all(issubclass(getattr(e, n), Event) for n in names)
print('ok')
"
# EXPECT: ok

# ACC-04
python -c "
import personalscraper.events
from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
assert 'ProviderFallbackTriggered' in _EVENT_CLASS_REGISTRY
print('ok')
"
# EXPECT: ok

# ACC-05
rg -t py 'type: ignore\[arg-type\]' personalscraper/api/metadata/registry/__init__.py
# EXPECT: no output, exit 1

# ACC-06
python -c "from personalscraper.api.metadata.registry import ProviderFallbackTriggered, RegistryBootValidated; print('ok')"
# EXPECT: ok

# ACC-07
rg -t py '^from personalscraper\.(api|scraper|pipeline|dispatch|verify|library|indexer|trailers)' \
    personalscraper/core/ personalscraper/conf/ | rg -v 'app_context.py' | rg -v 'TYPE_CHECKING'
# EXPECT: no output, exit 1

# ACC-08
python -m pytest tests/architecture/test_layering.py -q
# EXPECT: passed

# ACC-09
python -c "from personalscraper.api._contracts import CircuitOpenError, ApiError, MediaType; print('ok')"
# EXPECT: ok

# ACC-10
python -c "from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry; print('ok')"
# EXPECT: ok

# ACC-11
rg -t py 'from personalscraper.sorter.file_type import' personalscraper/ | rg -v 'personalscraper/sorter/'
# EXPECT: no output, exit 1

# ACC-12
python -c "
from personalscraper.core.media_types import VIDEO_EXTENSIONS, FileType, is_trailer_filename
assert isinstance(VIDEO_EXTENSIONS, frozenset) and 'mkv' in VIDEO_EXTENSIONS
print('ok')
"
# EXPECT: ok

# ACC-13
python -m pytest tests/architecture/test_registry_events_contract.py tests/architecture/test_event_schema_version.py -q
# EXPECT: passed

# ACC-14
python3 scripts/check-module-size.py
# EXPECT: exit 0; exactly two WARN lines (movie_service.py, library/scanner.py)

# ACC-15
cat VERSION
# EXPECT: 0.17.0

# ACC-16
grep -c '^## \[0.17.0\]' CHANGELOG.md
# EXPECT: 1

# ACC-17
python -c "import personalscraper; print('ok')"
# EXPECT: ok
```

- [ ] **Step 4.5.2: If any criterion fails — fix it before continuing**

Each failing criterion maps back to a specific phase:

- ACC-02/03/04/05/06/13 → Phase 1
- ACC-07/08/09/10 → Phase 2
- ACC-11/12 → Phase 3
- ACC-15/16 → this phase (version/changelog)

Fix the root cause in the relevant phase's files, commit with scope `(arch-cleanup-2)`,
then re-run the full suite.

- [ ] **Step 4.5.3: Phase gate commit**

```bash
make lint && make test && make check
# All must exit 0 before this commit.

git add -A   # review staged changes — should be docs only at this point
git commit -m "chore(arch-cleanup-2): phase 4 gate — docs, version bump, full acceptance suite green"
```

---

## Phase Gate

```bash
make check
# EXPECT: exit 0

cat VERSION
# EXPECT: 0.17.0

grep -c '^## \[0.17.0\]' CHANGELOG.md
# EXPECT: 1

python -m pytest tests/architecture/ -q
# EXPECT: all passed
```

---

## Acceptance Criteria (Phase 4 — full suite)

All 17 ACC criteria from DESIGN §6 must pass. See Step 4.5.1 for the complete
executable suite. Summary of Phase 4-specific checks:

```bash
# ACC-01 — global gate green
make check
# EXPECT: exit 0

# ACC-15 — version bump
cat VERSION
# EXPECT: 0.17.0

# ACC-16 — CHANGELOG entry
grep -c '^## \[0.17.0\]' CHANGELOG.md
# EXPECT: 1

# ACC-17 — smoke import
python -c "import personalscraper; print('ok')"
# EXPECT: ok
```

---

## PR Finalization

After all 17 ACC criteria pass and the phase gate commit is in place:

```bash
# Auto-invoked by /implement:phase at the last phase:
# /implement:feature-pr  → local gate + push branch + create PR + poll CI to green
# /implement:pr-review   → review + max-3 fix cycles + squash merge
```

If invoking manually:

```bash
gh pr create \
  --title "feat(arch-cleanup-2): architecture cleanup round 2 — event contract, layering, media_types" \
  --body "Closes the four architectural defects blocking web-facing roadmap items.
See docs/features/arch-cleanup-2/DESIGN.md for full rationale and acceptance criteria."
```
