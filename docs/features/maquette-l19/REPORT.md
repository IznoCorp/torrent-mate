# L19 — The producers · report

**Every figure here is taken ONCE, on the final head**, which is the fifth of the office's review
rules. A figure that moved during a repair round is not re-measured here; it is measured on the
head that is about to merge, and that is this one.

---

## 1. The contract, line by line

`docs/reference/frontend-architecture.md` § 4, entry « L19 — The producers », « Done when ».

| Line of the contract | Reading | Verdict |
| --- | --- | --- |
| `grep -c "panel\.open(" legacy.js` reads 0 | **0** | **met** |
| the inventory command lists only the harness panel | 2 sites, `legacy.js:8925` and `:8949` — the harness panel and nothing else | **met** |
| the fixture families that fed the producers are gone | **four converted** — `RISQUES`, `TRIS`, `SUG_BATCH`, `openJourneySheet.steps`. D5's bracket-match over 100 lines reads **9 declarations, 26 375 lines — unchanged** | **partly; see § 2** |
| the delegation handles only the frame's verbs | **not met, and not attempted** — see § 3 | **carried, with its owner** |
| the four map rows read `served` with a rule that bit | DOIT-8 → `served` (R121), NE-DOIT-PAS-9 → `served` (R122), NE-DOIT-PAS-3 → `served` (R124), **DOIT-4 → `partly`** with L21 named | **three met, one measured and owed** |
| the oracle is green or its divergences accepted | **2 958 measurements, NO DIVERGENCE**, on every one of the eighteen phases | **met** |
| the settings' two banners draw, each with a rule seen red | B-299 and B-300, each alone in its commit, each rule red before the surface existed | **met** |

---

## 2. The fixtures did not die, and this is the finding

**Four families converted. The nine large ones are untouched at 26 375 lines.**

The contract expected the fixture to die with the producer, and the reason it did not is worth
writing down rather than reporting as a shortfall:

**Every one of the nine is also read by a React surface, or by drawing the engine still does.**
`SHEETS_RAW`, `OWNED` and `CAST` are behind `sheetFor` / `seasonsOf` / `ownedFor`, which the media
feature reads. `SETTINGS` is behind `allSettings`, which the engine's own field verbs still call.
`LIBRARY`, `POSTERS`, `HERO_IMAGES` and `trailerIds` are behind `cardHTML`, `tileHTML`,
`posterBox` — the shared emitters every list and every gallery in this application still goes
through. `MAINT_ACTIONS` is behind the maintenance PAGE's own reference read.

**A producer was never their last reader.** L13 said the sixty families « belong to surfaces the
ENGINE still draws »; L10-ter corrected that to « surfaces the engine still PRODUCES ». Both are
half of it. The families that die with a producer are the ones a producer ALONE read, and there
were four. The rest die with the DRAWING — `cardHTML`, `tileHTML`, `posterBox`, `sheetFor` — which
is L13's, and this wave is the one that establishes it by subtraction rather than by argument.

**What did leave**: `legacy.js` 32 461 → **31 645 non-blank**, 816 lines. `states.js` 791 → **786**.

---

## 3. « The delegation handles only the frame's verbs » — carried, not met

**Measured on the final head: 133 `closest.dataset.` reads over 73 distinct names** (132 over 71
on `main`). The wave moved the two the contract's own objective names — `data-cancelsetting`
(settings) and `data-take` (arrivals) — and added none.
<sub>`grep -c "closest\.dataset\." frontend/maquette/design/src/engine/legacy.js` · `grep -o "closest\.dataset\.[A-Za-z0-9_]*" … | sed 's/.*\.//' | sort -u | wc -l`</sub>

**NEITHER FIGURE IS A VERB COUNT, and this file said « some 71 verbs, of which six are the
frame's » with no command under it.** `index`, `ep`, `sugidx` and `selectedTitle` are data the
handler reads off the tapped node, not acts; the split between a verb and a datum has never been
produced by any lot, this one included. What is measured is 133 reads over 73 names. What is
asserted below is that most of them are behaviour, and it is an assertion on a denominator nobody
has counted — said here rather than dressed as a measurement.

