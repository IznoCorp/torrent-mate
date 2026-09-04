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

**Measured on the final head: 133 `closest.dataset.` reads over some 71 verbs, of which six are
the frame's.** The wave moved the two the contract's own objective names — `data-cancelsetting`
(settings) and `data-take` (arrivals) — and added none.

**Why the rest were not moved**, said as a reading rather than as a shortfall:

- The lot's own contract says « no surface changes » and the office's first review rule says a
  conversion wave does not carry a behaviour repair. **Moving sixty-five verb readers is a
  behaviour surface**, and `data-take` is the evidence: moving ONE of them uncovered a live defect
  that had never been measured (B-309, § 5).
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

**Nine, found by this wave, on gates that were green in every tier.** Zero would have been a real
answer and this is not it.

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

**None carries an operator sign-off**, and saying so is the rule rather than an apology.

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
