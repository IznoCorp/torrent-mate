# TorrentMate Web UI — UX/UI Overhaul: Design Report (honest, guarantor-revised)

Closing counterpart to `DESIGN_VISION.md`. Branch `feat/webui-overhaul` (PR #251).
This revision replaces the prior "all objectives complete + live-verified" report:
a design-guarantor pass **re-tested every screen end-to-end in Chrome on
`tm-staging.iznogoudatall.xyz` against real data**, judged each against the brief,
and corrected the highest-impact gaps. It is written as a truthful ledger —
**declared vs constaté vs corrigé vs remaining** — not a victory lap.

Full audit + finding tables: `docs/analysis/2026-07-12-pr251-review.md`.

## 1. Method

Every surface was driven in a real browser (Chrome MCP) with real shared prod
data (staging shares `library.db`/`.data`/staging dirs). Mobile was rendered
faithfully at **390px** via a same-origin iframe (Chrome's window viewport is
pinned at 1440px, so `resize_window` alone can't shrink it). Backend invariants,
the API contract, and the design system were audited inline by the guarantor
(not delegated). No self-report was trusted: the read-model tests were
mutation-checked (breaking `_find_poster` fails 3 real tests), and `lint:ds` was
proven binding (a probe `<img>` fails it).

## 2. Declared vs constaté (what the agents shipped vs what the browser showed)

| Objective        | Declared                     | Constaté in Chrome                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OBJ1 Flow Board  | "complete, live-verified"    | **Functional but not "un coup d'œil"**: a redundant legacy stepper was stacked under the board (two stage models, different labels); the per-media timeline was **non-monotonic** (Obsession showed Trailers "Fait" while Matching/Scraping "En attente"); hero count vs breakdown didn't reconcile; the same media read as "identifiée" in one panel and "Non identifié" in another. |
| OBJ2A Library    | "complete"                   | **Genuinely strong** — real poster heroes via the local route, badges, filters, rich detail drawer (TVDB+TMDB, seasons, timeline). Missing the brief's density control; shared timeline bug.                                                                                                                                                                                          |
| OBJ2B Deck       | "complete"                   | Sound keyboard model + read-only resolved view. The queue was empty on staging, so the "20-in-2-min" chrono + resolve-flip were **not** live-verifiable without seeded data; no memorable flip micro-interaction.                                                                                                                                                                     |
| OBJ3 Acquisition | "complete, live-verified"    | **Under-delivered**: watch-list cards were giant empty rectangles (existing follows have no cached poster); the brief's headline "prochain déclenchement (Hot/Warm/Cold/cutoff → `--temp-*`)" was **absent** even though the cadence engine and the `--temp-*` tokens both already existed.                                                                                           |
| Transverse       | "states built in everywhere" | Staging read-only surfaced a **raw "403: read-only"** toast on writes (brief forbids it); `/api/maintenance/locks` cold path is **~31 s**; `lint:ds` was a **no-op** (`forbid:[]` + non-existent import paths).                                                                                                                                                                       |

## 3. Corrigé (this pass — code + tests + gates + Chrome re-verify)

| Fix                                                                                                                                                                                              | Commit     | Verified                                                                  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------- |
| Timeline made strictly monotonic (frontier model; trailers gate on the scrape, not the trailer file) + regression test                                                                           | `01768c96` | ✅ Chrome live: Obsession now Matching/Scraping/Trailers all "En attente" |
| Retired the redundant legacy stepper from the live page (FlowBoard is the single view)                                                                                                           | `4b9460ef` | ✅ Chrome live: page decluttered                                          |
| Branded poster-less fallback (kind-tinted gradient + initials + media-kind watermark)                                                                                                            | `4b9460ef` | ✅ Chrome live                                                            |
| Deck `n` (passer) shortcut surfaced                                                                                                                                                              | `4b9460ef` | ✅                                                                        |
| OBJ3 next-search + cadence temperature: `next_search_at`/`cadence_tier` on the API, rendered "Prochaine recherche ~…" in the `--temp-*` colour; new cadence helpers + tests; OpenAPI regenerated | `16e83915` | ⚠️ unit-tested; renders only when a follow has pending wanted items       |
| `lint:ds` made truly binding (forbid raw `<img>`; all images via DS `MediaPoster`/`BrandMark`; CandidateCard poster consolidated)                                                                | `92c96d10` | ✅ proven binding + CI frontend green                                     |
| web-ui.md documents the overhaul routes                                                                                                                                                          | `ae679eaf` | ✅                                                                        |
| **T-1** staging read-only → clean French consultation notice (no raw `403: read-only`), one-change global fix + `isReadOnly` flag                                                                | `7c60c692` | ✅ + regression test                                                      |
| **P-2** Flow Board station hero count reconciled with its own split (total processed, not bare "réussi")                                                                                         | `c6e579e5` | ✅ **Chrome live on prod**: SCRAPING hero "4" = split 1+2+1               |
| `follow backfill-metadata` CLI (id-matched provider search; never a wrong poster; column-guarded)                                                                                                | `45bdad71` | ✅ unit-tested + ran on prod                                              |

Gates: full local `make check` green (ruff + mypy + logging + **8277 passed** + module-size + cli-coverage); frontend lint/typecheck/vitest(610)/build green; **CI on PR #251 fully green** (all jobs incl. `test` + `frontend`).

## 4. Shipped — merged + deployed + verified on prod

PR #251 **squash-merged** → `main` (`82134341`); prod autodeployed it (`/api/version` = `82134341`). Post-merge, verified live **in Chrome on `tm.iznogoudatall.xyz`**:

- **Acquisition migration 005 applied** (the poster/overview/year/season_count columns were absent on prod — `user_version` 4 → 5), then **`follow backfill-metadata` ran on prod**: all 5 watch-list follows now carry real posters + overviews. **A-1 "cards sans âme" is resolved** — Rick and Morty / Silo / House of the Dragon render their real posters + descriptions.
- **Obsession + Ferrari re-scraped** (re-open decision → `scrape-resolve --provider tmdb --id`, the #3-fixed path): valid NFOs written (`<tmdbid>`, `<imdbid>`, `<title>`, `<year>`), both now `matched`/`nfo:True`, posters served — the scraping library shows them **"Identifié"** (Identifiés (1)→(3)). **The #3 drift-unlink fix is proven in real conditions** and the resolved-vs-no-NFO (P-4) contradiction is gone.
- **/pipeline on prod**: the redundant stepper is gone (P-1) and the station hero reconciles with its split (P-2, "4" = 1+2+1).
- **Branded fallback** shows on the genuinely-unidentified cards (clapperboard watermark + initials).

## 5. Remaining (honest follow-ups — minor / blocked on data)

- **Live proofs still un-run**: the deck "20-in-2-min" chrono and the P-6 pending-decisions CTA / S-6 resolve-flip all need **pending ambiguous decisions**, which do not currently exist (the queue is empty — Obsession/Ferrari are the only ones and are now resolved). A real ambiguous scrape run would populate them.
- **Manual grab live feedback (A-4)** — the trigger + detached runner are wired + tested; a live end-to-end grab on prod was not exercised (real tracker/download side-effects).
- **T-2** `/locks` cold path ~31 s (60 s cache only warms it) — split the instant lock/sentinel from the lazy orphan sweep.
- **S-2** library density control.

These are enhancement-level or data-blocked; none regress the shipped product. The operator's core grievance — card quality ("cards sans âme"), board readability, and the #3/Obsession-Ferrari state — is fixed and verified on prod.

## 6. v2 polish pass (C1–C25) — `feat/webui-polish` (2026-07-13)

A prescriptive second pass raised the interface to the brief's ambition and
closed the §5 reliquats. 25 corrections across four lots; each with a
`constat → fait → preuve` in `docs/analysis/2026-07-12-pr251-review.md`. Every
lot pushed with full gates green (`tsc -b`, `vitest`, `npm run build`, `eslint`,
`lint:ds` + new `lint:tokens`, backend `ruff`/`mypy`/`pytest`, OpenAPI drift).

**Lot A — Flow Board vivant.** Motion-token scale (C1); expressive stations with
attention/blocked washes + tonal counts + count-pop (C2); run-active shimmer +
animated connectors (C3); temporal legends + `run_trigger` (C4, contract);
impossible-to-miss pending-decisions banner (C5, closes P-6); DS states in the
stage drawer (C6).

**Lot B — Resolution Deck frictions.** Focus released after manual search + first
result preselected (C7, on the enqueue nominal path — live-verified); resolve
flip (C8, closes S-6); skip wrap + count (C9); scroll-into-view + live region
(C10); mobile thumb bar + coarse-pointer hint hiding (C11, closes S-8).

**Lot C — Acquisition cohérence & dette.** Monolith split to a 136-line shell +
panels (C12); single add flow re-verified (C13); backend-derived follow `status`
(C14, contract); scheduler-driven cron caption (C15); the follow card tells the
whole story — search-now/toggle/cadence in place (C16).

**Lot D — Bibliothèque, perf & transverse.** Adjustable density (C17, closes
S-2/P-7); filter warning tone + ambiguous/enqueue jump the deck to their decision
(C18, closes P-2/P-5; `decision_id` contract); `lint:tokens` DS guard (C19);
board/deck a11y (C20); motion coherence + reduced-motion (C21); **`/locks` cold
sweep decoupled to a background thread — locks <1 s, sweep skeleton** (C25,
closes T-2, measured on a staging cold boot).

**Still open after this pass:** the deck 20-in-2-min chrono + a live grab (need a
writable prod queue of ambiguous decisions — post-merge); and two operator
follow-ups filed 2026-07-12 for after this pass — the illegible mobile Scraping
nav badge and route-ifying detail views so browser Back closes them.