**Why the rest were not moved**, said as a reading rather than as a shortfall:

- The lot's own contract says « no surface changes » and the office's first review rule says a
  conversion wave does not carry a behaviour repair. **Moving the remaining readers is a behaviour
  surface**, and `data-take` is the evidence: moving ONE of them uncovered a live defect that had
  never been measured (B-309, § 5).
- The brief that opened the lot names exactly two and says « you do not add a verb ».

**The count rose by one**, 132 → 133, and it is honest to say why: the two behaviour phases added
`data-confirmrestart` and `data-reloadsettings` — both required by the surfaces the contract
asked for — while the two moved verbs kept their branches, which are now one line each.

**The remainder is inventoried for its owner**: the verbs that navigate (`data-mediasheet`,
`data-journey`, `data-resolve`, `data-releases`, `data-profile`) belong to the surfaces they open
and move with L13's delegation; the frame's six are L13's by name; the acquisition's own
(`data-follow`, `data-pause`, `data-remove`, `data-dropsug`, `data-sugmore`) are behaviour and are
**L21's**, on the producers this wave has just put in their features.

---

## 4. R103's reversal — made for what this lot owns, carried for the rest

The contract said R103 « then REFUSES the gap instead of printing it ». **Two of the seven
`setTimeout(…, 260)` sites left with this lot; five did not**, and they are named rather than
swept into a blanket refusal, which would have been a rule against the wrong subject.

| Site on the final head | Verb | Owner |
| --- | --- | --- |
| `9252` | the add-from-resolution path | arrivals' |
| `9321` | `data-releases` | releases' |
| `9342`, `9345` | `data-profile` | settings / releases |
| `9699` | `data-resolve` | arrivals' |

**Gone**: `data-journey`'s (R103 refuses it now — the panel is drawn at frame 3, where a 260 ms
wait puts it past 15) and `data-take`'s (R123 reads the queue at 120 ms).

---

## 5. What the wave found that nobody had measured

**Six defects, all of them live on `main` before this branch, none of them found by a gate.**

**B-309 — « Récupérer maintenant » threw and took nothing.** The document had TWO branches for
`data-take`; the release screen's was checked first and had no guard, so a medium's TITLE reached
`releases()[NaN]` and reading its `res` threw. The tap raised a TypeError, the panel closed, and
**nothing was taken**. The panel's own branch was unreachable dead code. Found by writing the rule
the brief said did not exist — and that rule was RED with no mutation needed, which is the
strongest form of « seen red first » this repository asks for.

**B-247's producer half, live on the poster gallery.** All SIXTY tiles of `acq-discover-posters`
were new nodes after any store write, so a tap landing between `pointerdown` and `click` was lost,
silently, on the one surface built to be browsed with a thumb. Found by the hold written for it.

**A destructive maintenance command could have announced itself in the SUCCESS tone**, and no rule
anywhere read what colour a command that deletes wears. `machine.py` walks that very panel and
reads its actions; the oracle measures a region root and a chip is a child of one.

**§5 was drawn and read by nothing**: a film is ADDED and a series is FOLLOWED, and a mutation
treating every suggestion as a series fell no hold — leaving the interface free to promise a watch
that will never end.

**The settings panel could have said the operator's edit did not take.** `valueShown` answering
the file's value unconditionally fell no hold in `settings.py`, which walks that panel, nor in
R120.

**`page_host.py` was ASSERTING B-300**: « a real tap on the restart offer TAKES it » — the
behaviour the register calls a defect, written down as a requirement. B-085's species from the
closest possible range.

---

## 6. Guards green over what they do not read

**Eleven found by this wave, and SEVEN more by round one's four readers — eighteen.** Zero would
have been a real answer and this is not it; nine was the wave's own count, written as a claim
awaiting readers, the readers came back at 78 % of it on a gate green in every tier, and repairing
what they found turned up two more of the wave's own.

