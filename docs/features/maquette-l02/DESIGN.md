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

The total agreed exactly — **and that agreement was two readers sharing one blind spot.** Both read
only QUOTED selectors. Three calls pass theirs as a template literal:

```python
document.querySelector(`[data-lmode="${m}"]`)      # cards.py:82, and two more
```

All three are `data-*`-anchored, so the honest split is **687 total, 281 class, 95 `data-*`**, and
**281 — the only figure this lot works to — is unchanged.** Recording the correction is worth more
than keeping the tidier number that matched.

That is also why `scripts/classify-rule-anchors.py` is a deliverable and not a one-off script: a
naive counter over the same corpus returns 687 calls and **428** class anchors, because it lacks the
anchor-precedence rule (`data-*` beats `#id` beats `.class` within one selector). **The method must
be pinned in a file under review before any number derived from it means anything.**

Spread: **36 of the 47 harness files** that select at all, **133 distinct selectors**, **96
distinct root tokens** — a long tail, not a few hot spots.

### D4's own method under-measures D4's objective, by 54 %

**Found by the classifier D4 asked for, on the day it first ran** — and it is the most consequential
finding of this lot.

D4's method sorts each selector into ONE bucket, its strongest anchor. Its published figures say so:
280 + 276 + 92 + 32 + 4 = 684, one bucket per call. So `#view .swipe` counts as *id-anchored*, and
the `.swipe` disappears from the measurement.

`.swipe` is a style class. **L07 replaces it and that selector falls**, exactly like the 281.

| | Calls |
| --- | --- |
| total selection calls | 696 |
| carrying no class token at all | 264 |
| **class is the ONLY anchor** — what the lot was sized for | **281** |
| **class token behind a stronger anchor** — invisible to the measurement | **151** |
|   ‣ `data`/`id` head, class LEAF (`#view .swipe`, `[data-page=acq] .navbadge`) | 102 |
|   ‣ class ANCESTOR, `data`/`id` inside (`.pipeline [data-pipe]`, `.card[data-nonmedia] .poster`) | 49 |
| **selectors that actually break at L07** | **432** |

<sub>method: strip `${…}` and every `[…]` block, then look for ANY `.token` — not the strongest one</sub>

**So the lot's headline criterion was satisfiable while 151 class dependencies stayed live**, every
one of them producing exactly the unattributable L07 failure — anchor, or style? — that D4 exists to
make impossible. A criterion that can be met without meeting its objective is the vacuous-criterion
defect this repository keeps paying for, and here it sat in the objective's own metric.

**The operator ruled the full scope in** (2026-08-21): 432, not 281. The reason is that the smaller
figure buys a green number and not the thing it stands for.

**And the unit of work changes with it.** A selector leaves the debt when it has NO class token left,
so `.screen.open .fback` is not finished by phase 2 — `fback` belongs to another surface. Counting
by SELECTOR makes phase 2 remove nothing and phase 6 remove 281. The baseline is therefore keyed on
the **class token occurrence**, which is what someone actually migrates, and which has exactly one
owning phase:

| | |
| --- | --- |
| class token occurrences across the harness | **633** |
| state assertions | **61** |
| **baseline entries** | **694**, then **834** once the held selectors entered the instrument |

### The second blind spot: selectors the harness HOLDS rather than passes

Found by dry-running phase 2's rewrite on a scratch copy. Rewriting the 63 baselined `.screen.open`
lines left **24** mentions of `.screen.open` behind — 17 in comments, and **5 live selectors** the
classifier had never counted:

```python
screen_port = ".screen.open .port"                                        # scroll.py:43
("mediasheet-series", '.screen.open[data-key^="mediaSheet:"]', "back")    # audit2.py:155
```

Both readers extract a selector ONLY when it is the literal argument of `querySelector` /
`querySelectorAll` / `locator` / `matches`. A selector stored in a variable, or in a table a helper
walks — `tap(selector)`, `querySelector(sel)` — is invisible to them, and it dies at L07 exactly like
the 633. The 1.3 report had already noted « 32 selection calls pass a variable/expression argument »
and that « both readers exclude them since no string exists at rest »; what was not measured was how
many selector strings those 32 calls consume.

