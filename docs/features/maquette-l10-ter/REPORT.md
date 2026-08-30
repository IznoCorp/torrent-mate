# L10-ter — session report

**Session**: 2026-08-29 → 2026-08-30 · **Started from** `main` at `faee1192` · **Left** `main` at
`336d4cb0` · **Pull requests**: #521 (the phase), #522 (the post-merge gesture), #523 (the
operator's nine answers, §17 completed, §20 dictated) — all squash-merged, `no-version-bump`, CI
green. **No application code was touched**, as the brief required. Written for the reader who
opens this folder without the conversation: what was asked, what was measured, what was decided,
what went wrong, and what the next agent inherits.

---

## 1. What was asked

Open L10-ter — a design phase, not a lot. Deliver a COMPUTED inventory of what the dying engine
still draws; a model of the application's frame (invariant 10's subject, never defined); the
objective « as close to a mobile application as possible » restated as measurable properties; every
lot from L11 to L14 re-read against the model; the placement of §17, §18 and §19; the clause map
for B-142's instrument — and **decide where and when the model becomes work**, amending the plan
under § 7.1. The brief's figures were to be re-derived, not copied.

## 2. What the survey measured, and why it changed the plan

| The brief said                           | Measured                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 12 `innerHTML` writes, 10 unidentified   | **13** `innerHTML` writes, **19 drawing sites** — the brief's grep demanded a space after `=` and one write breaks its line there. The honest command is in `SURVEY.md` § 1.1 with what it does NOT read: descriptors and toggles                                                                                                                                                         |
| L13: « the engine still draws surfaces » | **The engine draws no page** (eight `PAGES_OF` entries, all `shellOwned`, none with `render` — the `view.innerHTML` branch is dead) **and no screen** (`#screen` is never opened)                                                                                                                                                                                                         |
| —                                        | What the engine still owns: **the frame** (tab bar rebuilt on every `render()`, drawer, dialog, toast, selection bar, popover), **the entry** (splash, login, install, appearance), **the ladder's handler**, **all ten bottom-panel producers** (zero on the React side — invisible to any `innerHTML` grep), the Découvrir feed, 71 delegation verbs, **the page table in four copies** |
| —                                        | The delete dialog has **no history entry** (Back does not close it — against D1) and **paints under the tab bar** (`z-48` against `z-50`)                                                                                                                                                                                                                                                 |
| —                                        | Against production: **no desktop navigation beyond the drawer**, **no dynamic viewport unit** — two decisions nobody had taken                                                                                                                                                                                                                                                            |

## 3. The deliverables

| File                                             | What it holds                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SURVEY.md`                                      | The inventory (its command, the per-surface table), who owns every node of the frame, the layer ladder, the production comparison, the findings                                                                                                                                                                                                |
| `MODEL.md`                                       | The frame in **13 parts** (where it lives under invariant 10, what it owns, what it never knows, today → target with the lot); **30 mobile-application properties** with their instruments; the template (page · screen · panel · transient; one navigation table; a slot and a verb per layer); B-142's arm specified; `lib/queue.ts` decided |
| `docs/reference/product-intent-map.md`           | **23 clauses** DOIT / NE-DOIT-PAS → surface, verdict, proof or owning lot. Ratified by the operator (Q7)                                                                                                                                                                                                                                       |
| `docs/reference/backend-demands-architecture.md` | The backend's share of §17 / §18 / §19 / §20, inputs of the FUTURE backend brief — unscheduled by design                                                                                                                                                                                                                                       |
| `QUESTIONS.md`                                   | Nine questions, each with its context, the recommendation and **the operator's dated answer**                                                                                                                                                                                                                                                  |
| `docs/reference/product-intent.md` **v5**        | §17 « Ce que cela tranche », **§20 « Un tunnel par média »** — dictated by the operator                                                                                                                                                                                                                                                        |
| `docs/reference/frontend-architecture.md`        | The plan amended: L15, L19, L20 declared; L16 / L17 / L18 placed; L13 re-cut; L11 / L12 / L14 re-read; D5 and invariant 10 refreshed; § 5 gains the archive exemption and B-238's note                                                                                                                                                         |
| `BUGS.md`                                        | **B-228 → B-238**; the « Guards green » table gains L10-ter's row (5 — 1 by the phase, 4 by its review), total **98**                                                                                                                                                                                                                          |

## 4. The plan as it stands (the file's order decides, never the numbers)

| #   | Lot                                     | What it does                                                                                                                                                                   |
| --- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **L15 — The frame**                     | Chrome, entry, one navigation table; four behaviour changes in their own commits (B-229, B-230, B-233, B-237); the drawer alone at every width (Q1); builds B-142's instrument |
| 2   | L11 — Offline and PWA                   | Worker, offline shell, mutation queue, **every** platform entry point (Q4)                                                                                                     |
| 3   | L12 — Native interaction                | Transitions, gestures, mobile geometry, reduced motion, virtualised lists                                                                                                      |
| 4   | L14 — The oversized files               | Pulled before L19 (Q3)                                                                                                                                                         |
| 5   | L19 — The producers                     | The ten producers, the Découvrir feed and their verbs move into `features/`, their fixtures dying; the map's missing instruments                                               |
| 6   | L20 — The global levers and the history | Re-cut by §20: the parallelism bound, pause / resume of everything, the watcher, the history. No Pipeline page, no pipeline badge (Q6, Q9)                                     |
| 7   | L16 — §18 the ratio                     | **Blocked**: §18's open points are still to dictate                                                                                                                            |
| 8   | L17 — §19 cross-seed                    | **Blocked**: §19's open points are still to dictate                                                                                                                            |
| 9   | L18 — §17 accounts                      | Unblocked (Q8)                                                                                                                                                                 |
| 10  | L13 — The engine's residue              | Re-cut: the ladder's handler, the delegation's frame verbs, the boot, the seams, the dead `#screen`, `refonte.html`, `legacy.css`; `legacy.js` no longer exists                |

