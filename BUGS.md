# Bug register

## Rules of this file

1. Every defect the operator reports is written here the moment it is reported, with his words.
2. An entry is closed by its fix and a regression test seen red before the fix; the fix repairs the cause of the family, no instrument is built for it.
3. Status: `open` (diagnosed, not fixed) · `fixing` (being worked on) · `to confirm` (fixed, awaiting the operator) · `fixed #NNN` (in that pull request) · `closed` (operator confirmed).
4. History: a closed entry's full text is in git — cite `BUGS.md@638ebcfc`.
5. A row reads `| ID | Defect | Reported | Status |`; `Reported` counts how many times the operator had to say it (`2×`) or names who found it.

## Open

| ID    | Defect                                                | Reported    | Status       |
| ----- | ----------------------------------------------------- | ----------- | ------------ |
| B-030 | 87 library sheets carry no genre and no cast          | by rule     | `open`       |
| B-031 | « Réessayer » on every error surface is inert. **Owner:** the defects fast lane.          | by review   | `to confirm` |
| B-032 | The harness's data-scenario dial selects the wrong one. **Owner:** the tooling train. | by review   | `to confirm` |
| B-033 | `test_locks_tmp_orphans` is flaky under xdist          | by rule     | `open`       |
| B-034 | `TestQuickMode` reads a foreign `os.scandir` caller    | by gate     | `open`       |
| B-035 | `test_continues_on_per_file_error` writes no backup    | by gate     | `open`       |
| B-039 | `actions.py` prints `.freshtag` presence, asserts nothing | by mutation | `open`       |
| B-052 | A synthesised follow panel labels a film « Série »                  | by review   | `open`       |
| B-053 | A panel's layer entry is taken by a tab tap on the same layer (revisit) | by review | `open`     |
| B-054 | `data-go="acq"` no longer forces the « now » tab (revisit)           | by review   | `open`       |
| B-056 | A `@keyframes` name is French (`splashremplit`), invisible to no-french. **Owner:** the tooling train.  | by review | `open` |
| B-061 | The oracle cannot see a pseudo-element, so a class that generates nothing reads green. **Owner:** the tooling train. | by rule | `open` |
| B-068 | The wave's documentation drifted in forty small places, and one figure family is wrong. **Owner:** the steward's docs round. | by review | `open` |
| B-101 | The steward's brief predicted an oracle movement that could not happen. **Owner:** the steward's docs round. | by audit | `open` |
| B-143 | §17 (accounts, rights, Plex SSO) has no surface, no contract operation and no lot. **Owner:** L18 (§17, accounts, rights and Plex identity). | by audit | `open` |
| B-145 | §19 (cross-seed) has no route in either contract, and its events reach no stream. **Owner:** L17 (§19, cross-seed). | by audit | `open` |
| B-153 | The demand register is computed from OpenAPI paths, and a WebSocket has none. **Owner:** the steward's docs round. | by design | `open` |
| B-154 | `staleTime: Infinity` with no focus or reconnect refetch: a missed invalidation never heals. **Owner:** the backend brief, after the freeze. | by design | `open` |
| B-235 | No desktop navigation exists beyond the drawer. **Owner:** L24 (the orphans; the desktop-adaptation milestone). | by survey | `open` |
| B-247 | A store bump replaces a feature page's nodes, so a write between press and click destroys the click. **Owner:** the defects fast lane. | by L15 | `open` |
| B-249 | The screen flashes when a sheet action closes the sheet AND opens a page. **Owner:** the defects fast lane. | 1× | `open` |
| B-255 | `check-frontend-boundaries.py` is back at 952 lines, 48 from the hard ceiling it was cut away from. **Owner:** the tooling train. | by audit | `open` |
| B-267 | The real backend answers `{detail}`, which the queue's failure shape does not match — every refusal would be QUEUED at switchover. **Owner:** the backend brief, after the freeze. | by review | `open` |
| B-268 | R104 lives in the file it measures, and has been defeated twice by exactly that. **Owner:** the tooling train. | by audit | `open` |
| B-269 | Five corpus floors in `served_copy.py` are calibrated by hand, one figure per corpus. **Owner:** the tooling train. | by audit | `open` |
| B-270 | Two harness journals are labelled « R80 » — `attrs.py`'s has no number of its own. **Owner:** the tooling train. | by audit | `open` |
| B-273 | `scripts/mutate.sh` cannot judge a GUARD, and says « no hold fell » either way — and it exits SILENTLY when a mutation breaks the build. **Owner:** the tooling train. | by L12 | `open` |
| B-276 | A delay set by hand in an INSTRUMENT outlives the drawn duration it was set against — twice in one rule. **Owner:** the tooling train. | by L12 | `open` |
| B-277 | `exits.py`'s frame-count CONTROL flakes under the suite's parallel load — 2 falls in 3 runs, green alone. **Owner:** the tooling train. | by L12 | `open` |
| B-278 | The drawer's dismiss acknowledges itself TWICE — two marks, same millisecond, both with no previous value; unexplained. **Owner:** the tooling train. | by L12 review | `open` |
| B-288 | The media screen's priming matches a title by PREFIX, so a medium whose title prefixes another opens with the other one's poster and year. **Owner:** the tooling train. | by L12 review | `open` |
| B-291 | `harness-hold-counts.py --record` writes a reference nobody can tell from a good one: a `taken_at_commit` no guard checks (L12's gesture left it naming a squashed-away commit) and a baseline written over a rule that FAILED. **Owner:** the tooling train. | by audit | `open` |
| B-293 | 38 `Design:` markers name `docs/features/…` paths that left the tree, and the design-gaps pair passes over them. **Owner:** the tooling train. | by audit | `open` |
| B-299 | `SettingsState.conflict` is declared, set to `false` at boot, and never raised, drawn or copied — the conflict the contract answers has no surface. **Owner:** the conformity train's consolidation phase (12). | by survey | `to confirm` |
| B-300 | « Redémarrer maintenant » restarts on the tap, with no confirmation, while a restart cuts the service for the whole household. **Owner:** the defects fast lane. | by survey | `to confirm` |
| B-303 | A mutation applied BY HAND leaves the served copy of the previous build in place, so the reading taken next measures code nobody is testing — and a restore by `git checkout --` over the maquette's sources destroys whatever else is uncommitted there (the number is 303 and not 296 because #549 held 296-302 on `main`-to-be). **Owner:** the tooling train. | by L14 | `open` |
| B-304 | `git add -f` applied to a PATH rather than to the ignored files it was needed for swept 28 375 files into a commit, `node_modules` entire, and nothing in the repository refuses it — the only guard that noticed read five French PATH SEGMENTS, and they were the MAQUETTE's own ignored screenshots, not the vendored tree. **Owner:** the steward's docs round. | by L14 | `open` |
| B-307 | **Four** rules have now fallen under the recorder's parallel load and passed alone; the register holds one of them, under a title naming a fourth rule and a diagnosis that does not transfer. **Owner:** the tooling train. | by audit | `open` |
| B-309 | « Récupérer maintenant » on a medium's own panel THROWS and takes nothing: the release screen's `data-take` branch is checked first, has no guard, and swallows every `data-take` in the document. **Owner:** the defects fast lane. | by L19 | `to confirm` |
| B-311 | Coming back to a list after a medium's sheet does not restore the scroll position the list was left at. **Owner:** the defects fast lane. | 1× | `open` |
| B-312 | Changing the library's lens during a selection DROPS it — L14's own decision, RULED against by the operator on 2026-09-05. **Owner:** the defects fast lane. | 2× | `to confirm` |
| B-314 | The add screen's search shows no example result to try the flow with. **Owner:** the defects fast lane. | 1× | `open` |
| B-317 | The prototype's greeting toast covers the settings save bar, so a finger there does nothing while it lives. **Owner:** the defects fast lane. | 1× | `open` |
| B-318 | The build races its own output on a fresh `dist` again — B-098's shape, in two hooks this time. **Owner:** the tooling train. | 1× | `open` |
| B-319 | `fanout.py` holds the invalidation map against itself: a key dropped from the declaration is invisible to it. **Owner:** the tooling train. | 1× | `open` |
| B-320 | React #300 and #310 on the two non-ready acquisition surfaces, from a cold page, on head and on `main` alike. **Owner:** the defects fast lane. | 1× | `open` |
| B-324 | The BACKEND's own mirror of the PM2 crons names three of the seven the machine runs, and nothing reads it against `pm2 jlist` — B-308's finding on the end that has no guard at all. **Owner:** the backend brief, after the freeze. | by the backend brief | `open` |
| B-326 | `heavy.sh` offers no way to ask who holds its lock, so the natural probe — `cat` on what is a DIRECTORY — reads « free » whether the lock is held or not, and two sessions reached for it independently on the same night. **Owner:** the tooling train. | by the steward's office | `open` |
| B-327 | « Réglages » draws SIX scheduled jobs while the machine runs seven, and the same six are named twice in two French vocabularies that disagree on five of them — the row cannot be added until `SETTINGS` leaves the engine. **Owner:** the backend brief, after the freeze. | by L13 | `to confirm` |
| B-328 | `features/system/page.tsx` heads itself with a path that does not exist and describes a state field (`state.panne`) the code does not have. **Owner:** the conformity train. | by the next wave that opens `features/system/page.tsx` | `open` |
| B-329 | The backend's GENERATED contract does not declare the `409` its own route raises, so no diff between the two contracts can read it — the demand register is structurally blind to a refusal NE-DOIT-PAS-3 forbids the interface to show. **Owner:** the backend brief, after the freeze. | by the backend brief | `open` |
| B-330 | `scripts/mutate.sh` answers « no hold fell » when the RULE PATH it was given does not exist — a typo and a rule that does not bite are the same sentence, and the second is a finding while the first is a mistake. **Owner:** the tooling train. | by the instruments' debts block | `open` |
| B-331 | Réglages' pull-to-refresh indicator is drawn off-centre, at the left edge, and is still on screen after « Actualisé. » — R199 `pull_follows_the_refresh.py`: the CLOSING half is repaired (L13c c·5, the indicator now closes with the refresh's own answer time, 233/532/1716 ms against the control's fixed 1356/1347/1350 ms). **The CENTRING half is unmeasurable here** (reader C13's C6, round one: offset 0 on BOTH builds at every moment on this machine — the mechanism is real, proved by the centring mutation alone (−187 px, drawing the operator's own screenshot), but nothing on this machine separates candidate from control). **Owner:** the conformity train. | 1×; L13c c·5 | `to confirm` |
| B-333 | « Many pages have no back button, and the Back gesture does not work either » — the operator's reading of the frame's Back contract on the phone; one instance measured (B-332), the inventory of the others is owed. **Owner:** the defects fast lane. | 1× | `open` |
| B-336 | The library's kind chips (« Tout · Films · Séries », with counts) scroll horizontally with a VISIBLE scrollbar on the phone; the strip should hide it as `pillscroll` does. **Owner:** the conformity train. | 1× | `to confirm` |
| B-337 | A follow card swiped open: the first tap on a revealed action does nothing, the second acts — systematic on the phone. **Owner:** the defects fast lane. | 1× | `open` |
| B-339 | A DISABLED panel action is drawn exactly like an enabled one — « ✓ Ajouté » on the add screen's panel is `disabled` in the markup and full primary yellow on the screen, so the reader taps a spent act and « nothing happens ». **Owner:** the conformity train. | 1× | `to confirm` |
| B-340 | The « + » button reopens the add screen with the LAST query and mode still in place — after identifying an arrival, a new search starts on « Marvels Spider-Man 2 v1 526 0 -Mephis… », 0 results, and the « 2 médias ajoutés » strip of the previous visit. **Owner:** the defects fast lane. | 1× | `to confirm` |
| B-345 | The seeded data does not show every state a surface can take — the operator could not find a single medium « à prendre » to try « Récupérer maintenant » on; his ruling: the test data must always hold enough simulated states to exercise every case by hand. **The LIBRARY half closes as already satisfied, now guarded** (L13c c·8: the seeds already held every state the library draws — 345 loaded rows, a title held twice, a followed title, five incomplete, 20 without a poster; R128 gains eight holds, GREEN from the start, no seed touched — reader C13's C4, round one: nothing here for the operator to walk). Acquisition's share is L21's, settings' is #588's. **The OTHER surfaces' share stays open**, owner: a later lot. **Owner:** the defects fast lane. | 1×; L13c c·8 | `to confirm` |
| B-351 | `check-maquette-comments.py` reads five suffixes and `.mjs` is not one of them, so every `.mjs` under `frontend/maquette/` is invisible to the comment rule AND to the corpus count the floor is derived from — one real occupant measured, `vite.config.mjs:143`'s « (L08) ». **Owner:** the tooling train. | by L21 | `open` |
| B-360 | The pre-push gate refuses a push over a GREEN suite and shows the reason to nobody: each check runs silently first and, when that pytest dies of a signal, is rerun visibly — the rerun's « 11 325 passed » is printed and its result discarded, so the reader gets a green summary, then « Push aborted », and the failure in no output; three refusals in one morning on two branches, the same push landing on its next attempt. **Owner:** the tooling train. | 1× | `open` |
| B-363 | `residue.py` reads a typed variant's base through its string LITERALS, so a factory built from a shared constant reads EMPTY and is reported unreadable — a token scale cannot be written once and shared between two variants while that is true, and the repair that suggests itself (concatenating a literal with the constant) silences the report and leaves the reader comparing one token. **Owner:** the tooling train. | 1× | `open` |
| B-364 | Two hit-test helpers in `busy.py` press `hit.click()` on whatever `elementFromPoint` returns, and an SVG element has no `click` — so a rule that hit-tests an ICON-ONLY action throws `hit.click is not a function` instead of pressing it, and the same helpers print `hit.className` as the coverer, which on an SVG is an `SVGAnimatedString` and reads `[object SVGAnimatedString]`. **Owner:** the tooling train. | 1× | `open` |
| B-366 | A follow with NO MEDIA SHEET is drawn at all — a grid tile emits `data-mediasheet` for it, a poster that leads nowhere. RE-RULED by the operator: a follow without a sheet is not a state the product may represent, so the repair is to make it unrepresentable rather than to guard the tile. **Owner:** the defects fast lane. | by audit | `to confirm` |
| B-367 | The drawer's appearance control applies the theme and does not move its selection: pressing one of the three writes the choice and repaints the document, and `aria-pressed` stays on whatever was drawn when the drawer opened — so the operator reads « Clair » selected over a dark interface. Closing and reopening the drawer draws it correctly. **Owner:** the defects fast lane. | 1× | `open` |
| B-370 | `harness-hold-counts.py --compare` with no FILE exits 2 on an argparse usage error, which a gate reading exit codes cannot tell from a comparison that found drift — one pass of L21's gate compared nothing while looking like it ran. **Owner:** the tooling train. | 1× | `open` |
| B-388 | R51 promises « the prototype's own controls never sit on top of the app's » and reads ONE piece of harness chrome by literal — `[data-part="harness/bar"]` — so a second piece is outside it whatever the docstring says; the property now holds by two rules each naming its own subject, and a third would be held by neither. **Owner:** the tooling train. | by audit | `open` |
| B-389 | The 8899 harness host does not survive the invocation that starts it when that invocation runs under `scripts/heavy.sh` — `set -m` puts the run in its own process group and the release signals the group, so `mutate.sh`, which starts no host, runs its rule against a refused port and B-273 reads the crash as « no hold fell ». **Owner:** the tooling train. | by audit | `open` |
| B-390 | No arm of `check-no-french.py` reads TEXT in `frontend/maquette/design/index.html` — the Strings and Identifiers arms are rooted on `design/src`, and the only arm that opens the file reads attributes — so « the guard does not refuse these labels » was never evidence that an arm had read them. **Owner:** the tooling train. | by audit | `open` |
| B-391 | The DECLARED HARNESS DEVIATION block calls itself « the ONLY accepted divergence in the shell » and makes FIVE declarations, of which ONE diverges — the other four restate what the app's own variants already declare, so they can witness nothing and hid a dead comparison in the rule that reads them. **Owner:** the tooling train. | by audit | `open` |
| B-460 | R161's h2 floor is green over an affordance made invisible by `opacity: 0`, a clip or an off-screen transform — it reads a box above zero and `visibility`, two of the five ways to take a mark away. **Owner:** the tooling train. | by review | `open` |
| B-461 | `resolution_window.py`'s `LAST_FRAME = 6500` is called « the message's last reachable frame » while the message's opacity is 0 there, so only a SHRUNK window is armed — a message outliving the window passes all eighteen holds. **Owner:** the tooling train. | by review | `open` |
| B-462 | The candidate card's accessible name is its title and year alone, so the confidence, the provider, the kind and the synopsis are announced to nobody on the screen whose whole job is choosing between near-identical candidates. **Owner:** the defects fast lane. | by review | `open` |
| B-463 | `csstokens_ranks.py` attributes a rank to the nearest `export const` above it, so a rank declared under an unrelated binding passes silently at an already-recorded number and names the wrong site at any other. **Owner:** the tooling train. | by review | `open` |
| B-464 | The same arm never opens three scopes: a `<style>` block in the shell's markup, a `.css` in a subdirectory of `styles/`, and a negative `-z-N` utility. **Owner:** the tooling train. | by review | `open` |
| B-466 | `ui/variants/frame.ts` sits at 399 non-blank lines against a hard ceiling of 400, and the arm this wave added is what will demand the four-hundredth. **Owner:** the tooling train. | by review | `open` |
| B-471 | `readMediaSeasons` DECLARES `Season[]` (`{season, owned, aired}`) and ANSWERS the sheet's catalogue (`{number, episodes, airDate}`): two different shapes at one operation, and `contract-conformance.test.ts` cannot see it because it reads only a response's first-level required fields, never an element's. **Owner:** the tooling train. | by the mock-layer micro-wave | `open` |
| B-472 | `scripts/heavy.sh` takes its lock with a polled `mkdir` and no queue, so among several waves waiting an old demander has no precedence over a new one: with four agents on the machine the lock, not the work, sets a wave's pace. **Owner:** the tooling train. | by the mock-layer micro-wave | `open` |
| B-475 | The library holds episode numbers the catalogue does not list — American Dad! S16 holds 1–24 where the catalogue lists 20, Les Animaniacs S2 holds `[1, 4, 7, 9, 76–82]` where it lists 12 — and they are counted and drawn NOWHERE: every surface counts the numbers at or below what aired, so four and seven held files vanish. **Owner:** the backend brief, after the freeze. | the operator's ruling on numbering orders, then the wave that draws it | `open` |
| B-476 | « Dexter: Resurrection » is followed under a title no sheet carries (the sheet is « Dexter Resurrection », and its holdings are keyed there), and the follow's totals 96/96 are not its seasons' sums 10/10: one show, three families, three answers. **Owner:** the backend brief, after the freeze. | the wave that next touches the seeds' identity | `open` |
| B-477 | House of the Dragon, Ted Lasso and Strange New Worlds are followed « à jour » (26/26, 35/35, 33/33) while their media sheets answer `owned: false` — the holdings are keyed under « House of the Dragon (2022) » and « Ted Lasso (2020) », titles the sheet's identity does not name, or absent — so the follow says held and the sheet says not in the library. **Owner:** the backend brief, after the freeze. | the wave that next touches the seeds' identity | `open` |
| B-492 | Out of the desktop frame the overflow B-491 confined is the APP's own cascade — no element of the shell clips its absolute layers — so once `harness.css` ships nowhere a desktop document can scroll beside `#port` again. **Owner:** L24 (the orphans; the desktop-adaptation milestone). | by the scroll-jump micro-wave | `open` |
| B-495 | `scripts/heavy.sh` prints « holding off » once and « starts » with no timestamp, so how long a wrapped run WAITED for the lock and the readiness floor is unmeasurable afterwards — on 2026-09-13 the steward could not say whether a classed run held for a minute or an hour behind a host whose own one-minute load ran 9–15. **Owner:** the tooling train. | the next tooling wave (frozen apparatus: not before a defect reaches the operator) | `open` |
| B-496 | `hooks/pre-push`'s `run_check` runs a check with its output sent to `/dev/null` and, when it fails, RUNS IT AGAIN to show the output — so a check that falls once and passes on the re-run prints a green summary under « FAILED », and the only reading of the fall is discarded. **Owner:** the tooling train. | the next tooling wave | `open` |
| B-498 | Tile badges (`--waiting`, `--info`, `--warning`, `--neutral-signal`) draw with no fill the reader round could resolve to a declared token. **Owner:** the conformity train. | the reader round | `open` |
| B-502 | `index.html`'s `#ptr` utilities are erased by `__reposPTR`'s `className = "ptr"` at every driver reset — pre-existing, not repaired at a·18. **Owner:** the tooling train. | by review | `open` |
| B-503 | `panel-seasons.tsx`'s first render seeds two DISABLED query entries with an empty provider/id before the identity is known — inert, measured at 1 observer while the panel is open. **Owner:** the tooling train. | by review | `open` |
| B-504 | `frontend/maquette/harness/panel.py` has no deadline: a mutation that should fell it (`hasSheet: false`) hangs the served-copy lock instead, unwatched for 47 min. **Owner:** the tooling train. | the reader round | `open` |
| B-505 | `scripts/mutate.sh` read a MISSING rule path (`python3` exit 2, « can't open file ») as « FELL » — eight green-looking verdicts over nothing on L13b's b·5. **Owner:** the tooling train. | by L13b | `open` |
| B-506 | Without a mocks-on build, « Notes de conception » is drawn and answers nothing — its handler installs only `if (__MOCKS_BUILT_IN__)`. **Owner:** the tooling train. | the reader round | `open` |
| B-507 | `phase-a19`'s prescribed R72 (b) mutation is not the one the wave ran, and the plan's own mutation (removing the tag) does not fall alone — it fells (c) as well. **Owner:** the tooling train. | the reader round | `open` |
| B-508 | A typed media address whose read fails keeps an empty hero title and says « Bande-annonce inconnue. », unnamed by any ruling. **Owner:** the defects fast lane. | the reader round | `open` |
| B-509 | `bridge.py:300`'s hold « and the media sheet is gone » never asserts the sheet was open before the Back it reads. **Owner:** the tooling train. | the reader round | `open` |
| B-510 | Ruling 61's restoration is held by `bugs.py`'s crash on the missing button, not by a named hold asserting « Voir la fiche » present. **Owner:** the tooling train. | the reader round | `open` |
| B-511 | Ruling 61's register note says « 0 updates, 0 observers » where the measured candidate reads 1 observer on each empty-key query entry while the panel is open. **Owner:** the tooling train. | the reader round | `open` |
| B-512 | `selection_survives_the_tab.py` (R164) reads « the Médiathèque draws the bar over a real selection » red under the 28-named gate load and green alone — 2 red / 2 green on b·6's head in that shape, green before the move in the 19-rule shape; at the failing instant the bar exists and the point at its centre hits a tile's poster; its detail string is armed to name what hid the bar; owner b·13's full suite. **Cause (2026-09-30):** the prototype's welcome hint toast (z 57, above the bar) is still up when a slow boot is measured; the rule now enters measurement mode like the others. | by L13b | `fixed #654` |
| B-513 | The « a markup literal nobody compares » class is UNGUARDED since b·7: `check-markup-contracts.py`'s forwarded-value arm read `store.write({f: …dataset.x})` — the engine's delegation — and checked every emitted `data-*` literal against the readers that compare it, which is what caught `data-phase="prete"` (B-031) and a `data-fmode="gird"` that rendered nothing. The engine forwards nothing now: each name is answered through the tap registry, where a verb receives `node.dataset[key]`, so the same defect is writable and nothing reads for it. Re-aiming the arm at the registry's reads WIDENS its subject (ruling 78, measure 1), so it was deleted rather than re-pointed (ruling 87). Candidate: an arm reading the registry's dataset reads, after L13 — the operator's or the auditor's call. **Amended (L13r's docs PR)**: the same class lost two more instruments with their subjects since — the reference-slice arm at r·5 (ruling 104, `__referentiel` died) and the joined-fields correspondence check at r·17 (B-539) — neither re-aimed, both candidates for the after-L13 arm above. **Owner:** the tooling train. | by L13b | `open` |
| B-516 | `follow_seasons.py` (R192)'s named case and floor read the SEED, not the comparison: `if not sheet and not panel: continue` skips a series drawing no rows on both surfaces, « Silo is among the series compared » checks `NAMED in series`, and the floor `compared >= 5` holds for 9 series — a mutation making Silo answer nothing on both surfaces (as 4 of the 9 already do) stays green; owner the next repair train. **Owner:** the tooling train. | the reader round | `open` |
| B-517 | Two comments outside `engine/legacy.js` still name the deleted `paintSelBar` as a living model — `features/library/page.tsx:18-25` and `features/acquisition/discover-tab.tsx:12` — true on L13b's control head, false since b·6 (`c74362af1`, B-465's own gesture); owner L13r r·6. **Owner:** the conformity train's consolidation phase (12). | the reader round | `open` |
| B-532 | Three sites still write `<details>` raw after `ui/disclosure.tsx` exists — `features/acquisition/add-screen.tsx:353`, `features/media/season-list.tsx:256`, `features/media/panel-seasons.tsx:142` (`docs/features/maquette-l20/DESIGN.md@60c6d9b1d` § 9). Converting them is a three-surface conversion, which « one kind of change per wave » forbids a behaviour lot from carrying; it belongs to whichever lot next opens those files. Owner: none yet. **Owner:** the conformity train. | by L20 | `open` |
| B-537 | `check-markup-contracts.py` is green over the four lock part names: a literal `data-part="flux/row"` is overridden at runtime by the FactRow spread (`{...row, part: PARTS[index]}`) into `locks/pipeline`, `locks/pause-sentinel`, `locks/watcher-sentinel`, `locks/orphan`, and the rules select those four by computed selector, which the guard skips — nothing fails, the guard does not read them (instrument reading); owner `scripts/check-markup-contracts.py` (read spread part names) or literal parts in `locks.tsx` — apparatus frozen, measure 1. **Owner:** the tooling train. | the reader round | `open` |
| B-538 | A RUNNING history row has nothing to report on its second line — duration is null while running, so the row reads one text line shorter than the same row once ended (−14.8 px on `system/runs`, the page following), C8's consequence: a drawing choice for the operator's walk is that a running row's second line could say the elapsed time instead. Six oracle divergences accepted by name as this cause (`run-detail-running`, `watch-running` × `system/runs`, `system/body`, `shell/page`), STOP A ruled by the steward 2026-09-15 ~13:xx = option A. Owner: none yet — a behaviour wave on Système. **Owner:** the defects fast lane. | the reader round | `open` |
| B-539 | The joined-fields guard's loss (L13r r·17, ruling 114): `check-mock-seeds.py`'s correspondence arm joined a seed's `ids`/`poster` against the engine's own tables to catch drift between them — the builder that read both sides died with `engine-shape.ts`, and the seeds' ids/poster columns are now held by the `answers` schema arm alone, which checks each seed against its contract schema and never against the other seed. No cross-seed join check exists; owner none (B-513's shape). **Owner:** the tooling train. | L13r | `open` |
| B-540 | `scripts/rename-identifiers.py` refuses `useAcquisitionReference` as a shorthand property inside `import { useX, type Y }` — an import specifier, not an object — and printed « Nothing written, in any file » while four other files of the same run WERE rewritten (met at L13r r·5); workaround `--properties`, the diff read and typechecked; owner none — the tool is main's. **Owner:** the tooling train. | L13r | `open` |
| B-541 | Six harness rules CRASH rather than print a FAIL line when their re-aimed subject is mutated under a shape mutation, instead of falling by name: `busy.py` and `follow_has_sheet.py` (L13r r·8), `producers.py`, `secret_acts.py` and `seeds_at_rest.py` (r·10), `filters.py` (r·11, a prose rule with assertions). Ruling 77: « RULE CRASHED » is no verdict, so the crash proves the re-aimed read is LIVE and proves nothing about whether the rule judges it; owner none — apparatus frozen. **Owner:** the tooling train. | L13r | `open` |
| B-542 | Three harness rules read vacuously under the family shape mutations that should exercise them (L13r r·8/r·11): `audit.py`'s vocabulary check reports nothing on a follow carrying no `kind`, vacuous by its own design; `address.py`'s « every drawn address is the account's » holds trivially over the empty set when no address is drawn; `page_host.py` prints the action title it reads and no hold compares it against anything. None fell under mutation and none is guarded against it; owner none — apparatus frozen. **Owner:** the tooling train. | L13r | `open` |
| B-543 | `app/engine-data.ts` (the follows/staging prefetch, the driver's refill) and `app/engine-redraw.ts` (deck redraw on a query's arrival) are LIVE frame behaviour, inherited from the engine they left at L13r r·15 — their names still say « engine ». A rename is a later conversion; owner none (Re-read 2026-09-29: `app/engine-data.ts` died in `232a908ca`, #626; the defect survives in `app/engine-redraw.ts`.). **Owner:** the conformity train's consolidation phase (12). | L13r | `open` |
| B-544 | `virtual.py` read `features/library/reference.ts` by a path L13r r·5 renamed, and no phase gate between r·5 and r·18 named the stale reference — thirteen phases of full-suite gates passed over a `FileNotFoundError` this rule would raise the moment it ran, until r·18's own gate caught it. Re-aimed at `types.ts` in the same commit (`326ff6c4d`), gate green after; owner none — the instrument gap that let it stand. **Owner:** the tooling train. | L13r | `open` |
| B-545 | `scripts/check-no-french.py`'s unread-JavaScript arm counts untracked files as well as tracked ones: PR #605's body said it walked 372 files, the head's tracked count (`git ls-files`) is 370 — the figure is not a property of the commit (R4, round one's reader). Owner none — apparatus frozen. **Owner:** the tooling train. | the reader round | `open` |
| B-546 | Two unnamed falls under load in one evening, neither reproducible: CI's `harness-contracts` fell once on `audit2.py` (run `35012800269` on `d1526a0f1`, no hold line in the log) between two green runs on identical source (`35000037648`, `35017658636`); and `outbox.py` exited 1 during the steward's 141-rule hold-counts record at the sub-lot's gesture (22:26), green alone minutes later (`gesture-l13r-2256.log`). Neither is called « flaky » — the mechanism is not named. Two more `audit2.py` R11 falls on #608 (runs 35076327531, 35077284519); three loaded readings by the repair train of 2026-09-16 caught nothing — the CI runner is the only place it falls. A third occurrence (2026-09-27 14:4x), on #623 at `d1efa32d7` — a docs-only PR touching no file under `frontend/`, `scripts/`, `personalscraper/`, so the build is `main`'s own — R11 fell again (1 violation, « visible jargon or technical value »); the job re-run removed the load the fall needed, which is said, not proved. Mechanism still unnamed; **Owner:** the tooling train. | L13r | `open` |
| B-547 | `test_maintenance_panels.py::TestLocksRoute::test_locks_tmp_orphans` read `len(data["sweep"]["orphans"]) == 0` instead of 3, deterministically on worker gw2, twice, on the L13r docs pull request's pre-push run (2026-09-16). NOT a load race — alone, on the branch and on `main`, it passes in 1.1 s. **Mechanism: a test-order dependency, exposed by this branch's own test deletions (the debt arm's) moving the xdist distribution.** `_orphan_cache` is a MODULE-LEVEL cache (`personalscraper/web/routes/maintenance.py`); `get_locks` starts an un-joined daemon thread to fill it when stale, and two sibling tests — `test_locks_stale` (runs immediately before this one) and `test_locks_returns_pending_sweep_on_cold_read` — each trigger that thread and return without draining it, so it can still be running when the next test's `_reset_orphan_cache` fixture clears the cache and starts its OWN sweep: the leftover thread's later write (its own, usually-empty, result) can land after the current test's real one and overwrite it. **Repaired in this same pull request** (test-only commit, measure 5): both leaking tests now call `_wait_for_sweep` before returning, so no background thread survives past its own test. Same species as B-033's `test_locks_tmp_orphans` flake under xdist — B-033 stays open (this repairs a DIFFERENT reachable path to the same symptom, not xdist load in general). **Owner:** the tooling train. | the docs pull request's pre-push run | `open` |
| B-548 | Named states inherit a library dial by their ORDER: the driver's `reset()` (`harness/drive.ts`) does not write `libLens` or `libMode`, so `lib-incomplete`, `lib-recent`, `lib-search-empty` and the four `mediasheet-*` states are recorded in `oracle-reference.json` in the list layout inherited from `lib-list` before them; a probe resetting both moved 38 measurements on those seven states (`shell/library-list` display flex → grid, gap 8 → 10 px, heights). `libCat` and the sort were the same defect, invisible until a state or a rule moved them, and are reset since L13c c·1. **Amended by reader C13's C9** (round one, `review-archive/l13c/round-1/r1-C13.md`): driving all 114 named states twice, 103 inherit `libLens` from the state before them, and of those only NINE draw differently by the order — `pwa-android`, `signin`, `signin-error`, `lib-delete`, `lib-delete-multiple`, `mediasheet-series`, `mediasheet-movie`, `mediasheet-no-trailer`, `mediasheet-no-poster` — each drawing the library page underneath a sheet or a dialogue without pinning the lens; R198's cast half reads `mediasheet-movie` INSIDE the sheet, so no verdict of L13c moves. Ruling 117 deliberately declined resetting `libLens`/`libMode`. Owner: none — an instrument decision, not yet made; the fix is either the nine states pinning their own lens, or `reset()` writing both, plus the reference re-recorded. **Owner:** the tooling train. | L13c c·1's probe; amended reader C13 | `open` |
| B-549 | The mock seed gives the FILM « Star Wars : The Clone Wars » the SERIES' provider identifiers (`imdb:tt0458290`, `tmdb:4194`, `tvdb:83268`) — a fixture-identity defect, same class as B-088: two rows of different KINDS sharing one identifier set. `add_footer.py` fell on a second add until c·2 keyed a visit's identity by `kind` + sorted `provider:id` pairs (`f67401890`), which separates the pair; the seed row itself is untouched. **Owner:** the tooling train. | L13c c·2 | `open` |
| B-550 | The library's selection bar actions sit under the touch floor at 390 px: « Annuler » 71×34, « Supprimer » 86×34, against the 44 px a thumb needs — on BOTH builds, so the defect is old, not L13c's. Found by reader C13's affordance lens (round one, C8). Owner: a later lot — the bar's action variant in `ui/variants/`. **Owner:** the conformity train. | reader C13 round one | `open` |
| B-552 | The library's lens segment sits under the touch floor at 390 px: its tabs measure 34 px tall (`segmentTab` in `ui/variants/controls.ts`, `py-4 text-4`), against the 44 px the harness holds locally (`add_footer.py` `TOUCH_TARGET = 44`; no written directive names the floor). Found by R206's red reading on Acquisition's bar, which phase 8 of L22a lifted to 44 px (RULINGS 3) without touching the shared primitive. Owner: none — the operator's walk decides. **Owner:** the conformity train. | R206 red reading, L22a phase 8 | `open` |
| B-554 | The `shell/dialog` region measures a CLOSED dialog's stale box: `#dlg` keeps the last descriptor drawn after it closes, so a state's reading of the region depends on the last dialog ANY earlier state opened in the run order — 63 states moved together when L22a's `acq-abandon-confirm` (phase 11) became the last dialog before them, nothing they draw having changed (RULINGS 7 of L22). The same mechanism holds for the closed `#sheet` on `shell/sheet-content`: it keeps the last panel's box, and 42 states moved together when L22b's `acq-resolution-not-media` (phase 16) became the last panel before them (RULINGS 13). A third inheritance of the same family: `acqTab`, a dial the driver's reset leaves, so a state setting the Acquisition page without its tab drew the tab the state before left — three states pinned their tab when « Découvrir » left the tabs (RULINGS 20). A second occurrence of the closed `#dlg`: L22b's phase 24 added three confirmation states of « Supprimer », which became the last dialog of the run order before 63 states — all moved on `shell/dialog` alone, accepted by name under RULINGS 7. A fourth inheritance of the same family, read at L22b phase 38 (2026-09-28 05:44): `signin` and `signin-error` inherit the PAGE the state before them drew, because `showSignIn` (`frontend/maquette/design/src/app/entry.ts`) never pins a page — it toggles `#login`/`#loginerr` and rewrites the address, nothing else — species B-554, family of RULINGS 20 (a dial the driver's reset leaves unpinned reads the run order). A driver reset that cleared the descriptor would end it. **Owner:** the tooling train. | L22a phase 11 gate | `open` |
| B-559 | The rule `pwa.py` falls under load on `Page.goto: Timeout 30000ms exceeded`, with no hold read — an INSTRUMENT fall, not a verdict. Split from B-558, which it was filed beside (« possibly the same family, possibly not »): B-558's repair makes the ORACLE read in measuring mode and `pwa.py` does not import the oracle, so that repair does not reach it. Read twice on 2026-09-28 at `d29332cfe` (branch `fix/maquette-repair-2026-09-27`), both through `run.sh --contracts --oracle pwa.py` with `TM_HARNESS_JOBS=3` under `scripts/heavy.sh`: GREEN on the first run (heavy started at load 4.75, log `~/Library/Logs/tm-repair-0928/gain-gate-form.log`), FELL on the second (load 3.76 at start, 3.91 at the end; `FAILED: pwa.py` — `playwright._impl._errors.TimeoutError: Page.goto: Timeout 30000ms exceeded.`, log `gain-gate-form-2.log`). Run alone through `run.sh --rules pwa.py`, twice green (54 holds). Two readings are no rate; the cause is not read. Frozen by measure 1. **Owner:** the tooling train. | repair train 2026-09-28, gain measurement | `open` |
| B-561 | A folder with no identity opens a « Série » panel: Backrooms (dense « À traiter ») and the game folder (control) draw « Série · — épisodes » and « Aucune donnée de saison connue pour cette série » — ruling 5 draws such a folder WITHOUT identity, so the panel names a kind it is not owed. Old, present on the control (main) before L22b; the lot moved these folders into Acquisition's own tab, where reader B22 read it again. **Owner:** the defects fast lane. | reader B22, `review-archive/l22/round-1-B22/r1-B22.md` § B8 | `open` |
| B-562 | A one-off season ask's own confirmation carries no sentence of its own: read by reader B22 as a disagreement — « Récupérer la saison 5 » on an unfollowed show answered « Saison 5 de « Les Animaniacs » demandée — aucun épisode à récupérer. » while « En cours » drew the one-off card reading « 0/23 · 23 manquants » — fixed in #626 (`2b7b17d06`, `episodesMissingFromSeason` now counts a season `SEASON_COUNT` does not carry the way the season surfaces draw it, `seasonsAnswer`), so the two now agree. What is NOT fixed, by the fix's own commit body (« a sentence of its own for the one-off is a copy decision, left to the steward's docs PR »): the toast still reuses the FOLLOW family's generic `seasonAsked`/`seasonAskedOne`/`seasonAskedNone` (`i18n/fr.json`) for a one-off acquisition too, unlike `taken`'s own « … suivez-le dans « En vol ». » — no sentence says where a one-off went. Owner: none — the design owes the one-off's own copy. **Owner:** the defects fast lane. | reader B22, `review-archive/l22/round-1-B22/r1-B22.md` § B5; fixed in part #626 | `open` |
| B-563 | `frontend/maquette/resync.py`'s `ENGINE` constant still points at `design/src/engine/legacy.js`, deleted whole at L13r (`08400a22a`, #605, 2026-09-15) — `main()` calls `ENGINE.read_text()` unconditionally and CRASHES with an uncaught `FileNotFoundError` before reaching the graceful path its own header comment describes (« a stale path here would not corrupt anything — main reports « FOLLOWS block not found » and writes nothing »): that graceful message only fires when the file EXISTS but lacks the block, never when the path itself is gone. Reproduced 2026-09-28 on this branch: `python3 frontend/maquette/resync.py` — traceback, `FileNotFoundError: [Errno 2] No such file or directory: '…/design/src/engine/legacy.js'`. Broken since L13r (thirteen days), silently, because nothing in `make check` or CI runs this tool — it is invoked by hand only, when the suite names a counter drift. Owner: none — the tool needs a new source for the FOLLOWS block and the drawer footer it also rewrites, now that neither lives in the engine. **The same death took the seed-rebuild command with it**: `scripts/build-mock-seeds.py@c0a5062ac` and `scripts/extract-maquette-fixtures.mjs@c0a5062ac`, both instructed by `README.md`'s own mock-layer section, do not exist in `git ls-files` — deleted at the same L13r commit, `build-mock-seeds.py` alongside `legacy.js` itself. `check-mock-seeds.py` (still live) now validates seeds against the contract schema and a register/contract provenance correspondence, never against a fixture it rebuilds from — the README's own commands were left pointing at a rebuild step that no longer exists. **Owner:** the tooling train. | found while correcting `frontend/maquette/README.md`'s own stale references to `legacy.js`, at L22's close | `open` |
| B-570 | `scripts/check-live-relay.py`'s map-completeness arm reads an address only where it is SPELLED as a literal (`read_addresses`, `check-live-relay.py:522`: `queryKey: ["…"]`, an exported `…Key` constant, `useSystemRead("…")`, `prefetchQuery`, a `key:` table). A feature keying its reads on a module constant — `queryKey: [TRACKERS_ADDRESS]` in `features/trackers/queries.ts` — is invisible to it, so `/api/trackers`, `/api/acquisition/downloads` and `/api/acquisition/obligations` were read by a surface, refreshed by no event and exempted nowhere, while the guard printed green. **Escaped from**: every gate of L16 phases 1–8 (the guard runs among the cheap guards of the full suite only); **why**: the corpus is a list of spellings, not the cache's own keys — the shape « Guards green over what they do not read » counts; read at L16's midpoint suite (2026-09-29) only because phase 9's « Vu » verb spelled `queryKey: ["/api/trackers"]` as a literal. **Family**: every arm that collects identifiers by spelling. The three addresses themselves are refreshed at L16 phase 10 (`features/trackers/live.ts`); the guard is not repaired in L16 (measure 1). **Owner:** the tooling train. | L16 midpoint suite | `open` |
| B-571 | `entry.py` (R62) and `pwa.py` (R52, R105, R108, R111) still fall at random on `Page.goto: Timeout 30000ms exceeded` after B-564's repair (#631): in L16's closing suite (`~/Library/Logs/tm-l16/close-suite.log`, both) and in 2 of 3 `--rules entry.py pwa.py` draws (`close-o48-{1,2,3}.log`: 0/2, 2/2, 1/2). The hairpin is NOT the mechanism any more: launched with the rules' own `resolve_deployed_host_locally`, the deployed host loads 10 times of 10 in 0.1 s, `server_addr` 127.0.0.1:443, status 401 (`close-probe-deployed.log`), `torrentmate-design` online with 0 restarts. Which `goto` expires is NOT known: `run.sh:522` keeps 12 lines matching `FAIL|Error|Traceback…` and drops the `File …, line N` frame, so the deployed host (`entry.py:98`, `pwa.py:465`) and the harness host (`entry.py:106`, three in `pwa.py`) cannot be told apart. The rules read the deployed host and 8899, not the branch: L16 touches neither rule nor the sign-in. **Escaped from**: a repair (#631) proved on the hairpin alone; **why**: the timeout is one symptom for several causes, and the trace that would name the goto is filtered away; **family**: order 73 — next measure the steward's (a `run.sh` that keeps the whole trace, then 10 against 10 on `main`). **Owner:** the tooling train. | L16 closing suite | `open` |
| B-573 | Production: « One Punch Man » (follow 53, tvdb 293088) stays « en attente de torrent » after the season request and a forced search, while c411 carries every season (`06e151c7…` S01, `1ec2d806…` S02). The follow is stored as `title='ワンパンマン'`, `original_title` NULL: the web add-by-search posts the TVDB search card's `name`, which is the ORIGINAL-language title (`_tvdb_parsers.parse_search_result` → `web/acquisition/service._to_search_result`), and a full card makes no provider call. Every season search sent « ワンパンマン S0x »; c411 answered one real « One Punch Man » pack, and the season identity guard (`filter_to_season`, Groos/Groot) compared it to the Japanese title alone and dropped it — `no_matching_season` on wanted 345/346/347, and the original-title retry never ran (no original title). Measured on c411's real answers: with the Japanese title the guard keeps 0 packs for S1/S2/S3; with « One Punch Man » it keeps 18/22/17. **Escaped from**: the #435 cross-language work, which healed only follows carrying a TMDB id (`detect._backfill_original_titles`) and assumed the stored title was the localized one; **why**: the TVDB search card inverts that assumption — its `name` is the original title and its English/French names sit in translations the card drops — and no test built a follow from a TVDB card named in a non-Latin script; **family repaired by**: every follow created from a TVDB card whose `name` is in an original language the releases do not use (anime, Korean, Chinese…): (a) the web creation of a TVDB show localizes title and overview by id (`enrich_follow_metadata(localize_show=True)`) and keeps the card's name as `original_title`; (b) detect heals any TVDB-only show whose `original_title` is NULL through TVDB in the configured language (`DetectService._heal_tvdb_only_show`), which repairs row 53 at the next detect with no hand edit. Rules: `tests/acquire/test_detect_service.py::test_detect_heals_tvdb_only_show_named_in_original_language` (heal + the real ASKO pack through `filter_to_season`), `tests/acquire/test_metadata_enrich.py::test_tvdb_show_card_in_original_language_is_localized`, `tests/unit/web/routes/test_create_follow_metadata.py::test_tvdb_card_named_in_original_language_is_stored_localized` — RED on the test commit, GREEN on the fix. **Owner:** the backend brief, after the freeze. | operator, 2026-09-29 17:40 | `fixing` |
| B-574 | CI `harness-contracts` falls on a DIFFERENT rule each run, on heads that cannot touch the maquette: #637 @70e54cefa → `screen_addresses.py` (« five keystrokes rewrite the field AND the address — field='lcky' »); #638 @e6cdad8ac (a backend-only fix) → `audit2.py` (R11, 1 violation) + `scroll_memory.py` (« a layer really opened, and really closed … it closed: False »); #635/#636 green on the same tree. A chronic infrastructure-classed red (order 73). **Escaped from**: a build classed by which rule failed, never by what the runner shares across them. **Why**: mechanism CANDIDATE, not named — typing and animation waits shorter than the drawn duration, read on a loaded CI runner. **Family**: B-571 (the deployed-host `Page.goto` timeouts, same runner-load shape) and B-307 (the recorder's parallel load making several rules fall while the register holds one). The row stays open until the mechanism is named, or the rule leaves the gates (order 73). **Owner:** the tooling train (the next repair train). | CI harness-contracts | `open` |
| B-575 | The keychain wagon (#636, `--use-mock-keychain`) changed nothing: Playwright 1.62 already adds that flag to every Chromium launch (`coreBundle.js`'s `chromiumSwitches`), and the macOS keychain's « unexportable-keys » group kept growing under it regardless — 69 232 rows at 11:10 → 71 370 at 19:19 (2026-09-29). **Escaped from** : « la cause affirmée sur un drapeau jamais lu dans le processus ». **Famille** : « un correctif prouvé sur son diff, pas sur son effet » (auditor order 83). Purged on the operator's direct order, 2026-09-29 21:02:53: 71 443 local rows of the group (sync=0, no reference), backed up first (`sqlite3 .backup`, mode 600, `~/keychain-backup-20260929/`); the Chrome-side route (44–80 s per key) and a full keychain reset (Apple, iCloud, HomeKit passwords) were both set aside. The order-83 probe (`/Users/izno/dev/review-archive/keychain-probe/REPORT.md`, 90 real rule runs across three variants) measured **0 key added by the harness** as it launches Chrome — the source of the earlier growth is NOT the harness, and is STILL UNIDENTIFIED. **Owner:** the tooling train. | auditor, order 83 | `open` |
| B-576 | The Système runs list looks cut on the right on a phone — operator, verbatim: « Liste des executions du pipeline, sur le mobile je vois pas le border right, ce qui donne l'impression d'un tableau coupé sur la droite. » Mechanism (the responsive rule's first red, 320–1280 px): each run row is a `<button>` (`frontend/maquette/design/src/features/system/run-list.tsx`, `runRow`) with no border reset, so the user agent's outset border stays on its top, left and right edges. Escaped from: the harness measured at 390 px only and no rule read a row's painted edge; family: every `<button>` row without a border reset (the connection notice's button too). **Owner:** the conformity train (`feat/maquette-conformity`), phase 3. | operator, 2026-09-29 17:04 | `fixed #655` |
| B-577 | Retour from Réglages opened through Système lands on Acquisition instead of Système — operator, verbatim: « … quand je fais Systèmes => Réglage et que je reviens en arrière … je reviens pas sur la page précédente mais à la racine sur Acquisions. C'est une violation du système de routing demandé. Vérifier les autres cas également ». Mechanism: Système's topic row (`frontend/maquette/design/src/features/system/page.tsx`, `data-page="cfg"`) goes through the frame's page verb to `replacePath` (`frontend/maquette/design/src/app/page-switch.ts`): the history entry is replaced, not stacked, against constitution § 16 as amended (side-menu pages stack; an in-page link stacks, even towards the entry page). Escaped from: no rule walked a navigation edge and its Retour; family: every menu or in-page edge that replaces instead of stacking (five defects and two edges to confirm, read on 2026-09-29). **Family repaired by** the navigation lot: every history entry carries its trail (`lib/navigation-entry.ts`, `app/trail.ts`), and the verb says how a tap lands — a bar page unwinds, a menu page and every in-page link stack, a page revisited moves to the top (DECIDED 1–3). Held by R-navigation-b (cold `/system`, the Réglages row, one Retour → Système; red on `c6291e416`, `/acquisition`) and R-navigation-a (`frontend/maquette/harness/journey.py`: the 35 edges walked by finger, their table `navigation_edges.py`, a completeness hold that fails an unclassified emitter). | operator, 2026-09-29 17:07 | `fixed #656` |
| B-578 | Touching a candidate's poster on the resolution screen PICKS it instead of opening its sheet — operator, verbatim: « … j'ai cliqué sur le poster d'un candidat en espérant en savoir plus sur ce candidat et il semble que ça l'a choisi, le comportement attendu était ouverture d'une fiche média pour en savoir plus. Comme pour le reste de l'app. Il faut uniformiser les comportements. Sauf exception volontaire de ma part. » Mechanism: the whole candidate card is one button (`frontend/maquette/design/src/features/acquisition/resolution-cards.tsx`, `data-resolve`); « Choisir » is hidden inside it. Escaped from « la carte-geste » — no rule compares the touch of a poster from one screen to another; family: one element, different behaviours. **Owner:** the conformity train (`feat/maquette-conformity`), phase 8 — moved from the defects fast lane by the orchestrator, 2026-09-30 (order 97(2): a correction goes to the lot already touching the surface). | operator, 2026-09-29 22:1x | `fixed #655` |
| B-579 | The hamburger (the side menu's button) is invisible on iPhone, in light and dark — operator, verbatim: « Sur iphone on voit pas l'icone "hamburger" qui ouvre le menu sidebar ni en clair ni en dark mode. » Mechanism, read in both engines at 390×844: the burger's `<svg>` in `frontend/maquette/design/index.html` carried no size — L07's Tailwind conversion (#494) deleted `.topbar .burger svg { 20px }` and `.brand .mk { 28px }` and put the sizes on no element. An `<svg>` sized by its viewBox alone has no intrinsic width, so the centred flex box resolved it to the room left in Chromium (32 × 32) and to 0 × 0 in WebKit; the header's brand mark, in a shrink-to-fit flex row, was 0 × 0 in BOTH engines since L07. **Escaped from**: « aucune porte ne lit le moteur de l'iPhone » — every rule was Chromium; **why**: Chromium's stretch hid a size nobody declared; **family repaired by**: the responsive rule's `undrawn` arm (every `<svg>` the page shows, drawn at no size, in every pass) and the WebKit `unseen · menu` hold, out of `OWED` — both read RED on the old code. Repaired: the burger's icon `20px`, the brand mark `28px` and `text-primary`, their pre-L07 drawing. | operator, 2026-09-29 23:0x | `fixed #655` |
| B-580 | The « Apparence » selector (Système / clair / sombre) no longer re-renders on any phone — the theme changes, the selector does not — operator, verbatim: « … le menu dans la sidebar "Apparence" Système/clair/sombre ne change plus d'état de manière réactive, le theme change mais pas le selecteur. » Mechanism (auditor): `frontend/maquette/design/src/app/drawer.tsx` reads the current appearance once at render and relies on a store touch to redraw `aria-pressed`, which no longer happens — a regression, to be dated by the fix. Escaped from « aucune règle ne lit l'état du sélecteur APRÈS le choix »; family: a control that changes state without redrawing itself. Mechanism, read in the browser (a finger on « Sombre », then « Clair », in the drawer, read RED on `main` and on the conformity train before its repair — `appearance.py`, pressed [['system'], ['system']]): the choice lives in `localStorage`, the tap calls `store.touch()` to redraw, and the drawer subscribed to the store's STATE alone, which a touch does not move — so the drawer never redrew its pressed control. **Escaped from**: `appearance.py` (R102), which chose each appearance and RELOADED before reading, so the redraw without a reload was read by nothing; **why**: a rule proving a value survives a reload does not prove the value is shown before one — the family « Guards green over what they do not read »; **family repaired by**: the drawer subscribes to the store's version (`app/drawer.tsx`), and `appearance.py` holds that the pressed control follows the tap with no reload. **Owner:** the conformity train (`feat/maquette-conformity`), phase 11 — moved from the defects fast lane by the orchestrator, 2026-09-30 (order 97(2)). | operator, 2026-09-29 23:0x | `fixed #655` |
| B-581 | A FILM in the Médiathèque opens a panel that calls it a series — operator, verbatim (Android capture): « Médias j'ai un encart aucune données de saison sur un film. Il doit y avoir une personnalisation une différence entre film et série »: « On l'appelait Robin des Bois » shows « Série · — épisodes », the chip « À jour » and the no-season-data note, though its seed says film (`frontend/maquette/design/src/mocks/seeds/library-items.json`, category `movies`). Mechanism, read in the browser: a library item nobody follows reaches the follow panel (`features/acquisition/panel-follow.ts`) through `media:<title>` with its TITLE only, and `followFacts` synthesised `{kind: "show", status: "up_to_date"}` for it — the kind was lost between the library row and the panel. The cache could not carry it: « Récents » rows have no category, and a film on no loaded page is in no list. **Escaped from** « aucune règle n'ouvre le panneau d'un FILM depuis la Médiathèque »; **why**: every film panel a rule opened was a follow's, which carries its kind; **family repaired by**: the kind carried by the one whole-library read the panel already needs — `LibraryMembership.kind` (contract, mock layer from the engine's film categories), read by `followFacts` — and the panel's FILM variant (ruling 09-29): no seasons block and no episode note for any film, the « leaves the list » note only for a followed one. Held by `producers.py` § 5b on the named state `lib-film-panel` and on an animation film opened on no loaded page, a library series as control — read RED on the old code. The media sheet opened from the same tile already said « Film ». | operator, 2026-09-29 23:32 | `fixed #655` |
| B-583 | The line saying who asked for an acquisition (`card/requester`) was drawn at ZERO width at every width, on every « À traiter » card offering one answer and on a direct add's « Suivre » card — « origine inconnue », « ajouté par izno, dans qBittorrent » were in the markup and seen by nobody. Mechanism, read in the browser (320, 390, 1280 px, `acq-card-requester`, `acq-todo-loaded`, `acq-todo-dense`, `acq-now-direct-arrived`): `originRow` lays the line beside the card's one foot with the foot `flex-none`, and `actionButton` carries `w-full`, so the foot took the whole row (190 px of 190) and the line, `flex: 1 1 0%`, got 0 — its text 83–160 px wide inside a 0 px box, clipped by its own `truncate`. **Escaped from**: `requester_line.py` (R212), which reads that each card carries its line and what it says, never that the line has a width; **why**: a hold on a text's presence passes on a text nobody can see — the shape « Guards green over what they do not read »; **family repaired by**: the responsive rule's `cut` arm (R-conformity-a, `harness/responsive.py`), which read it first and now holds `card/requester` on every state (its `OWED` entry is gone). Repaired: the foot takes its label's width (`[&>button]:w-auto`) and the line wraps in what remains instead of truncating (§ 12). | the conformity train's responsive rule, 2026-09-29 | `fixed #655` |
| B-584 | Titles were CUT on every card and tile of the app — a card's title and sub-line, a tile's title under its poster, a cast member's name and role — each on one line with an ellipsis: at 320 px « Les aventures de Tintin » read « Les aventures de T… », and a homonym was told from its twin by the part that was gone. The constitution: « Rien d'essentiel n'est tronqué » (§ 12). Mechanism: `cardTitle`, `cardSubtitle` (`ui/variants/card.ts`), `tileTitle` (`ui/variants/tile.ts`) and `castCaption` (`features/media/variants.ts`) wore `whitespace-nowrap overflow-hidden text-ellipsis`, a choice made when the virtual window assumed one pitch for every line. **Escaped from**: every rule reading a title by its text — `textContent` is whole under an ellipsis; **why**: a hold on what an element CONTAINS passes on what nobody can SEE, the shape « Guards green over what they do not read »; **family repaired by**: the responsive rule's `cut` arm (R-conformity-a, `harness/responsive.py`), which read the four first (owed since phase 1) and now holds them on every state; the four wrap, and the virtual window measures every drawn line rather than assuming one pitch (`ui/virtual-rows.tsx`). | the conformity train's responsive rule, 2026-09-29 | `fixed #655` |
| B-585 | The bottom bar CUT « Médiathèque » at 320 px — « Médiathè… » under its icon, on every state of the app at the narrowest phone. Mechanism, read in the browser: each tab is a `<button>` 80 px wide, and a button arrives with the browser's inline padding (this prototype carries no preflight), so the label's box was 68 px for a word 71 px wide at the bar's own 12 px. **Escaped from**: every rule reading the bar by its labels' TEXT, whole under an ellipsis; **why**: « Guards green over what they do not read » — a text read is not a width read; **family repaired by**: the responsive rule's `cut` arm (R-conformity-a), which read it first and now holds `shell/tab-bar` on every state (out of `OWED`). Repaired: `tabBarButton` resets the inline padding (`px-0`); no size off the scale. | the conformity train's responsive rule, 2026-09-29 | `fixed #655` |
| B-591 | Trackers' tab bar was not placed as on the other pages — operator, verbatim: « Le menu des onglets de la page trackers est toujours pas positionné comme sur les autres pages comme si la page trakers n'avais pas le même layout. » Mechanism, read in the code: Trackers' navigation row declares `root: "body"`, so the page host wraps the whole page — its `Tabs` included — in the page column (`body()`, `pt-5 px-7`), and the bar's own `viewTabs` padding stacks on it: lower, inset twice, not the page's head as on Acquisition and Médiathèque. **Escaped from**: R-conformity-b, which held the bars' DRAWING (height, type, count) and never their PLACE; **why**: « Guards green over what they do not read » — a signature read is not a position read; **family repaired by**: R-conformity-b's position hold, which loads every page of the address table at 320, 390 and 1280 px and holds each tab bar drawn at Acquisition's place, as the page's head `view/tabs`. **Owner:** the conformity train. | operator, 2026-09-30 07:5x | `fixed #655` |
| B-590 | A `git push` whose pre-push hook runs longer than GitHub's SSH idle window exits 141 with the hook GREEN and nothing pushed: « All 5 checks passed. Pushing… » is printed, then « Connection to github.com closed by remote host », and `git ls-remote origin refs/heads/<branch>` answers nothing. Paid twice on #652's branch. **Mechanism:** `git push` opens the SSH connection BEFORE it runs the hook; the hook's pytest (~14 min at `-n 2`) leaves that connection idle until GitHub closes it, and the push then writes into a dead pipe (SIGPIPE, 128 + 13). **Workaround, until a repair:** push with `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=60"`, and prove the push by `git ls-remote`, never by the hook's green line. **Escaped from:** a push read by its hook's verdict, never by the remote. **Why:** the hook's last line says « Pushing… », which reads as done. **Family:** B-085, § Guards green over what they do not read — a check's green line taken for the outcome it did not observe. **Owner:** the tooling train. | #652's push | `open` |
| B-592 | The add screen's « Ou ajouter par identifiant » opened on an ERROR with nothing typed, in developer words: « Identifiant refusé : « 12e34 » n'est pas un nombre — `Number()` le lirait comme une notation scientifique. » — the refusal was a static paragraph under an empty field, and the placeholder was the refused example itself. Found by the conformity train's reader, 2026-09-30, on `main` too. **Escaped from**: every rule reading the add screen by its search, none by its identifier block; **why**: a mock's explanatory copy shipped as the product's; **family repaired by**: the refusal is drawn only once something is typed and refused (`features/acquisition/add-screen.tsx`), in plain French from `fr.json` (`screens.add.idRefusedImdb`, `idRefusedNumber`), no code name; the TVDB note is a hint in the muted tone, never the danger one. | the conformity train's reader, 2026-09-30 | `fixed #655` |
| B-593 | Follow cards showed PINK ARCS at their right corners, on Chrome and WebKit: the swipe drawers' layer filled the row edge to edge under the card, and its colour showed through the card's antialiased rounded corners. Found by the conformity train's reader, 2026-09-30, on `main` too. **Escaped from**: `drag.py`, which measured the drawers' buttons against the row and never the layer against the card's rim; **why**: a geometry read at the buttons' edge says nothing about a corner's pixels; **family repaired by**: `swipeActions` lies one pixel inside the rim, rounded as the card is (`ui/variants/rows.ts`) — every swipe row of the app — held by `drag.py` on both engines. | the conformity train's reader, 2026-09-30 | `fixed #655` |
| B-594 | At 390 and 320 px, the connection notice (« Session expirée » / « Connexion perdue ») and its only control, « Se reconnecter » / « Réessayer », were drawn UNDER the bottom bar: announced, present in the document, and out of a finger's reach — no way back to the sign-in on a phone. Found by the navigation lot's implementer walking S5, 2026-09-30. **Mechanism**: the notice is the one thing the React root (`#shell`) draws in the flow, and `#shell` is the LAST child of the phone frame's column, after the page (`#port`), so it sat at the frame's bottom, where the absolute bottom bar covers it. **Escaped from**: `relay_states.py` read the notice's words and pressed its control by `click()`, never by a hit test; **why**: a DOM click reaches a covered control; **family**: a layer or notice of the app drawn under the bottom bar — every named state walked (168), no other control outside the scrolled page is covered; **repaired by**: the mount node is ordered between the header and the page (`index.html`, `order-1` / `order-2`), held by `relay_states.py` (a hit test at the control's centre, 390 and 320 px, `lost` and `refused`). | the navigation lot's implementer, 2026-09-30 | `fixed #656` |
| B-595 | The Trackers page draws seven colour codes — the origin dot's two tones and the chips' `info`, `success`, `danger`, `warning` — and explains none: the operator, 2026-09-29 16:4x (3), « une légende pour les codes couleurs », and order 57. **Escaped from**: L16's reader round and its named states. **Why**: no layer read that a colour carries a word; the dot's `aria-label` satisfied the accessibility pass. **Family repaired**: the « Torrents » tab draws the ONE legend component (`ui/legend.tsx`, the seasons' legend its first caller), fed by the SAME derivation the cards draw from (`codesOf`), so a colour drawn without its entry cannot happen; R-L16bis-c (`trackers_selector_legend.py`) reads every drawn tone against the legend. The « Trackers » tab's chips are read the same way (phase 3). | order 57 (L16-bis DESIGN § 6) | `fixed #657` |
| B-596 | The Trackers page redrew what `ui/` already had: a title (`torrentTitle`), a filter line (`torrentFilter`, `torrentFilterClear`), a removal (`torrentRemove`), a tab floor (`trackersTab`), a « Vu » and a « Voir les torrents » of its own — nine feature variants — and folded its roster with a chevron that is not the app's. The operator, 2026-09-29 16:48 and order 79. **Escaped from**: L16's phases and reader round. **Why**: no layer read design-system reuse; the family is « a component redrawn ». **Family repaired**: a torrent is the media card in the swipe row, a tracker a fact row opening the panel with the one switch at its end, the selector the filter pill and the panel's option list, the legend the one `Legend`; `features/trackers/variants.ts` is gone. R-L16bis-i (`trackers_switch.py`) refuses any variant declared in `features/trackers`; the tab bar and chevron guard arms are the conformity train's (§ 1.9). | order 79 (L16-bis DESIGN § 6) | `fixed #657` |
| B-597 | Découvrir's header drew four `fr.json` strings as figures — « Réserve remplie il y a 2 h · », « 503 », « 1 832 », « ids TMDB possédés exclus » — read from no answer (§ 13, « aucun état affiché n'est une constante »). The operator, 2026-09-29 16:52: « son contenu remplacé par quelque chose d'utile ». **Escaped from**: L08-bis and L22's move of the surface. **Why**: a figure in copy passes every guard — `check-no-french` exempts `fr.json`, and no rule read the strip. **Family repaired**: the header, beside the view switch, says « n séries et m films à découvrir », both counted from the suggestions read; the four strings are deleted; R-L16bis-k (`discover_header.py`) reads every figure against the served answer and moves it with a rejection. | order 57 (L16-bis DESIGN § 6) | `fixed #657` |
| B-602 | Découvrir cut a text and let a thrown card stand out of the frame — his « Non tout doit être responsive, ça doit pas fonctionné que sur mon téléphone, mais sur tous ! » (09-29). The header's sentence ellipsised beside the view switch at 320 px on every Découvrir state and up to 390 px on `discover-header-unavailable` (WebKit too), as L16-bis S8 had drawn it against § 12; a deck card thrown at 768 and 1280 px flew a fixed 460 px and stood half out of a window wider than that. Found by CI's harness on #657 (`responsive.py`, `states.py`, `audit.py` R4). **Family repaired**: the header WRAPS in its place (`liveStrip` `inline`), never cut — S8 amended, `discover_header.py` hold 4 re-aimed; the flight's distance is the window's from the pile plus the turn's swing; the deck's body clips on x at the port's edges, so a card leaving is clipped by its surface. `states.py`'s and `audit.py`'s clipping walk re-aimed: past an overflowing clipper, a clipper inside the surface (the swipe row) decides. | by CI (#657) | `to confirm` |
| B-603 | Découvrir lost the pull-to-refresh every other page has (his 09-26 Rd 7 Q7): since #657 its header fills the pill place, a `.pillscroll` the pull gesture refuses, so a pull from the top row never armed (`touch.py`, `pull_wheel_turns.py` on `discover-full`, h=0). Found by CI's harness on #657. **Family repaired**: `pillScroll` has a `train` variant — a place holding no pill train neither scrolls sideways nor refuses the pull; Découvrir's header place takes `train: false`. | by CI (#657) | `to confirm` |
| B-607 | The torrent card's broken-obligation chip (« En infraction depuis le … ») is cut at 320 px: a chip never wraps, and the dated one is wider than the card's line (`responsive.py`, `torrent-obligation-breached` and `torrents-legend`, `cut torrents/obligation-breached [107, 322]`). Found by CI's harness on #658. **Family repaired**: a chip on a card's state or marks line (`cardMeta`) wraps its words when it alone is wider than the line; one that fits still reads on one line. | by CI (#658) | `fixing` |
| B-608 | Réglages' search did not filter as one typed: `#qsettings` listened to nothing and was keyed by the query, so only the clear cross ran the `qsettings` verb — typing « port » left the seven rubrics on screen. Found by C1's reader, 2026-09-30, on tm-design; on `main` too. **Why**: no rule typed in the field — `page_host.py` taps the cross. **Family repaired**: the field is uncontrolled with its own native `input` handler, the arrangement `#libq` and `#follq` have; R-C1-a 12 (`settings_leave.py`) types a word and reads the rows. | by C1's reader | `fixing` |
| B-609 | On a screen — a media sheet opened from a torrent's poster — the bottom tab bar took no tap: the hit test at « Acquisition » landed on the cast's avatars under it. Found by C1's reader, 2026-09-30, on tm-design; on `main` too (`app/focus.ts` is the same there). **Why**: `app/focus.ts` marks every sibling of the open layer `inert`, the tab bar included, and `inert` takes an element out of the hit test — while the bar is ranked above a screen (50 over 45) and drawn over it. **Family repaired**: while the layer on top is a screen, the tab bar is not its background and is never marked inert, for every screen; under the drawer, the sheet and the confirmation it still is. R-C1-a 13 (`settings_leave.py`) taps the tab over the sheet and lands on Acquisition. | by C1's reader | `fixing` |

**B-471 — one operation declares a shape and answers another.**
The contract gives `readMediaSeasons` a `seasons` array of `Season` — `{season, owned, aired}` —
and `mocks/handlers/media.ts` answers the SHEET's own catalogue, `{number, episodes, airDate}`. Not
one field name in common. The client re-projects the catalogue into the engine's short names
(`toEngineShapeEntry("SHEETS_RAW", …)`), so the interface works and nothing anywhere compares the
answer with the declaration.

**WHY NO GUARD SEES IT, and it is the useful half.** `mocks/contract-conformance.test.ts` holds
« every REQUIRED property of a declared response is present in the answer » — and reads the FIRST
LEVEL only: for this operation that is `seasons` and `owned`, both present. The elements of the
array are never looked at, and the file says so in its own header (« deliberately narrow »). So the
test is right about what it measures and blind to this.

Found while reading the media handler for B-380. **Not repaired here**: widening the conformance
test is a change to an instrument every other operation is judged by, and this wave's own changes
are judged by it. Status `open`. Owner: the next wave that opens the contract test.

**B-472 — the heavy lock is a poll, so waiting gives no turn.**
`scripts/heavy.sh` takes its lock with `mkdir "$LOCK"` in a loop that sleeps three seconds. There is
no queue: among several sessions waiting, the one that wakes first wins, whatever order they arrived
in. It also announces the holder ONCE (`announced=1`), so a wait that outlives two holders prints
the name of the first and never says it changed.

**Measured on 2026-09-12, with four agents on the machine**: a `run.sh --contracts` waited about
twenty minutes, announced « waiting for tooling-hygiene », and the lock passed to a third wave
without the waiter ever taking it. The orchestrator sequenced the waves by hand instead, which is
the right answer to an incident and not a mechanism.

It belongs to **B-386's family** — the wrapper's readiness policy — and is filed beside it rather
than inside it: B-386 is about the FLOOR a run waits for, this is about the ORDER waiters are served
in, and a repair for one does not touch the other. Owner: a tooling micro-wave.

**B-475 — held episodes the catalogue does not list are counted nowhere.**
Found by the mock-layer micro-wave while correcting B-380's season family. American Dad! S16: the
library's holdings are episode numbers 1–24, the sheet's catalogue lists 20 episodes and all 20 aired
by 2026-08-10. Les Animaniacs S2: holdings `[1, 4, 7, 9, 76, 77, 78, 79, 80, 81, 82]`, catalogue 12.
**These are two NUMBERING ORDERS meeting at one season**, the library's and the catalogue provider's,
not miscounts. `seasonsHeld` counts only the numbers at or below what aired, and B-380's correction
set the season family's owned count to that same derivation (20/20 and 4/12) so the sheet and the
follow panel agree — which is right for « manquant », and leaves the four and seven files beyond the
catalogue drawn on no surface and counted in no total. Whether they are shown, re-numbered, or
reported as a mismatch is a product question about numbering orders, and it is the operator's.

**B-476 — one followed show, three families, three answers.**
Found by R173 (the mock-layer micro-wave). The follow is recorded as « Dexter: Resurrection » with
totals 96/96; the season family holds `[1, 10, 10]` under that title; no media sheet carries it — the
sheet is « Dexter Resurrection », without the colon, and the owned episodes are keyed there too. So
the follow's totals are not its seasons' sums, and the title the follow and the seasons share is not
the one the sheet and the holdings share. B-088's class. **Not repaired by the micro-wave**: repairing
it moves the « Suivis » named states, which is B-369's cost and not B-380's subject. R173 holds the
disagreement as a NAMED exclusion that asserts it still holds, so the day this is repaired R173 falls
and the exclusion leaves with it.

**B-496 — the pre-push hook throws away the failing pass and shows a re-run.**
`hooks/pre-push` defines `run_check` as `if "$@" > /dev/null 2>&1; then OK; else FAILED; "$@" 2>&1 |
sed 's/^/    /'`: the first pass is silenced, and on failure the command is executed a SECOND time for
its output. For a deterministic check the two passes agree. For one that falls intermittently they
need not, and on 2026-09-13 they did not: pushing #588's `454bc6a42` under the tests lock at two
workers, `[5/5] pytest ... FAILED` was printed above « 11400 passed, 8 skipped, 1 xfailed in
241.48s » and « 1/5 check(s) failed. Push aborted. » — the fall is real, it refused the push, and
nothing in the output names the test, because the pass that fell is the one sent to `/dev/null`.
It costs twice: the suite runs twice on a failure (four minutes more on a shared machine), and the
verdict arrives with a reading that contradicts it. **The repair's shape**: run each check ONCE,
into a file, and print that file on failure — the failing pass's own output, never a second
execution. The same blind spot as `harness-hold-counts.py` (B-307's sixth instance), in another
instrument. Filed, not repaired: the apparatus is frozen.

**B-498 — tile badges carry no fill the reader round could resolve.**

The reader round's inventory of what stays alive past L13a's gesture names `--waiting`, `--info`,
`--warning` and `--neutral-signal` as declared nowhere it could find, for the tile badges that read
them. **Owner**: the wave that next touches the badge tokens.

**B-502 — `#ptr`'s own utilities are erased at every driver reset.**

`__reposPTR`'s `className = "ptr"` overwrites `index.html`'s `#ptr` element at every driver reset,
erasing whatever utility classes it carried — pre-existing, named at a·18 (ruling 59) and not repaired
there. **Owner**: b·8, the gestures phase.

**B-503 — two disabled query entries fire from an identity the panel does not have yet.**

`panel-seasons.tsx`'s first render seeds two query entries (`["/api/media","",""]` and
`["/api/media","","","seasons"]`) with an empty provider and id, before the follow panel's identity
read lands — DISABLED, so no request leaves, but they sit in the query cache the whole time. Reader
round's measurement (`.review/a11b_typed_follow.*.out`): **1 observer on each while the panel is open**,
0 once it closes on `/media` — corrects ruling 61's register note of « 0 observers » (B-511). **Owner**:
b·10-bis, where `LIBRARY`/`INCOMPLETE`/`knownMedium`/`SEASONS` die with their readers.

**B-504 — `panel.py` has no deadline, and a mutation that should fell it hangs the machine's mutex.**

Reader round finding A7 (M14, `hasSheet: false`): the mutation hung `panel.py` twice — 47 min
unwatched, then 600 s under the reader's own watchdog — holding the served-copy lock the whole time,
refusing another agent's gate at the door. Unreplayable as the wave claimed it. **Repaired on
`feat/maquette-l13b`** (auditor order 27, ruling 69): a 10-minute `TM_RULE_TIMEOUT_SECONDS` deadline
per rule invocation and per mutation, a timed-out rule named an INSTRUMENT fall, and `heavy.sh`'s
stale-lock break reads the holder's own PID and breaks only when that process is gone. `main` inherits
the repair at L13b's merge.

<sub>`/Users/izno/dev/review-archive/l13a/round-1/r1-A.md` § (g), finding A7</sub>

**B-505 — `mutate.sh` read a missing rule path as a fall.**

Ruling 77 (L13b, b·5): `mutate.sh` ran `python3` on a rule path that did not exist, read the
interpreter's own exit 2 (« can't open file ») as « FELL », and produced eight green-looking verdicts
over nothing. **Repaired on `feat/maquette-l13b`**: a missing rule now reads `RULE NOT FOUND` (exit 64)
distinct from `RULE CRASHED`. `main` inherits the repair at L13b's merge.

**B-506 — without a mocks-on build, « Notes de conception » is drawn and answers nothing.**

Reader round finding A3: the control's `#notesBtn` carries the engine's own handler in every build;
the candidate's handler lives in `harness/panel.ts`, installed only `if (__MOCKS_BUILT_IN__)
installHarness()` — a mocks-off build shows the button with nothing behind it. Invisible on the design
host, which always builds with mocks. **Closes when**: the toggle lives where every build installs it,
or the bar is not drawn without it — the steward's call, per ruling 31's « a reader's control ».

**B-507 — R72 (b)'s mutation of record is not the plan's, and the plan's does not fall alone.**

Reader round finding A4: `phase-a19:11-12` prescribes REMOVING the module tag so « (b) alone falls »;
the wave instead duplicated it. Replayed: removing the tag fells (b) AND (c) together (« no bundle
named — the module entry was not found »); duplicating it fells (b) alone, as the wave reported.
**Closes when**: the phase file names the duplicate as (b)'s mutation and (c)'s dependency on it, or
`harness/shell.py` reads the bundle independently of (b)'s tag.

**B-508 — a typed media address whose read fails keeps an empty title.**

Reader round finding A5: a typed `/media/<provider>/<id>` whose read answers 502 from the first byte
keeps the hero title empty (`aria-label=""`, `data-key="mediaSheet:"`) and prints « Bande-annonce
inconnue. » and « Distribution non lue. » — no ruling names the failed typed case, and
`screens.media.trailerUnread` still reads « inconnue » where its siblings (`fr.json:301`) say
« non lue ». **Closes when**: the failed typed screen names its title as unread with a non-empty
accessible name, and the trailer's failure text reads « non lue ».

**B-509 — `bridge.py:300`'s « the media sheet is gone » hold never asserts the sheet was open.**

Reader round finding A6: the hold reads the sheet's key by selector after a Back and nothing before it
checks the tap actually opened a media sheet — renaming the key (behaviour intact) fells no rule, only
undoing the Back's own behaviour does. Old in kind (a·5 named the same shape for a `#screen` nothing
opened), narrowed here, not closed. **Closes when**: a precondition hold asserts the tap opened the
media sheet, by the same selector, before the Back.

**B-510 — ruling 61's restoration is held by a crash, not a named hold.**

Reader round finding A8: removing `redrawOnIdentityArrival(title)` fells `bugs.py` only through
`TypeError: Cannot read properties of undefined (reading 'click')` at `bugs.py:31` — the step's own
`chk("2. media sheet from a follow sheet")` never runs, so any other reason the button is missing reads
the same crash. **Closes when**: the step asserts « Voir la fiche » present as a hold before it clicks.

**B-511 — ruling 61's register note contradicts the measured observer count.**

Reader round finding A9: the note reads « … `pending`, `fetchStatus` `idle`, 0 updates, 0 observers »;
measured on the candidate with the follow panel open on `/acquisition`, each empty-key entry
(`["/api/media","",""]` and `["/api/media","","","seasons"]`) carries **1 observer**, 0 once closed.
Corrected here in B-503's own row. **Closes when**: the note in
`docs/features/maquette-l13/plan/phase-a14-media-identity.md@763f15cf9` reads the measured count.

**B-546 — unnamed falls under load: `audit2.py` and `outbox.py`.**

**Two more occurrences, read from the docs pull request #608:** CI's `harness-contracts` fell on
`audit2.py` R11 (« visible jargon or technical value — 1 ») twice in a row, runs 35076327531 and
35077284519, over a source byte-identical to #607's, which passed the same job twice; the rule was green
alone on the same served copy on this machine. The CI log carries the rule's summary line only — `run.sh`
prints `■ R11 … — 1`, never the `note()` line naming the state and the token — so what R11 saw there is
unknown. Mechanism CANDIDATE, not named: R11 reads `innerText` a fixed 240 ms after `__go`, and under the
runner's parallel browsers a state may be read before it settles.

**The repair train of 2026-09-16 tried to catch it, and caught nothing — no repair.** Three loaded
readings on this machine (8 cores), each under the harness mutex: the contracts tier at
`TM_HARNESS_JOBS=4` with `audit2.py` named, as the load, and `python3 frontend/maquette/harness/audit2.py`
run beside it for its whole length so its `note()` lines land in a log of its own:

    reading 1   11:56–12:01   contracts 23 rules, 0 failed; audit2 beside them 0 violations, 13/13
                              (`w6-load-1-contracts.log`, `w6-load-1-audit2.log`)
    reading 2   12:02–12:07   contracts 0 failed; audit2 beside them 0 violations, 13/13
                              (`w6-load-2-contracts.log`, `w6-load-2-audit2.log`)
    reading 3   12:07–12:12   contracts 0 failed; audit2 beside them 0 violations, 13/13
                              (`w6-load-3-contracts.log`, `w6-load-3-audit2.log`)

The logs are under `~/Library/Logs/tm-repair-0916/` (the oracle's own divergences in the contracts logs
are the train's declared movements, not this entry). The fall reproduces nowhere but the CI runner, so the
entry stays `open` with that runner as the only place it falls; naming it needs the `note()` line there,
which is the instrument gap above (measure 1, the apparatus frozen).

**2026-09-27 — the `outbox.py` half is NAMED and repaired in #619 (L22a round one, ruling 31).** R107 read
the store the instant the reloaded page reported itself ready; the boot starts the drain at module
evaluation and `__loadingDone` is not its end, so it raced on ANY boot — measured alone, old read: main
`46806a88d` 2/8, the branch 3/5 and 2/8 (`~/Library/Logs/tm-l22a/r1-a3-*.log`). The read now waits,
bounded 3 s, for the departure to answer; 0/10 on the branch and 0/10 on main after it. The `audit2.py`
half stays open as above.

**B-477 — followed as held, sheet says not in the library.**
Found by R173 (the mock-layer micro-wave). House of the Dragon (26/26), Ted Lasso (35/35) and Star
Trek: Strange New Worlds (33/33) are followed « à jour », and their media sheets answer `owned: false`.
The owned episodes are keyed under « House of the Dragon (2022) » and « Ted Lasso (2020) » — titles no
sheet key shares with those identities — and Strange New Worlds has none at all, so
`readMediaSeasons` answers no holdings for any of the three. Latent on screen today: a sheet not owned
draws its catalogue without a fraction, so nothing contradicts itself on the sheet — but the follow
and the sheet state opposite facts about one show. B-088's class, beside B-380 and B-476.

**B-495 — the heavy wrapper does not measure the wait it imposes.**
`scripts/heavy.sh` prints « holding off » once when it first finds the lock held or the floor unmet,
and « starts » when the run begins — neither line carries a time, and nothing prints the seconds
between them. So a run's WAIT is not readable after the fact: on 2026-09-13 the tooling wave's `make
check` sat behind a `test`-class ceiling of load 6 on a host whose own one-minute load ran 9–15
(fseventsd, Spotlight, a Plex transcode), and neither the wave nor the steward could say for how long;
memory was never the constraint at any reading that night (4–5 GB free), the concurrency and the
ceiling were. **Closes when** « starts » prints the seconds waited (and « holding off » its cause —
lock, memory or load — each time it re-samples), so an accusation of a slow wave can be read against
the wrapper's own figure. B-386's family. Owner: the next tooling wave — none is opened for it, by
the operator's first measure of 2026-09-12.

**B-492 — out of the desktop frame, what clips the sheet is the harness, not the app.**

B-491's repair confines the scroll in `styles/harness.css`, the one stylesheet that ships in no production build. The
overflow it confines is not the harness's: out of the frame R140 holds `.device`'s `overflow` equal to the app's own
cascade, and in that cascade no element of the shell clips its absolute layers — `#sheet` closed sits 43 px below the
bottom edge with its 88 px drag band, and the document measured 989 against 900 at 1440 × 900 before the stage clipped
it. At switchover, when the maquette becomes the app and `harness.css` goes, a desktop window reading the shell at full
size can meet the second scroll container again.

**Closes when** the frame model decides which element of the app owns the clipping of its layers on a desktop window,
and a hold reads the document's overflow with no harness stylesheet in the page.

<sub>maquette-scroll-jump, 2026-09-13 · owner: the frame model (L13) · `docs/features/maquette-scroll-jump/DESIGN.md@519ba2136` § 5</sub>

**B-466 — `frame.ts` is one line from a hard ceiling, and the arm this wave added is what will demand that line.**

`python3 scripts/check-frontend-boundaries.py` on the wave's head exits **0** with
`[WARN] ui/variants/frame.ts: 399 non-blank lines`. `BLOCK_LINES = 400`, and a file at or over it
must be grandfathered against a lot or the guard refuses it
(`scripts/check-frontend-boundaries.py:294`, `:543`). The ranked list is written **one line per
RANK**, so a new site at an EXISTING rank costs nothing — but a rank at a NEW number costs exactly
one line and takes the file to the ceiling.

**The two guards this wave introduced now point opposite ways**: `scripts/csstokens_ranks.py`
refuses a rank the list does not name, and `check-frontend-boundaries.py` refuses the line that
would name it. The next reader meets both in the same commit with no room to move.

**This is not a defect in what was built.** The compression from 427 to 399 lost no entry, verified
by parsing both lists: the pre-compression commit recorded 24 sites, the head records 19, and the
five missing are exactly `LOCAL_DETAILS`' five (`.st .d`, `sheetDragBand`, the two
`::view-transition-group` entries, `viewTabs`). **Closes when** `frontend/maquette/design/src/ui/variants/frame.ts`
is grandfathered against the lot that splits it, or the ranked list moves into the arm's own module
beside `LOCAL_DETAILS`. Owner: the next wave that opens the file.

<sub>reader B, maquette-resolution-card round two, 2026-09-12 (B7) · `python3 scripts/check-frontend-boundaries.py` → exit 0 with the `[WARN]` line · both lists parsed, 24 → 19 + 5 exempt</sub>

**B-464 — three scopes `csstokens_ranks.py` never opens.**

Measured on scratch trees, each restored, the repository never touched:

- a `z-index` inside a `<style>` block of the shell's markup → **exit 0**. The markup arm reads
  `class="…"` attributes only, and **`frontend/maquette/design/refonte.html@60530dbd8` has a `<style>` at
  line 3** — a live file, not a hypothesis (it carries no `z-index` today; the reader checked).
- a stylesheet in a SUBdirectory of `styles/` → **exit 0**: the arm globs `*.css`, not `rglob`.
  Every stylesheet the maquette has is `styles/*.css` today, so nothing is missed now.
- a negative utility `-z-10` → **exit 0**: `UTILITY`'s lookbehind excludes a leading `-`. The
  docstring deliberately names `z-auto`, `z-full` and `md:z-10` as unread; it does not name this one.

**Expected**: an arm's docstring names what it does not read, so the next reader does not have to
find out by mutating it. **MINOR — none of the three is occupied today**, which is why this is filed
rather than repaired. **Closes when** the arm reads a `<style>` block in the shell's markup, walks
`styles/` recursively, and either reads `-z-N` or names it unread in its own docstring. Owner: the
next wave that opens `scripts/csstokens_ranks.py`.

<sub>reader B, maquette-resolution-card round two, 2026-09-12 (B5) · three scratch trees under the reader's `.review/scratch/`, each mutated and restored · `scripts/csstokens_ranks.py`, `UTILITY` and the stylesheet glob</sub>

**B-463 — the ranks arm attributes a declaration to the nearest `export const` above it.**

`scripts/csstokens_ranks.py:213-218` takes a rank's SITE to be the nearest `export const` above it
for sources, and the nearest line ENDING in `{` for stylesheets (`OPENS`, line 96). A declaration
whose own site is not an export — or whose rule is written on ONE line — inherits its neighbour's
name. Measured on scratch trees, the repository never touched:

| Scratch tree | The arm says | Should say |
| --- | --- | --- |
| `export const tabBar = cva("… z-50")`, then below it `const helper = "newthing z-50"` | `[(tabBar, 50), (tabBar, 50)]`, **exit 0** | a rank at 50 nobody recorded |
| the same, at `z-58` | exit 1, but « **`tabBar`** declares 58 » | « `helper` declares 58 » |
| `.hbtn { … }`, then `.newthing { z-index: 58; }` **on one line** | exit 1, but « **`.hbtn`** declares 58 » | « `.newthing` declares 58 » |

So a rank is **smuggled in silently when it matches its neighbour's recorded number**, and is
reported against the WRONG site at any other number. **Expected**: an arm that refuses « a rank
nobody recorded » names the thing that declares it.

**This does not weaken what the arm was built for**, and the reader established that independently:
an enumeration of its own (`rg --pcre2` over the sources, the two markup files and `styles/*.css`)
finds **exactly 24 declarations — 9 in CSS, 15 utilities** — against the arm's « 24 declared, 19
recorded, 5 exempt », site by site; and the arm BITES, proved on a copy of the whole design tree by
three mutations, each naming its own site. Its plumbing was read on all three ends —
`scripts/check-css-tokens.py:844` imports it, `:878` runs it in the default arm list, and
`Makefile:86`, `frontend/maquette/harness/run.sh:195` and `.github/workflows/ci.yml:286` each invoke
that guard on every non-draft pull request.

**Closes when** the site is taken from the declaration's own enclosing binding (any `const`,
exported or not) and `OPENS` matches a rule opened and closed on one line, with one test per
direction. Owner: the next wave that opens `scripts/csstokens_ranks.py`.

<sub>reader B, maquette-resolution-card round two, 2026-09-12 (B4) · the arm's own `declared()` and `ranks_arm()` driven over three scratch trees · the reader's independent `rg --pcre2 '(?<![\w-])z-(\[\d+\]|\d+)(?![\w-])'` enumeration, 24 sites, agreeing site by site · `tests/scripts/test_csstokens_ranks.py`, 13 tests</sub>

**B-462 — the candidate card announces its title and year, and nothing else.**

`Accessibility.getPartialAXTree` over every candidate card, both builds: on the wave's head the
five names are `Lucky! 2022` · `Lucky (2026) 2026` · `Lucky (2006) 2006` · `Lucky (2003) 2003` ·
`Lucky Chances 1990`, 11 to 18 characters, all distinct. On the control they were the whole card's
text, 192 to 521 characters, the third opening on the poster's stray `L`.

**The repair is exactly what the decided list asked for and it works.** What it also did, and
nobody had ruled at the time: the card is a `button` and now carries an `aria-label`, so **the
confidence, the provider (`TVDB 427619`), the kind and the synopsis are announced to no one** — on
the screen whose whole job is choosing between near-identical series, the one datum that says which
candidate the system believes, `confiance 90 %`, was in the control's name and is now in nothing.

**RULED by the operator, 2026-09-12**: the accessible name **announces the confidence and the
provider** — « Titre Année · 90 % · TMDB ». It is built by the next wave that opens
`frontend/maquette/design/src/features/arrivals/resolution-cards.tsx@1c0dbea64`, with a hold that reads the
**accessibility tree** rather than the markup. **Closes when** that name is emitted and that hold
holds it. Owner: the next wave that opens the file.

**Two edge cases the fixture cannot put under a finger**, read in the source and marked as reasoned:
a candidate with **no year** (`aria-label={year ? … : title}` gives the title alone, and R161's
expected name, parsed off the subtitle, agrees) and a title carrying a quote or an ampersand (the
label is a React prop, so the DOM escapes it and the protocol returns it literally). All five seeded
candidates carry a year and none carries either character.

<sub>reader B, maquette-resolution-card round two, 2026-09-12 (B3) · `Accessibility.getPartialAXTree` on every card of both builds · operator's ruling, 2026-09-12 · `frontend/maquette/harness/resolution_card.py` h9 reads the name and not what is announced beside it</sub>

**B-461 — a hold names a relation between two durations and reads one of them.**

`frontend/maquette/harness/resolution_window.py:68-75` calls `LAST_FRAME = 6500` « THE MESSAGE'S
LAST REACHABLE FRAME, measured at 6 500 ms after the tap: from 7 000 ms the host is hidden », and
w1's hold says « and is still held on the message's last reachable frame ». **Measured, both builds
identical**, the message's own opacity sampled every 100 ms after one finger-tap:

| ms after the tap | 5 800 | 6 000 | 6 200 | 6 300 | 6 400 | 6 500 | 6 600 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| the message's opacity | 1.0000 | 1.0000 | 1.0000 | **0.1924** | **0.0023** | **0.0000** | 0.0000 |
| the undo answers its own hit test | yes | yes | yes | yes | yes | yes | no |

The hold's ARITHMETIC is right — the send is unsent at every mark through 7 100 ms and present at
7 600 — but the last frame the message is VISIBLE on is ~6 200–6 300 ms. A hit test does not read
opacity, and the repair inherited its figure from an instrument that hit-tests.

**The consequence, and it is why this is filed rather than noted.** The repair armed ONE direction —
a window SHRUNK, and its own mutation proves it: 7 000 → 3 000 falls exactly one hold. **The other
direction is read by none of the eighteen**: if the message's own life grew past the window (6 s →
10 s, the window untouched), every hold stays green and the interface offers « Annuler » for three
seconds after the act has gone — the exact asymmetry the design exists to prevent. Nothing in R162
reads the message's life; nothing in R163 reads the window.

**Closes when** `LAST_FRAME` is derived from the message's own duration constant, or one hold reads
the message's opacity at `LAST_FRAME` — which would fall today, and is therefore the honest form:
name the real last frame (~6 200 ms) and hold the send there. Owner: the next wave that opens
`frontend/maquette/harness/resolution_window.py`.

<sub>reader B, maquette-resolution-card round two, 2026-09-12 (B2) · the opacity sampled every 100 ms on both builds · the send read on the network at nine marks · `frontend/maquette/harness/resolution_window.py:68-75`, w1</sub>

**B-460 — a floor whose subject is « the affordance is drawn » catches two of the five ways to take a mark away.**

R161's own h2 arithmetic (`AFFORDANCE` and the three checks at
`frontend/maquette/harness/resolution_card.py:342-359`) run over the mark wearing seven disguises,
on both builds:

| Disguise | h2 size | h2 drawn | h2 nature | **R161 h2** | What a user sees |
| --- | --- | --- | --- | --- | --- |
| as shipped | ✓ | ✓ | ✓ | **green** | 32 × 32, opacity 1 |
| `display: none` | ✗ | ✗ | ✓ | **RED** | 0 × 0 |
| `visibility: hidden` | ✓ | ✗ | ✓ | **RED** | 32 × 32, invisible |
| `transform: scale(0)` | ✗ | ✗ | ✓ | **RED** | 0 × 0 |
| `opacity: 0` | ✓ | ✓ | ✓ | **green** | **invisible** |
| `clip-path: inset(100%)` | ✓ | ✓ | ✓ | **green** | **invisible** |
| off-screen (`left: -9999px`) | ✓ | ✓ | ✓ | **green** | **not on the screen** |

**What it reads** is a box above zero and `visibility`. **Expected**: a hold whose subject is « the
affordance is drawn » falls when the affordance cannot be seen.

**The two mutations the wave named do prove the ground the inert one was aimed at**, and the reader
says so: the wave's `hidden` was genuinely inert (Tailwind's order, measured at the emitted
stylesheet's own offsets), and `style={{display:"none"}}` (2 holds) plus `invisible` (1 hold, the
visibility half alone) together cover it. This entry is what is left BESIDE that ground, not a doubt
about it. **MINOR — it takes a deliberate edit to reach, and no such edit is in the tree.**
**Closes when** h2 also reads `opacity` and the mark's own centre answers `document.elementFromPoint`
as the mark — one more conjunct on a value the browser already computes. Owner: the next wave that
opens `frontend/maquette/harness/resolution_card.py`.