| # | Green over | Found by |
| --- | --- | --- |
| 1 | a destructive command announced in the success tone | the phase's own mutation |
| 2 | §5's film/series distinction and its note | the phase's own mutation |
| 3 | an edited setting's panel showing the file's value | the phase's own mutation |
| 4 | R120's own refusal check accepting ANY throw, including the crash it was written to prevent | R120's own mutation |
| 5 | R103's new journey hold driving the SEAM, so the wait it refuses was never on its path | its own mutation |
| 6 | `pop.py`'s `main()` computing a verdict and never reaching the exit code | reading it to extend it |
| 7 | `pop.py` reading the popover's text and never whose episode it was | the phase's own mutation |
| 8 | R122's reachability satisfied by a second path, so its first mutation was survived correctly and its second was needed | its own mutation |
| 9 | `page_host.py` asserting B-300 as a requirement | the behaviour phase that repaired it |

**And two the wave's own instruments caught in the wave's own work**: `check-markup-contracts`
refused a selector emitted nowhere **three** times, and a class-token anchor once;
`check-state-ownership` refused the Découvrir feed's store writes as a component's.

**Round one's seven, and every one is in an INSTRUMENT** — not one is a product surface, which is
the opposite of what L11's four readers found and is worth saying:

| # | Green over | Repaired |
| --- | --- | --- |
| 10 | the size ledger is its own oracle: the FILE is compared with the record, the RECORD with nothing, so a growth is legalised by moving the number in the same commit | `baa16f2c6` — the record is read at the base and may only go DOWN, with the CI job given a base to read |
| 11 | `check-state-ownership.py`'s engine-owned exemption proved by SUBSTRING — a comment spelling the path keeps it alive after the import goes, in a file full of comments naming feature paths | `309263aca` — the specifiers are parsed, and the guard has a test file for the first time |
| 12 | `panel.py`'s boot needle, the same shape: a commented-out `import "./panel-field";` left the hold green at exit 0, where the deleted line fails it | `0991da79f` — the reach is a set of resolved paths |
| 13 | `paths_to_sheets.py`, twice: four of five reachability branches select nothing on all six surfaces, and the message counted the four-item SAMPLE as the number of dead ends | `bafab0e51` — the carrier is named on the green line, and the count and the sample are two fields |
| 14 | `fanout.py` holds the invalidation map against ITSELF — a key dropped from the declaration is invisible | filed, **B-319**: the repair is a second end, and it is the query layer's lot |
| 15 | `hold-counts-baseline.json` is compared by nothing — no guard, no CI job — and now carries eleven rows that are wrong or absent | § 9, with B-291 |
| 16 | `busy.py` raises its panels through the SEAM: the exact vacuity this wave caught in R103's journey hold, reproduced one rule along | § 9 |

**Three of the seven are one shape — a fact asserted by SEARCHING a file's text instead of
parsing it — and that shape shipped twice in this wave under its own author's review.** A wave
cannot audit its own instruments, and it cannot see its own habits either.

**And two more of the wave's own, both found REPAIRING round one rather than by a gate** — which
is this table's oldest reading arriving from the closest possible range, and the reason the count
above is eleven and not nine:

| # | Green over | Found by |
| --- | --- | --- |
| 10 | **`app/focus.ts` asserting a priority its selector cannot express.** « `[autofocus]` first, so a layer can name its own entry point » — over a selector LIST, where `querySelector` answers the first matching node in DOCUMENT order whatever order the alternatives are written in. The restart confirmation rendered `autofocus` on « Annuler », `[autofocus]` matched exactly one node, and `document.activeElement` was « Redémarrer ». The comment had been there the whole time and nothing read it | repairing round one's MINOR 1, when the repair did not take |
| 11 | **R82's own new hold, a green reading of nothing on BOTH builds.** It cleared the whole query cache between the Back and the Forward; the engine's addressed table asks `resolves` first, the journey's reads the LIBRARY and the QUEUE, so an empty cache had the address refused outright — « the addressed panel names nothing this interface holds » — and the walk never reached the suppression it was written to measure. `open=False · history.length 4 -> 4`, identically with the repair and with the repair mutated away | asking why the mutation's reading and the repaired reading were the same |

**Row 11 is lens A's own lesson arriving one day later, in this wave's hands**: a probe that taps
a covered button, or clears more than it meant to, is green over nothing at all — and the tell is
that the mutation and the control read the SAME.