**Measured over the whole harness**: every string literal shaped like a selector (starts with `.`,
`#` or `[`, selector alphabet only, not a Python method call) that sits outside a selection call and
carries a class token — **113 strings, 146 class token occurrences**, 93 of them in tables. That
sweep includes false positives — `.json5` ×5 is a file extension in `settings.py`, `.torrentmate` a
domain fragment — so the figure that enters the instrument is filtered by a RULE rather than a
list: a candidate is a selector only if every class token it carries is emitted by one of the three
design sites, or the string carries selector structure (a combinator, an attribute block, a list).

<sub>the call-argument extractor and the template-literal correction are the same family of defect: a reader that knows one syntactic position for its subject, applied to a corpus that has several</sub>

**This enters the instrument in phase 1, before any migration, and it is the one sanctioned use of
`--write-baseline --allow-additions`.** The ratchet refuses additions by design; a re-classification
of what the instrument reads is the case the flag's help text names, and it happens once, here,
with the count recorded in the commit. Every phase's burn-down is recalibrated after it, and the
held occurrences are tagged apart from the call ones in the baseline so a reader can tell the two
populations — and so a third blind spot, if one exists, has a precedent for how it is absorbed.

### The third, found by the first migration: an escaped quote hides a selection from a raw-text reader

Sub-phase 2.1 rewrote 63 `.screen.open` selections into `[data-part="screen"][data-open]` and the
guard's selection ⇒ emission arm read **55**. The other eight sat in single-line double-quoted
Python strings, where the selector is spelled `[data-part=\"screen\"]`, and that arm read the
harness as RAW TEXT: its pattern never matched the escaped form. Nothing refused it — the arm
counted one fewer, and a count nobody compares is a count nobody reads. The anchor arm counted
all 69 — not because it decoded anything (**nothing in the instrument decodes a string literal**;
a first draft of this paragraph claimed it did, and the fix's own audit showed `literal_eval`,
`unicode_escape` and `codecs` absent from `scripts/`) but because a class token carries no quote
to escape.

Three reader defects in one lot, and they are one family: **a reader that knows one syntactic
position, or one encoding, for its subject, applied to a corpus that has several.** The
template-literal call (backticks), the selector held in a variable (not a call argument), the
escaped quote (an encoding). Each was found by a measurement that disagreed with another — two
readers, a dry run, a tripwire count — never by reading the reader. The instrument's answer is not a decoder — a decoder would be a
first one, and still partial, since a host string can escape the selection CALL's own quotes and
the call extractor then skips it whole (`deck.py:30` is that shape). The answer is a **refusal of
the line**: a `data-part` selection written with an escaped quote is refused with the one-sentence
fix — host it in `'…'` or a triple-quoted string — proved by a mutation the unfixed guard let
through at 62 of 63, exit 0. **And the two readers must agree on every count, or the regeneration
refuses.**

Still open, named by the same fix: the third arm reads a `data-part` selection only as a CALL
argument; one HELD in a variable (`scroll.py:43`) it does not read — the second blind spot, on the
arm that was written after it. The anchor arm has a held pass; the third arm gets the same.

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

Beside the 432 class-carrying selections the harness makes **66 `classList.contains` assertions**. D4's letter
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

The arm lands in **phase 1**, with a baseline file holding **all 633 class token occurrences + 61
assertions = 694 current violations**, generated rather than typed. Every later phase REMOVES entries. The last phase empties it, deletes
it, and the arm's floor becomes a hard zero.

This is the shape `scripts/french-exemption-baseline.json` already uses here, and it exists to stop
the failure mode where a guard is written at the END of a wave — where it has nothing left to fail
on, and therefore was never seen fail.

The five genre assertions are the only permanent entries, each carrying its reason inline.

## Two prerequisites the guard itself imposes, found by reading it

Neither is optional, and neither is visible from the architecture file.

### `data-part` is refused on the day it is written

`check_data_attributes` in `scripts/check-no-french.py` reads every `data-*` NAME against
`scripts/code-vocabulary.txt` and refuses one built from a word the file does not hold. Three words
this lot needs are absent: **`part`**, **`announced`**, **`manifest`**. So `data-part` fails the gate
the first time it appears.

Adding them is one line each, and that is the design — « a French word can only enter by someone
typing it into a file under review. » These are English, they are under review here, and phase 1
adds them before the first attribute is written.

### ACC-12 would be VACUOUS, because nothing reads a `data-*` VALUE

