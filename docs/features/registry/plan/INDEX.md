# Provider Registry — Implementation Plan Index

> **Feature codename**: `registry`
> **Version bump**: 0.15.1 → 0.16.0 (minor)
> **Branch**: `feat/registry`
> **Design**: `docs/features/registry/DESIGN.md`

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan phase-by-phase.
> Each sub-phase = one commit. Scope = `(registry)`.

---

## Phases table

| #   | Phase                                     | File                                      | Status |
| --- | ----------------------------------------- | ----------------------------------------- | ------ |
| 0   | New types, shells, characterization tests | phase-00-types-shells-characterization.md | [ ]    |
| 1   | Boot wiring + chain migration             | phase-01-boot-wiring-chain.md             | [ ]    |
| 2   | Scraper locked migration                  | phase-02-scraper-locked.md                | [ ]    |
| 3   | Out-of-scraper consumers                  | phase-03-out-of-scraper.md                | [ ]    |
| 4   | Cleanup, observability, docs              | phase-04-cleanup-obs-docs.md              | [ ]    |

---

## Sub-phase map

| Phase | Sub-phase | Description                                                        |
| ----- | --------- | ------------------------------------------------------------------ |
| 0     | 0.1       | Error types + event dataclasses + semantics map                    |
| 0     | 0.2       | Data structures + `ProviderRegistry` public shell                  |
| 0     | 0.3       | `_factory.py` + `_validation.py` + config template                 |
| 0     | 0.4       | Unit tests (TDD — all ~45 tests, DESIGN §8.2)                      |
| 0     | 0.5a      | Registry core: chain / get / operations / status / providers_for   |
| 0     | 0.5b      | Registry fan_out / locked + cross_ref + LockedProvider mechanics   |
| 0     | 0.5c      | Boot validation + factory + cleanup discipline                     |
| 0     | 0.6       | Characterization tests + bad_providers fixture + baseline          |
| 0     | 0.7       | Pin baseline values into IMPLEMENTATION.md and ACCEPTANCE.md       |
| 1     | 1.1       | Pipeline boot wiring                                               |
| 1     | 1.2       | Atomic: orchestrator chain migration + E2E mock pivot              |
| 1     | 1.3       | Characterization equivalence gate (verification only, no commit)   |
| 2     | 2.1       | `artwork.py` + `trailer_finder.py` locked migration                |
| 2     | 2.2       | `keywords_cache.py` + `classifier.py` locked migration             |
| 2     | 2.3a      | `existing_validator.py` + `confidence.py` migration                |
| 2     | 2.3b      | `_tvdb_convert.py` + `scraper.py` cleanup (with pre-flight check)  |
| 2     | 2.4       | fan_out(RatingProvider) code path wired + unit tests               |
| 2     | 2.5       | Integration tests for registry semantics (~15 HTTP-level tests)    |
| 2     | 2.6       | Re-run characterization equivalence (verification only, no commit) |
| 3     | 3.1       | `trailers/orchestrator.py` migration                               |
| 3     | 3.2       | `library/rescraper.py` migration                                   |
| 3     | 3.3       | `commands/library/scan.py` migration + full ACC-02 verification    |
| 4     | 4.1       | Wire remaining EventBus emission sites                             |
| 4     | 4.2       | Structured logging at all documented levels                        |
| 4     | 4.3       | EventBus integration test (ACC-08) + `info providers` CLI command  |
| 4     | 4.4       | Docs: architecture.md + scraping.md                                |
| 4     | 4.5       | VERSION bump + CHANGELOG + final gate                              |
| 4     | 4.6       | Lint rule: forbid broad `except` around registry call sites        |

---

## Phase risk matrix (from DESIGN §9.1)

| Phase | Risk     | Reversible | LOC delta (est.) |
| ----- | -------- | ---------- | ---------------- |
| 0     | Very low | Yes        | +750 / -0        |
| 1     | Medium   | Yes        | +250 / -160      |
| 2     | Medium   | Yes        | +250 / -200      |
| 3     | Low      | Yes        | +100 / -80       |
| 4     | Very low | Trivial    | +150 / -20       |

---

## Commit convention

All commits in this feature use Conventional Commits with scope `registry`:

```
{type}(registry): description
```

Examples:

- `feat(registry): add ProviderRegistry shell + error types`
- `test(registry): characterization tests for legacy orchestrator fallback`
- `feat(registry): wire registry at pipeline boot, remove self._tmdb/_tvdb`

## ACC criteria summary (from DESIGN §10)

| ID      | Criterion                                             | Phase verified | Sub-phase verified |
| ------- | ----------------------------------------------------- | -------------- | ------------------ |
| ACC-01  | `make check` green                                    | 4              | 4.5                |
| ACC-02  | No direct TMDB/TVDB client outside `api/metadata/`    | 3              | 3.3                |
| ACC-03  | No `self._tmdb` / `self._tvdb` in `scraper/`          | 1              | 1.2                |
| ACC-04a | Boot positive control (credentials present)           | 4              | 4.3 + 4.5          |
| ACC-04b | Boot crashes when TMDB credentials missing            | 4              | 4.3 + 4.5          |
| ACC-05a | Synthetic broken config fixture exists                | 0              | 0.6                |
| ACC-05b | Broken config triggers aggregated RegistryConfigError | 4              | 4.3 + 4.5          |
| ACC-06  | `info providers` lists every configured provider      | 4              | 4.3                |
| ACC-07  | Registry unit tests count ≥ 45                        | 0              | 0.5a/b/c + 0.7     |
| ACC-08  | EventBus snapshot test passes                         | 4              | 4.3                |
| ACC-09  | E2E behavior preserved (count anchor)                 | 0 + 1          | 0.7 (pin) + 1.3    |
| ACC-10  | Version bump to 0.16.0                                | 4              | 4.5                |
| ACC-11  | CHANGELOG 0.16.0 entry                                | 4              | 4.5                |
| ACC-12  | Module-size guardrail                                 | 4              | 4.5                |
| ACC-13  | Characterization tests pass against refactored code   | 1              | 1.3                |

**ACC-04a/04b/05b mapping note**: these criteria invoke `personalscraper info providers`
(with optional `--config` flag for ACC-05b), which is the CLI command delivered in
sub-phase 4.3. They cannot be exercised before Phase 4. Phase 1 sub-phase 1.1 adds
a unit/integration test asserting `RegistryConfigError` is raised at boot when
`TMDB_API_KEY` is absent — this gives early confidence in the behavior, but the
shell-executable ACC commands are verified at Phase 4.