## 5. The operator's decisions (2026-08-30, all recorded)

Q1 the drawer alone, not frozen · Q2 the order as written · Q3 L14 before L19 · Q4 maximal
integration (every entry point) · Q5 (noted) Back closes the dialog · Q6 no pipeline badge ·
Q7 the map ratified · Q8 §17: three roles (Operator bypasses ACLs / Household member / Plex guest)
plus two per-account options; a requester on every acquisition (default: the Plex owner, Izno);
SSO added, not substituted, with e-mail linking; a rights-less Plex user admitted read-only on the
library; the quality profile as a per-acquisition override; the staging read-only role as an
instance ceiling · Q9 L20 after L19 · **§20 dictated**: a tunnel per media — parallel and bounded,
a blocked tunnel persists its state and resumes; the pipeline is followed per media through the
acquisition tunnel.

## 6. The adversarial review — and the author's own errors, reported

Three readers (figures · directive coherence · the constitution), 43 findings. **What they found
in this phase's own work**: six line citations wrong by 8 to 257 lines; three `grep -c` counts that
included the function's definition; a seams count produced by a command that could not count
distinct names; `100dvh` asserted from memory and false; five sentences that had lost their subject
(D5, four `ARBITRATED` blocks, L14's range, L15's « one kind of change »); and **two clause-map rows
marked `served` on proofs that did not read the clause** — a print statement and a rule about PM2
processes — in the document written to end exactly that defect. All repaired in `1e09d023`; seven
verdicts moved to `partly`; the four review-found instances are counted in the « Guards green »
row.

**The lesson, kept**: open every proof you cite; subtract the definition from a caller count;
re-grep every cited line number last.

## 7. Incidents

- The `commit-msg` hook refuses the `Claude-Session:` trailer — commits carry none.
- A test hard-coded « L19 = a lot the plan never declares »; declaring L19 made it fall. The
  fixture was repointed to `L99`, the guard's docstring and B-073's recorded mutation updated.
- The post-merge gesture « In flight → none » is MANUAL for a prose-only wave: the guard reads a
  version and such a wave names none — **B-238**, open.
- `git add` refuses `docs/` paths without `-f` (the global ignore); every docs path is force-added,
  as the repository's own gotcha prescribes.

## 8. What is open

- **B-238** — a version-less « In flight » row is held by nothing (the office's, under § 7.2's
  exception, or the next post-merge gesture by hand).
- **§18 and §19** — their open points are still to dictate, before L16 and L17; not before L15.
- **B-235** — answered by Q1 (not a defect); closes concretely with L15's drawer.
- **#524** — the steward's pull request (`claude/steward-l15-brief`), stopped in flight after its
  agent's session ended. Its state on 2026-08-30 evening: one commit, five files, up to date with
  `main`; **the L15 brief is written** (`docs/archive/features/maquette-l15/BRIEF.md`, 173 lines — archived with the wave on 2026-08-30); B-239
  filed (`CLAUDE.md` announced 24 properties where the model holds 30) and repaired; the plan's § 1
  sentence « has never been modelled » put in the past tense; version bumped to 0.98.54 rather than
  labelled. **Unfinished**: B-239's status still reads `fixing` (must read `fixed #524` — B-221's
  shape); the brief has had no second reader; `harness-contracts` was still pending; not merged.
  `HANDOVER.md` beside this file says how it is finished.

## 9. What the next agent inherits

L15 opens with its design and its plan, from `MODEL.md` § 2 (Parts 5, 6, 7, 9) and `SURVEY.md`
§ 1.2, under the brief #524 lands. It extends none of L14's four files; it leaves the ladder's
handler in the engine until L13 (the drawer and the dialog REGISTER with it, as the sheet does
through `window.__panel`); its four behaviour changes each land in their own commit with their
rule; it builds B-142's arm with its mutation. **`docs/features/maquette-l10-ter/` does not
archive** — § 5 names it exempt; it archives with L13.
