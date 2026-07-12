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
| OBJ3 next-search + cadence temperature: `next_search_at`/`cadence_tier` on the API, rendered "Prochaine recherche ~…" in the `--temp-*` colour; new cadence helpers + tests; OpenAPI regenerated | `16e83915` | ⚠️ unit-tested; not live (no pending follows on staging)                  |
| `lint:ds` made truly binding (forbid raw `<img>`; all images via DS `MediaPoster`/`BrandMark`; CandidateCard poster consolidated)                                                                | `92c96d10` | ✅ proven binding + CI frontend green                                     |
| web-ui.md documents the overhaul routes                                                                                                                                                          | `ae679eaf` | ✅                                                                        |

Gates: full local `make check` green (ruff + mypy + logging + **8275 passed** + module-size + cli-coverage); frontend lint/typecheck/vitest(609)/build green; CI on PR #251 green on every job except the still-running `test` (mirrors the local 8275-pass). Deployed to staging on every push.

## 4. Remaining (surfaced honestly — the brief's "tout conforme" is not yet met)

Not silently deferred — these are the open items between here and the brief's bar
(the brief conditions the squash-merge on _"quand tout est conforme"_):

- **Real posters for existing follows** (OBJ3 "cards sans âme") — needs a one-time provider/indexer backfill; the branded fallback only mitigates.
- **Live proofs**: the deck "20-in-2-min" chrono (keyboard + thumb) and the manual grab → detached-runner live feedback both need a **seeded writable instance** (staging queues are empty, staging is read-only).
- **Obsession/Ferrari re-scrape** — recovers their NFO and clears the resolved-vs-no-NFO contradiction; best run **post-merge from prod** (needs the #3 fix live), then verified in Chrome.
- **T-1** staging read-only friendly writes; **T-2** `/locks` split (instant lock/sentinel + lazy sweep); **S-2** library density control; **S-6** deck resolve-flip; **P-2/P-5/P-6** pipeline count reconciliation + pending-decisions CTA.

## 5. Recommendation

The branch is a genuine, gated, regression-free improvement over the state the
operator rejected, with the highest-impact defects fixed and verified live. It is
**ready to squash-merge once the operator accepts the remaining list** (or directs
the further correction) — at which point prod autodeploys `main`, `/api/version`
confirms the sha, Obsession/Ferrari are re-scraped, and a final prod Chrome
walkthrough closes the loop. Merging is deliberately left as the operator's call
because full conformity — the brief's own merge condition — is not yet reached.