---

## 7. The instruments this wave built or repaired

| Rule | Subject | Holds |
| --- | --- | --- |
| **R120** `producers.py` | the seam: which kinds are registered, the refusal by its named thrower, each kind opening a panel about the subject asked for, the chip's tone and its word, the holder both ways, §5's distinction | 33 |
| **R121** `replacement.py` | DOIT-8 — nothing is replaced in silence, and a medium the library does not own raises no dialog | 8 |
| **R122** `paths_to_sheets.py` | NE-DOIT-PAS-9 — six surfaces, three kinds of path, a floor each | 13 |
| **R123** `take.py` | `data-take` on both its paths, and B-249's shape on the panel's | 9 |
| **R124** `busy.py` | NE-DOIT-PAS-3 — the act lands, nothing answers 409, nothing says « occupé » | 7 |
| R100 `persistence.py` | gains hold (h), the panels' nodes, and hold (i), the feed's containers | 41 → 47 |
| R103 `exits.py` | refuses the gap on the journey's path, names the five it does not own | 17 → 18 |
| `settings.py` | the cancel verb, the pending edit shown, B-299's banner, B-300's confirmation through its CANCEL | 46 → 65 |
| `pop.py` | the episode's own facts, and a verdict that reaches the exit code | + the exit code it lacked |
| `page_host.py` | stops asserting B-300 | 44 |
| **B-306** `check-frontend-boundaries.py` | a grandfathered file's size is RECORDED and refused upward | 4 new cases |
| `check-state-ownership.py` | a module the engine imports back is the engine's — an exemption that is checkable rather than claimed | — |

---

## 8. Deviations from the design

**Recorded in the phase file that took each**, which is the only order that stops the drift. Nine,
by following the files:

`phase-01` one (the guard was split, and the ledger became `scripts/frontend_size_ledger.py`) ·
`phase-02` three (`needs` on the registration; `produce` waits for what a kind needs; R120 joined
the contracts tier) · `phase-04` one (a feature with more than one panel gathers its own siblings)
· `phase-11` one (the follow sheet in three files rather than six) · `phase-14` two (the feed's
technique is unchanged by decision; `check-state-ownership.py` was opened) · `phase-13` one (the
first shape of the take move grew the engine and was reshaped to shrink it).

**Six more, added on 2026-09-05 after round one read them off the code rather than off this
file.** A deviation nobody wrote down is indistinguishable from one nobody noticed, and five of
these six were found by a reader comparing the tree with the contract — which is exactly what
this section exists to make unnecessary.

| # | The deviation | Why it stands |
| --- | --- | --- |
| 10 | **« The delegation handles only the frame's verbs » is not met, and was not attempted** — the only one of the ten carrying an **operator sign-off**, given 2026-09-05 (« OK pour le placement L13 et L21 ») | § 3, and the plan now places the remainder in L13 and L21 |
| 11 | **`SettingsBanners` is rendered on FOUR branches** of `features/settings/page.tsx` (secrets, a topic, search, the rubric list); the read-only and restart banners existed on the rubric list alone | The save bar exists on every branch, and it is what raises B-299's banner — drawn on the list alone it would have been invisible exactly where the operator taps « Enregistrer ». Reverting it would put B-299's surface where nobody saves |
| 12 | **B-299's shape is not the brief's.** The brief § 3 says production answers **412**; the mock answers **200** with `conflict: true` and the banner reads the body, not an error path | D7 — the data contract is the maquette's own artefact, and a 412 branch mocked as an error path would have had the query layer treat a conflict as a failure. Reasoned in `features/settings/queries.ts` and in `plan/phase-17-b299-conflict.md` |
| 13 | **`panel-add.ts` reads the engine, not the cache** — `window.__searchResults?.()`, `window.__referentiel.addVerb(…)`, `window.__store` | Invariant 10's letter is « reads the query cache … never the engine's accessors », and the add search has no boot-askable key: its subject is what the operator just typed. Justified in the file, and a justification is not the invariant — which is why it is here |
| 14 | **The take sentence has two derivations** for the duration of the engine's life. `features/arrivals/verbs.ts` says `verbs.arrivals.taken`; `engine/legacy.js`'s `actionTake` still holds the same sentence as a template literal, with three live callers | §13 asks one derivation per question. The three callers are verbs this lot does not own (§ 3); the two agree today, and the engine's copy goes with its callers |
| 15 | **« each moved producer takes its `installX` seam out of `app/shell.tsx` » is unmet**: `install*(` reads **25 on `main` and 25 here** | No feature `queries.ts` seam was left to take — the clause described an arrangement that had already gone. `shell.tsx` did fall, 398 → 392, by other means. Recorded rather than claimed, because a clause silently unmet is a clause nobody re-reads |

