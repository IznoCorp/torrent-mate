# L02 — test anchors move to `data-*`

> Lot **L02** of `docs/reference/frontend-architecture.md` (BINDING) — Phase 0.
> `depends on L01`, whose dependency is satisfied: the recorded oracle landed in #467.
> Serves `docs/reference/product-intent.md` **§15** (the maquette is the visual reference; it is
> modified first and verified with its harness).

## Why this lot exists, and why it is second

The harness catches elements by their **style class**. `cards.py:142`, unedited:

```js
[...document.querySelectorAll('.card')].filter(visible).map(c => ({
  title: c.querySelector('.ctitle')?.textContent || '',
  body:  c.querySelector('.cbody'),
  poster: c.querySelector('.poster'),
}))
```

`.card`, `.ctitle`, `.cbody`, `.poster` are names the STYLESHEET owns. The day L07 converts that
surface to utilities they stop existing, and the rules that read them fall — with **no way to
attribute the failure**: anchor, or style? Separated, each failure has one possible cause. That is
D4's whole argument, and it is why the anchors move BEFORE the visual language, not during it.

## What it is, in one sentence

Every rule selection anchors on a `data-*` contract or a structural id, and a guard refuses the
next one that does not.

## The measurement, reproduced rather than quoted

D4 records 684 selection calls, 280 class-anchored. Re-run today over `harness/*.py` with the
method D4 states — extract the string argument of every `querySelector|querySelectorAll|locator|
matches` call and classify it:

| Anchor | D4 | Re-measured |
| --- | --- | --- |
| CSS class | 280 | **281** |
| id | 276 | 278 |
| `data-*` | 92 | 92 |
| bare tag | 32 | 32 |
| role | 4 | 1 |
| **total** | **684** | **684** |

The total agrees exactly; the class/id/role split differs by a handful because this classifier
recognises `[role=…]` less generously than D4's did. **281 is the figure this lot works to**, and
the difference is recorded rather than smoothed over.

Spread: **36 of the 47 harness files** that select at all, **133 distinct selectors**, **96
distinct root tokens** — a long tail, not a few hot spots.

### Where the markup lives — measured over all 114 tokens, not a sample

Two earlier passes were wrong, and both are recorded because the correction is the finding. The
first sampled nine classes, saw `legacy.js` emitting almost none of them, and concluded the
migration was a component-tree job. The second counted only two emission sites and left 17 tokens
unattributed. **There are three sites**, and `frontend/maquette/design/index.html` — the
application shell, 47 `class=` in 374 lines — is the one both passes missed.

Of the 114 distinct class tokens the 281 calls select on:

| Emitted by | Tokens | Examples |
| --- | --- | --- |
| the components only | 48 | `sact`, `reslist`, `settingrow`, `seg`, `body`, `open`, `field` |
| **the engine AND the components** | **34** | `card`, `ctitle`, `cbody`, `cfoot`, `poster`, `cov`, `chip`, `tile`, `sechead`, `ep` |
| **the engine only** | **17** | `fr`, `fn`, `fk`, `fs`, `sugwrap`, `dlgbtn`, `deck`, `manifest`, `nm`, `sel` |
| the shell (`index.html`) only | 9 | `bottombar`, `loginscreen`, `loginsubmit`, `splashbar`, `dlg`, `hbtn`, `installgo` |
| the shell and the components | 2 | `port`, `screen` |
| computed `className` expressions | 4 | `announced`, `eppop`, `modified`, `selbar` |

<sub>method: resolve every `.token` outside a `[…]` in the 281 selectors, then count
`className=`/`class=` emissions of each across `index.html`, `engine/legacy.js` and the 23
non-engine sources</sub>

**51 of 114 tokens — 45 % — have an end inside the dying engine**, and the lot must move those
too. That is not wasted work against D5, it is the argument FOR doing it now: a surface converting
out of `legacy.js` into a component KEEPS a `data-part` anchor and loses a class anchor. Every rule
still anchored on a class is a rule that breaks on the day its surface converts — which is exactly
the day someone needs it to hold.