The same arm says so in its own docstring: « The VALUES are not read, and must not be:
`data-go="profil"` names a page, and a page id is an address. »

That is right for `data-go` and wrong for `data-part`. A `data-part` value is not an address — it is
a **structural name someone chose**, which CLAUDE.md puts squarely under the rule (« If a human
typed it to designate something, it is a name »). This lot coins roughly 130 of them at once. With
no arm reading them, ACC-12 passes while measuring nothing about the vocabulary the lot creates —
the same vacuous-criterion defect L01 hit when `check-markup-contracts.py` turned out not to read
`data-region` at all.

Phase 1 therefore extends `check_data_attributes` to read the VALUES of the NAMING attributes
(`data-part`, and `data-region` with it — same status, same hole), while leaving address-valued
attributes (`data-go`, `data-key`, `data-panel`, …) unread, as they must be.

**Extended rather than added, deliberately**: `check_arm_count` holds the arm count against the
module docstring's numbered headings AND against a sentence in `CLAUDE.md`. A new arm costs both
edits; an extended one costs neither, and the docstring change it does need is the one that says
what the arm now reads.

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
| 1 | vocabulary, the guard arm, the full baseline, the dormant arm wired, the `data-part` VALUE arm, the per-rule hold-count capture | 0 migrated |
| 2 | `.screen` / `.sheet` / `.scrim` — and `data-open` on five layers | 69 `.screen` + 78 `.open` + 54 assertions = **201** |
| 3 | `.card` and its parts — `ctitle`, `cbody`, `cfoot`, `poster`, `cov`, … (14 tokens) | 141 + 2 = **143** |
| 4 | `.reslist`, `.sugwrap`, `.ep`, `.eppop`, … (7 tokens) | 46 + 0 = **46** |
| 5 | filters and settings — `fr`, `fn`, `fk`, `fs`, `settingrow`, `seg`, `sechead`, … (13 tokens) | 74 + 2 = **76** |
| 6 | the tail, 94 of its occurrences held in variables — then the baseline is emptied and deleted | 365 + 3 = **368** |

Baseline: **834** → 633 → 490 → 444 → 368 → **0** — 140 of the 834 are selectors the harness holds in
variables and tables, found by the second blind spot and tagged `held` in the file. The counts are token OCCURRENCES, not selectors:
one selector can owe work to two phases, and only the occurrence has a single owner.

## Risks, and what answers each

| Risk | Answer |
| --- | --- |
| An attribute changes rendering | the oracle, `--check` green at every phase gate |
| A rule is re-anchored onto a value nothing emits | the arm's selection ⇒ emission direction |
| A boolean attribute renders as `"false"` and matches always | the `\|\| undefined` arm, plus one rule mutation-tested against it |
| A rule keeps its hold count while measuring nothing | the full 50-rule suite at UNCHANGED hold counts, per phase |
| The guard is written where it cannot fail | it lands in phase 1 with 694 live violations |
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

**ACC-01 — zero class TOKENS remain in any rule selector**

> **Rewritten after the classifier measured D4's blind spot.** The first version asked for zero
> *class-anchored* calls, which D4's one-bucket method makes true while 151 selectors still carry a
> class token behind a stronger anchor — and every one of them falls at L07. The criterion now reads
> the thing it is for.

```bash
python3 scripts/check-markup-contracts.py; echo "exit=$?"
python3 scripts/classify-rule-anchors.py --tokens
```
Expected: `exit=0`, and `0 class token occurrences` over `harness/*.py`. On `f7e8073f` the same
command reads **633**.

**ACC-02 — the D4 classification, re-run by a reader that is not the guard**

```bash
python3 scripts/classify-rule-anchors.py --summary; echo "exit=$?"
```
Expected: `class 0` AND `0 class token occurrences`, with `exit=0`. **The total must still be the
total** — 696 calls on today's tree, which includes the nine `attrs.py` adds. A classifier that
stopped SEEING calls would also report zero class anchors, and that is exactly how this lot's first
measurement read 684: three template-literal selectors were invisible to it, and 151 class tokens
were invisible to the one-bucket rule.

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

