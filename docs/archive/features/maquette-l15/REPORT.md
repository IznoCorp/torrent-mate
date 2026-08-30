# L15 — the wave's own account of itself

**Written DURING the wave**, phase by phase, because L08 merged with twenty findings that lived
only in a commit message and it took another wave to recover them. Each phase records what landed,
the gates it passed with their numbers, and every mutation seen red and restored.

---

## The running count for B-085 — « a guard is green because of what it does not read »

The register's total stood at **98** when this wave opened. What this wave has added, each found
by asking the question rather than by a gate going red:

| # | Where | The shape |
| --- | --- | --- |
| 1 | `scripts/check-implementation-state.py` (B-246) | the version arm did not match `version **0.98.55**`, and the no-version branch exited 0 in silence — so the row this wave wrote was held by one of two arms under a green gate |
| 2 | `.github/workflows/ci.yml` + `test_ci_filter_covers_the_guards.py` (B-244) | the hold asks « is this path named by ANY filter? » and never « by the filter that gates the job that runs the guard? » — its two prior cases both had the same answer to both questions |
| 3 | `scripts/boundaries_addressing.py`, phase 1 | the reader searched for the first `[` after a TYPED declaration and found the type's own empty pair — an empty array read as « no pages ». Loud only because the caller has a « reads to nothing » branch at all |
| 4 | `harness/persistence.py` hold (a), phase 2 | P1 was first held by `performance.getEntriesByType("navigation").length == 1` — which is one entry PER DOCUMENT, so a full navigation produces a new document where the count is one again. A reading that cannot come out the other way |
| 5 | `harness/persistence.py` hold (a), phase 2 | its replacement counted `framenavigated`, which also fires for a `pushState` — 63 of them over the 87 states with the property holding perfectly. A signal meaning two things needs a threshold nobody can defend; `load` means one |
| 6 | `app/tab-bar.tsx`, phase 3 | the badge read the query cache SYNCHRONOUSLY and was subscribed to nothing, so it showed the previous scenario's count until an unrelated store write redrew it. Caught by `audit2.py` R16 — an existing rule, not a new one — and the reason it never bit before is that the engine's bar was rebuilt by `render()`, which the cache's redraw hook calls: the same mechanism that made the chrome's nodes disposable |
| 7 | R101's B-237 hold, phase 10 | it hit-tested the dialog's OWN rectangle. The named delete states raise dialogs of 184–660 and 142–702 against a bar at 787–844: they do not touch, so it passed at `z-48` exactly as at `z-56` |
| 8 | R101's B-237 hold again | `inert` takes an element out of HIT-TESTING as well as out of the focus order, and the background is inert while a layer is open — so `elementFromPoint` answered the dialog either way. The bar's `inert` is lifted for the length of one reading now |
| 9 | R101's selection-bar hold | it asserted over a bar `lib-delete-multiple` does not put on screen — a premise nobody had checked, reported as « absent » |
| 10 | R101's popover clamp, phase 11 | it opened at the FIRST and the LAST cell of a matrix that WRAPS, so both readings exercised the same edge and it reported the same placement twice |
| 11 | `check-live-relay.py` (B-250), phase 13 | its stale-figure arm treats a hyphen as a separator, so `B-154` is a match the day the corpus reaches that size. It did — and the arm then caught the first draft of its own repair saying « the corpus reached 154 files » |
| 12 | `check-viewport-directives.py`, phase 17 | a directive written as `"maximum" + "-scale=1"` was invisible to a reader of raw text — L07's split-class shape. Adjacent literals are folded before the search now |

---

## Phase 1 — the one navigation table

**Landed** `app/navigation.ts` (the table), `app/navigation-seam.ts` (what the dying engine reads),
`app/icons.ts` (29 paths, imported back by the engine), `fr.json`'s `navigation` namespace, the
badge derivations in the two features. **Subtracted** `PAGES_OF`, `NAVIGATION`, `PAGES` in the page
host, the dead page-render branch with `shellOwnsView` and `legacyNodes`.

**Gates** oracle 87 × 34 = 2 958 measurements, **no divergence** · contracts tier 11 rules and 20
guards, no violation.