**And one commit's shape, which is not a deviation from the design but is a defect in how it was
reviewed**: `ca09e9b28` lands `check-state-ownership.py`'s new exemption **beside the seven files
under `design/src/` that it exempts**. An exemption cannot be reviewed as a separate decision when
it arrives inside the change it permits. The other fifteen mixed commits in the wave are mandated
co-edits — a ledger re-record, a vocabulary word, a ceiling lowered in the commit that earns it.

**Only deviation 10 carries an operator sign-off. The other fourteen do not**, and saying so is
the rule rather than an apology.

---

## 9. What is owed after this wave

- **L13** — the nine large fixture families, whose readers are the shared emitters and the
  reference; the delegation's remaining verbs; `app/engine-data.ts`, now down to one family;
  `SETTINGS_STATE`, which is the engine's mutable object and moves with the last verb that writes
  it.
- **L21** — DOIT-4's « En file » pastille on the resolve queue, **measured not to exist**; the
  three tunnel verbs; the acquisition's own delegation verbs.
- **B-308** — the maquette draws six schedulers and the machine runs seven, since `4c0e274a7` on
  `main`. Filed, not repaired: drawing the seventh row is a surface change this contract forbids.
  **AND IT BLOCKS THE POST-MERGE GESTURE, which is round one's reading and not this wave's.**
  `machine.py` is the one rule failing in the full suite, so re-recording
  `hold-counts-baseline.json` at the gesture writes a baseline while `failed = 1` — B-291's second
  form exactly, and nothing refuses it. **The gesture must not re-record until B-308 is either
  repaired or quarantined**: the recorder needs a way to say « this row was taken over a failing
  rule », or the row it writes is indistinguishable from a good one. Owner of the repair: the wave
  that draws the machine page — the seventh row is a surface. Owner of the quarantine: whoever
  performs the gesture, before they perform it.
