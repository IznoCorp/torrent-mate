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

| ID      | Criterion                                             | Phase verified |
| ------- | ----------------------------------------------------- | -------------- |
| ACC-01  | `make check` green                                    | 4              |
| ACC-02  | No direct TMDB/TVDB client outside `api/metadata/`    | 3              |
| ACC-03  | No `self._tmdb` / `self._tvdb` in `scraper/`          | 1              |
| ACC-04a | Boot positive control (credentials present)           | 1              |
| ACC-04b | Boot crashes when TMDB credentials missing            | 1              |
| ACC-05a | Synthetic broken config fixture exists                | 0              |
| ACC-05b | Broken config triggers aggregated RegistryConfigError | 0              |
| ACC-06  | `info providers` lists every configured provider      | 4              |
| ACC-07  | Registry unit tests count ≥ 45                        | 0              |
| ACC-08  | EventBus snapshot test passes                         | 4              |
| ACC-09  | E2E behavior preserved (count anchor)                 | 1              |
| ACC-10  | Version bump to 0.16.0                                | 4              |
| ACC-11  | CHANGELOG 0.16.0 entry                                | 4              |
| ACC-12  | Module-size guardrail                                 | 4              |
| ACC-13  | Characterization tests pass against refactored code   | 1              |
