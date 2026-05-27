# Phase 5 — PR fixes cycle 1

Generated automatically by `/implement:pr-review` after the 4-agent review of PR #27.
This phase addresses 6 critical + 4 major findings retained after filtering against DESIGN.md.

## Gate

- Phase 4 milestone complete (`cf523b5` → `10bdc89`).
- PR #27 CI green on `feat/registry @ 31c6516`.
- 4 review agents returned findings (code-reviewer, pr-test-analyzer, silent-failure-hunter, type-design-analyzer).

## Goal

Land 6 critical fixes and 4 major fixes from cycle 1 review, in a coherent set of small commits. Minor findings are documented as follow-up issues. ACC-02 grep is tightened to match DESIGN §2 goal 7 (instantiation, not all references).

## Scope

- `personalscraper/api/metadata/registry/__init__.py` — populate `fan_out`'s `attempted` list, narrow `cross_ref` exception catch, rename `Named.name` → `Named.provider_name` for protocol consistency.
- `personalscraper/api/metadata/registry/_validation.py` — fix DFS cycle false-positive (parent-tracking).
- `personalscraper/api/metadata/registry/_factory.py` — `_eligible` allowlist for providers without `.circuit`.
- `personalscraper/conf/models/providers.py` (no change expected — verify).
- `personalscraper/cli_helpers/__init__.py` — add `try/finally: app_context.provider_registry.close()` in `per_step_boundary`.
- `personalscraper/commands/library/scan.py` — log `library_backfill_provider_unavailable` WARNING on UnknownProviderError fail-soft.
- `personalscraper/api/_contracts.py` OR `personalscraper/api/metadata/registry/__init__.py` — resolve `ProviderName` collision (rename registry's NewType to `RegistryProviderName` OR drop NewType and use Enum from `_contracts.py`).
- `docs/features/registry/ACCEPTANCE.md` — tighten ACC-02 grep precision.
- Tests: update assertions touching renamed `.name` attribute, add coverage for DFS 2-provider non-cycle, fan_out attempted population, cross_ref narrow catch, scan.py log emission, per_step_boundary close.

## Sub-phases

### 5.1 — `Named` Protocol attribute reconciliation

Rename `Named.name` → `Named.provider_name` to match the existing `provider_name: ClassVar[str]` declared on every concrete provider (TMDBClient, TVDBClient, IMDbClient, OMDbAdapter, TraktClient, RottenTomatoesClient).

- `personalscraper/api/metadata/registry/__init__.py`: change Protocol field + every reference (`.name` → `.provider_name`) inside ProviderStatus construction (`status()`), log fields (`registry_provider_skip`, `registry_provider_fail`, `registry_locked_xref`, `registry_locked_unresolved`), event payloads.
- Remove the `# type: ignore[return-value]` on `get()` and `providers_for()` — should now type-check cleanly.
- Update tests where `Named.name` is asserted.

Commit: `fix(registry): align Named protocol with provider_name ClassVar`

### 5.2 — Resolve `ProviderName` double-definition

Two incompatible types share the same name:

- `api/_contracts.py:62` — `class ProviderName(str, Enum)` (closed enum)
- `api/metadata/registry/__init__.py:76` — `ProviderName = NewType("ProviderName", str)`

Drop the registry's `NewType` and import the Enum from `api/_contracts.py`. Update all references:

- `ProviderMatch.provider` → `ProviderName` (the Enum)
- `AttemptOutcome.provider` → `ProviderName` (the Enum)
- `ProviderStatus.name` (or `.provider_name` per 5.1) → `ProviderName` (the Enum)
- `ConfigIssue.provider` → `ProviderName | None`
- All construction sites (`ProviderName(provider.provider_name)` becomes `ProviderName(<enum value>)`).

If the closed Enum doesn't accept arbitrary string values (only the declared members), provider name lookup `ProviderName(name_str)` raises `ValueError` for unknown — that's a fail-loud win.

Commit: `fix(registry): unify ProviderName on the api/_contracts.py Enum (drop NewType)`

### 5.3 — Fix `_check_idcrossref_cycles` 2-provider false-positive

`_validation.py:265-332` DFS reports a cycle when 2 IDCrossRef providers exist (`A→B→A` via bidirectional implicit edges).

Fix: track the parent in the DFS recursion, skip the immediate-parent edge so `A→B→A` is not flagged. Add a test asserting NO `idcrossref_cycle` issue for the 2-provider config (`IDCrossRef: { tmdb: 1, tvdb: 2 }`).

Commit: `fix(registry): DFS cycle detection ignores immediate-parent edge`

### 5.4 — `fan_out` populates `attempted` list

`__init__.py:418-431` currently emits `RegistryFanOutCompleted(attempted=[], ...)` always. Populate with per-provider `AttemptOutcome` (reason="circuit_open" for filtered-out, reason="other" for eligible).

Add a test asserting `attempted` is non-empty when some providers are filtered.

Commit: `fix(registry): populate fan_out RegistryFanOutCompleted.attempted with per-provider AttemptOutcome`

### 5.5 — Narrow `cross_ref` exception catch

`__init__.py:558-562` swallows all exceptions silently. Narrow to `(NetworkError, CircuitOpenError)` and log `registry_cross_ref_failed` WARNING with provider/target/exc_type. Other exceptions propagate.

Add a test asserting that a non-transport exception (e.g. `KeyError`) raised by the provider's `get_cross_refs()` does propagate.

Commit: `fix(registry): narrow cross_ref exception catch + log on transport failure`

### 5.6 — Registry leak in `per_step_boundary`

`cli_helpers/__init__.py:74-98` constructs ProviderRegistry but doesn't close it on exception/exit. Add `try/finally: app_context.provider_registry.close()`.

Add a test asserting close() is called via a spy fixture.

Commit: `fix(registry): close ProviderRegistry on per_step_boundary exit`

### 5.7 — `_eligible` strict for unknown provider shapes

`_factory.py:225-227` returns True for providers without `.circuit`. Refactor to allowlist:

```python
_NO_CIRCUIT_ALLOWLIST = frozenset({"imdb", "rotten_tomatoes"})  # documented façades
def _eligible(provider):
    circuit = getattr(provider, "circuit", None)
    if circuit is None:
        name = getattr(provider, "provider_name", None)
        return name in _NO_CIRCUIT_ALLOWLIST
    ...
```

Fakes in tests stay eligible via `MagicMock` exposing `.circuit.state = "CLOSED"`.

Commit: `fix(registry): _eligible strict — explicit allowlist for no-circuit providers`

### 5.8 — `commands/library/scan.py` log silent UnknownProviderError skip

`scan.py:438-453` currently does `tmdb_client = None` on UnknownProviderError without logging. Add `log.warning("library_backfill_provider_unavailable", provider="tmdb")` per branch.

Add a test asserting the WARNING is emitted via `caplog`.

Commit: `fix(registry): log library-backfill provider-unavailable fallback`

### 5.9 — Tighten ACC-02 in ACCEPTANCE.md

ACC-02 grep `rg -e TMDBClient -e TVDBClient` is too broad (catches TYPE_CHECKING + cast() + docstrings). DESIGN §2 goal 7 says "instantiation" — change to `rg -e 'TMDBClient\(' -e 'TVDBClient\('` (constructor calls only).

Commit: `docs(registry): tighten ACC-02 grep to constructor calls (matches DESIGN §2 goal 7)`

## Phase gate

- `make check` exit 0.
- All 4 review-cycle critical findings closed (verifiable per test).
- ACC-02 PASS strictly with the new (tighter) grep.
- Registry suite: 40+ unit + 28+ integration tests still pass.
- Architecture tests: 67 pass.
- Characterization tests: 6 pass.
- New tests added per sub-phase (DFS 2-node, fan_out attempted, cross_ref narrow, per_step close, scan.py log).

## ACC criteria touched

- ACC-01 (make check) — must remain PASS.
- ACC-02 (TMDB/TVDB outside api/metadata/) — tightened in 5.9.
- ACC-07 (registry unit test count) — likely increases beyond 40; re-pin if needed.
- ACC-13 (characterization tests) — must remain PASS.

## On gate failure

If the phase gate fails, revert sub-phase commits since last gate (`git revert <sha>`), investigate root cause, re-run `/implement:pr-review`. Do not proceed to cycle 2 without a green gate on cycle 1 fixes.
