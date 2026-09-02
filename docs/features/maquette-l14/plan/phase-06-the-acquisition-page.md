# Phase 6 — The acquisition page · **conversion**

**Owns**: `features/acquisition/page.tsx` 756 → under 400. **Constitution**: §15, §14.1 (the
acquisition workflow's three tabs stay three surfaces sharing one bar).

## What changes

| File                   | Carries                                                                                                                                              |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `acquisition-tabs.tsx` | `AcquisitionTabs` — the segment, the badge's read, the « more » control                                                                              |
| `now-tab.tsx`          | `NowTab` whole                                                                                                                                       |
| `follows-filters.tsx`  | the filter zone of « Suivis »: the search field with its native handler, the four pills, the three-mode switch — receives the pills' counts as props |
| `follows-tab.tsx`      | `FollowsTab` — the read, the sort, the descriptors, the three modes, the cadence line, the notes; it renders `FollowsFilters`                        |
| `discover-tab.tsx`     | `DiscoverTab` whole — the containers and the fill effect as ONE unit (D-L14-9), `SEARCH_AGAIN` stays with the follows                                |

`page.tsx` keeps `AcquisitionPage`: the `version` subscription and the tab switch. The
`("features/acquisition/page.tsx", "button")` key of `scripts/markup_dressing.py`'s
`BARE_ALLOWED` — the « connect TMDB » button inside `surfaceError()` — is re-keyed to
`discover-tab.tsx` in the same commit, reason unchanged.
`GRANDFATHERED["features/acquisition/page.tsx"]` is removed in the same commit. **The
`dangerouslySetInnerHTML` sites move as they are** — memoising them is phase 7's.

## Definition of done

- `grep -cve '^\s*$' frontend/maquette/design/src/features/acquisition/page.tsx` → **< 400**
  (estimate ~35); every new file under 400, `follows-tab.tsx` measured and written down if it
  crosses the 250 warning.
- `python3 scripts/check-frontend-boundaries.py --arm size` → **2** at or over the ceiling —
  `engine/legacy.js` and `engine/states.js`, both labelled L13. **This is the contract's line.**
- `python3 scripts/check-markup-contracts.py` green (the re-keyed `button` site).
- The oracle: zero divergence across the acquisition states (now, follows ×5, discover ×6, add).
- `run.sh --contracts` green (`page_host.py`, `audit2.py` drive the tabs); `npm run check` green.
- One commit: `refactor(maquette-l14): the acquisition page — five files beside it, nothing moved`.