**Two instruments of the review itself are wrong and are recorded here rather than lost**: round
one's `.review/a05_edges.py:108` measures `card.textContent.length` for the accessible name, so it
reports 521 for the third card where the announced name is 17 characters — a reader running it on
the repaired head would conclude B-462's repair had not happened; and
`frontend/maquette/harness/desktop_frame.py:132-137` cites `ui/variants/frame.ts:60 / :111 / :124`
for the tab bar, the action button and the selection bar, which are really at 94 / 145 / 158 on the
control and 100 / 151 / 164 on this head — already wrong before this wave (B-391 owns that block),
made one notch staler by its compression.

<sub>reader B, maquette-resolution-card round two, 2026-09-12 (B1, and the two corrected instruments) · h2's own arithmetic run over seven disguises on both builds · `frontend/maquette/harness/resolution_card.py:342-359`</sub>

**B-329 — the backend's generated contract does not describe what the backend does.**

`personalscraper/web/routes/acquisition_triggers.py:160` raises **409** when a requeue or a
re-scrape for the same item is already in flight. `frontend/openapi.json` — generated FROM that
backend — declares, for both routes, exactly `202` and `422`:

    grep -n "409" personalscraper/web/routes/acquisition_triggers.py
    python3 -c "import json;d=json.load(open('frontend/openapi.json'));\
      print(sorted(d['paths']['/api/acquisition/journeys/{info_hash}/requeue']['post']['responses']))"