**Mutations, each seen red and restored:**

| Mutation | The hold | What it said |
| --- | --- | --- |
| the `maint` row removed from the table | `check-frontend-boundaries --arm addressing` | « PAGE_PATHS declares an address for « maint », which the navigation table does not carry — an address leading nowhere » |
| `const NAVIGATION = […]` put back in the engine | `page_host.py` (d-quater) | « engine re-declares ['NAVIGATION'] » |
| the `maint` row removed (row count) | `page_host.py` (d-quater) | « 7 row(s) in app/navigation.ts against 8 page(s) drawn » |
| `view.innerHTML = ""` added to the engine | `page_host.py`, the law | « 1 write(s) to #view's innerHTML: ['    view.innerHTML = "";'] » |

**Ceilings moved, with their reasons**: `app/`'s domain-word ceiling 98 → 121
(`scripts/frame-domain-baseline.json`, arithmetic written in); `scripts/code-vocabulary.txt` gains
`seam`; `fixture-register.json` records `icons` as converted OUT of the engine, and
`build-mock-seeds.py`'s `converted_families()` is restricted to the seeded classes so a family with
no seed is not asked for a seed file.

---

## Phase 2 — the tab bar

**Landed** `app/tab-bar.tsx`, `app/frame.tsx` (D-L15-1), the seven bar rules as typed variants in
`ui/variants/layout.ts`, `ui/icon.tsx`'s optional `className`, R100
(`harness/persistence.py`, contracts tier). **Subtracted** the static `<nav id="nav">`, `renderNav`,
its call in `render()`, the `nav` capture, the `selecting` class write, and seven rules of
`styles/legacy.css`.

**Gates** oracle 87 × 34 = 2 958 measurements, **no divergence** · R100 8 holds, no violation.

**Mutation, seen red and restored**: the tab bar's `key` made to depend on the current page and the
badge — which is what an `innerHTML` rewrite amounts to. Three holds fell, and P28's message is
B-231 itself: `active element: {'page': None, 'inBar': False, 'body': True}` — focus on the
document body.

**And R100's own hold (a) was rebuilt twice before it measured anything** — entries 4 and 5 of the
table above. Its detectors now carry a positive control that runs last, because proving them alive
destroys the document every other hold measures.


---

## Phase 3 — the action button

**Landed** `app/action-button.tsx` (one decision point, two facts),
`app/message-presence.ts`, `ui/variants/layout.ts`'s `addAction`,
`lib/query-client.ts`'s `useServerStateVersion`. **Subtracted** the static `<button id="fab">`,
`refreshActionButton`, `pageWantsActionButton`, `messageIsOnScreen`, `actionButtonReturn`, the
`#fab` click binding and the `fab` capture.

**Gates** oracle 87 × 34 = 2 958 measurements, **no divergence** · contracts tier 12 rules and 20
guards, no violation · R86 (`hiding.py`) 26 holds, no violation — including the 200 ms return
window, « the collision, measured », and « a page with no action does not acquire one when a
message closes ».

**No new rule, and that is the finding.** The plan asked for a hold on the message/button overlap.
**R86 already holds it**, positive control included: it measures that with nothing on top the
message's close coordinates ARE the button. A second rule would have been ceremony. What phase 3
owed was to keep it biting through a reimplementation, and it does — every one of its 26 holds,
unchanged.

**Two defects found by making the change, neither of them looked for:**

- **The badge was subscribed to nothing** (entry 6 above), caught by `audit2.py` R16.
  `lib/query-client.ts` gains `useServerStateVersion()` — the frame re-derives its badges when any
  server state moves, and names none of it.
- **B-247** — a store bump replaces a feature page's DOM nodes, so a write between `pointerdown`
  and `click` destroys the tap. Phase 3 routed the message's presence through the store for one
  commit and `page_host.py`'s « a real tap on a command row » went red while a programmatic click
  on the same node worked. The engine dismisses its boot hint from a capture-phase `pointerdown`,
  which is exactly that gap, so the FIRST tap of a session on a React page was ALREADY being lost
  while the hint was up. L15 stopped depending on it — the message's presence is its own
  subscription with one subscriber — and **left the defect open**, because the repair is in the
  surfaces and the surfaces are L14's and L19's.