**Eleven have an end in the shell**, which no lot converts and which therefore keeps its
`data-part` for good. The four computed ones are conditional `className` expressions and are each
resolved at their own site — never assumed, because a token nothing emits is a rule already
selecting nothing.

## The vocabulary

One attribute, **`data-part`**, its value namespaced by `/` — the convention L01 already
established with `data-region="library/body"`.

```
data-part="card"          the container, selected as a set
data-part="card/title"    a part of that container
data-part="card/poster"
```

The namespace names the **owning DOM concept** (`card`, `screen`, `sheet`, `filter`, `setting`);
the leaf names the **role**. A value is a name someone chose, so §Language applies in full:
English, built from words `scripts/code-vocabulary.txt` holds.

**One attribute rather than ~130 flat ones**, and that is the reason: one attribute name is one
guard predicate and one vocabulary. A flat `data-card-title` scheme makes the guard hold a list of
permitted attribute names, and nothing stops a 131st appearing unseen.

**The style class STAYS beside it.** `className="ctitle" data-part="card/title"` — the class still
styles. L07 removes it. Keeping both is not duplication, it is the separation this lot exists to
create.

## The states

Boolean attributes, no value: `data-open`, `data-no-poster`, `data-empty`, `data-blocked`,
`data-announced`, `data-in-library`, `data-shown`.

```js
document.querySelector('[data-part="sheet"][data-open]')   // selection
el.hasAttribute('data-open')                               // assertion
```

### The React trap, and it gets an arm rather than a sentence

`data-open={false}` is believed **not** to disappear: React passes `data-*` through as strings, so
it should render `data-open="false"` — and `[data-open]` would then match **always**, sending the
rule green while it measures nothing. That is this repository's most expensive defect class, so the
belief is not load-bearing: **ACC-06 demonstrates it in the live document before the arm that
depends on it is written.** If the demonstration says otherwise, the arm changes and this paragraph
changes with it.

The imposed idiom is `data-open={isOpen || undefined}`, and a guard arm checks it at the source.
A rule nobody can break by accident is worth more than a rule everybody is told to remember.

### What migrating the anchors already revealed

`.screen` heads **30 of the 281** — the largest cluster in the lot. `open` in `.screen.open` is
**static**: the five screens write it into a literal (`className="screen open"` in `add.tsx:155`,
`resolution.tsx:316`, `media.tsx:385`, `profile.tsx:85`, `releases.tsx:48`), because a mounted
screen *is* open. Only `sheet.tsx:84,95` makes it conditional.

So one class name carried two different meanings, and 30 calls carried a redundant state token.
After migration the selectors are shorter AND more honest:

| Before | After | What it means |
| --- | --- | --- |
| `.screen.open` | `[data-part="screen"]` | a screen is mounted |
| `.sheet.open` | `[data-part="sheet"][data-open]` | the sheet is currently shown |

## The assertions are IN SCOPE, minus five

Beside the 281 selections the harness makes **66 `classList.contains` assertions**. D4's letter
covers selection only. Its intent does not: an assertion on a style class breaks at L07 exactly
like a selection does.

The split decides it — **61 assert a STATE**, 5 assert a GENRE:

| Kind | Classes | Count | Disposition |
| --- | --- | --- | --- |
| state | `open` (54), `noposter` (2), `show`, `in_library`, `fempty`, `fblocked`, `announced` | **61** | move to the boolean `data-*` attributes above |
| genre | `h2`, `flux`, `ep`, `radio`, `note` | **5** | **stay on the class**, listed with their written reason |

The five stay because the assertion's SUBJECT is the applied style. Moving them to a `data-*`
would make them true even after the style class is gone — the rule would measure less than it does
today, which is the opposite of the point.

Leaving the 61 behind was the alternative and it is worse than doing nothing: `.screen.open`
forces `data-open` to exist anyway for the selection side, so 54 assertions would go on reading
the class next to it. **One state, two sources of truth, free to diverge** — the three-ends defect,
re-created by the very lot written to end it.

