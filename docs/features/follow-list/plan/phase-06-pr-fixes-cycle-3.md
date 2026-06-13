# Phase 06 — PR review fixes cycle 3 (docs + cosmetic)

**Codename**: follow-list
**PR**: #197
**Date**: 2026-06-14

## Findings addressed

### M1 (`_ports.py` — lift `find_by_ref` matching semantics into Protocol docstring)

The concrete `_FollowSubStore.find_by_ref` in `store.py` documents its primary-ID
matching semantics (tvdb > tmdb > imdb, `ORDER BY id LIMIT 1`). The Protocol
docstring in `_ports.py` omitted these semantics. Added a concise 3-line summary
matching the implementation.

### m1 (`title_resolver.py` — cast + type: ignore audit)

- `cast(TvDetailsProvider, providers[0])`: **kept**. Removing it causes mypy
  `attr-defined` on `get_tv` (the `type: ignore[type-abstract]` on the `chain()`
  call prevents mypy from narrowing the return type to `list[TvDetailsProvider]`,
  so `providers[0]` is `Searchable` without the cast).
- `# type: ignore[type-abstract]`: **kept** — mypy requires it when passing a
  `Protocol` as `type[...]`.

### m2 (`title_resolver.py` — module docstring clarification)

Added a leading sentence: "The provider title is preferred; the fallbacks below
apply only when it is unavailable." and retitled the list header to "Fallback
precedence (when the provider lookup fails or is skipped):".

## Files changed

| File                                        | Change                                                             |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `personalscraper/acquire/_ports.py`         | Protocol `find_by_ref` docstring extended with matching semantics  |
| `personalscraper/acquire/title_resolver.py` | Module docstring clarified; cast + type:ignore audited (both kept) |

## Quality gates

| Gate                                      | Result                                                     |
| ----------------------------------------- | ---------------------------------------------------------- |
| `python -m mypy personalscraper/acquire/` | 0 errors                                                   |
| `python -m pytest tests/acquire/ -q`      | 271 passed                                                 |
| `python -m pytest tests/architecture/ -q` | 130 passed                                                 |
| `make check`                              | GREEN — 6701 passed, 3 skipped, 2 xfailed, 91.38% coverage |
| `git status --short`                      | clean after commit                                         |
