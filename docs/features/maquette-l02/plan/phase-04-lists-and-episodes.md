# Phase 4 — `.reslist`, `.sugwrap`, `.ep`, `.eppop`

## Gate

Phase 3 must have produced, all committed:

- `data-part="card"`, `card/title`, `card/body`, `card/foot`, `card/overview`, `card/poster` emitted at
  **both** the engine and the component sites;
- the 2 `noposter` assertions moved to `hasAttribute('data-no-poster')`;
- `frontend/maquette/anchor-baseline.json` down to **490 entries** (633 − 143);
- ACC-03 recorded as `exit=1` naming `cards.py`, its line and `.ctitle`;
- both `ctitle` sites in `resolution.tsx` anchored (phase 3 owes nothing else on ACC-04).

**ACC-04 is CLAIMED BY THIS PHASE**, not inherited. It needs a single-emitter target, and phase 3's
card family has none — every member straddles the engine boundary, so a surviving emitter keeps the
arm green. `.reslist` has exactly one emitter (`screens/add.tsx`) and is selected 17 times; run
ACC-04 from `DESIGN.md` as soon as `data-part="result/list"` is emitted in sub-phase 4.1.

## Measured on the committed baseline, not estimated

**43 token occurrences**: `.reslist` 17, `.ep` 8, `.sugwrap` 6, `.season` 4, `.eppop` 4,
`.eprow` 2, `.eps` 2. By file: `audit2.py` 8, `pop.py` 8, `screens.py` 7, `surfaces.py` 6,
`bridge.py` 3, `inter.py` 3.

Emitters: `.reslist` components only (1 site, `add.tsx`); `.sugwrap` engine only; `.ep`, `.eprow`,
`.eps`, `.season` straddle. **`.eppop` has NO static emitter** — no `className=`/`class=` literal
carries it anywhere. It is one of the four computed tokens; its four selections either reach a
dynamically composed class or select nothing. Resolve it at its site before anchoring, and if
nothing emits it, say so: a selector nothing emits is a rule already selecting nothing, and the
selection ⇒ emission arm will name it the moment it is moved onto `data-part`.

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

**46, and the first draft's two sub-phases could remove 36.** `eprow`, `eps` and `season` were named
by nothing — 10 occurrences with no owner. Measured on the committed 834-entry baseline, call + held:

| Sub-phase | Removes | Tokens |
| --- | --- | --- |
| 4.1 | **24** | `.reslist` 17 · `.sugwrap` 7 (1 held) |
| 4.2 | **12** | `.ep` 8 · `.eppop` 4 (no static emitter — resolved at its site first) |
| 4.3 | **10** | `.eprow` 2 · `.eps` 4 (2 held) · `.season` 4 |

24 + 12 + 10 = **46**. No assertion moves in this phase — see ACC-11. The baseline goes
**490 → 466 → 454 → 444**. **`wrap` is absent from `scripts/code-vocabulary.txt`** (measured
2026-08-21), so 4.1's `suggestion/wrap` fails the vocabulary arm until the word is added in the same
commit — one line, sorted, in the DESIGN section.

> **Never the Edit tool on `legacy.js`.** A formatter hook reformats the whole engine (33 000 lines) on
> the first `Edit`, silently in a `--stat`; 3.2 reverted and re-applied by script. Every engine change
> is applied by a script that rewrites exactly the bytes meant, then `git diff --stat`-checked.

> **`py_compile` every harness file after every rewrite.** A `data-part` value carries a `/`, so its
> selector needs quotes; substituted into a single-line double-quoted Python string, the raw `"`
> breaks the file — and the guard, the baseline, the oracle and the classifier all stayed green over
> two unparseable rule files in 4.1. `python3 -m py_compile frontend/maquette/harness/*.py` takes two
> seconds and must print nothing, before any proof.

> **Rewrite per string token, never per line.** The baseline's `line` is where the string literal
> BEGINS; in a multi-line `"""…"""` JS block the token can sit lines below, and a per-line
> rewrite aborts there (3.1 ran one, discarded it, and redid its 79 through `tokenize`). For each
> entry, locate the string token starting at (file, line), rewrite your class token inside it, and
> reconcile the whole-corpus count of your tokens against the baseline's before you start. Then
> re-host any single-line double-quoted string now carrying `[data-part=\"` in `'…'` or a
> triple-quoted string — the guard refuses the escaped shape.

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
      across 4.1–4.2 is **46** (3 of them held), and the file must now hold **444**.
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

## Sub-phase 4.3 — the episode row, the episode set and the season

One commit: `refactor(maquette-l02): anchor the episode row, set and season on data-part`

Three tokens the first draft never named, all straddling the engine boundary.

| Token | `data-part` | Emitted by |
| --- | --- | --- |
| `.eprow` | `episode/row` | engine + components |
| `.eps` | `episode/set` | engine + components — the list an episode row belongs to (2 of 4 held) |
| `.season` | `season` | engine + components — `details.season` in `media.tsx` |

- [ ] **Step 1.** Emit each anchor beside its class at every site, engine included.
- [ ] **Step 2.** Re-anchor the 10 occurrences by literal replacement with asserted counts, reading
      them (held included) from the classifier's `--baseline`.
- [ ] **Step 3.** `--write-baseline` → `10 removed`, landing at **444**. Guard exit 0.
- [ ] **Step 4.** `run.sh` / hold counts — no violation, unchanged. Commit.

## Closing proofs — run all three, record what they printed

```bash
python3 frontend/maquette/oracle.py --check          # no divergence, exit 0
frontend/maquette/harness/run.sh                     # no violation, per-rule hold counts UNCHANGED
make check                                           # exit 0
```

The hold counts carry a specific weight in this phase. `ep` keeps a class assertion while losing a
class selection, so a rule reading both now reads one of each. If its hold count moves, the two ends
were not separated as intended — one of them silently absorbed the other.