## The guard

A new arm in **`scripts/check-markup-contracts.py`**. Not a second file beside it — the
architecture file forbids that explicitly, and three independent reasons agree:

- it is **already in `make check` (`Makefile:86`) and already in CI (`.github/workflows/ci.yml:139`)**;
- it is **149 lines carrying one arm**, while `oracle.py` is **972** against a hard ceiling of 1000;
- it is already Python, and the new corpus (`harness/*.py`) is Python.

What the arm reads and refuses:

| Refusal | Corpus |
| --- | --- |
| a selector anchored on a CSS class | the string argument of `querySelector(All)` / `locator` / `matches` in `harness/*.py` |
| `classList.contains('<state>')` for any of the 7 migrated states | `harness/*.py` |
| a `data-part` value the harness selects and no source emits | selection ⇒ emission, the three-ends defect |
| `data-<state>={x}` written without `\|\| undefined` | the components, for the React trap above |

**Written where it says what it reads.** `check-markup-contracts.py`'s docstring today describes
one question over one corpus. It gains a second corpus, and the docstring says so per arm — the
file must not become a place where a reader cannot tell what is actually measured.

### The burn-down is a ratchet, not a promise

The arm lands in **phase 1**, with a baseline file holding **all 281 + 61 current violations**,
generated rather than typed. Every later phase REMOVES entries. The last phase empties it, deletes
it, and the arm's floor becomes a hard zero.

This is the shape `scripts/french-exemption-baseline.json` already uses here, and it exists to stop
the failure mode where a guard is written at the END of a wave — where it has nothing left to fail
on, and therefore was never seen fail.

The five genre assertions are the only permanent entries, each carrying its reason inline.

## The dormant arm — found while instructing this lot, and fixed by it

`oracle.py --contracts` **already holds half of D4**: it refuses a `regions.json` region anchored
on a CSS class, and `oracle.py:265` argues for it in the right terms — « Checked here rather than
only in an ACCEPTANCE criterion: a criterion runs once, a rule runs for ever. »

**It runs nowhere.** Not `make check`, not CI, not `run.sh` — whose only reference to the file
(`run.sh:140`) invokes `--check`. Grepping `oracle.py` across `Makefile`, `.github/workflows/`,
`run.sh` and `scripts/` returns that one line and three comments.

Run by hand today it passes — `33 regions declared, 18 of them anchored on data-region`, exit 0 —
so nothing is broken. But a rule that executes only when someone thinks of it is the exact
condition `run.sh`'s own header was written about, one tier up.

L02 wires `oracle.py --contracts` into `make check` and into CI. It is static: no browser, no
`library.db`, ~0.1 s. It therefore also satisfies the constraint that killed `arrivals.py` from the
per-PR tier.

## What it does NOT do

- **It changes no rendering.** Adding an attribute moves nothing, and this is checkable rather than
  asserted: the stylesheet's only attribute selectors are `[aria-checked]`, `[aria-selected]`,
  `[aria-pressed]`, `[aria-current]`, `[data-theme]` and `[data-depth]` — none on `data-part` or on
  any of the 7 state attributes. The oracle proves it per phase.
- **It removes no style class.** That is L07.
- **It does not re-anchor `regions.json`.** Its 33 regions are already clean: 18 on `data-region`,
  15 on structural ids, **0 on a class**. D4 permits ids.
- **It adds no accessible role.** Roles become a legitimate anchor after L03; the markup cannot
  carry them yet (0 `<main>`, 0 `tabindex`, 13 `role=`).
- **It touches no backend, and derives no app code.** `frontend/src` is untouched.

## Order of work

Six phases. The three ends of a `data-part` contract live in the same surface, so they move in the
same commit — the phases are cut by DOM concept, never by file kind.

**A concept's markup can sit on both sides of the engine boundary** (32 tokens are emitted by
`legacy.js` AND by a component). Cutting by concept is what keeps those together: cutting by file
would split one contract across two commits, which is the half-moved state this lot exists to make
impossible.

