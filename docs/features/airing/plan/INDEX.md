# airing (RP9) — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement phase-by-phase. Each phase file opens with a **Gate** section — verify it before starting.

**Goal:** Add the air-date set-poll capability (`poll_aired`) to the acquire lobe: given a set of followed TV series and a `ProviderRegistry`, enumerate their episodes via the existing metadata capability and surface the aired ones (`air_date <= today`). Stateless, capability-only — no store writes, no ownership calls, no cadence reads. Unblocks Follow D2.

**Architecture:** Stateless `acquire/airing.py` (mirrors `acquire/title_resolver.py`). New frozen `AiredEpisode` VO in `acquire/domain.py`. Chain fall-through (TVDB-primary → TMDB-fallback) per season. Fail-soft per series and per season. Three negative tests encode the RP9↔D2 boundary.

**Design doc:** `docs/features/airing/DESIGN.md`
**Branch:** `feat/airing`
**Commit scope:** `airing`
**Version bump:** 0.30.0 → 0.31.0 (minor)

---

## Phases

| #   | Phase                             | File                             | Status |
| --- | --------------------------------- | -------------------------------- | ------ |
| 1   | AiredEpisode VO + aired predicate | phase-01-aired-episode-vo.md     | [ ]    |
| 2   | Set-poll service                  | phase-02-set-poll-service.md     | [ ]    |
| 3   | Negative-boundary tests + wiring  | phase-03-negative-boundary.md    | [ ]    |
| 4   | Docs + ACCEPTANCE + gate          | phase-04-docs-acceptance-gate.md | [ ]    |

---

## File map

| File                                 | Action | Purpose                                                                                                     |
| ------------------------------------ | ------ | ----------------------------------------------------------------------------------------------------------- |
| `personalscraper/acquire/domain.py`  | MODIFY | Add `AiredEpisode` frozen dataclass (phase 1)                                                               |
| `personalscraper/acquire/airing.py`  | CREATE | `_parse_date`, `_is_aired`, `_fetch_season_with_fallback`, `poll_aired` (phases 1–2)                        |
| `tests/acquire/test_airing.py`       | CREATE | All airing tests: predicate, golden, set-poll, fail-soft, season-selection, negative, layering (phases 1–3) |
| `docs/reference/architecture.md`     | MODIFY | Surgical: add `airing.py` entry to acquire/ tree + RP9↔D2 boundary note (phase 4)                           |
| `docs/features/airing/ACCEPTANCE.md` | CREATE | ACC-01..ACC-15: all executable shell commands (phase 4)                                                     |

---

## Key symbols (all grounded against repo)

| Symbol                                                         | Location                            | Phase |
| -------------------------------------------------------------- | ----------------------------------- | ----- |
| `AiredEpisode`                                                 | `personalscraper/acquire/domain.py` | 1     |
| `_parse_date(air_date: str) -> date \| None`                   | `personalscraper/acquire/airing.py` | 1     |
| `_is_aired(air_date: str, today: date) -> bool`                | `personalscraper/acquire/airing.py` | 1     |
| `poll_aired(series, registry, *, today) -> list[AiredEpisode]` | `personalscraper/acquire/airing.py` | 2     |
| `_fetch_season_with_fallback(tvdb_id, season, registry)`       | `personalscraper/acquire/airing.py` | 2     |

---

## Repo rules (enforced throughout)

- Every `rg` command MUST carry `--type py` / `-g '*.py'` / `-g '*.md'` — the repo has a 14 GB fixture dir.
- Logging: `personalscraper.logger.get_logger` (NEVER `structlog.get_logger`).
- Google-style docstrings on all modules, classes, and functions.
- ruff line-length 120, mypy strict.
- Commit scope = `airing`. No AI attribution.
- Phase gate before each phase: run the Gate verification commands listed at the top of each phase file.
- Final gate: `make check` exits 0 + `python3 scripts/audit_design_coverage.py --strict` exits 0 + `python3 scripts/update_feature_map.py --check` exits 0.
