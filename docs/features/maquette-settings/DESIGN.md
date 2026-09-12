# maquette-settings — what was measured, and with what

Every figure below carries the command that produces it, and every figure was taken on this
branch's FINAL head. A number without its command rots; a number nobody re-measures is a number
nobody can contest.

## The state this wave started from

    git log --oneline origin/main -1              → 468162dc6, version 0.98.83
    python3 scripts/check-bug-register.py --next  → B-393 on this branch

The reserved register block for this wave is **B-397 to B-419** and **R165+**: B-393..B-396 and
R161..R164 belong to the resolution-card micro-wave, unmerged on the day this opened; the tooling
wave holds B-420+ and the L20 design wave B-440+. Gaps are accepted.

## What each repair is, and the rule that reads it

| Entry | The repair | The rule |
| --- | --- | --- |
| B-332 | A Configuration rubric PUSHES its arrival and draws `data-part="screen/back"`; the engine's `dataset.topic` branch is deleted | R165 `harness/topics.py` |
| B-361 | The same on Maintenance; `dataset.maintopic` deleted, and the cross-reference that navigated is a back that POPS | R165, the same 16 holds over both pages |
| B-341 | « Valider » in the field's panel, a registered verb; the two labels say what they are | R166 `harness/settings_editing.py` |
| B-342 | The mock reads the request's BODY and keeps the values; a file changed on disk takes nothing | R166 |
| B-343 | The restart flag leaves `SettingsState` for the layer; the banner reads a query | R166 |
| B-334 | « Remplacer la valeur » writes the key through the layer, from a field the panel now offers | R167 `harness/secret_acts.py` |
| B-335 | « Retirer la clé » asks first, in the dictated words, and the walk goes through the CANCEL | R167 |
| B-345 | At rest one file answers `conflict: true` on its own write; any other save reaches the restart | R128 `harness/seeds_at_rest.py`, four holds added |

**B-299 and B-300 are NOT closed here.** They are made confirmable by hand, and each says so in its
own entry; the confirmation is the operator's.

## The engine only shrank

    grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/legacy.js   → 31451 (was 31467)
    grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/states.js   → 786 (unchanged)

Two delegation branches DELETED (`dataset.topic`, `dataset.maintopic`) and two field writes
substituted line for line — `resetSettings`'s `SETTINGS_STATE.redemarrage = false` and the named
state `settings-restart`'s `= true` now call the layer's own dial, because that is where the fact
lives once B-343 lands. No line was added to either file. The size ledger is re-recorded DOWNWARD
in the same commit, which is what `scripts/frontend_size_ledger.py` asks for:

    python3 scripts/check-frontend-boundaries.py --arm size

**The `data-toast` branch STAYS**, and `data-restart` with it. The brief allows deleting a branch
that has lost its last reader; `features/maintenance/panel-action.ts` still emits a `toast:` target,
and the restart banner still emits `data-restart`. A branch with a reader elsewhere stays.

## The mutations

Each was applied to the built tree, the rule replayed, the FAIL line read, and the tree restored.
`scripts/mutate.sh` judges a rule by its FAIL lines (B-273), so each is named by the hold it felled.

| Mutation | Rule | The hold that fell |
| --- | --- | --- |
| *(recorded at the head; see the wave's report)* | | |

## What the fixtures cannot show

- **The conflict is a property of a FILE here, and in production it is a property of a moment.**
  The seeds mark one file as changed on disk, permanently, so a hand can always reach the banner.
  A real editor meets it when someone else writes while they are editing. What the maquette proves
  is that the banner is REACHABLE and honest; when it fires is the backend's.
- **A secret's value is never read back**, so no rule can assert that the key the layer now holds
  is the key that was typed. What R167 holds is that the write HAPPENED and that the key's posed /
  absent state moved — which is the whole of what this interface is ever told.
- **The restart itself restarts nothing.** `restartWeb` clears the layer's flag and the banner goes;
  no service stops. That is the contract's own shape (D7), and it is what makes B-300's
  confirmation walkable at all.

## One defect this wave's own rule found in this wave's own repair

The rubric verb's first build closed the rubric on ANY pop. A panel is addressable and lays its own
entry OVER the rubric, so the first Back that shut a panel also shut the rubric under it — and a
reader who had just filed an edit landed on the list of rubrics. R166's walk read it as « 0 rows »
after a save that had demonstrably succeeded. The reader ignores an entry that carries a layer.

## One defect this wave found and did NOT repair

**B-397** — a panel re-produced after an edit pushes a second history entry, so shutting it takes as
many Backs as the edits made in it. The field's NATIVE commit path has done this since the panel
became this feature's, so it is not this wave's to carry; the entry names L13 and the ladder.
R166 walks the extra steps in a bounded loop on purpose, rather than driving `__panel.close()`,
so the cost stays visible instead of being hidden by a seam.