| Phase | Subject | Approx. calls |
| --- | --- | --- |
| 1 | vocabulary, the guard arm, the full baseline, the dormant arm wired | 0 migrated |
| 2 | `.screen` / `.sheet` / `.scrim` — and the static-`open` correction | 30 + 54 assertions |
| 3 | `.card` and its parts — `ctitle`, `cbody`, `cfoot`, `poster`, `cov` | ≈61 |
| 4 | `.reslist`, `.sugwrap`, `.ep`, `.eppop` | ≈27 |
| 5 | filters and settings — `fr`, `fn`, `fk`, `fs`, `settingrow`, `seg`, `sechead` | ≈35 |
| 6 | the tail, then the baseline is emptied and deleted | ≈128 |

## Risks, and what answers each

| Risk | Answer |
| --- | --- |
| An attribute changes rendering | the oracle, `--check` green at every phase gate |
| A rule is re-anchored onto a value nothing emits | the arm's selection ⇒ emission direction |
| A boolean attribute renders as `"false"` and matches always | the `\|\| undefined` arm, plus one rule mutation-tested against it |
| A rule keeps its hold count while measuring nothing | the full 50-rule suite at UNCHANGED hold counts, per phase |
| The guard is written where it cannot fail | it lands in phase 1 with 342 live violations |
| Markup added to `legacy.js` is thrown away with the engine | it is not: a converting surface KEEPS its `data-part` and loses its class. The 51 engine-side tokens are where the anchor pays off most |
| A token nothing emits is a rule already selecting nothing | the 17 unresolved tokens are each traced to a computed `className` or to `index.html`, never assumed |
| 96 root tokens named ad hoc across six phases | the vocabulary rules above are fixed in phase 1, before any migration |

## Carried, not hidden

Two things found while instructing this lot. Neither belongs to it; both are recorded so they are
not found again from scratch.

- **`docs/features/tech-debt-2/`** has sat unarchived since #443, holding a lone `DESIGN.md`.
- **`media.tsx:708`** carries `data-fkind={isFilm ? "Film" : "Série"}` — a French value someone
  chose to designate a kind, neighbouring B-036. No arm reads it.

## ACCEPTANCE

Every criterion is an executable command with its expected output, per
`docs/reference/feature-lifecycle.md`. Each is filled in with what it ACTUALLY printed as its
phase lands — never with what it was meant to print.

Browser criteria assume the prototype is built and copied where the harness reads it;
`frontend/maquette/harness/run.sh` does that itself.

> **The independent classifier lives in `scripts/`, not in `harness/`.** `run.sh:72` globs
> `harness/*.py` and runs every file but `common.py` as a rule, so a tool dropped there would be
> executed as one. It is also deliberately a SECOND reader: the guard proves what it reads, and a
> classification cross-checked only by the guard that produced it proves nothing.

**ACC-01 — zero class-anchored selection calls remain**

```bash
python3 scripts/check-markup-contracts.py; echo "exit=$?"
```
Expected: a line reporting `0 class-anchored selection call` over `harness/*.py`, and `exit=0`.

**ACC-02 — the D4 classification, re-run by a reader that is not the guard**

```bash
python3 scripts/classify-rule-anchors.py --summary; echo "exit=$?"
```
Expected: `684 selection calls` with `class 0`, and `exit=0`. The total must still be 684: a
classifier that stopped SEEING calls would also report zero class anchors.

**ACC-03 — the guard FALLS on a re-introduced class anchor, and names it**

```bash
F=frontend/maquette/harness/cards.py; cp "$F" /tmp/l02-acc03.bak
python3 -c "
import pathlib
p = pathlib.Path('$F'); t = p.read_text()
old = '[data-part=\"card/title\"]'
assert t.count(old) >= 1, f'{t.count(old)} occurrences — mutation ABANDONED'
p.write_text(t.replace(old, '.ctitle', 1))"
python3 scripts/check-markup-contracts.py; echo "exit=$?"
cp /tmp/l02-acc03.bak "$F"
```
Expected: `exit=1`, and the output names `cards.py`, its line, and the selector `.ctitle`.