FastAPI derives an operation's responses from its SIGNATURE; a `raise HTTPException` inside a body
is invisible to the generator unless it is declared. So the document says the route cannot refuse,
and the route refuses.

**Why it is filed rather than fixed here.** It was found while L21 declared the tunnel's verbs, and
the demand it hides is exactly the one that lot serves: NE-DOIT-PAS-3 and §20 forbid the interface
showing a 409 for a legitimate ask — an ask at the bound is QUEUED, visibly. The maquette's
contract therefore declares a queued 202, and `scripts/compare-contracts.py` § 2c was built in the
same wave to compute status demands. **It cannot compute this one**: a table diffing two documents
reports only what one of them carries, and neither carries the 409. The demand is written by hand
in **B-302** for that reason.

It is the BACKEND's own defect and L21 does not open `personalscraper/` (D7). The repair is one
`responses=` declaration on each route, and it belongs with whoever writes the backend brief —
alongside **B-324**, which is the same species on the other end: a backend fact no guard reads.

**B-330 — `mutate.sh` cannot tell a typo from a rule that does not bite.**

It runs each rule as `python3 "$RULE"` and decides by grepping the output for `^  FAIL` or
`violation(s)`. A `$RULE` that names no file makes Python print « can't open file » — no `FAIL`
line — and the script announces:

    (no hold fell — the rule does not catch this mutation)
    mutate: NO RULE FELL. That is the finding.

**Measured, and it cost a false finding that was nearly written down.** A mutation of
`data-part="season/grab"` was reported as caught by nothing, over a rule that catches it with
SIX violations naming the right defects — verified by applying the same mutation by hand,
publishing the served copy, and running the rule directly. The only difference was the argument:
`season_grab` instead of `frontend/maquette/harness/season_grab.py`. The tool did exactly what
it was told; what it cannot do is say that it was told something impossible.

**It is B-273's family**, and the shape is the same one: a verdict that reads identically whether
the instrument measured something or nothing at all. B-273 records the two known forms — a GUARD's
exit code it cannot read, and a mutation that breaks the build, which also exits silently. This is
the third: a rule path that does not resolve.

**The repair is one line and it is not a refinement**: refuse a `$RULE` that is not an existing
file, before mutating anything. `NO RULE FELL` is the strongest sentence this tool prints, and it
must be reachable only when a rule really ran.

**B-337 — a NEGATIVE reading, and it does not close the entry.**

Measured on 2026-09-06 by R132 (`harness/pause_verb.py`), which drives a REAL touch rather than a
synthetic one: touch start, eight moves, a dwell, touch end, dispatched over CDP through the
browser's own input pipeline — then ONE tap on the revealed action. That is the reading the entry
asks for (« a finger, not a click »), and `page.touchscreen.tap` cannot reach the defect class at
all, since the engine's swipe machinery arms its click-swallowing only after a drag that MOVED.

**The first tap ACTED**: « Ne plus chercher » on the swiped-open row moved the follow
`pending → disabled`, once, with no error. Nine holds, no violation.

**What that licenses, and it is not « fixed »**: this instrument, on this machine, does not see it.
The operator sees it on an Android through the design host; a CDP touch in headless Chrome is
closer to a finger than a synthetic tap and is still not a finger. The entry stays `open` with this
recorded as a negative reading, and the next attempt belongs on the device — read directly off the
phone rather than reproduced beside it.