- **B-291, with eleven more rows.** `hold-counts-baseline.json` is untouched by this wave, which
  is correct — it is the post-merge gesture's file — but nothing in the tree compares it: `rg
  'hold-counts-baseline'` finds the recorder, `IMPLEMENTATION.md` and `BUGS.md`, and no guard and
  no CI job. Against this head it is wrong or absent in eleven places (`exits` 15→18, `fanout`
  142→150, `panel` 50→51, `persistence` 39→47, `settings` 46→65, `pop` unparseable→a real count,
  and five rules it does not carry at all). A baseline nobody compares is a baseline nobody can
  tell a good row from a bad one in.
- **B-316 to B-319**, filed by round one and none of them this wave's: the suggestion producer with
  no finger path, the greeting toast over the settings save bar, the build racing its own output
  again (B-098's shape), and `fanout.py`'s map held against itself.
- **`busy.py` opens its panels through the seam** (§ 6, row 16). The tap on the action is real; the
  path that RAISES the panel is not walked, so a lost `data-panel` on a busy page is invisible to
  it. Left as it is rather than repaired blind: the correction is the one R103 took — drive the
  delegation — and it belongs with the wave that owns those verbs (L21).

---

## 10. The gates, on the final head

Each run ALONE, wrapped in `scripts/heavy.sh`, at `TM_HARNESS_JOBS=2` and three test workers.
Never a build beside a run.

| Gate | Reading |
| --- | --- |
| **oracle** | 87 states × 34 regions, **2 958 measurements, NO DIVERGENCE** — and on every one of the eighteen phases before it |
| **full suite** (`run.sh`, no flag) | **92 rules**, one failure: `machine.py` — **B-308**, pre-existing, proved not this branch's |
| `run.sh --contracts` | 18 rules and 26 repository guards, no violation |
| `--a11y` | **0 violations** over 87 states; the light theme unmoved at its ceiling of **166** |
| `harness-hold-counts.py --compare` | **`failed` read FIRST (B-291): 1, and it is `machine.py`.** Six rules changed — `exits.py` 15→18, `fanout.py` 142→150, `panel.py` 50→51, `persistence.py` 39→47, `pop.py` unparseable→3, `settings.py` 46→65 — and five are new: `busy.py` 7, `paths_to_sheets.py` 13, `producers.py` 35, `replacement.py` 8, `take.py` 9. Every movement upward |
| `make check` | **11 077 passed, 0 failed, 0 errors** (4 skipped, 2 xfailed) |
| `tsc --noEmit` · `vitest` | clean · 134 files, 1 374 tests passed |

### The figures, taken once

| Reading | Before | After |
| --- | ---: | ---: |
| `grep -c "panel\.open(" legacy.js` | 10 | **0** |
| the inventory command | 9 sites | **2** — the harness panel alone |
| `grep -c "closest\.dataset\." legacy.js` | 132 | **133** — § 3 says why it rose |
| `setTimeout(…, 260)` sites | 7 | **5** — the two this lot owned are gone |
| `install*(` in `app/shell.tsx` | 25 | 25 |
| `app/shell.tsx` non-blank | 398 | **392** |
| `engine/legacy.js` non-blank | 32 461 | **31 645** |
| `engine/states.js` non-blank | 791 | **786** |
| fixture families over 100 lines | 9 / 26 375 | **9 / 26 375** — § 2 says why |
| families the register records converted | 27 | **31** |
| `check-frame-domain` `app/` | 129 | **126**, ceiling lowered with it |

### The plan's own self-check

```
git log --oneline origin/main..HEAD | wc -l                     → 48
git log --oneline origin/main..HEAD | grep -c "maquette-l19"    → 48
grep -L "^## Verdict" docs/features/maquette-l19/plan/phase-*.md → (no output)
```

**Every commit carries the codename and every phase file carries a verdict.** The phases chained
without pause; the only stops taken are the ones the plan named — Stop A (the harness, asked of
the steward and granted), Stop B (DOIT-4's pastille, measured not to exist and recorded), and
Stop D, which is the pull request.

---

## 11. Six operator reports arrived during the closing gates

They are in the register with their readings. **None of the six is this wave's**, and each was
walked rather than argued.

| # | Report | Reading |
| --- | --- | --- |
| **B-310** | the bottom panel seen again after the media sheet | **identical on head and control** — 24 frames of panel-after-sheet on each. B-249's open half, seen from a side the register had not described: the panel is not re-opened, it never finished leaving |
| **B-311** | a list does not come back at the place it was left | **not reproduced on either**, twice. And the first probe is recorded as the green reading of nothing it was: its « drag » never scrolled |
| **B-312** | the lens drops the selection | L14's decision, **ruled against by the operator**; its reason is spent because L14 re-keyed by title in the same wave |
| **B-313** | « Voir le parcours » offered twice | **main's producer emits it twice, byte for byte** — `legacy.js:31699` and `:31734`. An asymmetry the engine carried: « Voir la fiche » is guarded against exactly this, and says so in its own comment |
| **B-314** | the add screen shows no example results | **not reproduced** — 5 results on both, the same copy. No family the add screen reads died with a producer |
| **B-315** | Découvrir's « charger plus » | three parts: the end mark exists and is identical, a press adds a batch, and the button's SIZE did not move — which the ORACLE says at 2 958 measurements |

**Two of these are the same question the brief's § 10 asked** — « the difference must not include a
family a React surface still reads » — and the answer, measured twice, is that it does not.

**And one of them is a finding about this wave's own instruments rather than its code**: a probe
that reads a number having never performed the gesture is a green reading of nothing, and it took
a second walk to see it. It is written into B-311 rather than quietly replaced.