**ACC-04 — the guard FALLS on a half-moved contract**

```bash
F=frontend/maquette/design/src/screens/resolution.tsx; cp "$F" /tmp/l02-acc04.bak
python3 -c "
import pathlib
p = pathlib.Path('$F'); t = p.read_text()
old = 'data-part=\"card/title\"'
assert t.count(old) == 1, f'{t.count(old)} occurrences — mutation ABANDONED'
p.write_text(t.replace(old, 'data-part=\"card/heading\"'))"
python3 scripts/check-markup-contracts.py; echo "exit=$?"
cp /tmp/l02-acc04.bak "$F"
```
Expected: `exit=1`, naming `card/title` as selected by the harness and emitted by no source.
`resolution.tsx:121` is one of the four emitters of `.ctitle` — two there, two in `legacy.js`.
This is the three-ends defect, caught from the markup end.

**ACC-05 — the guard FALLS on `data-open={x}` written without `|| undefined`**

```bash
F=frontend/maquette/design/src/components/sheet.tsx; cp "$F" /tmp/l02-acc05.bak
python3 -c "
import pathlib
p = pathlib.Path('$F'); t = p.read_text()
old = 'data-open={open || undefined}'
assert t.count(old) == 1, f'{t.count(old)} occurrences — mutation ABANDONED'
p.write_text(t.replace(old, 'data-open={open}'))"
python3 scripts/check-markup-contracts.py; echo "exit=$?"
cp /tmp/l02-acc05.bak "$F"
```
Expected: `exit=1`, naming `sheet.tsx` and `data-open`.

**ACC-06 — the React trap is DEMONSTRATED in the browser, not quoted from documentation**

```bash
python3 frontend/maquette/harness/attrs.py; echo "exit=$?"
```
Expected: `exit=0`, having asserted in the live document that a `data-*` attribute given `false`
renders the string `"false"` and is matched by `[data-…]`, while one given `undefined` is absent
and is not. Without this, the `|| undefined` arm rests on a belief about React.

**ACC-07 — the oracle is green: the wave moved no pixel**

```bash
python3 frontend/maquette/oracle.py --check; echo "exit=$?"
```
Expected: `no divergence`, `exit=0`.

**ACC-08 — the 50-rule suite is green at UNCHANGED hold counts**

```bash
frontend/maquette/harness/run.sh 2>&1 | tail -3
```
Expected: `harness: 50 rule(s), no violation.` — the same rule count as on `main` before the wave,
with per-rule hold counts equal. A rule that still passes while holding FEWER things has stopped
measuring, and the count is the only thing that says so.

**ACC-09 — the dormant arm now runs automatically**

```bash
make check 2>&1 | grep -c "regions declared"
```
Expected: `1`. On `main` before this wave the same command prints `0`.

**ACC-10 — the baseline is empty and gone**

```bash
ls frontend/maquette/anchor-baseline.json; echo "exit=$?"
grep -c "anchor-baseline" scripts/check-markup-contracts.py
```
Expected: `No such file or directory`, `exit=1`, and `0` references left in the guard — its floor
is a hard zero in code, not a file that happens to be empty.

**ACC-11 — the five genre assertions survive, each with its written reason**

```bash
python3 scripts/classify-rule-anchors.py --exceptions
```
Expected: exactly 5 entries — `h2`, `flux`, `ep`, `radio`, `note` — each printed with a non-empty
reason. A reason-less entry is itself a violation, as it already is for `french-ok` pragmas.

**ACC-12 — no French entered the vocabulary**

```bash
python3 scripts/check-no-french.py; echo "exit=$?"
```
Expected: `exit=0`.

**ACC-13 — the whole gate**

```bash
make check; echo "exit=$?"
```
Expected: `exit=0`.