<sub>L21, 2026-09-06 · `harness/pause_verb.py` — swipe leftward (the pause and the removal are in
`data-side="right"`, uncovered by the card travelling left), then one `Input.dispatchTouchEvent`
pair at the action's hit-tested centre</sub>

**B-351 — the comment rule cannot see a `.mjs`, and does not say so.**

`scripts/check-maquette-comments.py` refuses a maquette source comment that references a lot, a
phase, a session or a date — those comments must still read years from now, out of context. Its
corpus is `SUFFIXES = (".py", ".ts", ".tsx", ".css", ".js")` (`:46`), and **`.mjs` is not in the
tuple**. So a `.mjs` file under `frontend/maquette/` is not exempt, it is INVISIBLE: no arm reads
it, and the `read` count the floor is derived from never moves for it either — the guard prints
`clean` over a file it never opened, which is exactly the class it exists to prevent elsewhere.

**Measured, not reasoned.** Four files sit in the hole:

    frontend/maquette/design/vite.config.mjs        2 references — one is REAL
    frontend/maquette/harness/rename.mjs            3 — all prose or code (`ecmaVersion: 2024`)
    frontend/maquette/harness/bare_elements.mjs     0
    frontend/maquette/harness/panel_verbs.mjs       0

The real one is `vite.config.mjs:143`: « WHETHER THE MOCK LAYER IS BUILT IN (L08) » — a lot
reference in a maquette source, which is precisely what the rule refuses, standing under a green
gate since L08.

**How it surfaced**, and it is worth recording because no gate produced it: the departure micro-wave
warned that any new file under `frontend/maquette/` takes the comment corpus past the recorded
`read` count and falls the guard's TEST (never the guard, which prints clean). Three files were
added here — `harness/panel_verbs.mjs` and two rules — and only the two `.py` moved the count. The
`.mjs` not moving it was read as « outside the corpus »; it is not outside anything, it is unread.

**The repair looks like one line and the measurement says it is**: add `".mjs"` to `SUFFIXES` and
correct that single reference. It is not taken here because widening a guard's corpus is outside
L21's contract; recorded so the next wave that opens that file does it deliberately.

<sub>L21, 2026-09-06 · `grep -n "SUFFIXES" scripts/check-maquette-comments.py` → `:46` · the four
files and their counts from `find frontend/maquette -name '*.mjs' -not -path '*/node_modules/*'`
with a reference grep over each</sub>

**B-278 — the drawer's dismiss acknowledges itself twice, and I could not explain it.**
One leftward swipe on the drawer produces TWO `data-feedback` marks on `#drawer`, at the same
millisecond, **both reporting no previous value**. The sheet's dismiss, driven the same way in the
same run, produces exactly one.

**What is ruled out, each by measurement rather than by reasoning:**

- **A stale observer in the probe.** The probe installed its `MutationObserver` twice without
  disconnecting the first; both pushed into one array, which would double every record. Disconnecting
  it changed nothing.
- **`React.StrictMode` double-invoking the install.** `installDrawerDismissGesture` returned `void`
  and its `useLayoutEffect` had no cleanup, so two independent gesture closures were plausible. A
  disposer was added — the effect now aborts its listeners — and the double mark **survived it**.
- **Two elements.** There is exactly one `#drawer` node.
- **One element marked twice in a task.** That would give the second record `oldValue: "commit"`.
  Both read `null`.

**What it is NOT: a visible defect.** The drawer closes once, correctly, and two marks of the same
kind inside 200 ms restart one timer — the acknowledgement simply lasts marginally longer. Nothing
the operator validated is affected.

**Why it is filed anyway.** « One `feedback()` call site every gesture passes through » is D9's whole
reason for the seam, and a gesture that appears to pass through it twice is either a second call
nobody can name or a mark nobody can account for. Both matter the day haptics make the seam fire
something. **The remaining candidate I did not test is a node REPLACED between the two marks** — a
re-render giving a fresh `#drawer` that is also marked — which would explain both `null` oldValues
and the single node count.

