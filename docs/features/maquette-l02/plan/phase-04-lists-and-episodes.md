# Phase 4 — `.reslist`, `.sugwrap`, `.ep`, `.eppop`

## Gate

Phase 3 must have produced, all committed:

- `data-part="card"`, `card/title`, `card/body`, `card/foot`, `card/cover`, `card/poster` emitted at
  **both** the engine and the component sites;
- the 2 `noposter` assertions moved to `hasAttribute('data-no-poster')`;
- `frontend/maquette/anchor-baseline.json` down to **195 entries** (258 − 63);
- ACC-03 recorded as `exit=1` naming `cards.py`, its line and `.ctitle`;
- both `ctitle` sites in `resolution.tsx` anchored (phase 3 owes nothing else on ACC-04).

**ACC-04 is CLAIMED BY THIS PHASE**, not inherited. It needs a single-emitter target, and phase 3's
card family has none — every member straddles the engine boundary, so a surviving emitter keeps the
arm green. `.reslist` has exactly one emitter (`screens/add.tsx`) and is selected 15 times; run
ACC-04 from `DESIGN.md` as soon as `data-part="result-list"` is emitted in sub-phase 4.1.

## Emission sites touched

This phase covers all four kinds of site the DESIGN distinguishes, which is why it is the phase that
teaches the classification rather than merely applying it.

| DOM concept | `design/index.html` | `engine/legacy.js` | the 23 components | DESIGN row                          |
| ----------- | ------------------- | ------------------ | ----------------- | ----------------------------------- |
| `reslist`   | no                  | no                 | **yes**           | _the components only_               |
| `sugwrap`   | no                  | **yes**            | no                | _the engine only_                   |
| `ep`        | no                  | **yes**            | **yes** — 2 files | _the engine AND the components_     |
| `eppop`     | no                  | —                  | —                 | **computed `className` expression** |

**`eppop` is resolved at its own site, never assumed.** It is one of the four conditional
`className` expressions the DESIGN isolates, and the reason is stated there: a token nothing emits
is a rule already selecting nothing. Before anchoring it, find the expression that produces it and
read what it actually evaluates to. If nothing emits it, that is a finding to record — not a
`data-part` to invent.

## Baseline entries removed

**27 class-anchored selections**, each in the same commit as the migration it corresponds to. No
assertion entries move in this phase — see ACC-11 below, which is the whole point. The baseline goes
195 → 168. The DESIGN writes ≈27; record the actual number.

---

## Sub-phase 4.1 — the result list and the suggestion wrapper

One commit: `refactor(maquette-l02): anchor the result list and suggestion wrapper on data-part`

These two are deliberately paired: one is emitted **only** by a component, the other **only** by the
engine. Doing them in one commit makes the reviewer confront both ends of the boundary at once.

- [ ] **Step 1.** Emit `data-part="result/list"` beside `className="reslist"` at its component site.
- [ ] **Step 2.** Emit `data-part="suggestion/wrap"` beside `class="sugwrap"` in `legacy.js`. The
      engine-side markup is not wasted work: a surface converting out of `legacy.js` into a
      component **keeps** its `data-part` and loses its class. The 51 engine-side tokens are where
      the anchor pays off most, because every rule still on a class is a rule that breaks on the day
      its surface converts — exactly the day someone needs it to hold.
- [ ] **Step 3.** Confirm the names are English and built from words `scripts/code-vocabulary.txt`
      holds — `result`, `list`, `suggestion`, `wrap`. A value is a name someone chose, so
      `CLAUDE.md` § Language applies in full.
- [ ] **Step 4.** Re-anchor the harness selections via `python3 scripts/rename-identifiers.py`, then
      **re-read the diff**, not the tool's summary line.
- [ ] **Step 5.** Remove the corresponding baseline entries in this same commit.
- [ ] **Step 6.** `python3 scripts/check-markup-contracts.py; echo "exit=$?"` → `exit=0`. The
      selection ⇒ emission arm is the one that matters here: it reads all three emission sites, so
      an engine-only token anchored in the harness and emitted nowhere is named rather than missed.
- [ ] **Step 7.** `run.sh` — no violation, hold counts unchanged. Commit.

## Sub-phase 4.2 — the episode row and the episode popover

One commit: `refactor(maquette-l02): anchor the episode row and popover on data-part`

- [ ] **Step 1.** Resolve `eppop` at its site first. Locate the conditional `className` expression
      that produces it and read what it evaluates to in each branch. Record the finding in the
      commit message. Only then decide where its `data-part` is emitted — a computed class is
      emitted by whichever branch runs, so the anchor goes where the element is built, not where the
      string is concatenated.
- [ ] **Step 2.** Emit `data-part="episode"` at both of `ep`'s sites — `legacy.js` and the two
      component files — and `data-part="episode/popover"` at the site resolved in step 1.
- [ ] **Step 3.** Re-anchor the harness selections on `.ep` and `.eppop`. Take care with `.ep` as a
      **prefix**: `.eppop` starts with `ep`, and a careless pattern rewrites both. Re-read the diff
      and confirm each selector kept its own identity.
- [ ] **Step 4.** Remove the corresponding baseline entries in this same commit; the phase total
      across 4.1–4.2 is **27**, and the file must now hold **168**.
- [ ] **Step 5.** **Leave `classList.contains('ep')` exactly as it is.** It is one of the five
      permanent genre exceptions. The distinction is the phase's lesson and it is not cosmetic:
      the selection `.ep` asks _which element is this_, and moves; the assertion
      `classList.contains('ep')` asks _is the episode style applied_, and its SUBJECT is the applied
      style. Moved to a `data-*` it would stay true after the style class is gone — the rule would
      measure less than it does today, which is the opposite of the point.
- [ ] **Step 6.** **ACC-11** — the five genre assertions survive, each with its written reason:

```bash
python3 scripts/classify-rule-anchors.py --exceptions
```

Expected: exactly 5 entries — `h2`, `flux`, `ep`, `radio`, `note` — each printed with a non-empty
reason. A reason-less entry is itself a violation, as it already is for `french-ok` pragmas.

- [ ] **Step 7.** Confirm the guard agrees with the classifier: `check-markup-contracts.py` must not
      refuse `classList.contains('ep')`, because `ep` is not one of the 7 migrated states. If it
      does, the arm's state list is wrong — fix the arm, not the assertion.
- [ ] **Step 8.** `run.sh` — no violation, hold counts unchanged. Commit.

---

## Closing proofs — run all three, record what they printed

```bash
python3 frontend/maquette/oracle.py --check          # no divergence, exit 0
frontend/maquette/harness/run.sh                     # no violation, per-rule hold counts UNCHANGED
make check                                           # exit 0
```

The hold counts carry a specific weight in this phase. `ep` keeps a class assertion while losing a
class selection, so a rule reading both now reads one of each. If its hold count moves, the two ends
were not separated as intended — one of them silently absorbed the other.