> **Rewritten before it could be run.** The first version mutated `data-part="card/title"` in
> `resolution.tsx` and asserted `count == 1`. That file emits `ctitle` TWICE (`:121`, `:195`) and
> `legacy.js` twice more, so the precondition abandons — and had it not, renaming one emitter of
> four proves nothing: the other three still emit the value and the arm stays green. **A
> half-moved-contract mutation needs a target with exactly ONE emitter.** Forty tokens qualify;
> `.reslist` is the strongest — one emitter in `screens/add.tsx`, selected 15 times.

```bash
F=frontend/maquette/design/src/screens/add.tsx; cp "$F" /tmp/l02-acc04.bak
python3 -c "
import pathlib
p = pathlib.Path('$F'); t = p.read_text()
old = 'data-part=\"result/list\"'
assert t.count(old) == 1, f'{t.count(old)} occurrences — mutation ABANDONED'
p.write_text(t.replace(old, 'data-part=\"result/listing\"'))"
python3 scripts/check-markup-contracts.py; echo "exit=$?"
cp /tmp/l02-acc04.bak "$F"
```
Expected: `exit=1`, naming `result/list` as selected by the harness and emitted by no source, and
naming at least one of the 15 harness calls that now select nothing. This is the three-ends defect
caught from the markup end.

**ACC-05 — the guard FALLS on `data-open={x}` written without `|| undefined`**

> **Same defect, same fix.** `sheet.tsx` gains the idiom at TWO sites — the scrim and the sheet — so
> a `count == 1` precondition abandons there too. The mutation replaces the FIRST occurrence and
> asserts the count it actually expects.

```bash
F=frontend/maquette/design/src/components/sheet.tsx; cp "$F" /tmp/l02-acc05.bak
python3 -c "
import pathlib
p = pathlib.Path('$F'); t = p.read_text()
old = 'data-open={open || undefined}'
assert t.count(old) == 2, f'{t.count(old)} occurrences — mutation ABANDONED'
p.write_text(t.replace(old, 'data-open={open}', 1))"
python3 scripts/check-markup-contracts.py; echo "exit=$?"
cp /tmp/l02-acc05.bak "$F"
```
Expected: `exit=1`, naming `sheet.tsx`, its line, and `data-open`. One site is enough here, because
this arm reads each emission independently — unlike ACC-04's, which reads a contract that any
surviving emitter satisfies.

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

**ACC-08 — the suite is green at UNCHANGED per-rule hold counts**

> **Rewritten: the first version could not be executed.** It named `run.sh`, and `run.sh` captures
> each rule's output into `out="$(python3 …)"` and prints it **only on failure**. A passing rule's
> `N rules EXECUTED — no violation` line never reaches the log, so « unchanged hold counts » was not
> obtainable from the command the criterion named. It would have been recorded « passed » on the
> strength of a line that says only how many rules ran.
>
> It also said `50 rule(s)`. `run.sh` globs `harness/*.py` minus `common.py`, and this lot adds
> `attrs.py` — so the suite is **51** from phase 1 onward, and the criterion would have failed on
> its own arithmetic at the first gate.

```bash
python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json
```
Expected: `51 rules, no violation`, and `0 rule(s) changed hold count`. The per-rule capture is a
phase-1 deliverable — the wave needs it at all six gates.

The baseline it compares against is recorded on `f7e8073f` before any migration, where the suite
reads **`harness: 50 rule(s), no violation.`** and the oracle reads **`82 states x 33 regions, 2706
measurements`, `reference taken at 59931d45`, `no divergence`** — run and captured on 2026-08-21,
not assumed.

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

**ACC-12 — no French entered the vocabulary, and something actually READS it**

> **Rewritten: the first version was vacuous.** `check-no-french.py` reads `data-*` NAMES and
> deliberately not their values, so `python3 scripts/check-no-french.py` would have exited 0 over
> roughly 130 new `data-part` values it never looked at. See § « Two prerequisites the guard itself
> imposes ».

```bash
python3 scripts/check-no-french.py; echo "exit=$?"
python3 scripts/check-no-french.py --counts | grep 'data-part values'
```
Expected: `exit=0`, and a non-zero count of `data-part` VALUES examined — the second line is the
criterion. A gate proves what it reads, so the number it read is the evidence, not the exit code.

Mutation: rename one `data-part` value to a French word, confirm `exit=1` naming the file, the line
and the word, restore.

**ACC-13 — the whole gate**

```bash
make check; echo "exit=$?"
```
Expected: `exit=0`.