**B-299 — the settings' version conflict is declared and never drawn.** `SettingsState.conflict:
boolean` (`features/settings/reference.ts`) is set to `false` where the engine builds the state and
reset to `false` on save, and no reader, no variant and no `fr.json` key exists for it —
production's `ConflictDialog` (the 412 when the file changed under the editor) has no maquette
counterpart, while the copy names « three banners » and draws two. Placed 2026-09-02 with **L19**:
the banner is born when the settings producer moves.

<sub>`grep -rn "conflict" frontend/maquette/design/src/features/settings/ frontend/maquette/design/src/engine/legacy.js` → the declaration and two `= false`, no reader · `grep -c "conflit" frontend/maquette/design/src/i18n/fr.json` → 0</sub>

**FIXED on this branch, L19 phase 18.** The banner draws, from the LAYER's own answer.

**THE BRIEF SAID 412 AND THE MAQUETTE'S CONTRACT SAYS OTHERWISE**, and the contract is the
maquette's own artefact (D7): `updateConfigurationFile` answers `{ restartRequired, conflict }` on
**200** and declares 409 for a refusal. So « the file moved under the editor » is something the
write SUCCEEDS in telling, and drawing it from an error branch would be drawing it from a case the
contract does not describe. Followed, and recorded rather than reconciled silently.

**The save had to start asking.** `data-save` cleared the pending edits, raised the restart flag
and said « Enregistré » **without writing anything** — so a field the contract has always answered
had no reader by construction. It writes each changed file now, through
`features/settings/queries.ts`, and reads what comes back. A held write (offline) and an empty
answer are passed through rather than flattened: neither is a conflict, and neither is a promise
that there is none.

**A conflict does not throw the edits away.** The file moved under the editor, so what is on screen
no longer describes what is stored — losing the operator's work on top of that would be the second
loss. Reloading is OFFERED, as a decision.

**And the banners moved to where the operator is.** All three were written inline in the RUBRIC
LIST alone, so a read-only instance said so on the list and said nothing once a rubric was open —
while the save bar, which raises the third, exists on every branch. B-299's banner would have been
invisible exactly where « Enregistrer » is tapped. `SettingsBanners` is one component, rendered on
all four.

**The rule is `harness/settings.py`'s, three holds, and it was RED before the banner existed**
(`86fe9549a`'s sibling commit): the flag is raised from the layer's answer, the page says so in the
same `data-part` the other two banners wear — a third shape would be a third banner nobody styled —
and it offers to reload. `window.__mocks.setConfigurationConflict(true)` is the dial, a property of
the FILE rather than of the request, which is why it is a dial and not a scenario.

**THE PROOF THE STATUS CLAIMS, written where the status claims it.** `to confirm` is defined at
the head of this file as « fixed, rule green, mutation proven », and this entry named a rule and a
run and no mutation. Both are here now.

    the rule            harness/settings.py, three holds — the flag is raised from the LAYER's
                        answer; the page says so in the same `data-part` the other two banners
                        wear; and it offers to reload
    seen RED first      before the banner existed, against the code as it stood — the strongest
                        form this repository asks for, and the reason the phase carries two
                        commits rather than one
    the mutation        the banner's own branch removed from `features/settings/page.tsx`'s
                        `SettingsBanners`, rebuilt and re-served
                        → FAIL « the version conflict is said where the operator saves »
    the run             `python3 frontend/maquette/harness/settings.py` → 65 holds, no violation

<sub>`python3 frontend/maquette/harness/settings.py` → 65 holds, no violation — the entry read 57 until 2026-09-05, a figure taken before the phase that added the restart holds</sub>

**B-300 — « Redémarrer maintenant » restarts on the tap.** The settings' restart banner's button
(`data-restart`) is handled by the engine with no confirmation: the flag drops, a toast says «
Service redémarré ». Production confirms first (`RestartConfirmDialog`). A restart cuts the service
for every account of the household (§17), which is the case NE-DOIT-PAS-6's spirit covers even
though nothing is destroyed. Placed 2026-09-02 with **L19**, beside B-299: the confirmation uses
`ui/dialog` and lands with the producer's move.

<sub>`grep -n "dataset.restart" frontend/maquette/design/src/engine/legacy.js` → the branch sets `redemarrage = false` and toasts, no dialog</sub>

**FIXED on this branch, L19 phase 18.** The tap raises a `ui/dialog` confirmation — no new drawing
primitive, only a use of one whose paragraph colour and danger contrast R116 has held since L12.
The sentence says the thing §17 makes this a confirmation FOR: the service is unavailable **for
every account of the household, not only for you**, and an acquisition in flight resumes where it
stopped. « Êtes-vous sûr ? » would have been a dialog that says nothing.

**A RULE WAS ASSERTING THE DEFECT.** `harness/page_host.py` held « and a real tap on the restart
offer TAKES it » — which is the behaviour this entry calls a defect, written down as a
requirement. It reads « ASKS before it takes it » now. That is B-085's species from the closest
possible range: a rule can certify the defect, and this one did for as long as the defect stood.
Its neighbours then failed for a reason that was not theirs — a modal left up makes every later
tap « present but not tappable » — so the walk dismisses the confirmation before going on.

**The rule that closes it is `harness/settings.py`'s, seven holds, and it was RED before the
confirmation existed.** THE WALK GOES THROUGH THE CANCEL, which is the half that separates a
confirmation from a delay: cancelling leaves the restart OWED and says nothing about one having
happened; only confirming restarts, and then it says so.

**THE PROOF THE STATUS CLAIMS, written where the status claims it**, as for B-299:

    the rule            harness/settings.py, seven holds, and the walk goes through the CANCEL —
                        the half that separates a confirmation from a delay
    seen RED first      before the confirmation existed, against the code as it stood
    the mutation        `askToRestart()` replaced by the direct `restart()` — the defect restored
                        → FAIL « the tap ASKS before it takes it », and `page_host.py`'s own hold
                        with it
    the run             `python3 frontend/maquette/harness/settings.py` → 65 holds, no violation ·
                        `python3 frontend/maquette/harness/page_host.py` → 44 holds, no violation

<sub>`python3 frontend/maquette/harness/settings.py` → 65 holds, no violation · `python3 frontend/maquette/harness/page_host.py` → 44 holds, no violation</sub>

**CONFIRMABLE BY HAND SINCE #588 (the settings micro-wave), and the confirmation is the operator's
to make — this entry is NOT closed here.** B-343's two causes are gone: the restart flag is the
layer's and the banner reads it, so a real save raises it; and B-342's mock keeps the value, so the
row shows what was written. The path is now: open a rubric, tap a setting, type, tap « Valider »,
tap « Enregistrer » — the banner comes up, and « Redémarrer maintenant » raises the confirmation
this entry says is fixed. Walked end to end by R166 (`harness/settings_editing.py`, « so B-300's
confirmation is reachable by the path a hand walks, and not only from a named state »). B-299's
banner is reachable the same way, by saving a setting in the file the seeds mark as changed on disk
(B-345's settings half, held by R128).

**CONFIRMATION ATTEMPTED by the operator on 2026-09-06 and NOT REACHED**: on the design host, editing a
field and saving showed the toast and no restart banner — the flag is raised on an engine object nothing
re-renders (B-343), and the value itself was not kept by the layer (B-342). So the confirmation dialog
this entry says is fixed could not be seen through the real path; the status stays `to confirm` until
B-343 lands and the operator taps the banner's button himself.

**B-309 — « Récupérer maintenant » throws, and the medium is never taken.**
The follow panel's PRIMARY action for a medium waiting to be taken carries `data-take` with the
medium's TITLE. The document's click delegation has two branches for that attribute, and the
first one — the release-choice screen's — is checked first and carries no guard:

    if (closest.dataset.take) {
      const release = releases()[Number(closest.dataset.take)];   // Number("The Hawk") → NaN
      …
      toast(`« ${release.res} …`);                                // throws

So the tap raises `TypeError: Cannot read properties of undefined (reading 'res')`, the panel
closes, **and nothing is taken**. The second branch — the panel's own, at `legacy.js:9964`, which
reads the title and calls `actionTake` — is unreachable dead code.

**Measured, not inferred**, on a build of `2f8503614` (this wave, at phase 11's head — a sha, because the branch it was on is deleted at the squash):

    window.__panel.produce("follow", "The Hawk")   → the panel offers « Récupérer maintenant »
    click('#sheetin [data-take]')
    pageerror                                      → "Cannot read properties of undefined (reading 'res')"
    window.__panel.isOpen()                        → false

**Why nothing caught it.** `grep -ln 'data-take' frontend/maquette/harness/*.py` returned NOTHING
on 2026-09-04 — the brief that opened L19 says so, and this is what it cost. The verb is EMITTED
by React (`features/releases/releases-screen.tsx:113`) and READ by the engine, a contract with two
ends in two worlds and no reader at all.

**Repaired by L19's phase 13**, which is where that verb's reader moves: the panel's take and the
release screen's take stop sharing an unguarded branch. The rule was written FIRST (phase 12),
against the engine as it stands, and it was RED without needing a mutation — which is the
strongest form of « seen red before the move » this register asks for.

**FIXED on this branch, phase 13.** The two takes are told apart by WHAT THEY CARRY, which is
what the engine's branch never asked: an INDEX is the release screen's, a TITLE is the panel's.
The arrivals feature answers which values are its own (`features/arrivals/verbs.ts`) — one door
that says whether it acted, so the delegation's branch is a SINGLE LINE and the engine SHRINKS
rather than grows — and it asks the QUEUE rather than the value's shape — « is it a number? » would be a rule about spelling, and
a medium whose title is a year would break it (`2012`, `1917`, `300`). The panel's dead branch is
deleted with it.

**The rule that closes it is R123** (`harness/take.py`, 9 holds, in the contracts tier), and it
was RED before the repair with no mutation needed:

    before   FAIL tapping it raises no error (B-309) — ["Cannot read properties of undefined (reading 'res')"]
             FAIL the medium LEAVES what is waiting to be taken — ['The Hawk','Backrooms'] → ['The Hawk','Backrooms']
    after    PASS the medium LEAVES what is waiting to be taken — ['The Hawk','Backrooms'] → ['Backrooms']
             PASS and JOINS what is in flight — ['President Curtis',…] → ['The Hawk','President Curtis',…]

It reads the STATE and not the message — a toast can be right about nothing — and it walks the
RELEASE screen's take too, because the two share an attribute and a repair that fixed one by
breaking the other would leave a one-sided rule green.

<sub>`sed -n '9615,9616p' frontend/maquette/design/src/engine/legacy.js@86fe9549a` · `python3 frontend/maquette/harness/take.py`</sub>

**CONFIRMATION ATTEMPTED by the operator on 2026-09-06 and NOT REACHABLE BY HAND**: no medium on the
design host sat « à prendre », so the button never appeared to him (B-345). The status stays `to confirm`
on the rule's own reading (`take.py`, R123, green on `main`) until the seeds offer the state and the
operator taps it.

**B-311 — a list does not come back at the place it was left.**
Reported by the operator on 2026-09-04, verbatim: « quand je reviens sur la liste après avoir vu
la fiche, je ne reviens pas avec le même scroll sur la liste ». Read: open a medium's sheet from a
list, go Back, and the list is not where it was.

**WHICH LIST MATTERS, and it is the first thing to establish rather than assume.** The library's
place-keeping was rewritten at L14 — `ui/reader-place.ts` and `ui/virtual-rows.tsx` restore a ROW
INDEX across a pitch change rather than a pixel — and that is a different mechanism from
`app/scroll-restoration.ts`, which keeps a scroll position per history entry for an ordinary page.
The two answer the same question on different surfaces, so a walk on the wrong one measures the
wrong mechanism.

**What L19 touched, measured**: `git diff origin/main...HEAD` reaches `features/library/` at phase
07 alone (the sort sheet), and touches **neither** `ui/reader-place.ts`, `ui/virtual-rows.tsx`
**nor** `app/scroll-restoration.ts`. What it did change on a page that scrolls is the Découvrir
feed (phase 14), whose list container the feature now fills.

**Rule 4 of this file applies before any repair**: the rule must cover the path the operator
actually walks — list → the medium's sheet → Back — and `harness/scroll_memory.py` is where it
goes. Whether it drives that path on a WINDOWED list is the question the reading has to answer.

**THE OPERATOR NAMED THE SURFACE AND THE MECHANISM.** « Acquisition », the « En cours » tab and
**not** « Suivis »; and « Bouton retour ou geste retour, même résultat : retour sur la liste EN
HAUT » — so the back mechanism is not the difference.

**WALKED TWICE ON BOTH BUILDS AND NOT REPRODUCED — said plainly rather than closed.**

    first walk    `#port.scrollTop = 900`, history back, sheet from a row
                  head    library 900 → 900 KEPT · follows 900 → 900 KEPT
                  control library 900 → 900 KEPT · follows 900 → 900 KEPT

    second walk   a WHEEL over `#port`, « En cours », a tap on a card, the interface's own
                  `__bridge.back()`
                  head    960 → 960 KEPT      control 960 → 960 KEPT

The first walk was worse than it looked and is recorded as such: it aimed at `#view` on a page
where the add screen is a LAYER, and its « finger drag » moved nothing at all — `#port` is the
scroller and a mouse drag on it does not scroll it. **A probe that reads 900 → 900 having never
scrolled is a green reading of nothing**, which is this register's oldest species; the second walk
scrolls for real and reads 960.

**Three differences remain between this walk and his**, and the entry stays open until one of them
is closed: (1) a TOUCH drag with momentum rather than a wheel — the virtualiser keeps its place
from a scroll offset, and a momentum scroll settles after the gesture ends; (2) the **standalone
PWA**, where the system back gesture reaches the app through history rather than through the
interface's own verb — his status bar shows the app installed; (3) a real device's own scroll
restoration, which a headless viewport does not have.

« I could not reproduce it » is an honest answer. « It does not happen » is not one this probe can
give, and the entry does not say it.

<sub>reported through the steward, 2026-09-04 · probe on 8899 and on a control of `4c0e274a7` served on 8902 · `git diff --stat origin/main...HEAD -- …/ui/reader-place.ts …/ui/virtual-rows.tsx …/app/scroll-restoration.ts` → empty</sub>

**B-312 — changing the lens during a selection drops it.**
Reported by the operator on 2026-09-04, verbatim: « sur médiathèque, à la sélection de médias,
quand je change de filtre — je passe de Tout à Films ou Séries — et que je sélectionne un média,
la sélection précédente est reset ».

**IT IS L14's DECISION, working as written, and that is why this entry is a RULING to obtain
rather than a repair to make.** The selection is dropped when the listing's QUESTION changes —
`legacy.js` writes `selected: new Set()` on a lens change and on clearing the search, and
`features/library/library-head.tsx` does the same from the React head. L14's reason was « a tick
nobody can see is a tick nobody can untick », and it was the right reason at the time: the
selection was keyed by a row's POSITION, so a tick surviving a change of listing could land on
another medium — which is the destroying-the-wrong-media defect L14 itself found.

**What changed under it**: L14 also re-keyed the selection by TITLE. A tick that survives a lens
change can no longer land on another medium, so the reason for dropping it is spent. What remains
true is the second half — a tick hidden by the lens has to be visible SOMEWHERE — and the
selection bar already counts MEDIA rather than rows, which is most of that answer.

**Not L19's**, whose contract is « no surface changes ». The operator's ruling is the gate; the
wave that owns the library's selection surface carries whatever it decides.

**RULED by the operator on 2026-09-05: « La sélection doit survivre au changement des filtres. »**
L14's decision is overruled, and the reason it was taken is spent — the selection is keyed by
TITLE since that same wave, so a tick that survives a change of listing cannot land on another
medium.

**REPORTED AGAIN by the operator on 2026-09-06** (« le bug de sélection reset lors du changement de
filtre dans la médiathèque est toujours là »): the ruling is four days old and no lot carries it —
neither `frontend-architecture.md` nor the clause map names B-312. PLACED BY THE STEWARD, PROPOSED:
**L13**, whose conversion of the library's engine half is where `selected: new Set()` is written on a
lens change (`legacy.js`) beside the React head's own write (`library-head.tsx`) — the two writers of one
fact; the operator ratifies or names another lot.

**Two guard-rails come with the ruling**, and they are the second half of « a tick nobody can see
is a tick nobody can untick »: the selection bar counts every ticked MEDIUM, hidden by the lens or
not; and the delete dialog NAMES every ticked title, the hidden ones included. A selection that
survives a lens change without both is a selection the reader cannot audit before destroying it.

**The rule the repair lands with**, named here so it is not invented twice: tick under « Tout »,
switch to « Films », read the bar's count and the dialog's titles; the mutation is the lens write
re-dropping the set, and the hold must fall on it.

**Owner**: the wave that owns the library's selection surface, or a behaviour wave beside B-313.
**Not L19** — its contract is « no surface changes » and it does not touch this.

**REPAIRED IN L13c c·1, rulings 115 and 116.** Five writers dropped the set, not two: `lens`, `cat`,
`setsort` and `clear-search` in `features/library/verbs.ts`, and the search commit in
`library-head.tsx`; none drops it now, and clearing the search no longer clears. The bar and the
delete dialog already read the whole stored set. **R195** `selection_survives_the_listing.py`, seen
red on the tree before the move — for each writer « the store still holds the same titles » and
« the bar's caption counts all of them » fell, and the dialog named no title under « Films » — then
green with its 14 holds; the mutation putting the `lens` write back fells exactly the two « the
lens » holds by name. The dialog's fold at four titles stays the drawn dialog (ruling 116): a
selection of five or more names its hidden titles only inside « et N autres ». Waiting for the
operator's hand.

<sub>`grep -n "selected: new Set()" frontend/maquette/design/src/engine/legacy.js` · `git show 9ce9b0508:docs/features/maquette-l14/REPORT.md` § the selection keyed by title</sub>

**B-314 — the add screen shows no example result to try the flow with.**
Reported by the operator on 2026-09-05: « Ajouter un suivi : le formulaire de recherche ne montre
plus d'exemple de résultat pour tester ». « Ne montre PLUS » says he saw them on an earlier build,
so the first question is which build — and it is answered by walking both, not by reading either.

**WALKED ON BOTH BUILDS AND NOT REPRODUCED.** The add screen is a LAYER over the acquisition
page, so the first probe read the page BENEATH it and saw nothing — corrected, and read inside
`[data-part="screen"][data-open]`:

    head     acq-add-empty   0 row(s), 2 field(s), « Cherchez un titre. Vos recherches récentes… »
             acq-add-results 5 row(s), query « star wars », « 5 résultats affichés sur 5 trouvés »
    control  acq-add-empty   0 row(s), 2 field(s), the same sentence
             acq-add-results 5 row(s), the same query, the same sentence

**Identical.** The example results are drawn on both, and no family the add screen reads died with
a producer — which is the § 10 question this entry was filed to answer, and the answer is no.

**What the fixtures cannot show**: the operator's « ne montre PLUS » refers to a build he saw, and
the two here are this head and `origin/main`. If the examples were lost on a build between them —
or if what he means by « exemple » is the RECENT SEARCHES the empty state offers rather than the
results — this walk does not reach it. The entry stays open for that answer rather than being
closed on a reading that does not contradict him.

<sub>reported through the steward, 2026-09-05 · probe on 8899 and on a control of `4c0e274a7` served on 8902</sub>

**B-317 — the greeting toast covers the settings save bar.**
At the centre of `#savebar [data-save]` — point (327, 758) at 390 px — `elementFromPoint` returns
a `SPAN` inside `DIV.toast`, on the head AND on a control of `4c0e274a7`. A finger there does
nothing at all while the toast lives; dismiss the toast and the same finger works.

**It is filed for two reasons and the second is the larger one.** The first is the defect: the
prototype's own greeting sits over the one control the settings page exists for. The second is
that it makes probes lie — round one's first two walks of B-299's banner read « no banner » and
were a green reading of NOTHING, because they tapped a covered button. Any rule that taps the save
bar without dismissing the toast measures the toast.

**Owner: the wave that draws the settings page's chrome.** The toast is the frame's, the save bar
is the page's, and which of them yields is a drawing decision.

<sub>found in round one's walk of PR #558, 2026-09-05 · `elementFromPoint` at the save bar's centre, head and control</sub>

**B-318 — the build races its own output on a fresh `dist`, again.**
B-098 was this defect in ONE hook and is recorded `fixed #503`. It is back in two:
`frontend/maquette/design/vite.config.mjs` `:62-78` and `:103-116` — both `closeBundle` hooks run
before rolldown writes. On a copy with no `dist`, `npm run build` fails deterministically with
`ENOENT scandir dist/vite`; three runs, one of them polling for twenty seconds. It succeeds only
where `dist/vite` already exists, **which means `buildWorker` composes `sw.js`'s precache from the
PREVIOUS build's bundle names** — the second half, and the worse one, because it is silent.

**Filed rather than repaired here.** It is not this wave's code and the repair is a build change
with a service worker downstream of it; a conversion lot carrying it would be the third kind of
change in one wave.

<sub>found in round one of PR #558, 2026-09-05 · three builds on a copy with `dist/` removed · B-098's shape, `fixed #503`</sub>

**B-319 — `fanout.py` holds the invalidation map against itself.**
The rule reads the declared invalidation map and checks that each refresh touches what it
declares. Two mutations of it were **survived**, and both say the same thing: every key in the map
is a single element, so the docstring's « a prefix one element too short » is a defect that cannot
exist in this tree; and a key REMOVED from the declaration is invisible, because the declaration
is what the rule compares against. **The map is its own oracle** — the same species as the size
ledger's record before 2026-09-05, and as `check-state-ownership.py`'s exemption before it.

The rule does bite where it reads the CODE: an operation that stops invalidating
`/api/library/incomplete` fails it, 7 violations, exit 1.

**Owner: the lot that next touches the query layer's invalidation.** The repair is a second end —
the map compared against the operations' own `invalidateQueries` calls, so a key dropped from
either side is a divergence rather than an agreement.

<sub>found in round one of PR #558, 2026-09-05 · two survived mutations of `frontend/maquette/harness/fanout.py`, one falling one</sub>

**B-320 — React #300 and #310 on the two non-ready acquisition surfaces.**
`acq-now-loading` and `acq-now-error` each log **three** `Minified React error #300` from a cold
page, and a sweep of the 87 named states also caught a `#310` — « rendered more hooks than during
the previous render » — reaching `acq-now-idle` immediately after `acq-now-error`. The surfaces
still draw, which is why no walk had met it: the errors are on the console, not on the screen.

**PRE-EXISTING, and measured on both builds.** `features/acquisition/now-tab.tsx` and
`features/acquisition/page.tsx` are unchanged between `4c0e274a7` and PR #558's head — `git diff
--stat` over that directory lists neither — and the acquisition files the wave did touch
(`queries.ts`, `live.ts`, `reference.ts`, `discover-tab.tsx`) carry no hook change. #310 is a hook
ORDER defect, so it is a conditional hook or an early return between hooks on a path only the
non-ready states take.

**Why nobody had seen it**: the wave's walks and the rule suite drive the LOADED states, and round
one read « zero console errors » honestly — no walk drove those two.

**Owner: the wave that next opens the acquisition page's non-ready branches.** Filed rather than
repaired here: a hook-order defect is a component change, and this lot's contract forbids one.

<sub>found in round two of PR #558, 2026-09-05 · 87 states swept and the two isolated on a fresh page each, head `583247947` and control `2f8503614`, three `#300` per state on both</sub>

**B-324 — the backend's mirror of the PM2 crons names three of the seven, and nothing reads it.**
`personalscraper/web/schedulers/registry.py`'s `CRON_JOBS` is, by its own header, « a static mirror
of the scheduled personalscraper crons » — the web process may not shell out to `pm2` nor read
`ecosystem.config.js`, so it hard-codes them. It holds **three**: `follow-detect`, `grab`,
`library-index --mode enrich`. The machine runs **seven** with a `cron_restart`, so `search`,
`health-check`, `backfill-ids` and `index-full` are absent from the list the production Dashboard's
schedulers panel is built from, and the header still says « the three crons here » under a comment
dated « verified 2026-07-15 ». `GET /api/maintenance/schedulers` therefore answers a watcher row
plus three cron rows on a machine running eight processes.

**IT IS B-308'S FINDING, on the end that has no guard at all.** B-308 says the fixture and the
machine are one contract with two ends and only one end has a guard; the maquette's end is now held
by `machine.py`, which reads `pm2 jlist` on the operator's machine. NOTHING reads `CRON_JOBS`
against anything — not a test, not a guard, not a startup check — so a cron added to
`ecosystem.config.js` is invisible here exactly as it was invisible to the maquette, and this list
has been four crons behind for longer than B-308's row was missing. The shape of the repair is the
same as `machine.py`'s and cannot be: the web process is forbidden `pm2`, so what it can hold is
the list against the deployed `ecosystem.config.js`, or a single declaration both read.

**Not repaired in the B-308 micro-wave**, and the reason is D7's: the backend follows the interface,
and the interface is not frozen. Owner: **the backend brief** —
`docs/reference/backend-demands-architecture.md` is where the backend's demands are gathered, and
this is one of them. Filed rather than left in a report because a defect with no entry is nobody's.

<sub>`python3 -c "from personalscraper.web.schedulers.registry import CRON_JOBS; print(len(CRON_JOBS), [j.name for j in CRON_JOBS])"` → `3 [...]` · `pm2 jlist | python3 -c "import sys,json;print(sorted(p['name'] for p in json.load(sys.stdin) if p['pm2_env'].get('cron_restart')))"` → 7 names</sub>

**B-326 — the lock's own probe reads « free » whether it is held or not.**
`scripts/heavy.sh` takes its lock with `mkdir "$LOCK"` (`:95`) and writes the holder's name to
`"$LOCK/who"` (`:96`), so `/private/tmp/tm-heavy/holder` is a **directory**. The script offers no
query — no `--held`, no `--holder` — so the natural way to ask « is anyone running » is
`cat /private/tmp/tm-heavy/holder`, which reads a directory as a file: it fails, and with the
`2>/dev/null` everyone writes it with, it prints NOTHING. **Empty output means « I could not read
this », and it is indistinguishable from « nobody holds it ».**

**Measured, on a private lock so no running work was touched** —
`HEAVY_LOCK=/private/tmp/tm-heavy-probe/holder sh scripts/heavy.sh probe-demo sleep 6`, probed two
seconds in, while HELD:

    cat holder        -> []            <- reads EMPTY while HELD
    cat holder/who    -> [probe-demo]
    test -d holder    -> HELD
    (after release)   -> free

**THE PROBES THAT READ** are `test -d "$LOCK"` for « is it held » and `cat "$LOCK/who"` for « by
whom ». Neither is written down anywhere, which is why neither was used.

**It cost twice in one night, in both directions**, which is what makes it an entry rather than a
note. The B-308 micro-wave reported « heavy lock free » twice to the steward as evidence that the
machine was clear, on a probe that cannot fail — a proof that certified nothing, offered as a
proof. The steward's own hygiene sweep read the same empty output and reported a `run.sh
--contracts` running UNLOCKED, which it was not: `heavy.sh` prints its own `starts` / `done` lines
around the command it holds the lock for, and every one of that wave's logs carries them. **One bad
probe produced a false clean and a false accusation in the same hour, and neither reader could tell
from the output.**

**Owner: the steward's office.** `heavy.sh` is the office's own instrument — the exception § 5's
« the steward does not carry code » carves — so the `--held` query, its hold in
`tests/scripts/test_heavy.py`, and the correction of the hygiene paragraph's probe are the office's,
not a wave's. This entry carries the reading; it changes nothing under `scripts/`.

<sub>`grep -n 'mkdir "\$LOCK"' scripts/heavy.sh` → `:95` · `grep -n '\$LOCK/who' scripts/heavy.sh` → `:96` and `:99` · the demonstration above · `grep -c '^heavy: ' <log>` on the wave's kept logs → the `starts`/`done` pair in each</sub>

**B-327 — « Réglages » is a job behind the machine, and names the others twice.**
« Système » draws **7** scheduler rows, « Réglages » under « Les passages programmés » draws **6**,
and `pm2 jlist` reports **7** processes carrying a `cron_restart`. `personalscraper-index-full` is
in neither the `passages` topic of `mocks/seeds/settings.json` nor — until #567 — the
`settings.labels` table that names its rows.

**IT IS PRE-EXISTING, and that is measured rather than conceded.** `seeds/settings.json` is
byte-identical at the branch point (`git diff be460fb79..HEAD -- …/seeds/settings.json` → empty)
and the machine already ran seven schedulers then. So « Réglages » was a job behind before B-308's
repair and is a job behind after it. **What the repair created is the VISIBLE DISAGREEMENT** —
« Système » right, « Réglages » still behind — where before the two surfaces were wrong together.
A wave that corrects one of two drawings of the same list does not own the other; it owes the
entry, which is this one.

**THE HOLD THAT WOULD CATCH IT IS WRITTEN, AND IT RAN.** It was added to `harness/machine.py`,
seen RED on the head, and taken out again because the defect it names cannot be repaired here. It
is kept whole so the wave that can inherits a rule rather than a description:

    await pg.evaluate("()=>{window.SETTINGS_STATE.topic='passages';"
                      " applyState({page:'cfg', phase:'ready'});}")
    await pg.wait_for_timeout(320)
    passages = await pg.evaluate('''
        ()=>[...document.querySelectorAll('[data-part="setting/row"]')].map((r) => ({
          key: (r.querySelector('[data-part="setting/origin"]') || {}).textContent || '',
        }))''')
    drawn_keys = sorted({row["key"] for row in passages})
    journal.check(
        "every scheduler the machine runs has a row on Réglages, and no row names one it does not",
        drawn_keys == sorted(real_schedulers),
        f"drawn: {drawn_keys} vs real: {sorted(real_schedulers)}")

**The hold above is B-327's; the LABEL half of that run is not.** The second violation of the same run was the label hold, and #567 keeps it — renamed « every scheduler the machine runs is named in the schedule's LABEL TABLE », because it reads the TABLE and not the surface, and a hold named for a surface it never opens reads as a certificate for it.

It reads the drawn keys as a SET and not a count, because a name that is WRONG and a name that is
MISSING are different defects a count cannot tell apart. What it printed, on `0ab9c9f29`:

    FAIL every scheduler the machine runs has a row on Réglages, and no row names one it does not
         — drawn: ['personalscraper-backfill-ids', 'personalscraper-follow-detect',
           'personalscraper-grab', 'personalscraper-health-check',
           'personalscraper-index-enrich', 'personalscraper-search']
           vs real: [… the same six …, 'personalscraper-index-full']
    91 rules EXECUTED — 2 violation(s)

**WHY THE ROW WAS NOT ADDED — four refusals, each measured, so nobody re-derives them.**

1. `SETTINGS` is not `converted` in `fixture-register.json`, so `check-mock-seeds.py --arm
   correspondence` re-derives `seeds/settings.json` from `legacy.js` byte for byte. Editing the
   seed alone fails that arm.
2. Adding the row to the engine fixture as well: the edit was made, the arm run and the edit
   reverted — « `engine/legacy.js` — recorded at 31 591 non-blank lines and reads **31 600, 9
   more**. A grandfathered file is one that may not be EXTENDED », exit 1. D5's exception covers
   only a defect that DESTROYS the operator's data; a row missing from a fixture is not one.
3. Marking the family `converted` while the engine still declares it: `--arm classification` fails
   — « the register calls it converted and the engine still declares it ».
4. Removing it: `const SETTINGS` spans **1 461 lines** (`legacy.js:5812-7272`) and is read by the
   engine's own `allSettings()` (`:7359`) and by **eleven** `window.SETTINGS` reads in
   `harness/settings.py`.

**AND THE SECOND HALF, which is why the first is not merely a missing line.** `settings.labels` is
keyed by the exact process names, and those are NOT the names « Système » draws: five of the six
differ — « Contrôle de santé » against « Contrôle de santé du système », « Détection des suivis »
against « Détection des épisodes diffusés », and so on. **The prototype names the same six jobs
twice, in two French vocabularies, in one file, with nothing holding them together.** A rule
joining a drawn list to `pm2` therefore needs neither the backend nor D7 — it needs the prototype
to name a job once. #567 adds the seventh to that table in « Système »'s own words, so the two
vocabularies gain no third. **Two holds in `machine.py` carry that**, and they are two because
presence and agreement are two questions: « every scheduler the machine runs is named in the
schedule's LABEL TABLE » reads that a name EXISTS for each, and « a scheduler the LABEL TABLE names
as « Système » does keeps that name, and a new one is placed » reads that it is the RIGHT one,
against a mapping of process name to the label « Système » draws — the five that disagree accepted
by name here, a sixth refused.

**Owner: L13**, the wave that converts `SETTINGS` — the family, its 1 461 lines, `allSettings` and
the eleven harness reads move together, and the row and the single vocabulary are that wave's to
land. **Done when** « Réglages » draws seven, the hold above is in `machine.py` and green, and one
job has one name.

<sub>**the FAIL line above is the attested one**, and it is corroborated outside this wave: the
independent reader of round three replayed this snippet verbatim on its own build of `512673ccf`
and read « drawn keys on « Les passages programmés »: 6 vs real: 7 → would FAIL ». **The run also
printed a SECOND violation — the label half — and that line is NOT quoted here, because no kept
artefact carries it**: it was in the wave's own session and in no report, probe or transcript a
later reader can open, and a sentence nobody can corroborate does not belong in an entry someone
else inherits. What became of that half IS checkable: #567 kept it in `machine.py` as the two holds
named above, both green, both mutation-proven. — on `0ab9c9f29` · `git diff be460fb79..HEAD -- frontend/maquette/design/src/mocks/seeds/settings.json` → empty · `python3 scripts/check-frontend-boundaries.py --arm size` with the row added → « 31 600, 9 more » · `grep -c "SETTINGS" frontend/maquette/harness/settings.py` → the eleven reads · reported by the independent reader of #567, round two, 2026-09-06</sub>

**REPAIRED IN L13c c·6.** The `passages` topic's seed gains `personalscraper-index-full` (Mondays
01:00), and the four refusals recorded above are all spent: `SETTINGS` is a converted family since
a·16, so no correspondence arm re-derives the seed, and the row is one row. **The hold this entry
kept whole is restored in `machine.py`, word for word but for its two reads** — the rubric is opened
by its own row, because driving a named state puts the settings back, topic included; and a drawn
origin carries its file before the key, so the key is taken from it. Seen red first, printing exactly
what this entry recorded: six drawn against seven real. The mutation removing the seed row fells it by
name. **One job, one name**: the seventh is labelled by `settings.labels` in « Système »'s own words
(« Analyse complète de l'index », added by #567), so it joins the schedulers named ALIKE and the two
vocabularies gain no third; the five that already disagree stay accepted BY NAME, which is the state
this lot leaves them in. `format.test.ts`'s two pinned counts moved with the seed (159 → 160 fields,
6 → 7 schedules), and the oracle accepted one state by name — `settings-field-schedule`, 55.4 px
taller for one more row. Waiting for the operator's hand.

**B-328 — `features/system/page.tsx` names a path and a field that do not exist.**
Its first line heads the file « design/src/pages/system.tsx », a path no commit holds, and its
tenth describes the surface's inputs as « `state.phase` … and `state.panne` » while the component
reads `state.fault` (`:90`). Both are byte-identical at the branch point, so neither is #567's —
that wave edited this file eight lines below the second of them and did not read up. A header that
names the wrong file and a comment that names a field the code does not have are the species
`CLAUDE.md` § Language calls out: prose that outlives its subject reads as current to the next
session, and this one has outlived two renames.

Owner: **the next wave that opens `features/system/page.tsx`**. Two lines.

<sub>`sed -n '1p;10p' frontend/maquette/design/src/features/system/page.tsx` · `grep -n "state.fault" …/page.tsx` → `:90` · `git diff be460fb79..HEAD -- …/page.tsx | grep -c "pages/system\|panne"` → 0</sub>

**B-331 — Réglages' pull-to-refresh indicator is off-centre and outlives the refresh.**
Reported by the operator on 2026-09-06 from his phone with two screenshots, verbatim: « Bug de loader
il est décentré et reste apparent ». On « Réglages », after a pull, the toast « Actualisé. » is up and a
16 px spinner is drawn at the LEFT edge of the viewport, cut on its left side, level with the top of
the scrollport; on the second screenshot the content sits 44 px lower with the spinner still there.

**What the code says, read rather than guessed.** The indicator is `#ptr` — `grid place-items-center
overflow-hidden h-0` with a `.spin` child — and the ENGINE drives it (`legacy.js`, the pull block near
`onRelease`): an armed release sets `.loading` and `height: 44px`, and a **1 100 ms timer** removes both
and toasts « Actualisé. ». So the second screenshot is the indicator OPEN (44 px, the content pushed by
exactly that) and the first is the moment the timer fires. Nothing in that block re-reads the surface:
the refresh is a fixed-length pretence (D7: the mock layer answers nothing here), and the toast lands
while the height transition is still closing. **The centring is NOT explained by the code** — at rest
on the device `#ptr` reads `display: grid` and its spinner at x = 177 of 369, centred, and
`place-items-center` is in the built stylesheet. Whether the spinner is at the left ONLY while
`.loading` is on (a rule in `legacy.css` — `.ptr.loading .spin` — animates it, and a transform on a
grid item does not move it left) is to be established by sampling the pull itself on the device; the
steward's driven pull on 2026-09-06 could not be read because the operator was using the page.

Owner: **L13**, the wave that converts the settings family and the engine's pull block with it — the
indicator is the frame's (`lib/pull-gesture.ts` is the gesture; the block that opens and closes the
indicator is still the engine's). The reading to take first is written above so it is not re-derived.

<sub>operator's screenshots, 2026-09-06 09:57 · `grep -n "ptr.classList" frontend/maquette/design/src/engine/legacy.js` → the `loading` / `armed` toggles and the 1 100 ms timer · `#ptr` read on the device over CDP at rest: `[177, 69, 16]` for the spinner's x, y, width · `grep -o "place-items-center{[^}]*}" …/dist/vite/*.css` → present</sub>

**REPAIRED IN L13c c·5 — the outliving half; the centring half is NOT REPRODUCED on this machine.**
`app/pull-indicator.ts`: an armed release now asks every query the page is showing again
(`refetchQueries({ type: "active" })`), the indicator stays open for exactly as long as that takes, and
« Actualisé. » is said after its closing transition; a reset or a newer pull makes an older answer
arrive for nobody. **R199** `pull_follows_the_refresh.py` samples the spinner at rest, armed, loading
and closing at 390 px on « Réglages » — **centred at every moment here, offset 0** — then holds the
closing after each of two mock answer times (400 and 1 600 ms) and the message after the closing. Red
on the tree: closed at about 1 300 ms whatever the answer time, and the message said while the
indicator was still open, at both. The mutation restoring a fixed delay fells both closing holds by
name; the mutation removing `place-items-center` from `#ptr` fells the centring hold and **draws the
operator's screenshot exactly** — the spinner at x = 0, 187 px left of centre. Two readers were
re-aimed and said: R55 (`touch.py`) and `press.py` give the mock layer an answer time after the state
is driven, since an instant refresh leaves no moment at which the indicator is up. The centring half
stays the operator's device reading.

**B-333 — « beaucoup de pages n'ont pas de bouton retour et le geste retour ne fonctionne pas non plus ».**
The operator's reading of 2026-09-06, verbatim, with the sentence that makes it a frame matter: « ça
devrait être impossible car faisant partie du carcan de l'App ». The frame's model (P3, « Back walks the
ladder ») reads **true** under R59, R65, R69, R82 and R94, and D1b says a top-level page carries no back
button by design — Back from a page lands on `/acquisition`. So either the operator meets screens that
are NOT the four pages and still draw no back, or the ladder does not answer the SYSTEM gesture on his
device the way the rules drive it. One instance is measured (B-332: a topic replaces instead of pushing).
**The inventory is owed and it is the steward's**: every named state that is a screen or a topic below a
page, read for (a) whether entering it pushes an entry (`history.length` +1), (b) whether it draws a
back affordance, (c) what the system Back does there on the device — taken on the phone paired to this
machine, never inferred from the rules that already read true. Filed rather than answered so the
inventory has a name and the operator's sentence is not lost.

Owner: the **steward's inventory first**, then the lot the inventory names per screen.

<sub>operator, 2026-09-06 · `docs/reference/frame-model.md` P3 · D1b rules 1–3</sub>

**THE INVENTORY, TAKEN ON THE OPERATOR'S PHONE (steward, 2026-09-06 11:40–11:50, Chrome 152 / Android 16, the
design host serving L21's head `3afba585a`).** Two passes: every named state that is a screen, a topic, a panel
or a page driven by `window.__go` (29 states), then the REAL path — a real load, a real tap, then
`history.back()`, which is what the system gesture calls inside the PWA — on the cases the operator meets.
What it read:

    the five SCREENS (media, add/identify, releases, quality, resolution)
        push an entry (real path on the media screen: history 16 → 17), draw `screen/back`, and Back
        lands on the parent page (`/media`), then on `/acquisition`         → P3 TRUE
    the PANELS (journey, follow, more, user) and the DRAWER
        Back closes them and lands on the page beneath                        → TRUE
    the PAGES (media, arrivals, system, settings, maintenance, account)
        no back drawn (D1b: none by design); Back lands on `/acquisition`    → TRUE, as ruled
    the TOPICS — Réglages' rubrics (B-332) and Maintenance's rubrics (B-361)
        entering pushes NOTHING (settings: the address is not even written; maintenance: written as
        `?topic=query` by replacement), no back is drawn, and Back leaves the PAGE for `/acquisition`   → FALSE

So the sentence « beaucoup de pages n'ont pas de bouton retour et le geste retour ne fonctionne pas » is
TRUE of every topic and false of every screen: the reader who enters a rubric of Réglages or Maintenance
has no way back but the tab bar, and the gesture throws him out of the page. **Not measured**: an arrival's
resolution by the real path — no card on the design host carried `data-resolve` at rest (B-345's shape).
**Owner, per screen**: the topics are B-332's and B-361's owners; nothing else is owed by this entry.

<sub>steward, 2026-09-06 · `scratchpad/cdp-back-inventory.py` (29 states, `back-inventory.jsonl`) and `cdp-back-real.py` / `cdp-back-real2.py` (`back-real*.jsonl`), raw CDP on the phone's tm-design tab; `window.__go` builds its own stack, so the FIRST pass reads the affordance and where Back lands, and only the SECOND pass reads whether entering pushes</sub>

**B-336 — the library's kind chips show their scrollbar.**
Reported by the operator on 2026-09-06, verbatim: « Filtre médiathèque Tout/films/séries il y a un
scroll horizontal, la barre de scroll est visible elle ne devrait pas l'être ». The strip under the
library's search — « Tout 1861 · Films 717 · Séries 528 » — overflows the 369 px viewport and scrolls
sideways with a visible bar. The prototype already has the idiom for a strip that scrolls without
showing it: `pillscroll` (`ui/variants/controls.ts`, `[scrollbar-width:none] [&::-webkit-scrollbar]:hidden`),
and D11 says a scrollbar is STYLED, never replaced — a strip of chips is the one place a bar is hidden
because the chips themselves are the affordance. **Where the strip is drawn is to be located before it
is repaired**: it is not in `features/library/` (`library-head.tsx` draws the three LENSES, not the
kinds), so it is the engine's library head, and its container carries neither `pillscroll` nor the
two declarations. Owner: **L13**, with the library's engine half; if a wave opens that head earlier,
it takes the two declarations with it.

<sub>operator, 2026-09-06 · `grep -rn "kindAll" frontend/maquette/design/src` → the ADD screen only (`add-screen.tsx:283`), not the library · `grep -n "pillscroll" frontend/maquette/design/src/ui/variants/controls.ts` → the idiom</sub>

**REPAIRED IN L13c c·4, ruling 119.** The strip was already drawn by `library-head.tsx` through
`pillScroll`, whose `[scrollbar-width:none]` was written and never computed: `styles/base.css`'s
`* { scrollbar-width: thin }` is unlayered and beats every layered utility. The declaration takes
Tailwind's important mark in that variant alone. **R198** `kind_chips_scrollbar.py` reads the strip at
390 and 369 px — it overflows and a horizontal wheel moves it, and its computed `scrollbar-width` is
`none` — red on the tree (`thin` at both widths), green after; the mutation removing the two
declarations fells both `scrollbar-width` holds by name. The media cast strip wears the same defeated
idiom and was not touched. Waiting for the operator's hand.

**B-337 — a swiped-open follow card ignores the first tap on its revealed action.**
Reported by the operator on 2026-09-06, verbatim: « Lorsqu'on glisse une carte de suivi à droite ou à
gauche pour afficher les actions, il faut 2 clics sur le bouton pour que ça soit pris en compte, le
premier clic ne fait rien systématiquement ».

**What the code says, and what it does not settle.** The engine's swipe (`legacy.js`, the block from
`cadre.addEventListener("pointerdown"` to the capture-phase `click` guard) arms `clickAfterDrag` at the
release point of any drag that travelled more than 4 px, and swallows the next click within 24 px of it
— written for a MOUSE, whose click follows a drag; its own comment says « after a touch drag the browser
suppresses the click by itself ». On touch, then, the mark stays ARMED after the swipe, and the next
`pointerdown` clears it (`clickAfterDrag = null` is the handler's first line) — so by that reading the
first tap should pass. Two mechanisms are left to tell apart on the device, and the reading is a
finger, not a click: (a) the first tap's `pointerdown` on the open row re-enters the drag machinery
(`cardDrag` with `depart = openCardDx`) and something on its release — `endCardDrag`, the press
arbitration's own `swallowClick`, or a `pointercancel` the compositor fires because the row carries
`touch-action` — swallows the click; (b) the revealed action sits under the translated card's hit area
for the first tap and the tap CLOSES rather than acts. Whichever it is, « systematic » means the rule
that reads it is cheap: swipe a card open with a real touch, tap the revealed action ONCE, hold that
the act happened.

Owner: **L21** if it touches `follows-tab.tsx`'s swipe while moving `data-pause` / `data-remove` (the
revealed actions ARE those verbs, and a rule that taps them once is the rule the brief asks for);
otherwise **L13**, with the engine's swipe.

<sub>operator, 2026-09-06 · `grep -n "clickAfterDrag" frontend/maquette/design/src/engine/legacy.js` · `grep -n "swallowClick" frontend/maquette/design/src/lib/press-arbitration.ts` · to measure: a touch swipe then ONE touch tap on `[data-part="swipe/action"]`, reading which listener consumed the click</sub>

**B-339 — a disabled panel action looks enabled.**
Reported by the operator on 2026-09-06 with a screenshot, verbatim: « Le bouton ajouter ne fait rien
sur cet écran » — the add screen, a result already added (the strip says « 2 médias ajoutés », the row's
chip « ✓ Ajouté »), its panel's primary action reading « + ✓ Ajouté » in full primary yellow.

**Read in the code: the act IS spent, and the drawing does not say so.** `features/acquisition/panel-add.ts`
gives the action `desactive: done` (`done` = the result's position in `state.added`), and
`ui/panel/index.tsx` writes it as `<button class="sact primary" disabled …>`; `addVerb` (the engine's
label derivation, `legacy.js`) reads the SAME set and prints « ✓ Ajouté ». So the button is disabled and
its tap does nothing, correctly — but `.sact` and `.sact.primary` (`styles/legacy.css:1674-1703`) carry
**no `:disabled` rule at all** (the only one in the residue is `.btnprimary:disabled`, another
element), so a spent primary action is painted identically to an available one: same yellow, same
weight, a « + » icon beside a check mark. The reader reads an act, taps, and reads a defect. It is not
the add screen's alone: every panel action that passes `desactive` is drawn this way, and DOIT-4's
queued state (an act that cannot be taken NOW) has no visible form to inherit either.

Owner: PROPOSED **L21** — it is the lot drawing new panel actions with a not-available state (the
queued button, DOIT-4), and the disabled drawing is that state's floor; the action's variant leaves the
residue for `ui/variants` with its `disabled:` half. The operator ratifies, or names L13 (D10: the
residue dies there).

<sub>operator's screenshot, 2026-09-06 10:10 · `grep -n "desactive" frontend/maquette/design/src/features/acquisition/panel-add.ts frontend/maquette/design/src/ui/panel/index.tsx` · `grep -n "\.sact" frontend/maquette/design/src/styles/legacy.css` → 1674, 1688, 1694, 1697, 1703, none with `:disabled` · `grep -n ":disabled" …/legacy.css` → `.btnprimary:disabled` only</sub>

**REPAIRED, in two halves (ruling 118).** The opacity half landed with L20 (`60c6d9b1d`, #603):
`disabled:opacity-50` on the action variant's base, after this entry was filed. L13c c·3 closes the
rest: a spent act wears no « + » (`features/acquisition/panel-add.ts` — the producer knows it is spent,
the variant stays neutral). **R197** `disabled_action.py` reads two real add panels of one answer, one
result added by a finger: the spent act is disabled and a re-tap adds nothing, its drawing differs
from the available act on `opacity` in the dark theme, the light theme and with reduced motion, and it
wears no « + ». Written before any move, it read green on the first three holds — said in its
docstring — and red on the icon; the mutation removing `disabled:opacity-50` fells the three drawing
holds by name, the one handing `icons.plus` back fells the icon hold. Waiting for the operator's hand.

**B-340 — the « + » button reopens the add screen where the last visit left it.**
Reported by the operator on 2026-09-06 with a screenshot, verbatim: « Une fois que j'ai cliqué sur la
répartition d'une arrivée, la recherche pour l'ajout aux suivis reste avec une recherche active, elle
devrait s'être reset quand j'appuie sur le bouton + pour pouvoir lancer une nouvelle recherche. L'état du
formulaire n'est pas celui attendu ». The screen: query « Marvels Spider-Man 2 v1 526 0 -Mephis… » (a
release name the identify path had seeded), « 0 résultat affiché sur 0 trouvé », and the footer strip
« 2 médias ajoutés » from the previous visit.

**Read in the code, two halves.** (1) The floating action button (`app/action-button.tsx:41`) opens the
screen with `window.__screens.add(String(state.addQ ?? ""), "follow")` — it hands the LAST entry query
back in. `state.addQ` is written by every visit (`add-screen.tsx`'s `search()` keeps the legacy readers
in sync, and the resolution path seeds it with the folder's name before `screens.add(trim, "identify")`,
`legacy.js`), so a « new search » from the « + » is the previous search, in the previous words. The add
screen itself reads the ROUTER's `q` and says so in its own comment — the store's copy « is the ENTRY
query and is stale by construction » — which is exactly the copy the button reads. (2) `state.added`
(the positions already added, the footer strip's count and every « ✓ Ajouté ») is `new Set()` only in
the named states' reset and in the store's initial shape (`legacy.js:5214`, `:5632`); nothing clears it
when the screen is opened for a new search, so the strip and the ticks outlive the results they were
about — and since they are keyed by POSITION, a new answer's row 0 inherits the tick of the previous
answer's row 0 (B-339's « ✓ Ajouté » on a result that may never have been added is this defect seen from
the panel).

**What the operator expects, and it is the frame's contract**: the « + » opens a FRESH add screen —
empty query, mode `follow`, nothing added yet — while the identify path keeps seeding the folder's name
as it does. Owner: PROPOSED **L13** with the add screen's engine-owned state (`addQ`, `addMode`,
`added`); the FAB's one line is the frame's (`app/`) and moves with it. The operator ratifies or names
another lot.

<sub>operator's screenshot, 2026-09-06 10:13 · `sed -n 41,42p frontend/maquette/design/src/app/action-button.tsx` · `grep -n "added: new Set\|added.add" frontend/maquette/design/src/engine/legacy.js` → 5214, 5632 (resets: initial shape and named states only), 9526, 9586, 9592 (adds) · `grep -n "screens.add(trim" …/legacy.js` → the identify seed</sub>

**REPAIRED IN L13c c·2.** « + » opens `screens.add("", "follow")`; `addQ`, `addMode` and `added` left
the store. `features/acquisition/add-visit.ts` holds ONE visit — begun at the add screen's first
render, its mode mirrored from the router for the verbs and the panel, what was added keyed by the
result's kind and provider identifiers, never its position; the identify path seeds the folder's name
through the address, unchanged. **R196** `add_screen_opens_fresh.py` walks the screenshot's journey by
finger and was seen red before the move — the field kept « Backrooms 2026 » at both openings, the
strip of an earlier visit, one row of five checked — then green with its 7 holds; the mutation
handing the stored `resolveTarget` back to « + » fells the two empty-field holds by name, and the one
not beginning the visit fells the strip and the checked-row holds. B-339's « ✓ » on a result never
added, from a stale position, is gone with it: a fresh visit checks no row (R196's last hold); the
drawing of a disabled act is c·3's. Waiting for the operator's hand.

**B-345 — the seeds do not offer every state to a hand that walks the interface.**
The operator, on 2026-09-06, trying to confirm B-309 on the design host, verbatim: « Pas testable, j'ai
aucun torrent dans cet état qui me permet de tester, d'ailleurs c'est un bug global, on devrait toujours
avoir assez d'états simulés dans les données de test afin de tester tous les cas de figure ! » The
harness reaches every state through NAMED STATES (`engine/states.js`, `window.__go`), which re-seed the
layer for a rule; the operator walks the interface with a finger and reads what the seeds hold at rest
— and at rest, no follow's medium sits in Arrivées « à prendre » on his head (`seeds/takeable.json`
holds two cards, and none reached his screen as such), so the one verb B-309 repaired was unreachable to
him. **The ruling is a property of the fixtures, not of one seed**: the data the design host serves at
rest holds at least one subject in every state every surface can draw — a takeable arrival, a blocked
one, a paused follow, a season with a hole, a conflict, a restart owed — so any case can be tried by
hand without a named state. §13 (real data) and the fixture clause the operator ratified on 2026-09-05
(a measurement L13 inherits) are where this lands: the fixture families' owner measures the states each
surface can draw against the states the seeds hold, and fills the holes. Owner: **L13** with the
fixture clause; a wave that reseeds a family earlier takes its surfaces' share (L21's `acquisition-verbs`
seeds are the first case: a takeable arrival for a followed medium is one line).

<sub>operator, 2026-09-06 · `python3 -c "import json; print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/takeable.json'))))"` → 2 · `grep -n "toTake" frontend/maquette/design/src/features/acquisition/follow-facts.ts` → `queue.takeable.some(…)`</sub>

**RULED by the operator on 2026-09-06 (round 2, question 3): each wave fills its own family as it passes.**
**L21, now**: the acquisition seeds offer at rest a takeable arrival for a followed medium, a blocked one, a
paused follow and a season with a hole, with a rule that counts them. **The « settings » micro-wave**: a
conflict and a restart owed. **L13**: the library and the rest, with the fixture clause.

**THE SETTINGS HALF IS DONE #588 (the settings micro-wave), and the register's own words for it
were « a conflict and a restart owed ».** At rest one configuration file is marked as having
CHANGED ON DISK (`mocks/state.ts`), so its write answers `conflict: true` and a HAND reaches
B-299's banner by saving a setting that lives in it — with no dial and no named state. The dial
(`setConfigurationConflict`) STAYS a dial: it is a property of the REQUEST, and what the seeds add
is a property of the FILE. Any other save reaches the restart banner, so B-300's confirmation is
one tap further on. The file is a notifications one rather than a storage one on purpose: the paths
are what one edits first when trying the editor out, and having THAT save answer « le fichier a
bougé » would make the ordinary case the surprising one.

    the rule            R128, `harness/seeds_at_rest.py`, five holds added — and it calls
                        `window.__go` NOWHERE, which is that rule's whole design: the walk is a
                        boot and taps a thumb makes, so what it measures is what a hand reaches
    the run             `python3 frontend/maquette/harness/seeds_at_rest.py` → 15 holds, no
                        violation

**THE LIBRARY HALF IS HELD, AND THE SEEDS ALREADY HELD IT — L13c c·8.** The states the library's
surfaces draw were listed from the drawing's own branches and measured against what the layer serves
at rest: the three lenses, every category chip, a title the library holds TWICE and one that is also
FOLLOWED (the delete dialog's two figures), a title with a HOLE, a listing longer than one screen (the
sort and the paging), and a row with no poster. **Every one has a subject at rest**, so nothing was
filled: **R128** gains eight holds that were green the day they were written, said in its docstring.
Two mutations fell them by name — a category emptied of its media, and the one title held twice made
single. **The first reading of these holds was RED on five of them and the instrument was at fault**:
it judged the seeds by ONE page of a paged listing and by the layer's `total`, which answers the
library's own 1 861 — a figure the seeds never had. Read to `loaded`, what the layer holds, there are
345 rows and every state among them. The other surfaces' share of this entry (L21 did acquisition,
#588 settings) is not measured here and is reported to the steward. Waiting for the operator's hand.

**B-360 — the pre-push gate refuses a push over a green suite, and shows the reason to nobody.**
Measured on 2026-09-06, three refusals in one morning on two branches. `hooks/pre-push` runs every check
SILENTLY first (`"$@" > /dev/null 2>&1`, its `run_check`) and, on a non-zero exit, reruns it VISIBLY
(`"$@" 2>&1 | sed`) and counts the failure whatever the rerun says. So when the silent pytest run dies of
a signal, the reader is shown the RERUN's green summary — « 11 307 passed » on the steward's
`claude/steward-reports-0906`, « 11 325 passed » on L21's `feat/maquette-l21` — followed by « 1/5
check(s) failed. Push aborted. », and the only trace of the failure is bash's own job line:
`line 36: 86894 Terminated: 15  "$@" > /dev/null 2>&1` on one push, `94910 Exit 1 … 94911 Abort trap: 6
| sed` on another. The steward's push, re-run twenty minutes later under the lock at three workers,
landed unchanged. **Where the signals come from is NOT read**: no crash report was written, the lock
script's watchdog printed nothing and exits 75 when it acts (these runs exited 1), the hook wraps
nothing in a timeout, and the suite's own signal-sending tests (`tests/scripts/test_heavy.py`,
`tests/trailers/test_state.py`) terminate only processes they started. **What IS read is the
instrument's shape**: a gate whose verdict rests on an output it throws away, and whose visible output
contradicts its verdict. A reader who trusts the summary bypasses the gate; one who trusts the verdict
looks for a red test that does not exist; and the L21 agent, rightly, did neither and stopped at 60 %
context with nineteen commits it could not land. Two things owed, in the hook: the silent run's output
kept in a file the abort message names, so the reason is readable; and a rerun that passes is a check
that passed — or no rerun at all. Owner: **the next wave that opens `hooks/`**, and CI is not exposed to
this shape (it runs the suite once and shows it). Numbered from the steward's block (B-360+): L21 holds
B-351+ and the departure wave B-346+ on their branches.

<sub>steward, 2026-09-06 · the two pushes' logs (`push-reports.log`: `Terminated: 15`, then 11 307 passed, then « Push aborted »; `push-reports-2.log`: landed) · the L21 agent's report of 11:2x (`Abort trap: 6`, 11 325 passed, « Push aborted », `heavy: l21 done (exit 141)`) · `sed -n '32,42p' hooks/pre-push` · `find ~/Library/Logs/DiagnosticReports -newermt "-90 minutes"` → nothing</sub>

**B-363 — a shared token constant cannot be read by the instrument that compares variants.**

`harness/residue.py`'s `read_factories` builds a `cva()` factory's base from the STRING LITERALS
of its first argument. A factory written as `cva(`mt-4 ${scale}`)` therefore has an empty base, and
the reader says so rather than passing — `unread` is a violation and never a skip, exactly as its
own docstring promises: « a factory the reader could not read is a pair that silently stops being
compared ».

**Measured** when the load footer's two actions — the retry and « load more » — were given one
`footerActionScale` constant to share, which is the shape the catalogue wants for a scale used
twice: `tests/scripts/test_residue.py::TestFactoryReading::test_the_repository_accounts_for_every_call`
named both factories as unread.

**THE OBVIOUS REPAIR IS WORSE THAN THE DEFECT, and that is the part to remember.** Writing
`cva("mt-4 " + scale)` gives the reader a literal, so the complaint goes away — and the base it
then reads is the single token `mt-4`. It would go on comparing that one token, report nothing, and
have stopped reading the pair. A gate quieted is not a gate passed.

**Worked around, not fixed.** The scale is spelled out in both variants and the two are held equal
by a unit test (`ui/variants.test.ts`), which fails out loud when one moves without the other. The
cost is a duplicated string; the alternative was a blind instrument.

**What a fix would take**: reading the first argument through the TypeScript parser rather than by
literal extraction, and following a same-file constant to its own literal — the parser is already
used by `check-markup-contracts`, so the capability exists and is not wired here. **Owner: the next
wave that touches `residue.py`.**

<sub>L21 · `python -m pytest tests/scripts/test_residue.py::TestFactoryReading::test_the_repository_accounts_for_every_call` → `assert ['loadErrorAction() in surfaces.ts', 'loadFooterAction() in surfaces.ts'] == []`</sub>

**B-364 — a hit test that cannot press an icon.**
`PRESS_THE_ACTION` and `PRESS_THE_ACTION_BY_PART` in `harness/busy.py` do the right thing and then
undo it: they take the control's own centre, ask `document.elementFromPoint` what is really there,
confirm the answer is inside the control — and then call `hit.click()` on the ANSWER. When the
centre of a control is an icon, that answer is an `SVGElement`, which does not inherit from
`HTMLElement` and has no `click` method. The rule does not fail its hold; it THROWS
`TypeError: hit.click is not a function` and takes the whole walk with it.

**MEASURED, on this prototype, on an element these very helpers could meet.** A probe over the
arrivals cards raised the identical error from the identical expression — a card whose hit-tested
centre resolved to the icon inside the folder button. R124 is green today only because the panel
actions it presses carry their TEXT across the centre; a control drawn icon-only, or an icon that
grows, moves the hit under the SVG and the rule stops running.

**Two lines below it, the diagnostic has the same origin**: `covering: hit.className` reads
`SVGAnimatedString` on an SVG element, so the message naming what covered the control prints
`[object SVGAnimatedString]` — a coverer nobody can identify, in the field written to identify it.

**NOT A MEMBER OF § Guards green over what they do not read**, and that is why it is filed here
instead of counted there: it is loud. A throw is red, and this table's species is a hold that
PASSES over the thing it exists to catch. Saying which of the two a finding is costs a sentence and
is the difference between a count that means something and a count that flatters.

**What a fix would take**: dispatch on the control rather than on the hit — the handler is
delegated, so a real finger on a child bubbles to the same place — or drive the point with the
harness's own mouse, which is what `panel_label_once.py` does (`page.mouse.click(x, y)`); and read
the coverer with `getAttribute("class")`. **Owner: the next wave that touches `busy.py`.**

<sub>L21 · probe over `arr-queued`'s cards → `Page.evaluate: TypeError: hit.click is not a function` · `grep -n "hit.click()" frontend/maquette/harness/busy.py` → 2</sub>

**B-366 — a follow with no media sheet is not a state this product has.**

**THE OPERATOR RULED, and the ruling changes what the defect IS:** « il ne doit pas y avoir de
suivi sans fiche, si on a un suivi c'est qu'on a identifié le média, si on a identifié le média
alors on peut afficher sa fiche, le suivi sans fiche n'est pas un état possible ».

So this is not a tile that must ask a question before it offers a poster. **Following a title IS
having identified the medium**, and an identified medium has a sheet; the sheetless follow is not a
case to be handled, it is a case that must not exist. The repair is to make the state
UNREPRESENTABLE — the contract and the mock unable to produce it, and a guard that refuses one —
rather than to teach one more drawing to guard against it.

⚠ **A FOLLOW WITH NO EPISODE DATA IS A DIFFERENT THING AND STAYS LEGITIMATE.** A show whose
provider offers no episode listing is identified, has a sheet, and is followed on purpose; the
prototype carries such a case deliberately. « No sheet » and « no episodes » are not the same
absence, and a guard that conflated them would refuse a state the product needs.

**WHAT WAS MEASURED, and it stands.** `audit.py`'s R1 (« every tappable poster leads to a
FILLED-IN sheet ») read two violations on `acq-follows-grid`: `legacy.js`'s tile drawing puts
`data-mediasheet="<title>"` on every follow's poster, and two follows had titles no sheet answers
to. The follow PANEL already refuses the same offer — `features/acquisition/follow-actions.ts`
carries the sentence in its own comment, « AN UNIDENTIFIED RELEASE HAS NO SHEET. Offering to open
one is the same broken promise as a poster that leads nowhere » — and the card drawing refuses it
too, with `data-nonmedia="dossier"` and a FOLDER button in place of the poster. Under the ruling
those two guards are no longer the model to copy: they are handling a state that should never
reach them.

⚠ **THE INSTRUMENT IS QUIET AND THE DEFECT IS NOT REPAIRED.** The two follows were renamed to
titles that already have sheets, so nothing in the prototype now carries a sheetless follow and R1
stops reading the case entirely. That is the fixture no longer producing the subject. A register
entry is the only thing that can say so, which is why this one exists.

**WHY IT IS NOT MADE UNREPRESENTABLE HERE, and the number is the reason.** Every route runs into
the same wall. The tile's drawing is `legacy.js`'s, and D5 has the engine dying by subtraction —
`frontend_size_ledger.py` refuses it upward against its record. Giving a title a sheet is the same
wall in other clothes: `SHEETS_RAW` is a **20 538-line object literal inside `legacy.js`**
(`:9897` to `:30434`) and `mocks/seeds/media-sheets.json` is a DERIVED copy that
`check-mock-seeds`'s correspondence arm re-derives and refuses drift on, so seeding a sheet adds
lines to the engine as surely as editing the tile would. And making the state unrepresentable in
the CONTRACT — a follow that cannot be described without a sheet — is surgery on the contract, its
types, its handlers and the engine that reads them, which is a lot's worth of work and not a
guard.

**Owner: L13**, with the tile's drawing, and the shape of the repair is now dictated: not a guard
on the tile, but a follow that cannot be built without a sheet.

⚠ **R156 IS A GATE, NOT THE REPAIR, and nobody should later read it as one.** It refuses a
sheetless follow in the prototype — every followed title is asked of the drawing's own resolver and
the suite falls if one resolves to nothing — which keeps the state out while it remains
DESCRIBABLE. Making it unrepresentable is the ruling, and it is still owed.

<sub>`audit.py` → `■ R1 hollow sheet behind a poster — 2` on `acq-follows-grid` · `legacy.js:7732` (the tile), `:5314` and `:5322` (the card, which guards it) · `const SHEETS_RAW = {` at `legacy.js:9897`</sub>


**REPAIRED IN L13c c·7 — and the enforcement is NOT the type.** Measured first: making `Follow.ids`
optional in the contract produces ZERO tsc diagnostics, because every reader already guards the
field; and the interface's own create sent a title and a kind and no identity at all, so the only
source of one was the layer's join against what it serves. **The refusal therefore lives on that
path**: the mock answers the contract's 400 and records nothing when it can identify a create from
neither the request nor the entry the title was followed from. The act now CARRIES the identity when
its caller holds one — a search result, a suggestion — and `queries.ts` sends it as
`provider`/`providerId` (a provider identifier the contract can carry is a number, so a title-shaped
one is not the one sent). The two branches drawing a follow without a sheet are gone: the panel's
« Voir le parcours » fallback and its wait for an identity to arrive. The CARD's own branch stays —
an unidentified RELEASE is not a follow. **R200** `follow_needs_an_identity.py`: red on the two
refusal holds (the layer answered 200 and recorded the follow), with a create it CAN identify as the
control, and a hold saying that a follow with no episode data is created like any other — « no
sheet » and « no episodes » are two different absences. The mutation removing the refusal fells both
by name. Waiting for the operator's hand.

**B-370 — a gate that exits on a usage error looks exactly like a gate that ran.**
`scripts/harness-hold-counts.py --compare` takes a FILE. Invoked without one, `argparse` prints a
usage line and exits **2** — and a wave gate that reads « did it exit non-zero? » sees the same
shape as a comparison that found drift, while a gate that reads a log sees a step that produced no
verdict at all. One pass of L21's own gate ran that way: the compare was in the script, the script
ran, and NOTHING was compared.

**IT IS THE SHAPE, NOT THE TOOL.** Every gate assembled as a list of commands has this hole: a step
that fails to START is indistinguishable from a step that ran and passed, unless something reads
the step's own verdict LINE rather than its exit code. `mutate.sh` has the same defect from the
other end and it is B-273 — a crashed rule prints FAIL lines and no `EXECUTED` line.

**What a repair would take**: the tool prints a verdict line whatever happens, and the gate reads
that line rather than the exit code. NOT DONE HERE, deliberately — filed for whoever next opens
that script.

<sub>`python3 scripts/harness-hold-counts.py --compare` → `error: argument --compare: expected one argument`, exit 2</sub>

**B-367 — the appearance control paints the theme and leaves its selection behind.**
The drawer offers three appearances. Pressing one writes the choice, repaints the document — and
does not move which of the three is shown as chosen. The operator reads « Clair » selected over a
dark interface, which is exactly what a stale selection looks like after a second choice.

**MEASURED, and the mechanism is not the one the storage key suggests.** Both halves of the write
work. Pressing in turn `light`, `dark`, `system`, `light`, the stored value and the painted theme
follow every press — `stored` goes `light`, `dark`, `system`, `light` and `data-theme` goes
`light`, none, none, `light`. `aria-pressed` does not move once: it reads
`system=true light=false dark=false` at every one of those four readings, which is the state the
drawer was drawn in. Closing the drawer and reopening it reads `system=false light=true
dark=false` — correct, and against the theme in force.

**SO IT IS A REDRAW THAT DOES NOT HAPPEN, and the code says the opposite in a comment.** The
handler calls `window.__store.touch()` beside a comment reading « The bump is what redraws the
pressed state ». The measurement above says that bump does not reach this control: the pressed
state is read from `currentAppearance()` at render, and nothing re-renders the drawer until it is
mounted again.

**Owner: the « settings » MICRO-WAVE** (`docs/features/maquette-settings/BRIEF.md@a155b54fb`), with B-332 and
B-361 — the drawer's own behaviour, not the surface this lot draws. Filed, not repaired.

<sub>operator, on the design host · a real drawer open, four presses through the control: `{"theme": null, "stored": null, "pressed": ["system=true", "light=false", "dark=false"]}` at rest, then `stored` `light` / `dark` / `system` / `light` with `pressed` unchanged at every reading, then after a close and a reopen `["system=false", "light=true", "dark=false"]` · `app/appearance.ts` (`chooseAppearance`, `STORAGE_KEY = "tm-apparence"`), `app/drawer.tsx` (the control, and the comment)</sub>

**B-388 — the rule that keeps harness chrome off the app's controls reads one control by name.**
`frontend/maquette/harness/chrome.py` opens « The prototype's own controls never sit on top of the
app's » and then measures `document.querySelector('[data-part="harness/bar"]')` — one literal, the
harness bar, at 390 px and 1280 px across every named state. The promise is about a CLASS of thing
and the reading is about one member of it. Found while adding the second member: the desktop switch
is held against the same list of the app's fixed chrome by its own rule, at both of its states, so
the property is true today — by two rules that each name their own subject rather than by one rule
that reads the class. A third piece of harness chrome would be covered by neither, and nothing would
say so: R51 would stay green, `--a11y` audits at 390 px where harness chrome is deliberately absent,
and the oracle measures under `html.measuring`, which clears it. **What would settle it**: R51
selecting every element whose `data-part` begins `harness/`, with a floor on how many it found — a
reading that cannot go vacuous the day someone renames one. Owner: **the next wave that opens
`chrome.py`**, or a steward instrument; it touches no application code.

<sub>audit, desktop-frame micro-wave · `grep -n "harness/bar" frontend/maquette/harness/chrome.py` → the one literal · `grep -c "data-part=\"harness/" frontend/maquette/design/index.html` → 3 after this wave (the switch and its label), 1 before</sub>

**B-389 — the harness host dies with the wrapped invocation that started it, and the mutation tool reads the wreck as a verdict.**
`frontend/maquette/harness/run.sh` starts the host it needs as
`(python3 "$HERE/server.py" --serve 8899 "$SERVED" >/dev/null 2>&1 &)` — forked inside the
invocation's own process group. `scripts/heavy.sh` runs its command under `set -m`, which puts that
command in a process group of its own precisely so the watchdog can signal the whole tree
(`kill -TERM -"$child"`), and the host is in that tree. So a host started inside a WRAPPED run does
not outlive the run. Every invocation this project's method mandates is wrapped.

It is harmless for `run.sh`, which starts a host whenever nothing is listening, and that is why it
went unseen. It is harmful for `scripts/mutate.sh`, which rebuilds and republishes the served copy
and starts NO host: run after a wrapped suite, its rule meets `net::ERR_CONNECTION_REFUSED` — and
B-273's first half then reports the crash in the words of a verdict, « NO RULE FELL. That is the
finding. » The two defects are only dangerous together, which is why this one is filed apart: fixing
either breaks the chain.

Measured 2026-09-07 while mutation-testing R140. The host was pid 41947, listening throughout the
wrapped run that started it and absent the moment it ended; the mutation that followed reported
« no hold fell » over a Playwright traceback and exit 1. The same mutation, re-run against a host
started with `nohup` OUTSIDE the wrapper, fell correctly on one hold and named the box it found.

**Re-measured on `run.sh` ITSELF, later the same day, and the first version of this entry needed
it.** What the paragraph above measured was a host forked inside a script of the agent's own —
the same shape and the same wrapper, but not this file. By then a `nohup` host was already
listening, so every `run.sh` invocation took its `lsof` branch and forked nothing at all: the
sentence naming `run.sh` was an inference from a mechanism, written as though it were a reading.
L21's agent noticed the gap from the other side — it measured the NOHUP host surviving a wrapped
`run.sh --contracts` (pid 52469, ppid 1) and asked which sentence was true.

Both are. The reading that settles it: the nohup host was killed and the port confirmed empty,
then `sh scripts/heavy.sh desktop-frame frontend/maquette/harness/run.sh --contracts` was run — so
`run.sh` had to fork its own host, and it did, the tier passing 18 rules and 27 guards with no
violation. **The moment the wrapped invocation ended, nothing was listening on 8899.** A host
forked INSIDE the signalled group dies with it; one started outside that group does not; and
`mutate.sh` starts neither, which is how it comes to run a rule against a refused port.

**The office's sentence needs a clause.** `frontend/maquette/design/…` aside, the brief and the
harness's own comment say « the host on 8899 is `run.sh`'s and is left running ». That is true only
of an UNWRAPPED invocation. Owner: **the next wave that touches `heavy.sh` or `run.sh`** — the
cheapest shape is for the host to be started outside the signalled group, or for `mutate.sh` to
start one the way `run.sh` does.

<sub>audit, desktop-frame micro-wave · `grep -n 'server.py --serve' frontend/maquette/harness/run.sh` · `grep -n 'set -m' -A3 scripts/heavy.sh` and the `kill -TERM -"$child"` beneath it · after a wrapped run: `lsof -nP -iTCP:8899 -sTCP:LISTEN` empty</sub>

**B-391 — the frame's « only accepted divergence » is one declaration inside a block of five.**
`frontend/maquette/design/src/styles/harness.css`, the DECLARED HARNESS DEVIATION: it repositions
the tab bar, the action button and the selection bar to `absolute` within the frame, and sets the
bar's `inset-inline: 0; bottom: 0`. Its comment says « This is the ONLY accepted divergence in the
shell », and the parity probe carries it as a justified allowlist entry.

Four of those five declarations diverge from nothing. Read in the app's own variants rather than
guessed: `ui/variants/frame.ts:60` draws the tab bar as `bottombar fixed inset-x-0 bottom-0`, so the
frame's `inset-inline: 0` and `bottom: 0` restate what the app already says; `:111` draws the action
button as `fab absolute …` and `:124` the selection bar as `selbar absolute …`, so `position:
absolute` on those two changes nothing at all. **The real deviation is one property on one element**
— the tab bar's `position`, `fixed` in the app and `absolute` in the frame — and that one is
genuine, measured `fixed` against `absolute` at 1280 px.

**How it was found, and why it is filed rather than fixed here.** R140 compares every property the
frame re-asserts against a document with no frame, and holds that each must read DIFFERENTLY — a
property the frame does not move cannot show the frame leaving. With the list grown from three
properties to ten, that hold fell on the four that cannot move. The tempting repair is to relax the
hold; the honest one is to name them, which is what the rule does now (`REDUNDANT`, each with the
variant line it was read from), so a NEW dead comparison and a listed one coming alive both fall it.
Deleting the four declarations is the real repair and it is not this wave's: they are the frame's
behaviour at 390 px, which this micro-wave's brief forbids it to touch.

Owner: **the next wave that opens the deviation block**, or the parity probe's owner — the allowlist
entry describes a block whose justification covers one fifth of it.

<sub>audit, desktop-frame micro-wave · `sed -n '30,52p' frontend/maquette/design/src/styles/harness.css` · `grep -n "bottombar fixed\|fab absolute\|selbar absolute" frontend/maquette/design/src/ui/variants/frame.ts` → the three lines that make four of the five redundant</sub>

**B-390 — the guard that was cited as confirming a ruling reads no text in the file the ruling is about.**
The wave put its two French labels in `design/index.html` rather than in `fr.json`, on the steward's
ruling that the file is static markup served raw and no markup i18n exists anywhere — that part
stands and was re-checked. What does not stand is the sentence written to support it, in
`RESUME.md` and in the pull request: « `check-no-french` does not refuse them, which is the tree
confirming the ruling ».

`scripts/nofrench_lexicon.py` roots the Strings and Identifiers arms on `SHELL = MAQUETTE /
"design" / "src"`, and `index.html` sits at `design/`, one level above it. The only arm that opens
that file at all is the `data-*` arm in `scripts/nofrench_values.py`, which reads ATTRIBUTES and
never text nodes. So the guard is silent about those two strings because **no arm reads text in
that file**, not because an arm read them and allowed them. Fifteen arms, exit 0, and the file's
visible French was never in front of any of them.

This is B-085's species aimed at a ruling rather than at a behaviour: a green gate cited as
positive evidence, where the green means « not looked at ». The ruling may well be right — it was
argued from the tree, not from the guard — but the sentence supporting it has been struck from both
documents rather than left to be read as proof in two years.

**What would settle it**: an arm that reads text nodes in the maquette's own `index.html`, or an
explicit statement in the guard's own output that the file is outside every text arm. Owner: **the
next wave that touches `check-no-french.py`**. Found by round one's independent reader, outside its
lens, and confirmed on the tree before it was written down.

<sub>audit, desktop-frame micro-wave, reader A round one · `grep -n "SHELL = " scripts/nofrench_lexicon.py` → rooted on `design/src` · `python3 scripts/check-no-french.py` → exit 0, « 15 arms … no violation » over two French labels in `design/index.html`</sub>

**B-307 — three rules have fallen under the recorder's parallel load, and the register holds one.**
`exits.py` is B-277, diagnosed as a frame sampler counting against an animation measured in
milliseconds. Since then `outbox.py` fell during L14's close and `drag.py` fell during the steward's
post-merge re-record; both passed alone, and neither fall is written anywhere in the tree —
`outbox.py`'s only account left with the wave's report. The mechanisms are probably not one:
`drag.py` is a gesture rule and plausibly B-277's, while `outbox.py` is a queue rule where a timeout
under contention is likelier. B-277's own body warns that « the habit it teaches is to re-run until
green, and that habit is how a real fall elsewhere gets dismissed as this one » — which is what
happened twice. Owner: whoever next reads a fall under load. What would settle it: each rule alone,
expected green, then three runs at `TM_HARNESS_JOBS=8` on an idle machine, reading whether the fall
is a frame count or a timeout.

**A FOURTH, read on 2026-09-06 during #567's round-four gate, and recorded here because this entry's
own rule is « whoever next reads a fall under load ».** `touch.py` FAILED inside
`harness-hold-counts.py --compare` at `TM_HARNESS_JOBS=2` — « harness: 1 of 92 rule(s) FAILED —
touch.py (exit 1) » — with its hold count **unchanged at 25** and « 0 rule(s) changed hold count »
in the same run, so nothing about the count moved. Run ALONE immediately afterwards on the same
head and the same served copy: **25 rules EXECUTED — no violation, exit 0**.

**Said in the same breath as the verdict, as B-277 requires**: running it alone removed the load the
failure needed, so that green is not proof the rule is sound — it is only proof the fall did not
survive isolation. The branch touches neither `touch.py` nor anything it reads.

**And the SUITE was re-run whole, at the same fan-out, before the wave called anything green: 92
rules, no violation, « 0 rule(s) changed hold count ».** So the fall reproduced neither alone nor
under the load it appeared in — which is a stronger reading than the isolated re-run, because it
did not remove the condition. Two readings, one of each kind, and neither shows a defect in the
rule; what they show is an instrument that fails intermittently and says nothing about why.

**It is a fourth rule and it does NOT print what its diagnosis needs.** The repair B-307 asks for —
each of the three printing, when it falls, the evidence that separates a frame count from a timeout
— was never made, so this fall carries no reading at all beyond « exit 1 ». That is the whole cost
of the debt, arriving on a fourth instrument: three waves have now met this shape and none can say
which mechanism it was.

<sub>`grep -n 'exits.py' BUGS.md` names B-277 · `rg -n -g '*.md' 'outbox\.py|drag\.py' BUGS.md` → no fall recorded · #567's round-four gate: « harness: 1 of 92 rule(s) FAILED — touch.py (exit 1) » then `python3 frontend/maquette/harness/touch.py` alone → « 25 rules EXECUTED — no violation »</sub>

**READ on 2026-09-04 by the steward, at `cb2128220`, and the protocol above is replaced.** It asked for
three runs at `TM_HARNESS_JOBS=8` « on an idle machine », which the office forbids for arithmetic (eight
browsers ≈ 8.8 GB against ~6 GB free; the watchdog stops the run under 2 GB) — a protocol the office
cannot run is a sentence. What was run instead, every reading under `scripts/heavy.sh`, the host on 8899
up: each rule ALONE — `exits.py` 15 holds in 7 s, `outbox.py` 21 in 2 s, `drag.py` 22 in 16 s, all green;
then each rule THREE times beside `virtual.py` and `persistence.py` running concurrently (fan-out 3, the
most this machine's free memory allows): **nine passes, zero falls**, and the durations did not move —
10/10/10 s, 6/5/5 s, 19/18/19 s. So the contention at three is not the contention the suite produces at
eight, and the fall's MECHANISM stays unread. **What settles it is not a bigger run but a rule that says
why it fell**: each of the three prints, when it falls, the evidence its diagnosis needs — `exits.py` the
frames it sampled against the milliseconds the exit was drawn with, `outbox.py` and `drag.py` the wait
that elapsed against the timeout it was given — so the NEXT natural fall under the suite carries its
own reading, and « re-run until green » stops being the only habit available. Named in the plan's § 5
debts block for the next wave that touches those rules.

<sub>`TM_HARNESS_JOBS=3 sh scripts/heavy.sh <who> sh passes.sh` — each target rule three times with `virtual.py` and `persistence.py` started 3 s before it; the nine logs read `N rules EXECUTED — no violation` and exit 0</sub>

**A FIFTH INSTRUMENT, 2026-09-12 at `88b5e2f84`, by the tooling micro-wave — and this one PRINTS what
its diagnosis needs.** `virtual.py` fell in the full suite and the fall carries its own reading:

    FAIL a reader three hundred pixels down keeps their row through the mode and back
         — the first row is a place like any other
         — top row "On l'appelait Robin des Bois" at 300px, "On l'appelait Robin des Bois"
           at 0px after — the port moved 300px, and a row measures 134px

So the ROW is the same on both sides and the PORT is not: the reader was put back at the container's
start instead of 300 pixels down, which is the exact distinction the hold's own comment says a title
comparison cannot make. The hold waits 500 ms after the scroll, 600 ms after entering selection mode
and 700 ms after leaving it; under the suite's load those three waits are what gives way, and the
restoration lands before the port has been written. **The load, from the wrapper's own line**:
`heavy: tooling-hygiene starts (4547MB free, load 5.73)`, `TM_HARNESS_JOBS=2`, 119 rules, two at a
time, beside two other waves on the machine.

**Replayed ALONE immediately afterwards, same head, same served copy: `36 rules EXECUTED — no
violation`, exit 0.** Said in the same breath, as B-277 requires: running it alone removed the load
the failure needed, so that green says nothing about the rule's soundness — only that the fall did
not survive isolation. **And the suite was NOT re-run whole**, by the steward's ruling of the same
day: a re-run that comes back green has removed the condition and proves nothing about the fall,
while costing twenty minutes of a mutex two waves were queued on. The record is what is kept instead.

The wave that met it touches no surface — `git diff --stat origin/main -- frontend/maquette/design/src
| wc -l` → 0 — and that is recorded as a fact rather than offered as an alibi: what this entry needs
is the reading, and for the first time in five instances it has one.

**A SIXTH, 2026-09-12 during #588's gate — and unlike the fifth it carries NO reading.**
`journey.py` (R82) FAILED once inside `harness-hold-counts.py --compare --jobs 2` on `9ecce44d4` —
« harness: 1 of 122 rule(s) FAILED — journey.py (exit 1) » — under `heavy: settings starts (5522MB
free, load 3.94)`, `TM_HARNESS_JOBS=2`; the same head read it green in the full suite (« 122 rule(s)
and 27 repository guard(s), no violation ») and in a replay (70 holds). The ONE re-run the steward
allowed was driven through a scratch wrapper that imports the tool unchanged and keeps, for any rule
that falls, its whole output, its duration and the load and free memory around it — on `a1c1fd553`,
the same compare at the same fan-out, load 5.27 at start: **122 rules, no violation, nothing fell,
nothing captured.** Said with the verdict, as B-277 requires: not reproduced alone nor under the
compare's load, which is no proof the rule is sound; the mechanism is not read. **The cheapest repair
is in the TOOL, not the rules**: `harness-hold-counts.py` runs each rule with `capture_output` and
keeps only the parsed count, so a rule that falls under it arrives with « exit 1 » and nothing else —
the wrapper that kept the output is the repair's shape. Filed, not built: the apparatus is frozen.

**B-293 — 38 `Design:` markers point at paths that left the tree, and nothing says so.**
`grep -rhoE 'Design: docs/[^#[:space:]]+' --include='*.py' tests | sort | uniq -c` shows 16 for
« docs/features/api-unify/DESIGN.md », 13 for `torrent-fetch`, 5 for `watch-seed`, 2 for
`scraper`, 1 each for `webui-ux/plan/phase-04-scraping.md` and `test-coverage` — features archived
long ago. `update_feature_map.py --check` and `audit_design_coverage.py --strict` are green over
them: a marker whose path resolves to no map file is not an error to either. A guard green over
what it does not read (B-085 species). Left as found by #539, which moved the 78 live markers;
the fix is the design-gaps pair refusing a marker whose path `git ls-files` does not hold.

<sub>`grep -rhoE 'Design: docs/features/[^#[:space:]]+' --include='*.py' tests | sort | uniq -c`</sub>

**B-291 — the hold-count recorder produces a reference indistinguishable from a good one, two
ways.** (1) `taken_at_commit` is provenance nothing reads. L12's post-merge gesture recorded the
baseline on `chore/maquette-l12-post-merge` and squash-merged it as `b4b75a67a`, so the file on
`main` named `a4cfc3b18` — a commit no clone holds. The plan's § 5 names this exact species for the
oracle (« squashing replaces that commit, so on a fresh clone the pointer names nothing »), and the
wave that had just applied that paragraph to the oracle reproduced it one file over, in the same
hour: a paragraph is not an arm. The wave found it itself, an hour after the merge, while answering
the steward. (2) `--record` writes a baseline even when a rule EXITED 1: it sets `"failed": 1` in
the totals, a `"reason"` on the rule, records the count the rule printed while falling, and exits
zero. L12's gesture needed four attempts because R113 and R118 fell under eight parallel rules,
and the recorder wrote all three bad baselines without a word. Both are one defect — an instrument
that produces a reference no reader can distinguish from a good one — and one owner: the
instruments' debts block of the plan's § 5, so the next wave that touches
`scripts/harness-hold-counts.py` takes it. The form: refuse a pointer that is not an ancestor of
`main`, as `oracle.py --check` refuses a dangling one, and refuse to write when `failed > 0`. The
steward's audit re-recorded the baseline at `b4b75a67a` — 0 movement on 86 rules, 1 928 holds,
`failed 0` — and the gesture paragraph now names both pointers and the hand check. **The same
question reaches the cited-paths guard, twice** (docs-cleanup, 2026-09-01): its arm 1 resolves
`path@sha` citations, so (a) a sha that is not an ancestor of `main` — a branch head the squash
erased — reads like a live one until `git show` is asked, and (b) the guard must run where the
checkout holds the history: a fourth hold of `tests/scripts/test_ci_filter_covers_the_guards.py`
— « a guard that resolves shas is launched only by a job whose checkout has `fetch-depth: 0` »
— falls the day somebody moves it out of `harness-contracts`. Both belong to whoever next
touches the guard; the guard already names a truncated checkout rather than accusing the
citation.

<sub>`git merge-base --is-ancestor a4cfc3b18 origin/main; echo $?` → 1 before the audit; `python3 -c "import json;d=json.load(open('frontend/maquette/hold-counts-baseline.json'));print(d['taken_at_commit'][:9],d['totals'])"` → `b4b75a67a {'rules': 86, 'parseable': 74, 'unparseable': 12, 'holds': 1928, 'failed': 0}` after</sub>

**B-288 — the media screen's priming matches a title by prefix.**
`useMediaSheet` primes from `reference.sheetFor(title)`; the engine's lookup falls back to a
normalised key and then to a PREFIX match (`key.startsWith(clef2 + " ") && clef2.length > 6`). So a
medium whose title is a prefix of another's — **and longer than six characters** — opens with the
other medium's poster and year for as long as the read is in flight, then corrects itself when the
answer lands.

**The « Lucky » family is NOT an instance, and naming it was an error found by an adversarial
reader.** `clef2` is the QUERIED title normalised: « Lucky » is five characters, so the guard
refuses it, `baseTitle` strips « (2026) » to the same five, and `SHEETS_IDX` holds no `Lucky*` key
but « Lucky Luke » — the four Lucky titles live only in `POSTERS`. `sheetFor("Lucky")` answers
`null` and the screen shows its skeleton, which is correct. The mechanism stands on its own reading
of the code; **no instance of it is claimed on this fixture**, and the entry says so rather than
carrying an example that cannot reach the branch it accuses.

**Not a defect of the priming**, which is why it is filed against the lookup rather than the screen:
an absent title answers `null` and the screen shows its skeleton, which is correct. What is wrong is
a resolver that answers « close enough » to a question about identity. The placeholder is never
written into the cache — verified — so nothing durable is corrupted; what the reader sees for a few
hundred milliseconds is another film.

<sub>`grep -n "startsWith" frontend/maquette/design/src/engine/legacy.js` around `normalisedKey`;
prime `/media` for a title that prefixes another and read the hero before the answer lands</sub>

**B-277 — `exits.py`'s frame-count control flakes under the suite's parallel load.**
« The scrim's exit really animates, so the hold below has something to measure » fell in two full-suite
runs out of three and passed **alone, twice, reliably** — reading `0 frame(s)` where it wants more
than three. The suite runs eight rules at a time; `requestAnimationFrame` is what the sampler counts
by, and under that contention 24 frames span a window the exit no longer sits inside.

**It is worth an entry precisely because it is a CONTROL.** Its whole job is to refuse a vacuous
reading of the hold beneath it — « something to measure ». A control that itself flakes trains a
reader to re-run until green, which is how a real fall gets dismissed as noise; and the harness's own
« re-run it alone » rule, applied to a control, means the first thing the re-run removes is the
condition the failure needed.

**Not attributed to L12's changes**, and that was checked rather than assumed: the suite ran green
several times AFTER the scrim's duration was redrawn, and the two falls came later with only a CSS
deletion and prose between. The likely shape is a sampler counted in FRAMES against an animation
measured in MILLISECONDS — B-276's neighbour rather than its instance.

**ITS BOUND — WHEN IT MAY BE READ AS TRUE, AND WHEN AS FALSE.** A control that flakes can lie in
both directions, so its reading is only worth what its conditions are. Written out because the next
reader will meet it as a red line in a suite and has to know which way it can be wrong.

- **A FALL is not evidence of a defect** *by itself*, and specifically not when the suite ran it
  alongside seven others: 24 frames of `requestAnimationFrame` under that contention span a window
  the exit no longer sits inside, and `0 frame(s)` is what that reads as. **Re-run it ALONE. A fall
  that survives running alone is real** — that is the only reading of a fall that stands.
- **A PASS is worth its full weight**, in the suite or alone. Nothing about frame starvation invents
  frames: if more than three frames were seen mid-exit, the exit animated. This control cannot pass
  falsely; it can only fail falsely, which is why the remedy is a re-run and not a tolerance.
- **AND THE RE-RUN IS ITSELF A HAZARD**, which is the reason this entry exists at all. « Run it
  alone » applied to a control REMOVES the load the failure needed, so the habit it teaches is to
  re-run until green — and that habit is how a real fall elsewhere gets dismissed as this one. Anyone
  re-running it alone should say so in the same breath as the verdict, as this wave's close does.

**Left open**: the fix is to sample against the clock, or to make the frame budget follow the
duration it watches, and that is the harness's tooling rather than this lot's.

**TWO MORE OF THIS SPECIES, both in L12's own repairs, both closed and named (2026-09-01).** Neither
is left open: each is repaired, and each is written here because the SHAPE recurs and the next
reader needs to know which way each instrument can still be wrong.

- **R113's arming sample.** It read a FIXED step of a fixed cadence, and a settle read added 60 ms of
  dead time in front of it: under parallel load the step drifted past the press delay, the mark had
  already gone, and the rule fell announcing « the mark is placed on `pointerdown` after all » — a
  FALSE DIAGNOSIS of the defect it names, in the repair for a flake of this very species. Repaired
  by sampling every step and choosing both readings by the moment each one landed, **stamped in the
  PAGE**: a stamp taken in Python before the call is the moment the round trip BEGAN, so every
  reading executes later than the moment recorded against it, by one CDP hop. Both boundaries carry
  a 20 ms margin now, where the settle had none and the arming window had 40.

  **AND THE CADENCE STOPPED BEING A BET.** The first repair sampled a fixed number of times at a
  fixed interval, which is a wager on how fast the machine is — and it lost twice, both times in a
  post-merge recording run that launches eight rules at once: at a flat 50 ms cadence no reading
  landed inside the 120 ms settle, and a denser opening then put none inside the arming window
  instead. Neither was a defect in the page, and the first of them was reported as « the mark is
  placed on `pointerdown` after all », which is a different finding entirely. It samples every
  16 ms until the gesture's OWN clock passes the press delay, so both windows are covered at
  whatever speed the machine runs; and each window's precondition is its own hold, so an empty one
  says so rather than accusing the code. **Which way it can still be wrong**: a reading whose page
  moment falls within 20 ms of a boundary is discarded, so a settle moved to within a frame of the
  sampling interval would leave nothing to classify — which the two precondition holds report as
  themselves.
- **R118's mid-flight capture.** A screenshot is not instantaneous and can outlast the 450 ms
  crossing on a loaded runner, so the flight flag read true before the capture and false after.
  Repaired by retrying rather than by dropping the second read — a sample taken after the end is
  exactly the vacuity that hold exists to refuse. **Three retries was not enough**: the post-merge
  recording run, which launches eight rules at a time, straddled all three. Two things changed
  together — the read moved from 200 ms into the crossing to 120, which leaves 330 ms for the
  capture instead of 250, and the retries went to six. **Which way it can still be wrong**: six
  straddles in a row on a very slow runner report a violation where the page is correct, which is
  loud and in the safe direction.

<sub>`frontend/maquette/harness/run.sh` (2 falls in 3) against `python3 frontend/maquette/harness/exits.py` (green, twice)</sub>

**B-276 — a hand-set delay in an INSTRUMENT outlives the duration it was set against.**
Named as a species because it happened twice in one rule, in one wave, and neither instance was
wrong when it was written.

`harness/touch.py` waited **420 ms** between press surfaces and **340 ms** after closing the sheet.
Both were calibrated against a layer that took 200–300 ms. L12 drew the panel's rise on
`--duration-4`, so the close became 450 ms and the scrim's `visibility` carries that as a DELAY —
and the rule then pressed a poster the scrim was still covering, and pressed the next surface while
the previous sheet was still closing. Two of five surfaces failed; both passed in isolation, which
is what makes this expensive to diagnose.

**This is B-269's shape moved from a guard into an instrument.** B-269 is five corpus floors
« calibrated by hand, one figure per corpus »; these are two delays calibrated by hand against a
duration somebody else later redraws. The failure mode is identical — right on the day it was typed,
wrong the day the thing it describes legitimately changes, and indistinguishable in a log from a
real defect.

**Not fixed as a species here**, and the distinction matters: both instances are repaired, with the
reason written beside each, but nothing stops the third. The shape a fix would take is a delay
DERIVED from the value it waits on rather than typed beside it — the harness would have to read the
drawn durations, which is a piece of tooling and not this lot's.

<sub>`frontend/maquette/harness/touch.py` — `wait_for_timeout(700)` twice, each with the duration it now follows</sub>

**B-273 — `scripts/mutate.sh` cannot judge a guard, and is silent when a mutation breaks the build.**

**The second half, found 2026-09-01 and it is the sharper one.** The script reports « no hold
fell » for a GUARD under mutation *whatever the guard says*: it decides by reading journal `FAIL`
lines, and a guard in `scripts/` prints violations and exits 1 without ever printing one. Three
mutations aimed at `check-markup-contracts.py` were reported as caught by nothing while the guard
was in fact naming the defect and exiting 1 — and the first two of those were believed, and led to
the arm being rewritten twice on a false reading. **A verdict that is the same whatever happened is
not a verdict**, which is this register's own subject applied to the tool the register's proofs are
made with. Until it reads exit codes as well as journals, a guard's mutation is run by hand.
It mutates, runs `npm run build`, then `served_copy.py --publish`. When the mutation
breaks the build — renaming an exported symbol its importers still name, which is an
ORDINARY mutation to want — the publish fails, `set -e` exits the script, and the trap
restores the file. **No rule runs, and nothing is printed about why.** The output is the
mutation line and the restore line, with neither a rule's verdict nor the « NO RULE FELL »
the script prints when a rule genuinely does not catch something.

It is not actively misleading — the absent verdict is not a false one — but it is one
glance away from being read as « the tool ran and found nothing », and this repository has
a register entry for exactly that reading (« a failed command is not a no-op »). Met while
mutating the feedback seam: the branch had to be exercised by hand instead, running the
guard directly, which needs no build because it reads source.

**Not fixed here**: the fix is `mutate.sh`'s, one visit for whoever next touches it, and it
is small — report the build's failure and say that the mutation was invalid rather than
that nothing happened.

**A third case, met 2026-09-07, and it is the first half's sharpest form.** The verdict is blind to a
RULE that crashed before it reached the page. `python3 "$RULE" >"$OUTPUT" 2>&1 || true` discards the
exit status, and the grep that follows looks for `^  FAIL|violation\(s\)` — which a Playwright
traceback matches no more than a guard's violations do. Mutating `harness.css` against R140 with the
8899 host down (B-389) printed « (no hold fell — the rule does not catch this mutation) » and « NO
RULE FELL. That is the finding. » over `net::ERR_CONNECTION_REFUSED` and exit 1. « The rule does not
catch this mutation » is a finding; « the rule did not run » is a broken machine; the tool says the
same words for both. **The proof shape for whoever repairs it**: point a mutation at a rule with
nothing serving 8899, and the tool must say the run FAILED rather than that nothing was caught —
four lines, reading `$?` beside the journal.

**A fourth instance, 2026-09-07, and it is the one that defeats the obvious repair.** The third
case is a rule that printed NOTHING before dying, and « no output at all » is at least a visible
oddity. This one printed **two `FAIL` lines and then died**: a mutation hid a control at every
desktop width, `page.click` on it timed out, and the rule was killed partway — after two holds had
already reported. `mutate.sh` matched those two lines, printed them, and reported the run as a
mutation the rule catches. **Two failures from a crashed rule are indistinguishable from two
failures from a rule that finished**, and the second is a finding while the first is a broken
measurement. So reading `$?` is necessary and not sufficient on its own to make the OUTPUT
trustworthy: what tells the two apart is the JOURNAL's own closing line — `common.Journal.summary`
prints « N rules EXECUTED … », and a rule that died before it prints no such line. A tool that reads
the exit status AND requires that line before believing any verdict cannot be fooled by either
shape. Caught only because the agent had, an hour earlier, given that exact check to another session
and then had to apply it to itself.

<sub>`scripts/mutate.sh frontend/maquette/design/src/lib/feedback.ts 't.replace("export function feedback(", "export function acknowledge(")' scripts/check-feedback-seam.py`</sub>

**A THIRD READING, AND IT IS NOT A GUARD**: the verdict-grep is coupled to ONE rule's output
format. `mutate.sh` looks for `^  FAIL` or `violation(s)`; `audit.py` — a rule, not a guard, and one
of the largest in the suite — prints `■ R1 hollow sheet behind a poster — 2` and
`TOTAL: 2 violations · 13/13 rules executed`. « violations » is plural and carries no parentheses,
and there is no `FAIL` line at all. So the tool printed « no hold fell — the rule does not catch
this mutation » over a rule that had reported its two violations exactly as before. The limitation
is wider than « a guard »: it is every rule whose summary is not `common.Journal`'s.

**AND THE SILENT-BUILD HALF WAS MET AGAIN, from the direction that makes it dangerous.** A
mutation expression using `str.replace` matched a SECOND occurrence nobody intended — two
neighbouring ternaries ended in the same three tokens — and produced invalid TypeScript. The build
failed, `npm run build >/dev/null 2>&1` swallowed the reason, and the run printed the mutation line,
NO rule banner at all, and the restore, exiting 1. What separated it from a real reading was the
absence of the `── <rule> ──` banners: **a mutation that produces no verdict line is not a mutation
that found nothing.** Read the banners and the `EXECUTED` count before the FAIL lines — a crashed
rule and an unmoved rule are indistinguishable in this tool's own summary.

**A fourth, adjacent, and it belongs here because it is the same species from the other end**:
`check-mock-seeds`'s correspondence arm refuses a `media-sheets.json` edited by hand and names
`python3 scripts/build-mock-seeds.py --write` as the remedy — a command that re-derives the seed
from `legacy.js` and therefore DELETES the edit it is offered for. The message is correct about the
mechanism and misleading about the intent: the seed is derived, so a hand edit is always wrong, and
what the reader needs told is that the fixture lives in the engine, not that a rebuild will fix
their change.

<sub>`scripts/mutate.sh … frontend/maquette/harness/audit.py` → « no hold fell » over `TOTAL: 2 violations · 13/13 rules executed` · a `str.replace` matching two ternaries → build failed, no banner printed, exit 1</sub>

**B-270 — two harness journals are labelled « R80 », and `attrs.py`'s has no number of its own.**
`harness/residue.py` is R80 (a typed variant and the residue rule shadowing it agree; the README's rule
table says so). `harness/attrs.py` — how React renders a boolean into an attribute — opens no rule
number and labels its journal `Journal("R80 — how React renders a boolean into an attribute")`. Any
reader that keys on the label merges two rules; the hold-count baseline keys on the FILE, which is
why no count is wrong today, and why nothing said so. Found while re-deriving the L12 brief's rule
citations. One line to fix, with the next free number — the harness's, in the same visit as B-268 and
B-269.

<sub>`grep -n "R80" frontend/maquette/harness/attrs.py frontend/maquette/harness/residue.py`</sub>

**B-269 — five corpus floors in `served_copy.py` are calibrated by hand, one figure per corpus.**
`served_copy.py:619` floors five filtered corpora, each floor « set near its own corpus » — which is
five hand-written figures, B-254's species inside an instrument: right on the day they were typed,
wrong the day a refactor legitimately shrinks a corpus, and indistinguishable in a log from a floor
that still bites. The wave's own author said they would not defend them hard. Two honest exits: DERIVE
each floor (a fraction of the corpus measured at record time, stored beside the hold counts so the
squash re-record refreshes it), or keep the calibration and write next to each figure the command
that re-measures it. Owner: the next wave that touches the harness — with B-268, they are one visit.

<sub>`grep -n "for name, corpus, floor in" frontend/maquette/harness/served_copy.py`</sub>

**B-268 — R104 lives in the file it measures, and has been defeated twice by exactly that.**
R104 holds `served_copy.py`'s publish-then-stamp ordering and is DEFINED in `served_copy.py`. It has
been beaten twice by self-reference: three substrings satisfied on the rule's own assignment lines,
then both search anchors found in the rule's own source (`1419 < 9068`, where 9068 was the searching
line). The current answer, `_function_body`, is one file-reorder from the same class: if `publish()`
ever moves below the rules, `find()` meets the rule's literals first. **The shape is the defect**: a
rule inside the file it measures inherits every future edit of that file as a potential self-match,
and the repository's own doctrine — an instrument written by whoever it measures inherits their
blind spots — applies here at the level of the FILE. Recommendation: the ordering holds move to a
reader OUTSIDE the file (a `tests/scripts/` test reading `served_copy.py` as text through its AST,
where the searching source and the searched source cannot be the same object). Owner: the next wave
that touches the harness; the operator may place it sooner.

<sub>`grep -n "_function_body" frontend/maquette/harness/served_copy.py` · `grep -c "def publish(" frontend/maquette/harness/served_copy.py`</sub>

**B-267 — the real backend's failure shape does not match the one the queue reads, and at switchover every refusal becomes a queued mutation.**
Found by the fourth adversarial round, and it is LATENT rather than live: the mock layer emits the
right shape, so nothing in the maquette is wrong today. `isRequestFailure` requires
`{status, title, detail}`. `personalscraper/web/deps.py` raises `HTTPException(403, detail="…")`
and FastAPI serialises `{"detail": "…"}` — no `status`, no `title`, and there is no
`exception_handler` reshaping it. On the day `send()` points at that server, **every** refusal —
403 read-only, 401, a 400 for a missing `X-Requested-With`, a 409 — fails the shape test, takes the
OUTAGE branch, and is queued: the optimistic write stands over an action the server refused, and
the replay meets the same answer forever. NE-DOIT-PAS-1 from both ends at once.

**It belongs to the lot that binds the maquette to the backend**, and it is written here so that
lot finds it rather than discovering it in production. The fix is one of two: a FastAPI exception
handler that emits the problem shape the interface already reads, or a reader on this side that
accepts `{detail}` — and the first is the one §15 asks for, since the interface declares what it
requires and the backend follows.

<sub>`grep -rn "HTTPException(" personalscraper/web/deps.py | head -3` · `grep -n "isRequestFailure" frontend/maquette/design/src/lib/query-client.ts`</sub>

**B-255 — `check-frontend-boundaries.py` is back at 952 lines, 48 from the hard ceiling it was cut away from.**
B-050 (#500) found it at 921 and L07-bis split three guards on a subject rather than a line count.
`python3 scripts/check-module-size.py --root scripts` on `main` at `99a82a35` warns at **952** — it grew
through L08 to L15 by an arm at a time, the shape B-050 named. The next arm added to it crosses 1 000
and `make check` refuses the pull request that adds it, for a reason foreign to that pull request.
Open, and the split is a wave's: the next lot that touches the file cuts it on a subject first —
the ADDRESSING arm is a whole one on its own (the executing agent's own reading, 2026-08-30, owning
its share: L15 added twice to a file already at the soft warning, and « the change is small » is how
a file reaches a ceiling nobody decided to approach). On a subject, not on a line count, or it is
back at 900 in two waves with the arms interleaved differently.

<sub>`python3 scripts/check-module-size.py --root scripts`</sub>

**B-253 — B-247 was reassigned to L14 and L19 by the wave that left it, and the plan named it in neither.**
L15's report said B-247 (a store bump replaces a feature page's nodes, so a write between
`pointerdown` and `click` destroys the tap) « is L14's and L19's ». `grep -n "B-247"
docs/reference/frontend-architecture.md` returned nothing: a debt with no named owner, which the plan's
own L14 entry calls « a debt nobody pays, and it reappears in the last lot ». Both entries name their
half now, and L19 names B-249's producer half (the 260 ms wait R103 prints) in the same move.

<sub>`grep -c "B-247" docs/reference/frontend-architecture.md` → 2 · `grep -c "B-249" docs/reference/frontend-architecture.md` → 2</sub>

**B-247 — a store bump replaces a feature page's nodes, and a write between press and click destroys the click.**
Found on 2026-08-30 during L15's phase 3, by a rule that fell for a reason that had nothing to do
with what it was written for: `page_host.py`'s « a real tap on a command row opens THAT command's
panel » went red while a programmatic `.click()` on the same node opened it perfectly.

**What is really happening.** A store write re-renders every page, and `features/maintenance/page.tsx`
does not keep its DOM nodes across one — measured directly:

    const before = document.querySelector(row);
    window.__store.write({ … });          // any write at all
    // 60 ms later
    before.isSameNode(document.querySelector(row))   // false
    before.isConnected                                // false

A real finger's tap is `pointerdown`, then `pointerup`, then `click`, and the browser dispatches
`click` on a node that is still in the tree. **So any store write in that gap loses the tap
entirely** — no error, no event, the interface simply does nothing. The engine dismisses its boot
hint from a **capture-phase `pointerdown`** handler, which is exactly that gap, so the FIRST tap of
a session on a React page was already being lost while the hint was up. L15 found it because phase
3 briefly routed the message's presence through the store and made the window wider.

**This is B-231's shape one layer down.** L15's P2 holds the CHROME's node identity — the tab bar's
buttons across a page switch and a store bump — and it is scoped to the chrome by name. A PAGE's
rows have the same property and nothing reads it. `harness/persistence.py` is where the equivalent
hold goes, and it is not L15's to write: the repair is in the surfaces, and the surfaces are L14's
(their reduction) and L19's (their producers).

**What L15 did about it, and what it did NOT do.** It stopped depending on it: the message's
presence is `app/message-presence.ts`, its own subscription with its own subscribers — today
exactly one, the action button — so a message no longer re-renders every page. **The defect itself
is untouched and open**: any other store write in that gap still loses a tap.

**THE SURFACE HALF IS DISCHARGED BY L14 (#547); THE ROW STAYS OPEN FOR THE PRODUCER HALF.** Every
surface React draws keeps its nodes across a store bump and across a store write, held by
`persistence.py`'s hold (f) on the states its list names — and the mechanism turned out to be two, one of them
nobody had named: **B-295**, React 19 assigning `innerHTML` on the prop object's identity. What is
NOT repaired: the Découvrir containers the engine fills, which move with their producers (L19), and
the engine's bumping itself, which is unchanged. A re-render keeps its nodes now; the engine does
not bump less.

<sub>`page_host.py` (c-bis) · the identity measurement above, run against `features/maintenance/page.tsx`</sub>

**B-153 — the demands register cannot describe the thing L10 is about.**
`scripts/compare-contracts.py` COMPUTES `docs/reference/frontend-backend-demands.md` by diffing
paths and operations between `frontend/maquette/contract/openapi.json` (50 paths) and
`frontend/openapi.json` (61). **Neither declares the event stream**, and neither can: OpenAPI does
not describe a WebSocket.


> **ARBITRATED, 2026-08-29.** The three sections are recorded in `frontend-architecture.md` § 1 as
> **lots that are OWED and not yet declared** — deliberately without a number, an order or a
> position, so § 0's rule cannot reach them: a lot the file has not placed is not electable.
> **L10-ter places all three**, in the order §18 → §19 → §17 unless it measures a reason to differ.
> They wait for it because §17 and §19 need new screens and L10-ter is redefining what a screen in
> this application IS — placing them before the template exists is drawing them twice.
> **B-142's instrument goes to L10-ter as well**, and the reason is not scheduling: the arm needs a
> declared mapping from each DOIT clause to the surface that serves it, and a mapping is a design
> decision rather than a grep. L10-ter is already modelling what a surface is.
>
> **SUPERSEDED the same day**: placed as L16 / L17 / L18 (`frontend-architecture.md` § 4, Phase 5);
> the mapping is written and the arm is **L15's**. This block sits in B-153's entry by the accident
> of where the arbitration was pasted; the placement notes live under B-143, B-144 and B-145.

<sub>`python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(len(d['paths']),[k for k in d['paths'] if 'ws' in k or 'event' in k])"` → `50 []`</sub>

So every demand L10 raises about the stream must be filed BY HAND, and the computed register will
go on reporting nothing about it — which reads as « no demands » rather than « out of scope ».
D7 says the contract is the maquette's own artefact; the stream is part of that contract and has
no artefact. Left open: what shape a stream contract should take is an arbitration, not a fix, and
L10 does not take it — it files its demands by hand and says so.

**B-154 — the cache has no way to heal itself, and nothing says so where it matters.**
`lib/query-client.ts` sets `staleTime: Infinity`, `refetchOnWindowFocus: false`,
`refetchOnReconnect: false`, `retry: false`. Each is argued in the file, each is right, and their
SUM is a property no one of the four comments states: **a query that misses an invalidation is
stale for the life of the process.** There is no clock, no focus event and no reconnect refetch
underneath.

Production's `useWsInvalidation` is a per-surface hook and is safe there because 21 `refetchInterval`
sites poll underneath it — a missed event costs 60 seconds. Here it would cost forever. The same
shape, transposed, would be a defect that only ever shows as « the screen was out of date and I do
not know since when ».

L10 designs around it (the relay subscribes once, at boot, never with a surface — D-L10-1). The
entry stays open because the PROPERTY is still undocumented at the one place a future reader meets
it: nothing in `query-client.ts` says the four options together forbid self-healing.

**B-052 — a synthesised follow panel can label a film « Série ».**
Found during the same review that produced B-045: an entry fabricated by `knownMedium`'s now-
narrowed match can still carry the show-shaped label on a film-shaped title, when the synthesis
path is reached at all. Cosmetic on the surface, but it is the same fabrication class as B-045 —
recorded so it is not rediscovered as a new defect.

**B-053 and B-054 — two behaviours changed inside the L05 repair wave, not separately arbitrated.**
Recorded so they are revisitable rather than silently permanent: (B-053) a panel's layer entry
is now taken by a tab tap that lands on the same layer, where before the tap and the panel were
independent; (B-054) `data-go="acq"` no longer forces the acquisition page onto its « now » tab
on arrival, which some journeys relied on implicitly. Neither broke a hold — both are readings
the repair wave settled on to close its own defects, not product decisions taken with the
operator. Either may be the right call; neither has been asked.

**B-056 — a French name sits where no arm reads it.** `refonte.html` names a keyframe
`splashremplit` (used by `.splashbar i`). A keyframe name is a name someone chose — code,
under the English-names rule — and none of `check-no-french.py`'s fourteen arms reads
`@keyframes` names, so the gate is green over it. Found during L06 sub-phase 1.3, not fixed:
outside the lot's letter, which folds values onto a scale and refuses any naming change
beyond D-L06-4's publisher move. Fixing it needs both ends moved in one step (the
`@keyframes` declaration and every `animation`/`animation-name` reading it) through the
rename discipline, plus a fifteenth arm so the next one does not sit the same way.

**B-061 — the oracle measures an element, so a pseudo-element that stopped existing is invisible to it.**
The recorded oracle reads a bounding rectangle plus 19 computed properties **of the element
itself**. A `::after` that stops being painted changes neither, so the oracle stays green — and
correctly, by its own contract. L07 phase 15 produced the measured example: the media sheet's
legibility gradient was written across four concatenated string literals, Tailwind reads
candidates out of RAW TEXT, no single literal carried the whole class name, and the utility was
never generated — leaving the hero's text resting on the bare image, the one thing that rule
exists to forbid. **R26 caught it**, because R26 reads `getComputedStyle(bg, "::after")`.

**What #494 repaired is the concatenation, not the blindness.** The hold that refuses a split
class name is the sixth of `scripts/check-tailwind-confinement.py` — **not** of R26, which is the
rule that CAUGHT the defect and is unchanged. A literal ending in a space is a clean break between
class names; a literal ending in anything else continues a name into the next. Mutation-tested by
cutting `bg-muted` in half. ⚠ That hold then read six files and was blind to the three holding the
shared vocabulary, which is its own entry in this wave's story and is repaired in the same pull
request. The oracle's own blind spot
stands: **no pseudo-element is among its 2 739 measurements**, and the next one to disappear will
disappear silently unless a rule happens to read it. Not fixed, and not fixable by a call-site
change — it is a question about the oracle's contract (whether a named region may declare a
pseudo-element to measure), and it belongs with whoever owns that contract.


**Arbitrated 2026-08-25: the oracle is NOT widened.** It keeps its contract — it measures
elements — and the limit is written into D8 of `frontend-architecture.md`, where it is read
before anyone relies on the instrument. A pseudo-element carrying a function is covered by a
named rule instead, the way R26 covers this one. A surface that leans on a functional
pseudo-element with no such rule is the defect; the oracle is not.

**B-068 — the wave's prose drifted in forty small places, and the inventory is kept.**
An adversarial doc-accuracy review over #494 re-measured every figure the wave asserts. **Most
are right** — 2 739 measurements, 530 rules, 4 136 lines, 30 colours, 8 shadows, 55 rules, 936
bytes leaked, and D-L07-1's six line ranges are exact. What is not right is written up, item by
item, in `docs/archive/features/maquette-l07/drafts/documentation-drift-inventory.md@79ccebe2`, which travels with
the wave into the archive — git history since 2026-09-01. **That file is the source and this entry is the index**,
the same arrangement B-043 to B-048 use.

Three families, and they fail differently. **Counts** that no longer measure what they say (nine,
plus two pre-existing). **Comments detached from their subject** — an orphaned table comment, a
docblock about a factory sitting atop a barrel, five orphaned comments in the residue, and
`harness.css` citing two tools deleted in 2026-08-20 and **re-committed into a living source file
by this wave**. And **§ Language**: `CLAUDE.md` says maquette and harness comments carry no
reference to a session, a phase or a dated decision, and this wave added eighteen « CONVERTED
(L07 phase N) » banners plus a dozen more. The durable half of each is already written; the phase
number is what has to go, and a rename campaign over comments is its own wave's work, not a
tail-of-session sweep. **What #494 repaired instead** is every sentence that was actually FALSE
rather than merely dated — those are in its own commit, because a wrong sentence is read as
current and a phase number is only noise.

**B-034 and B-035 were found running `make check` on Linux, and they are NOT one defect.**
Both fail identically on `origin/main` with no local change — a worktree at `9632491c` reproduces
them — so neither belongs to the work that found them. They are written as two because they have
two causes, and merging them would let one hide behind the other's fix (the same reason B-013 to
B-015 are three).

They surfaced with eleven others that had a single mundane cause: **`rsync` was absent from the
container**. Installing it took the same files from `14 failed` to `173 passed, 3 failed`. That
is worth recording on its own — eleven red tests said nothing about the code, and the honest
first reading of them was wrong.

**B-034 — the two `TestQuickMode` holds.** Both die on
`[c for c in scandir_calls if c.startswith(mount)]` with `AttributeError: 'int' object has no
attribute 'startswith'`, so the recorder caught a call made with a file DESCRIPTOR rather than a
path. `_walker` cannot be the source: `_list_dir_entries` is the only `scandir` site in the whole
`scanner/` package (ACC-08) and it passes `dir_abs`. The diagnosis — **stated as a diagnosis, not
as a confirmed cause** — is that patching `personalscraper.indexer.scanner._walker.os.scandir`
patches the SHARED `os` module rather than a name private to that module, so any other caller
active inside the `with` block is recorded too. Which foreign callers run there differs by
platform and by installed dependencies, which is why the operator's machine and CI do not see it.
If that holds, the defect is in the test's reach, not in the walker.

**B-035 — `TestRestoreMergeBackup::test_continues_on_per_file_error`.** `backup.exists()` is
False: the run left no `.merge_backup` beside the destination. Not root-caused, and not guessed
at — per rule 1 of this file, it is written down before any work starts.

**Neither is dismissed as « environment ».** That reasoning was put and rejected here on
2026-08-20: *if it were true on main, CI would not have passed* — and a gate that is green by
accident of the environment is not a gate. What makes these different from that precedent is
narrower and it is measured: **CI never runs this suite on `main`** (the workflow triggers on
`pull_request` only), so « CI passed on main » is not evidence that exists. The suite's last real
execution is the run of #465.
**B-033 was seen ONCE, and is written down rather than guessed at.** `make test` reported
`tests/web/test_maintenance_panels.py::TestLocksRoute::test_locks_tmp_orphans` failed on worker
`gw7`; the same test passes alone and the very next full run was 10 742 green. Its assertion is
`len(orphans) == 3` — an EXACT count over what a background sweep reports — and the `test_config`
fixture is function-scoped with its own `tmp_path`, so a sibling test cannot be leaking into its
staging directory. The cause is therefore not the obvious one, and the obvious fix (count only
this test's own paths) would weaken a hold whose failure nobody has explained. Reported before
any work starts, per rule 1 of this file.

**B-031 and B-032 are ONE defect class, and it is the eighth and ninth instance of it.**
A `data-*` value, the handler that forwards it verbatim into a store field, and the readers that
compare that field are a THREE-ENDED contract, and nothing tied them together. `data-phase="prete"`
wrote a phase no reader knows, so the retry button on every « Impossible de charger… » surface
wrote a value nothing renders and the error screen never cleared. `data-hscen="reel"`/`"charge"`
wrote scenario names whose readers compare `real`/`loaded`, so « État réel du 10 août » landed on
the loaded branch and both dial buttons showed unpressed.

Both PRE-DATE the English rename that exposed them, both were found by an adversarial review, and
neither was visible to the 50-rule suite, to a reading of the diff, or to a sweep for French
strings — they are not French-versus-English, they are markup-versus-reader. Fixed with
`scripts/check-markup-contracts.py`, which asks the only question that catches the class: **does
anything understand what this button writes?** Mutation-proven on both.
**B-018 was written down as a regression from B-016, and that was wrong.** It has two ways in, one
of which is older than this work — the correction is recorded here rather than quietly amended,
because a register that only ever gets more accurate teaches nothing about how it goes wrong.

B-013 to B-015 arrived as **one** report about the navigation drawer. They are written as three
because a fix closes only with a rule that bites, and three symptoms with three causes need three
rules — merging them would let two hide behind the one that got fixed.

B-017 was reported by nobody. The mutation proving R65 bites found it, which is the whole reason
mutations are run against a rule rather than trusted to be green.
**B-030 was found by a RULE that could not reach it before.** R1 (« every tappable poster leads
to a filled-in sheet », `harness/audit.py`) drives named states, and every state that drew the
library drew its FIRST page — twenty-four rows, all of whose sheets are complete. The wave that
migrated the Médiathèque added a state for the load-failure surface, which drew two pages, and R1
fired immediately. Measured over the whole library: **87 of 345 titles have a sheet with no genre
(`g`) and no cast**, and none of them is in the first twenty-four — « Chouette, un jeu
d'enfants », « Andrew The Problem Prince », « Furies » and eighty-four more. It is reachable in
the app by scrolling past the first page and tapping any of their posters: the sheet opens, and
it has nothing to say. The defect is in the embedded DATA, not in the drawing, so closing it is a
scraping question rather than a rendering one — which is why it is written down rather than
fixed in a conversion wave. The state that found it was narrowed back to one page, so the suite
measures the surface it was added for; R1 remains the rule that bites the day the data is filled
in or the state widened.
**B-024 to B-029 arrived from an adversarial code review of commit `3e66fa66` (#434), not from
the operator** — same standing as B-017: found by tooling, written down before anyone walks into
them. None is reproduced on a device yet; each entry below records the walk that would.

- **B-024** — `data-go` (refonte.html ~17901) closes up to three layers but settles exactly ONE
  history entry (`__pont.remplacer` overwrites only the top). With two layer entries buried
  (screen over screen — the case the block's own comment claims to handle — or sheet over
  screen), one Back after the navigation lands on a stale `{layer}` entry and answers a
  legitimate Back with the « Encore un retour pour quitter » toast; a second Back exits the app.
  **Latent, non atteignable** — re-measured post-SP4a, walked control by control: the DOM carries
  exactly five `[data-go]` producers, no more. Four render only into
  page-body `#view` content (`viewAcquisition`, `viewArrivals`, `viewIntrouvable`, `viewSystem`)
  — and that census now spans TWO files, because Système moved to the shell: three producers
  remain in the fragment (`refonte.html` 12020, 12532, 12631) and the fourth is
  `design/src/pages/system.tsx`'s own `data-go="arr"` button, which renders into the SAME `#view`
  through the page host and is covered by a layer exactly as it was;
  `#view` sits under every layer (`.screen` z-45, `.sheet` z-47 over `.topbar` z-40), so each is
  covered — and therefore untappable — the instant any layer is open, meaning zero layers, let
  alone two, ever precede their tap. The fifth is the user sheet's « Profil et préférences »
  (`cible:{go:"profil"}`, the only dynamic producer in the whole file — confirmed by grep) — its
  only trigger is the header avatar (`data-sheet="utilisateur"`), itself in `.topbar` and so
  covered the same way whenever a screen is already open (measured: `elementFromPoint` at the
  avatar's coordinates resolves to `.screenbar` inside `#screen`, not the avatar, and a click there
  opens nothing). One layer (the sheet itself) is therefore the most that can ever precede this
  control's tap; a fresh-boot walk confirms `history.length` is unchanged before and after tapping
  it, matching the single-entry case the fix already covers. No live call path stacks a second
  screen either: `openScreen`'s `dejaOuvert` branch (pushed layer on top of an already-open screen)
  exists in code, and `data-fiche` (18336-18349) is its one UNGUARDED trigger — when no sheet is
  open (`couche` false) it calls `openFiche(fiche)` directly, with no `closeScreen()` first, so a
  `[data-fiche]` element tapped from inside an already-open screen WOULD stack a second one. But
  no `[data-fiche]` element is ever rendered inside a screen today: its three producers —
  `cardHTML`'s poster (11578), `tileHTML`'s tile (15395), the Découvrir deck's poster (15855) —
  are called only from page-list/grid/deck builders (11555-15987), never from `openFiche`,
  `openResolve`, or `openReleases` (39527-40337, the only functions that build screen content);
  `openResolve`'s own cards (`releaseCardHTML`, 11613-11637) are marked `data-nonmedia` and carry
  `data-resolve`, not `data-fiche`, by design ("no medium here yet"). The sheet-to-screen half of
  `data-fiche` is guarded (`couche` true closes the sheet first, 18342-18344), and `data-refiche`
  reopens the SAME key (`memeEcran`, no new layer). The comment still overclaims — it is true of
  the DOM, not of history — but no reachable walk buries two entries under a `[data-go]` tap
  today. Fix shape unchanged: one loop, one entry per closed layer.
  **Final status (SP4b, task 6): latent, held by the Task-1 measurement.** No close-block fix
  applied — the entry-count law would be exercised on a control that cannot reach it. The
  handler's own comment no longer claims to handle a buried second entry (corrected to name the
  single-entry assumption, `refonte.html` ~17861); the intro comment's second example (the add
  screen's « Voir mes suivis ») is removed too — it left `data-go` in the interim (see B-025).
  Settles with the ownership law when `data-go` itself migrates to the shell (SP4d): if a sixth
  producer, or a new path to the existing five, can ever reach a layer, the entry-count law
  (`__pont.regler(n)`, sketched but unapplied here) is owed then, not before.

  **CLOSED by L10-bis, and the phase name above is dead.** SP4d ran — its two waves are recorded
  in `IMPLEMENTATION.md` as #447 and #448 — and `data-go` did NOT migrate to the shell in it. The
  phase that owns that migration today is **L13**, where the dying engine is subtracted. A
  forward-looking sentence pointing at a phase that has already passed reads as pending to every
  session after it, and this one has read that way since 2026-08-20.

  **THIS IS ONE OF THE TWO CLOSURES WITH NO INSTRUMENT, and rule 3's amendment obliges naming
  which one cannot and why.** No guard here greps prose. `check-no-french.py` reads names, not
  citations; `check-bug-register.py` reads the index, not the bodies; the harness reads a browser.
  A phase name inside a paragraph of English is text nothing in this repository parses. What was
  done instead is this correction, written beside the original rather than over it (§ 7.1).

  **The lead the entry offered was checked and is already spent.** « Five such sentences were found
  in the plan » — `docs/reference/frontend-architecture.md` carries none today; a later wave
  repaired them. The two survivors are in `product-intent.md` and are HISTORICAL (« ce qui a été
  livré de SP5 avant cette règle — SP5a »), which is a record and not a forecast, and that document
  is the operator's. An arm refusing a dead phase name would therefore have to tell a record from a
  forecast, which is a judgement about a sentence's tense and not a thing to grep. Recorded as
  measured rather than built, so the next wave inherits the measurement and not the suggestion.

  ⚠ The citation `refonte.html ~17861` in the paragraph above is stale by the same species: that
  file is **7 057 bytes** today and holds no such line. Left as written, because § 7.1 corrects
  beside and never over — and named here so a reader does not go looking.
- **B-025** — harness `bugs.py` check 10b stops at the landing (`10b. « Voir mes suivis » lands`)
  and never presses Back; only the sheet half (9b) is guarded. The `remplacer`-on-screen half of
  the fix — exactly what B-024 concerns — can regress without a single check falling.
  **Fixed (SP4b, task 6).** The footer itself left `data-go` between the review and this walk
  (Task 5 migrated « Voir mes suivis » to `AddScreen`'s own `toFollows`, a router-owned
  `remplacer:true` — same "the layer's entry becomes the arrival" semantics `data-go`'s own
  comment describes), so the regression this entry names now lives there, not in the shared
  handler; the guard follows it. `bugs.py` 10b gained a Back press, `10c`: after the footer
  lands, one real Back must leave `/ajout` in a single hop (no buried `layer` entry, `page`
  still `acq`) — mutation-verified by mutating `toFollows`'s `remplacer:true` to `false` at
  source (`10c` fell, naming the still-buried `/ajout`), rebuilt, then restored (`git diff`
  empty), rebuilt, re-run green.
- **B-026** — the `data-go` handler's outer `try { … } catch (error) {}` (house pattern from
  `data-navgo`) silences a `remplacer` failure: the page renders the destination while URL and
  history still describe the layer — a silent violation of the DOIT-10 claim that « the URL and
  the interface never disagree », with nothing logged.
  **Fixed (SP4b, task 6).** Three swallows now `console.error` and raise
  `window.__navEchec = true`, a probe published next to the other probe flags
  (the precedent set by the unnamed-subject set, which the shell publishes as `window.__settingLabels.unnamedSubjects`) for the harness to read: the `data-go` handler's own tail,
  `noterLeChemin`'s (`refonte.html` ~16561, the write door every OTHER navigation goes
  through), and `data-navgo`'s own tail (`refonte.html` ~18188-18194) — the pattern's
  ORIGIN, byte-identical in shape and risk, and left silent in the first pass (a review
  finding on the same commit). Mutation-verified for both call sites: with the intact
  catch, stubbing `__pont.remplacer` to throw (page context) and driving « Profil et
  préférences » from the user sheet (`data-go`, the one control that can fire `remplacer`
  from a layer) or the drawer's own first entry (`data-navgo`, opened through its handle)
  raised the probe (`true`) in both cases; a plain tap left it `false` either way (no false
  positive). Reverting either catch to silent and repeating the SAME forced throw on that
  path left the probe `false` — the hold falls without the fix, confirming it bites — then
  each catch was restored in turn.
  **Known residual, not fixed, deliberate.** The three silent catches in
  `window.__demarrerMoteur` (`refonte.html` ~40699-40721: the opening `remplacer`, the
  guard `remplacer`, the boot `noter`) stay silent. Boot-time, pre-render — a failure there
  leaves the splash/boot state visible rather than a rendered interface disagreeing with
  its URL, which is the lower-risk failure mode DOIT-10 is not written against. Settles
  when the legacy engine itself dies (SP4-end), not before.
  **The residual is closed on `fix/maquette-l05` (#484), and its justification had stopped being
  true.** « Boot-time, pre-render » no longer describes those three writes: `render()` runs above
  the first of them and `__loadingDone()` between the first and the second, so a refusal leaves a
  fully drawn interface standing on an address nothing wrote — the failure mode DOIT-10 IS written
  against, not the lower-risk one. The third is also the entry an addressed panel's layer is
  stacked on, so losing it makes the first Back spend the exit guard instead. All three now log in
  English and raise `window.__navEchec`, and R69 reads the flag on a cold load whose boot write is
  refused from outside the page.
  **A fourth swallow, found by the SP4b final review and fixed, not left residual.**
  `shell.tsx`'s `openPanel` wrapped `window.__pont.coucher("sheet")` in the same
  silent `try { … } catch {}`, inherited from the legacy `openSheet`'s own guard around this
  call. Unlike the boot-time residual above, `window.__pont` is assigned synchronously at
  this module's top level, before any producer can call `ouvrir` — there is no window where
  the bridge is genuinely absent, so the swallow's own justification ("a bridge that is not
  there yet") no longer held. A throw here means the write itself failed, and the store had
  already flushed the panel open: exactly the URL/UI disagreement DOIT-10 forbids, silently.
  Wired to `console.error` + `window.__navEchec = true`, the same pattern as the other three.
- **B-027** — `resync.py` extracts a follow's title with the FIRST `t: "…"` match anywhere in
  the object and counts braces with no string-awareness. An object whose first `X: "…"` key is
  not the title, or a title containing `{`/`}`, silently skips or — worse — rewrites the WRONG
  follow's counter. Holds today only by convention (all 12 objects start with `t:`), asserted
  nowhere.
  **Fixed.** The title is now read anchored on the object's own opening brace
  (`re.match(r'\s*\{\s*t:\s*"((?:[^"\\]|\\.)*)"', obj)`): the title must be the FIRST key or the
  script RAISES, naming the object's head. **Mutation** (proof executed, `task-7-report.md`, re-run
  after the script's messages moved to English): a scratch FOLLOWS fragment whose sole object opens
  on `x:` instead of `t:` → `resync.py` raises
  `ValueError: FOLLOWS object whose first key is not "t": …` quoting the object, rather than
  silently skipping it.
- **B-028** — `resync.py` cannot say a title went unmatched: a FOLLOWS title absent from the
  DB reads exactly like « already in sync », prints `0 correction(s)` and exits 0. Especially
  live once vo-title (#435) changes which spelling a follow carries — the operator running the
  documented remedy gets silence instead of « 4 of 12 titles never looked up ».
  **Fixed.** Every FOLLOWS title with no matching row in `acquire.db` is now collected during the
  same pass and, if any exist, `resync.py` prints
  `nothing written — N title(s) never looked up: …` naming each and exits 1 — `0 correction(s)` is
  only ever printed once every title matched. **Mutation** (proof executed, re-run after the
  script's messages moved to English): a copy of `refonte.html` with one real FOLLOWS title
  (« Kyma, l'onde mystérieuse ») misspelled → exit 1,
  `nothing written — 1 title(s) never looked up: Kyma, l'onde MISSPELLED`. **The mutation must be
  applied INSIDE the `const FOLLOWS = [` block**: that same title string also appears in the
  embedded référentiel earlier in the file, so a first-match replace edits the référentiel, leaves
  FOLLOWS intact, and the run prints `0 correction(s)` — which reads exactly like a guard that no
  longer bites.
- **B-029** — `content.py`'s counter rule tests `f"{n} recherche" in s["facts"]`: « 1 recherche » is
  a substring of « 11 recherches », so whenever the real count is a suffix of the embedded one the
  drift the rule exists to name is never named.
  **Fixed.** The hold now compares numbers with a word boundary
  (`re.search(rf"\b{r['searches']}\s+recherche", s["facts"])`), so a digit that merely ENDS the
  embedded count no longer satisfies it. **Mutation** (proof executed against the built prototype on
  8899): a copy of `refonte.html` with « Kyma, l'onde mystérieuse »'s embedded `recherches` set to
  17 while `acquire.db` still holds 7 → the rule falls:
  `FAIL the numbers come from acquire.db, not from the mock-up — ["Kyma, l'onde mystérieuse : « …
17 recherches » vs 7"]`, where the pre-fix substring check
  (`"7 recherche" in "… 17 recherches"`) would have stayed silently green. The searched word
  `recherche` is the French the prototype RENDERS — it stays French; only the hold's own label and
  the verdict word moved to English.

**B-039 — `actions.py:81` prints whether `.freshtag` exists and asserts nothing.**
The follow flow the rule drives never produces a `fresh` descriptor, so the probe printed `False`
before L02 anchored the element as `card/fresh-tag` and prints `False` after — measured across all
83 named states: `[.freshtag, [data-part="card/fresh-tag"]] = [0, 0]`. The contract is faithful and
nothing holds it: neither end can move and fall a rule. A state that produces a fresh follow, or a
hold after a follow action, is behaviour work outside the anchoring lot (2026-08-21).

**B-101 — a brief that told a wave what it would measure, and was wrong about it.**
The steward's hand-off for L08-bis stated, in bold: « **Cette vague VA faire bouger l'oracle** —
B-081 change ce qui est peint par défaut », and instructed the wave to expect a re-record and to
name every accepted divergence. **It could not move, and the reason was available before the brief
was written.**

The oracle captures with `html.measuring` on, and `harness.css`'s
`html.measuring .note { display: none !important }` was the ONE surviving rule touching `.note` —
a fact the steward had itself measured and written into B-081 the day before. The notes were
therefore absent from all 2 739 measurements and had always been. Restoring the hidden-by-default
pair aligns the judged document with the measured one **without changing the measured one**: the
oracle staying at zero IS the proof of the repair, not a surprise. Had it diverged, eye and
instrument would still be aimed at two documents.

**The failure is not the prediction; it is deducing where a measurement was one command away.**
The steward held both halves — the probe runs under `measuring`, and `measuring` hides `.note` —
and joined them into a forecast instead of into a check. That is the shape this register counts
under « guards green over what they do not read », applied to a person rather than a guard, and it
is the second time in two waves: B-082's five elements were read from the markup without opening
`base.css`.

**Why it belongs in the register rather than in a session's apologies.** A brief steers a wave: it
says what to expect, and an agent that expects a divergence looks for a reason to accept one. This
one did not — it measured and contradicted the brief, which is the outcome to want. The next brief
may be read by an agent that does not. **A figure in a brief carries the same duty as a figure in
the plan: the command that produces it, or it is not stated.**

Fix: no forecast of an instrument's behaviour in a hand-off without the command that establishes
it, the same rule § 0 of the architecture file already holds every figure to.

<sub>`grep -n 'measuring' frontend/maquette/design/src/styles/harness.css` · `grep -n 'measuring' frontend/maquette/oracle.py`</sub>

**B-235 — no desktop navigation exists beyond the drawer.**
`#nav` is `md:hidden` (`index.html:448`) and no rail exists anywhere under `design/src` — at
768 px and above the burger's drawer is the only navigation. Production draws a persistent
`Sidebar` there. §12 says the desktop « doit rester pleinement fonctionnel » (it is, through the
drawer) and is not the starting point of the drawing. **An unexplained difference between the
maquette and production is a decision nobody took**; this is one, filed `open` because the answer
is the operator's (`QUESTIONS.md` Q1) and not because the maquette is known to be wrong. Closed
by the answer, and by L15 if the answer is a surface.

<sub>`grep -n "md:hidden" frontend/maquette/design/index.html` · `grep -rln "sidebar\|Sidebar" frontend/maquette/design/src/{app,features,ui,lib}` → none</sub>

> **ANSWERED, 2026-08-30 (Q1): the drawer alone, at every width — and not frozen.** Not a defect: a
> decision, taken; a rail is drawn only if real use asks for it. Closes with L15's drawer.

**B-249 — the screen flashes when a sheet action closes the sheet AND opens a page.**
Reported by the operator on 2026-08-30, on a phone: tapping an action of the acquisition sheet that
navigates — « Voir la fiche », « Voir le parcours », « Chercher une autre release » — produces a
visible flash of the whole interface, too fast to capture; closing the sheet alone (handle, scrim,
Back) does not. Not diagnosed here; two candidates are readable in the code and both are the
frame's. The engine's `applyState` (`legacy.js:9446`) runs `hideLayers()`, then a store write, then
`port.scrollTop = 0`, then a full `render()` — a whole-page repaint with a scroll reset sits between
the close and the open. And B-247 (L15's, filed on its branch) records that a store bump REPLACES a
feature page's nodes, which is a paint of nothing between two paints of the page. **L15's**: it is
converting the layers and their hosts now, and P1 (« one document, no full navigation ») is the
property the flash violates in spirit. The rule must walk the operator's path — a real tap on a
sheet action that navigates — and read paints or replaced nodes, not the final state.

<sub>`sed -n '9446,9456p' frontend/maquette/design/src/engine/legacy.js` · `grep -n "panel.close(" frontend/maquette/design/src/engine/legacy.js`</sub>

**DIAGNOSED AND HALF CLOSED BY L15, and neither candidate was it.** Sampled frame by frame on the
operator's own path — a long press on a library tile, then the first action of the sheet it raises:

    frame  0   the scrim is up, the sheet is in place
    frame  2   `visibility: hidden` on BOTH — while opacity and transform
               still have 200 and 300 ms to run
    frame 18   the destination screen appears, already in place

**`visibility` is not animatable the way `opacity` is.** Left out of the transition list it swaps on
the first frame, so the dimmed page snapped to full brightness in ONE frame and stayed bare for
sixteen — and the exit every producer waits for was already over before the wait began:
`data-mediasheet` closes the panel and calls `setTimeout(…, 260)` « to let the sheet finish
leaving ».

**The frame's half is repaired**: `visibility` transitions with a delay equal to the fade, on the
CLOSED state only. The bare gap goes from sixteen frames to three. **On the closed state only is
not decoration** — putting it on both broke focus ENTRY into the sheet, because `app/focus.ts`
focuses into a layer the instant `data-open` appears and an element whose `visibility` is still
resolving is not focusable. R81 caught it; it is the one hold in the suite that reads that instant.

**The other half is not L15's**: the 260 ms wait belongs to the producer, and a producer is Part
12's — **L19's**. R103 (`harness/exits.py`) measures the remaining gap and PRINTS it. A rule that
refused a number nobody in this wave may change would be a rule against the wrong subject, and a
number nobody prints is a number nobody acts on. **Left `open` for that half.**

<sub>`python3 frontend/maquette/harness/exits.py` — 5 holds, no violation, and the gap printed. Mutation: `visibility` taken back out; both exit holds fall.</sub>

**B-143 — the constitution gained a section, and nothing in the plan answers it.**
The operator dictated **§17 — Comptes, droits et identité Plex** on 2026-08-26: the application
manages users, profiles and rights, and Plex users authenticate through Plex SSO. `DOIT-12` was
added with it — the actions offered are those the connected account may exercise.

**Recorded here the day it was written, because B-142 is one entry old**: three instruments measure
this interface and none reads the constitution, so a clause it gains is invisible to every gate
until someone says so. This is that someone.

**What exists today, measured**: one role (`PERSONALSCRAPER_WEB_ROLE=staging`, refusing writes
through the single `require_not_staging` dependency), one account (`WEB_PASSWORD_HASH` and a signed
session), and `GET /api/auth/me` in the maquette's contract carrying `avatar`, `email`, `name` and
nothing about rights. Plex is integrated for library refresh (`X-Plex-Token`, `plex-api.md`) and
never for identity.

**What §17 needs and nothing provides**: no operation in the 53 the interface declares concerns a
user other than the one connected, a role, or a permission; none of the thirteen lots names
accounts; and `frontend/maquette/design/src/features/account/` is a single `page.tsx` showing the
current person, not a model of several.

**The one thing §17 says that is a REQUIREMENT on existing code rather than new work**: the
read-only role must be ABSORBED by the rights model, not sit beside it. Two authorisation paths is
NE-DOIT-PAS-7, and the one that exists today is a single shared dependency — which is what makes
absorbing it cheap now and expensive after a second path exists.

Four questions §17 leaves open are written INTO the section rather than here, so that whoever
implements it reads them where the rule is: which roles and their exact rights, whether Plex SSO
replaces or joins the current sign-in, what becomes of a Plex user with no rights here, and what a
Plex account sees by default. None is the steward's to answer.


> **ARBITRATED, 2026-08-29.** The three sections are recorded in `frontend-architecture.md` § 1 as
> **lots that are OWED and not yet declared** — deliberately without a number, an order or a
> position, so § 0's rule cannot reach them: a lot the file has not placed is not electable.
> **L10-ter places all three**, in the order §18 → §19 → §17 unless it measures a reason to differ.
> They wait for it because §17 and §19 need new screens and L10-ter is redefining what a screen in
> this application IS — placing them before the template exists is drawing them twice.
> **B-142's instrument goes to L10-ter as well**, and the reason is not scheduling: the arm needs a
> declared mapping from each DOIT clause to the surface that serves it, and a mapping is a design
> decision rather than a grep. L10-ter is already modelling what a surface is.

<sub>`grep -n 'WEB_ROLE\|require_not_staging' docs/reference/web-ui.md` · `python3 -c "import json;print([p for p in json.load(open('frontend/maquette/contract/openapi.json'))['paths'] if 'auth' in p])"`</sub>

> **PLACED, 2026-08-29 (L10-ter): L18**, last of the three, after L16 and L17, with §17's four open points written into the lot as its blocking note. It is the one lot after L15 that edits frame CODE (the gate, for Plex SSO; L16 and L20 only add navigation-table rows), and the plan says so.

**B-145 — 797 lines of engine that inject torrents at third parties, and no way to know it happened.**
The operator dictated **§19 — Le cross-seed se voit et se décide** on 2026-08-26, with `DOIT-14`.

**Measured, and it is the most closed of the three sections dictated today.**
`personalscraper/acquire/cross_seed.py` is 797 non-blank lines. It emits `CrossSeedInjected` and
`CrossSeedRejected` on every decision. **Neither contract carries a single route for it** — zero
matches for cross-seed in `frontend/openapi.json` AND in `frontend/maquette/contract/openapi.json` —
and nothing under `personalscraper/web/` relays those events to `/ws/events`. The only trace
reaching any interface is a boolean configuration key, `"cross_seed": False` in
`web/routes/config.py:113`.

**The three sections dictated today are three different distances, and the distinction decides how
each is planned:**

| Section | What exists | What is asked |
| --- | --- | --- |
| §18 — ratio | three operations answering, none called | wire them, plus one write for the policy |
| §17 — accounts | one role, one account, no notion of several | a model, then surfaces |
| §19 — cross-seed | an engine, and **no exposure at all** | the backend follows the interface (§15) |

**§19 is where D7's rule earns itself.** « The maquette declares the contract its interface
REQUIRES … every divergence is recorded as a demand on the backend. » There is nothing to read from
here, so the demand has to start from what the experience needs — which is precisely the case D7
was written for, and the first one to arise since it was written.

**The defect this entry files, beyond the gap**: an engine that acts on third parties and reports
to nothing is `NE-DOIT-PAS-5` — silent failure — applied to a SUCCESS as much as to a failure. The
events are emitted and dropped. Whatever §19 becomes, the cheapest half is already built and
unplugged: two event types, already carrying their reason.


> **ARBITRATED, 2026-08-29.** The three sections are recorded in `frontend-architecture.md` § 1 as
> **lots that are OWED and not yet declared** — deliberately without a number, an order or a
> position, so § 0's rule cannot reach them: a lot the file has not placed is not electable.
> **L10-ter places all three**, in the order §18 → §19 → §17 unless it measures a reason to differ.
> They wait for it because §17 and §19 need new screens and L10-ter is redefining what a screen in
> this application IS — placing them before the template exists is drawing them twice.
> **B-142's instrument goes to L10-ter as well**, and the reason is not scheduling: the arm needs a
> declared mapping from each DOIT clause to the surface that serves it, and a mapping is a design
> decision rather than a grep. L10-ter is already modelling what a surface is.

<sub>`grep -rc 'cross.seed' frontend/openapi.json frontend/maquette/contract/openapi.json` · `grep -rn 'CrossSeed' personalscraper/web/` · `grep -c '[^[:space:]]' personalscraper/acquire/cross_seed.py`</sub>

> **PLACED, 2026-08-29 (L10-ter): L17**, depending on L16 because §19 is « le prolongement direct du §18 » and extends the tracker surface L16 draws. D7's first real case: routes declared by the maquette, mocks invented, the oracle recording the surfaces as new.

## The operator's reports — closed

| ID | Defect | His words | Closed by |
| --- | --- | --- | --- |
| B-001 | The list poster is still too small | « quitte à faire des cards plus hautes » | closed 2026-08-14 — `BUGS-CLOSED.md` |
| B-002 | The startup bar is never seen on a real load | — | closed 2026-08-14 — `harness/startup.py` |
| B-003 | In Arrivées a poster does not lead where a poster leads | — | closed 2026-08-14 — `harness/cards.py` |
| B-004 | Dragging the sheet handle down no longer closes the panel | — | closed 2026-08-14 — `harness/touch.py` |
| B-005 | A long press on a poster raises the browser's own menu | — | closed 2026-08-14 — `harness/touch.py` |
| B-006 | Two different sign-in screens: arrival and sign-out | — | closed 2026-08-14 — `harness/entry.py` |
| B-007 | `--accent` referenced 11 times, defined nowhere | — | closed 2026-08-14 — `harness/palette.py` |
| B-008 | The card poster should bleed to the card's edges | — | closed 2026-08-14 — `harness/cards.py` |
| B-009 | Swiping a media card should reveal its quick actions | — | closed 2026-08-14 — `harness/drag.py` |
| B-010 | Only one row open at a time | — | closed 2026-08-14 — `harness/drag.py` |
| B-011 | The drawer renders wrong on iOS | — | closed 2026-08-14 — `harness/drag.py` |
| B-012 | The startup screen plays a second time once loaded | — | closed 2026-08-14 — `harness/startup.py` |
| B-013 | The drawer's entries lead nowhere | — | closed — `harness/drawer.py` |
| B-014 | The drawer's current entry is unreadable | — | closed — `harness/drawer.py` |
| B-015 | Back reopens the drawer that was just closed | — | closed — `harness/drawer.py` |
| B-016 | Swiping a row right, then left, makes it jump | « 4 of 12 titles never looked up » | closed — `scripts/check-markup-contracts.py` |
| B-018 | On a desktop, dragging a row opens the panel | « 4 of 12 titles never looked up » | closed — `scripts/check-markup-contracts.py` |
| B-019 | Many media sheets have lost their visual | — | closed — `BUGS-CLOSED.md` |
| B-020 | Actor portraits on media sheets are broken | — | closed — `BUGS-CLOSED.md` |
| B-021 | Signing out leaves the bottom panel on top | — | closed — `harness/bugs.py` |
| B-022 | « Voir mes suivis » in the add search is inert | — | closed — `harness/bugs.py` |
| B-023 | Médiathèque « Incomplets »: every visual broken | — | closed — `BUGS-CLOSED.md` |
| B-080 | The drawer shows a hard-coded version and build, and calls itself up to date | (paraphrase) Reported by the operator on 2026-08-25 from a live screenshot, while `main` stood at 0. | fixed #505 |
| B-081 | Design notes can no longer be hidden, and the oracle measures without them | (paraphrase) Reported 2026-08-25: the design-note paragraphs are visible on every screen, and the toggle's toast announces « Notes masquées » | fixed #505 |
| B-082 | `hidden` hides nothing on five elements, so an invisible button is still tappable | (paraphrase) Reported by the operator on 2026-08-25 from a live phone: on opening the design host, the design-notes toast covers the floating add button; **the toast's close button (×) … | fixed #505 |
| B-099 | A test pass writes 13 GB of real zeroes into `/tmp` and pytest keeps three of them | (paraphrase) Reported by the operator on 2026-08-26, in the hardest available form: the machine's boot volume filled up mid-session and no command could run at all — the tool could not … | fixed #505 — `tests/_media_files.py` |
| B-138 | The profile panel's avatar is unconstrained, inside a region whose probe reads only the container | (paraphrase) Reported by the operator on 2026-08-26 from a live phone: opening the user sheet from the header avatar paints the image at its natural size. | fixed #516 — `harness/avatar.py` |
| B-139 | Three typed variants were written and never wired; one leaves a bare button unreadable | « Elle réserve pas sa place elle passe par dessus c'est une notification comme une autre, elle est fermable. » | fixed #516 — `scripts/check-markup-contracts.py` |
| B-140 | Back returns to the top of a page: the scroll memory only knows overlay screens | (paraphrase) Reported 2026-08-26: scroll a page, open an item, come back — the page is at the top | fixed #512 |
| B-248 | The bottom sheet rises behind the tab bar; the operator wants it to cover the bar | « par-dessus » — dictated 2026-08-30 from a screenshot of the acquisition sheet | fixed #528 — `harness/stacking.py` |
| B-251 | A file under `docs/` that no commit force-added is invisible to `git add -A`, to `git status` and to every gate | — | fixed #532 |
| B-310 | Opening a media screen from a bottom panel paints the PANEL again for one frame, open and opaque, after the crossing — the departing snapshot's `animation:` … | « effet de clignotement du panel bottom après l'ouverture de la fiche média : on revoit rapidement le panel bottom puis la fiche réapparaît » | fixed #573 — `harness/departure.py` |
| B-313 | The follow sheet offers « Voir le parcours » TWICE — once as the primary act, once in the secondary row — whenever the primary falls through to it | « dans les Arrivées, au clic sur un média, le panel bottom affiche 2 boutons "Voir le parcours" » | fixed #572 — `harness/panel_label_once.py` |
| B-315 | Découvrir's « charger plus »: the button is too big, one press should show more, and the feed must say when the reserve is spent | (the title is his report; his ruling of 2026-09-06: « A ») | fixed #572 — `harness/load_more_scale.py` |
| B-316 | The suggestion producer is registered and no finger reaches it — the media screen takes every point of the card | — | fixed #572 — `harness/discover_gestures.py` |
| B-322 | The release screen fires TWO take toasts into one element in the same tick, and the first is never seen | — | fixed #572 — `harness/release_take_sentence.py` |
| B-332 | A Réglages topic cannot be left: entering one REPLACES the address instead of pushing an arrival, and the topic view draws no back affordance, so Back … | « Réglage je rentre dans une section et je peux jamais revenir en arrière » | fixed #588 — `harness/topics.py` |
| B-334 | The secret panel's « Remplacer la valeur » does nothing: the action's whole effect is a `data-toast` the engine's dead message element answers, and no … | « Réglage: bouton remplacer la valeur ne fait rien » | fixed #588 — `harness/secret_acts.py` |
| B-335 | The secret panel's « Retirer la clé » does nothing and asks nothing: the same `data-toast` shape as B-334, on a destructive act that owes a confirmation … | « Réglage: bouton retirer la clef ne fait rien, et il devrait proposer une confirmation » | fixed #588 — `harness/settings.py` |
| B-341 | A settings field commits its edit only when the finger LEAVES it — no validation affordance in the panel — which the operator reads as counter-intuitive; … | « Pas de bouton de validation d'un changement faut sortir du champ ce qui est contre-intuitif et non ergonomique, puis on enregistre dans un second temps seulement » | fixed #588 — `harness/settings_editing.py` |
| B-342 | « Enregistrer » says « Enregistré — torrent.json5 » and the row shows the ORIGINAL value again: the mock's write records the file name and never the value, … | « quand on a enregistré sur la liste la valeur est reset à la valeur d'origine » | fixed #588 — `harness/settings_editing.py` |
| B-343 | After a real save the restart banner does not appear: the flag is raised on the engine's `SETTINGS_STATE` object and nothing re-renders the page, so « … | « Aucun redémarrer maintenant apparaît » | fixed #588 — `harness/settings.py` |
| B-344 | On a desktop browser the design host shows the prototype inside the phone frame only — the operator cannot test the interface's desktop layout there; he … | « Quand on est sur tm-design sur desktop, le design s'affiche dans un template de téléphone pour pouvoir voir le rendu sur téléphone, c'est très bien, c'est ce qu'il faut, mais du coup je peux pas … » | fixed #576 — `harness/desktop_frame.py` |
| B-350 | A PAUSED SERIES is dimmed in the follows grid with no word saying why: the tile's caption is `stFraction(follow) ?? paused`, so a fraction always outranks … | « on dirait que le suivi est stoppé mais rien ne l'indique » | fixed #572 — `harness/paused_tile.py` |
| B-361 | A Maintenance rubric cannot be left either — entering it writes `?topic=…` by replacement, pushes no entry and draws no back, so the system Back leaves « … | — | fixed #588 — `harness/topics.py` |
| B-365 | R124's « no mutation was answered 409 » hold reads Playwright's response events, and the mock layer replaces `globalThis.fetch` and answers IN THE PAGE — so … | — | fixed #572 — `harness/busy.py` |
| B-368 | The Découvrir feed is drawn BELOW the « charger plus » action: a pile spent before the mode leaves the deck outlives that mode, because the sweep that … | (paraphrase) seen once by the operator on the design host, not reproduced by him | fixed #572 — `harness/spent_deck_cleared.py` |
| B-371 | DOIT-4's « En file » pastille is reachable by NO path a finger can take: it reads the layer's `pipelineState`, which only the pipeline operations write and … | — | fixed #603 — `harness/queued_by_hand.py` |
| B-376 | Every push to a DRAFT pull request ran the whole pipeline, and no trigger answered the pull request leaving draft: a wave that opens its pull request early … | « on ne l'exécute qu'à la sortie de draft, afin d'économiser du temps de CI » | fixed #578 — `tests/scripts/test_ci_skips_draft_pull_requests.py` |
| B-393 | A resolution candidate is chosen by a full-width « C'est celui-ci » pill while the card itself answers no tap: the act takes more room than the medium it … | « Le bouton de sélection prend trop de place, c'est toute la carte média qui doit être cliquable. » | fixed #585 |
| B-394 | The harness's two floating buttons (the design note ⓘ and the states list ≡) are painted OVER a message shown at the top of the frame, so the sentence … | (paraphrase) read on the journey sheet of « Wicker »: the harness buttons cover the message at the top of the frame | fixed #585 |
| B-395 | The library's selection bar stays drawn on every other tab: `app/bottom-slot.tsx` renders it unconditionally and its own condition reads `selMode` alone, so … | (paraphrase) photographed on Acquisition › Suivis: the bottom bar still said « N sélectionnés » with « Annuler » and « Supprimer » | fixed #585 |
| B-490 | Acquisition › En cours throws the reader back to the top after a return from « Résoudre → »: the scroll restoration's late re-apply fires on a lazy poster's … | « Bug majeur : double scroll systématique sur Acquisition › En cours ; dès que le scroll arrive au niveau de Lucky on remonte automatiquement en haut de la page. » | fixed #593 — `harness/scroll_keeps_place.py` |
| B-491 | Out of the desktop frame the document scrolls beside `#port`: the closed sheet and its drag band overflow `.device` by 89 px once the frame stops clipping | « double scroll » (half of his sentence, see B-490) | fixed #593 |
| B-500 | The `card/pick` check mark on every resolution candidate card reads as « already selected »: nothing says the card is tappable to CHOOSE — closes: the « … | (his Q4 ruling, 2026-09-15: no marked card; the message « Identifié comme … · Annuler » names the choice) | fixed #598 |
| B-501 | « Rechercher une autre release » always lands on 0 candidates: the mock seed `releases.json` holds four releases, all Silo, and the handler filters by the … | — | fixed #598 — `harness/release_candidates.py` |
| B-530 | The navigation drawer closed by a firm leftward swipe shows itself open again for a fraction of a second as the closing animation ends | « il apparaît rouvert une fraction de seconde au moment où l'animation de fermeture se termine » | fixed #598 — `harness/gestures.py` |
| B-553 | The pull-to-refresh indicator's wheel is never seen turning — the operator, 2026-09-26, on tm-design, his Android phone: « Le loader quand on glisse vers le … | « Le loader quand on glisse vers le bas pour recharger ne tourne pas. » | fixed #616 |
| B-556 | A pull to refresh begun ON a card does nothing in « Suivis » — the operator, 2026-09-27 ~15:05, on tm-design (main a6fb6fc1d), his Android phone: « Onglet … | « Onglet suivi : impossible de tirer pour rafraîchir » | fixed #626 |
| B-557 | Acquisition's tab bar at 390 px — the operator, 2026-09-27 ~15:05, on tm-design (main a6fb6fc1d, four tabs): « Menu d'onglets: cassé voir capture » — « À … | « Menu d'onglets: cassé voir capture » | fixed #626 |
| B-572 | tm-design boots into the REAL world, where `movingReel` is empty by design (`mocks/state.ts:122`); the front reads the dense world only when `scen === … | « Je vois rien dans "En cours" par exemple. Comment tester tout les cas, si j'ai pas un exemple de chaque cas ? » | fixed #644 — `harness/panel.ts` |
| B-582 | Plex videos stalled, the machine saturated by a harness run | « J'ai plex qui bug, les videos tourne plus la machine est saturé ? » | fixed #646 |

## Requested evolutions

| ID | Evolution | His words | State |
| --- | --- | --- | --- |
| E-001 | Médiathèque sort inversion (2026-08-15) | every sort type must be reversible — A→Z and Z→A each way | drawn, `harness/library_sort.py` (R78) |
| E-002 | The menu closes on a leftward swipe from its right edge (2026-08-28) | dictated as a hand-drawn mark on a screenshot | confirmed by the operator on a device 2026-08-29 — `harness/gestures.py` (R98) |
| E-003 | The sheet closes on a downward swipe from a widened top edge (2026-08-28) | same mark: four times the 22 px grab band | confirmed by the operator on a device 2026-08-29 — `harness/gestures.py` (R98) |
| E-004 | The 240 ms dead delay on `data-next` (« Passer à la suivante ») (2026-08-16) | flagged to the operator: he may want it dropped | open |