---

## Phases 6 to 19 — what landed, and at what gate

| Phase | Landed | Oracle | Mutation, seen red and restored |
| --- | --- | --- | --- |
| 6 — the message | `ui/toast.tsx`, `app/toast-host.ts`, `app/message-layer.tsx`; the engine's 34 callers keep their verbs | no divergence | the region mounted with its message (« region False »); the undo made a `<span>` |
| 7 — the drawer | `ui/drawer.tsx`, `app/drawer.tsx`, `app/appearance.ts`, `app/layer-registry.ts`; 13 residue rules; `data-apparence` → `data-appearance` | no divergence | the drawer registered under another name — R65 falls 15 holds, naming `rungs=['drawer-not-on-the-ladder']` |
| 8 — the dialog | `ui/dialog/`, `app/dialog-host.ts`, `app/dialog-layer.tsx`; the two producers hand descriptors; **the scrim gets its one owner** (phase 12's subject) | no divergence | R80 caught `.dlgbtn` declared twice and the variant carrying one of the two |
| 9 — B-229 | the dialog's rung, pushed and unwound | no divergence | `pushLayer` removed: the back lands on `{"tm":"garde"}` — the exit guard, which IS the defect |
| 10 — B-237 | the rank 48 → 56, and the ranked list | invisible by construction | the rank restored: « at: 'nav', dialogRank: '48', barRank: '50' » |
| 11 — the popover | `ui/popover.tsx`, `app/popover-host.ts`; the SENTENCE stays a producer (L19) | no divergence | the clamp removed: `left: -80` on one edge, `right: -64` on the other |
| 13–15 — the entry | `app/entry.ts`; the markup stays in `index.html` for two different reasons | no divergence, after a bisect | — |
| B-245 + B-233 | the spellings agree; `theme-color` reads the painted ground | invisible (one theme, no `<meta>`) | the French spellings back (« first frame None »); the meta write removed (« light 11,11,13 against dark 11,11,13 ») |
| 17 — B-230 | the fallback deleted; `check-viewport-directives.py` | no divergence | the directive restored, split across a concatenation |
| B-248 | the sheet's rank 47 → 52; the reserved padding goes | **167 divergences, accepted** — one region, two properties | the rank restored: « at: 'nav', sheetRank: '47' » |
| B-249 | `visibility` joins the exit transition | the same 167, diffed line for line | `visibility` taken back out: both exit holds fall |
| 18 — B-142 | `scripts/check-intent-map.py`; **B-244 closed at seven guards** | — | three on the map; and the CI-filter hold seen RED over seven guards before the filter was fixed |

## The accepted divergences, in one sentence

**167, all on `shell/sheet-content`, all of one cause**: `padding: 2px 14px 76px` → `2px 14px 18px`
on 86 states and the height that follows from it on 81. They are B-248's, they are named in its
register entry, and every later phase diffed its own oracle report against them line for line rather
than against a count.

## Rules this wave added

**R100** `harness/persistence.py` — the chrome persists (P1, P2, P28), and the message's live region.
**R101** `harness/stacking.py` — one ranked order, hit-tested (B-237, B-248, the popover's clamp).
**R102** `harness/appearance.py` — the appearance survives a reload, the status bar follows (B-245, B-233).
**R103** `harness/exits.py` — a layer's exit is seen (B-249's frame half).

And two guards: `scripts/check-viewport-directives.py`, `scripts/check-intent-map.py`.

## The adversarial review, and what it changed

Three reviewers read the finished wave — one on the frame's product code, one on the
instruments, one on the seams. Every tier was green in front of them: 75 rules, `--a11y` at
zero, `make check` at zero, the oracle at its 167 enumerated divergences. **They returned
fifteen findings of the B-085 species and ten product defects**, and the register's table
carries the fifteen with their detail.

**The ten product defects, and none of them was reachable from a green gate:**

- **The destructive button was transparent with white text.** `selectionAction` declared
  `bg-transparent` in its BASE and `bg-danger-fill` on the `danger` branch — two utilities of
  equal specificity, and Tailwind emits colour utilities alphabetically, so `transparent`
  always follows `danger-fill`. Legible on the dark ground by accident; **white on white under
  `data-theme="light"`, contrast 1.00**. The residue's two rules never had this problem:
  `.selbar button.danger` (0,2,1) beat `.selbar button` (0,1,1) by specificity. The three
  properties a tone decides are now declared per tone and never in the base.
- **`.dlg p` lost its `color`** — the residue declared four properties and three were restated.
- **Three of the five layers never got B-249's exit idiom**: the message, the drawer and the
  confirmation still flipped `visibility` at the head of their transition. R103 read two.
- **The action button came back for one painted frame.** `useEffect` runs after paint, so the
  render that first sees `messageShown` false commits `hidden={false}` — the target appears
  under a finger still travelling towards the close it was aiming at, which is the whole reason
  the wait exists. `useLayoutEffect` closes that frame.
- **`publishBarHeight()` was still called from the boot**, where the bar no longer exists: it is
  a component since this wave. It is called from the bar's own layout effect.
- **`coverLoading` and `hideSignIn`'s `silent` were not forwarded whole** on `window.__entry`.
- **`window.__navigationState` was never published**, so a seam the harness names had no writer.
- **`window.__messagePresent` was published and read by nothing** — new machinery with no
  subject, in a wave whose own comments cite that shape twice. Deleted.
- **`render()`'s 404 fallback failed quietly**; it fails loudly now.
- **`data-dismiss` collided with the engine's own `dataset.dismiss`**, which calls
  `dismissSug(Number(…))`. An empty value is falsy, so the collision was inert — and would have
  become `dismissSug(0)` the first time anyone gave the attribute a value. It is
  `data-dialog-dismiss`.

**And one instrument was a false RED rather than a false green**, which is worth its own line
because the register's table does not hold that species: `hiding.py` slept 400 ms for a leave
measured at **403 ms on an idle machine**, and it came up red once in the full suite, where
eight browsers share four cores. It waits for the quiet state now, bounded, with the wait as its
own hold — so a message that never leaves is named there rather than mis-attributed to the
collision measured after it.

## The wave's gates, at the close

| Gate | Result |
| --- | --- |
| `harness/run.sh` (75 rules) + the 22 cheap guards | no violation |
| `harness/run.sh --a11y` | 87 states, 0 violation; light-theme ratchet 166 against a ceiling of 166 |
| `make check` | exit 0 — 10 936 passed, 4 skipped, 2 xfailed; frontend 1 374 passed |
| `oracle.py --check` | 167 divergences, all `shell/sheet-content`, all B-248's, enumerated above |
| `scripts/harness-hold-counts.py` (ACC-08) | `back.py` 12 → 17, `drawer.py` 26 → 28, `hiding.py` 26 → 27, four rules new; **no rule lost a hold** |

The hold-count baseline could not be compared against its own recorded commit — a squash merge
replaces the commit a branch-recorded baseline names, so the pointer dangles while every count in
the file stays perfectly good. `main`'s counts were re-recorded in a worktree and compared against
those; the new baseline is recorded on this branch and will dangle in exactly the same way for
the next wave.

## What this wave did NOT do, and said so

- **B-247 stays open.** A store bump replaces a feature page's DOM nodes, so a write between
  `pointerdown` and `click` destroys the tap. L15 stopped depending on it; the repair is in the
  surfaces, and the surfaces are L14's and L19's.
- **B-249's other half stays open.** The 260 ms wait belongs to a producer, and a producer is L19's.
  R103 measures the gap and PRINTS it rather than refusing a number nobody in this wave may change.
- **The install proposal's MARKUP did not move.** It is the one piece of the entry neither a server
  nor the first paint pins, so it is the one that can move at any time; moving it is forty lines of
  copy into `fr.json` for no property this lot owes.
- **No producer moved.** The ten `panel.open` producers, the Découvrir feed and the popover's
  sentence are L19's, and the inventory command still names them.
