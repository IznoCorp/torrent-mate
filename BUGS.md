# Bug register

Every defect the operator reports lands here **the moment it is reported**, before any work
starts. A bug leaves this file only through the `Fixed` column, and only with a rule that fails
when the defect comes back.

## Rules of this file

1. **Reported = written down.** No triage, no judgement first. An unwritten bug is a bug that
   comes back a third time.
2. **One bug is closed at a time**, and the operator confirms the fix before the next one starts.
3. **A fix is not a fix without a rule that bites.** The rule is mutation-tested: break the
   behaviour on purpose, confirm the rule falls and names the right defect, restore. A closing
   entry names the script and the mutation.
4. **The rule must cover the path the operator actually walks.** Several bugs below survived a
   green harness because the rule drove a named state instead of the real journey — a cold load,
   a real finger, a real browser menu.
5. **Repeats are counted.** `Reported` records every time the operator has had to say it again.
   A count above one is a failure of this register, not of memory.

## Status vocabulary

| Status       | Means                                                          |
| ------------ | -------------------------------------------------------------- |
| `open`       | Reproduced and diagnosed, not yet fixed.                       |
| `fixing`     | Being worked on right now. Exactly one bug may hold this.      |
| `to confirm` | Fixed, rule green, mutation proven — waiting for the operator. |
| `fixed #NNN` | Fixed on a branch, in the pull request named — not on `main` yet. |
| `closed`     | Operator confirmed on a real device.                           |

---

> **What is open is in the table below, and only there.** This banner used to carry a count of
> its own; it read « two » while three entries already said `open`, because a summary that is
> written once and never recounted stops being true on the next line added. The `Status` column
> is the answer. What belongs here is only what the column cannot say — WHY an entry is still
> open when its diagnosis looks finished:
>
> **B-024** is diagnosed **latent and unreachable**: the census of `[data-go]` producers shows
> every one of them renders into `#view`, which sits under every layer, so none can be tapped
> while a layer is open — real, with no path to it. **B-030** is a defect of the maquette's
> embedded DATA (87 of 345 sheets carry no genre and no cast), not of the drawing, and the
> operator has excluded it from the batch closure. Neither was ever `to confirm`.

## Open

| ID    | Defect                                                | Reported    | Status       |
| ----- | ----------------------------------------------------- | ----------- | ------------ |
| B-019 | Many media sheets have lost their visual              | 1×          | `closed`     |
| B-020 | Actor portraits on media sheets are broken            | 1×          | `closed`     |
| B-021 | Signing out leaves the bottom panel on top            | 1×          | `closed`     |
| B-022 | « Voir mes suivis » in the add search is inert        | 1×          | `closed`     |
| B-023 | Médiathèque « Incomplets »: every visual broken       | 1×          | `closed`     |
| B-013 | The drawer's entries lead nowhere                     | 2×          | `closed`     |
| B-014 | The drawer's current entry is unreadable              | 1×          | `closed`     |
| B-015 | Back reopens the drawer that was just closed          | 1×          | `closed`     |
| B-016 | Swiping a row right, then left, makes it jump         | 1×          | `closed`     |
| B-017 | Closing a panel sends the list back to its top        | by mutation | `closed`     |
| B-018 | On a desktop, dragging a row opens the panel          | 1×          | `closed`     |
| B-024 | `data-go` settles ONE history entry, layers pile      | by review   | `open`       |
| B-025 | The screen half of the `data-go` fix has no Back rule | by review   | `closed`     |
| B-026 | A silent `catch {}` can let URL and UI disagree       | by review   | `closed`     |
| B-027 | `resync.py` trusts `t:` first-match + naive braces    | by review   | `closed`     |
| B-028 | `resync.py` says « 0 correction » for unknown titles  | by review   | `closed`     |
| B-029 | Counter rule misses suffix drift (« 1 » in « 11 »)    | by review   | `closed`     |
| B-030 | 87 library sheets carry no genre and no cast          | by rule     | `open`       |
| B-031 | « Réessayer » on every error surface is inert          | by review   | `to confirm` |
| B-032 | The harness's data-scenario dial selects the wrong one | by review   | `to confirm` |
| B-033 | `test_locks_tmp_orphans` is flaky under xdist          | by rule     | `open`       |
| B-034 | `TestQuickMode` reads a foreign `os.scandir` caller    | by gate     | `open`       |
| B-035 | `test_continues_on_per_file_error` writes no backup    | by gate     | `open`       |
| B-036 | Two state ids are still French: `panne`, `groupe`      | by review   | `open`       |
| B-037 | `arrivals.py` reads a French global nothing defines      | by review   | `open`       |
| B-038 | `arrivals.py` reads `empty` and asserts nothing on it    | by mutation | `open`       |
| B-039 | `actions.py` prints `.freshtag` presence, asserts nothing | by mutation | `open`       |
| B-040 | Names in files no arm reads: `sweep.py`, a region id, `oracle.py` | by review   | `open`       |
| B-041 | `check-frontend-boundaries.py` has no committed test                | by audit    | `open`       |
| B-042 | An orphan `http.server` holds port 8900 on the operator's machine   | by review   | `open`       |
| B-043 | A deep media address lands the 404 page underneath it               | by review   | `fixed #484` |
| B-044 | A 404's address recomposes to `/` after a cold load                 | by review   | `fixed #484` |
| B-045 | `?panel=follows` without its colon is accepted, and fabricates media | by review   | `fixed #484` |
| B-046 | The fallback port moved onto `switchover.py`'s, whose bind error is swallowed | by review | `fixed #484` |
| B-047 | The navigation-failure flag is raised by no guard and read by no rule | by review   | `fixed #484` |
| B-048 | The ninth boundary arm stays green with `addresses.ts` deleted      | by review   | `fixed #484` |
| B-049 | A rule reads the operator's live `acquire.db` and turns red on every cron | by review | `open` |
| B-050 | `check-frontend-boundaries.py` is at 921 lines, 79 from the hard ceiling | by review | `open` |
| B-051 | `toFollows()` carries the page in its query, invisible to the boundaries arm | by review | `open` |
| B-052 | A synthesised follow panel labels a film « Série »                  | by review   | `open`       |
| B-053 | A panel's layer entry is taken by a tab tap on the same layer (revisit) | by review | `open`     |
| B-054 | `data-go="acq"` no longer forces the « now » tab (revisit)           | by review   | `open`       |
| B-055 | The a11y floor measures only the dark theme — light carries 154 findings | by review | `open` |
| B-056 | A `@keyframes` name is French (`splashremplit`), invisible to no-french  | by review | `open` |
| B-057 | `audit2.py`'s R12 silently measures four of five contexts, not five | by review   | `open`       |
| B-058 | commit-msg's AI-attribution match is unanchored, flags quoting prose | by mutation | `open`       |
| B-059 | `check-css-tokens.py` crossed the 1 000-line hard ceiling during L07        | by audit    | `fixed #494` |
| B-060 | The rename tool could not rename a CSS custom property, and reported it as success | by mutation | `fixed #494` |
| B-061 | The oracle cannot see a pseudo-element, so a class that generates nothing reads green | by rule | `open` |
| B-062 | Three markup readers were blind to `cva()` factories, which emit a class name with no `class=` | by gate | `fixed #494` |
| B-063 | The wave's per-phase gate tier runs none of the repository's own guards | by gate | `open` |
| B-064 | R72's mutation recipe names an environment variable no code reads | by review | `open` |
| B-065 | A duplicated `design/frontend/maquette/design/src/` tree is tracked, dead and drifting | by review | `open` |
| B-066 | Two off-scale values sit under a named exemption rather than on the scale | by gate | `open` |
| B-067 | A typed variant shadowed by the unlayered residue is inert, and nothing says so | by review | `open` |
| B-068 | The wave's documentation drifted in forty small places, and one figure family is wrong | by review | `open` |
| B-069 | `legacy.css`'s licence to exist names a decision only an about-to-be-archived doc defines | by review | `open` |
| B-070 | `rename-identifiers.py` passed the 800-line soft ceiling | by gate | `open` |
| B-071 | The design-notes toggle survives the overlay it toggles | by review | `open` |
| B-072 | `build-surface-manifest.py` crashes: its own command no longer runs | by review | `open` |

**B-041 — the newest guard is the only one of its family with nothing to re-run.**
`scripts/check-frontend-boundaries.py` is 515 lines and eight arms, and it landed with L04
(#478). Its pull request reports **twelve mutations, each seen red and restored** — the work was
done. What is missing is that it can be done again: there is no file under `tests/scripts/`, so
the proof exists as a sentence in a merged pull request body and nowhere a gate can reach.

Invariant 11 of `docs/reference/frontend-architecture.md` asks that every change land with a rule
that bites, mutation-tested. A mutation performed once in a session satisfies the letter on the
day and nothing afterwards: the arm that stops biting next month falls silent, and silence is
what this register exists to refuse. **The four closest members of the same family all have
theirs** — `test_check_no_french.py`, `test_check_css_tokens.py`, `test_check_markup_contracts.py`,
`test_check_module_size.py`.

Found by the steward's audit of L04, not by a gate — a guard with no test is invisible to every
guard. **Not fixed here**: the office that found it does not carry code (`docs/reference/frontend-steward.md`),
and the test belongs with whoever wrote the eight arms and knows which mutation each one deserves.

**B-042 — a stray process holds a port nothing in the repository claims.**
A `python3 -m http.server` listens on **8900** on the operator's machine, working directory
`/private/tmp/tm-a11y-probe`, and **no file in this repository mentions that port**. It is the
residue of an accessibility probe launched by hand during L03. Harmless in itself — 9.6 MB — and
reported by the L04 wave, which correctly declined to repair something that was not its own.

It is written here because that report lived only in a merged pull request body, which is the
same defect as B-041 read from the other end: a finding recorded where nothing re-reads it has
not been recorded. The port the harness actually uses is **8899**; `run.sh` starts it and reuses
it deliberately, and that one is not this.

**B-043 to B-048 — what L05 left on `main`, and why they are here rather than only in a phase file.**
All six were found by an adversarial review that did not write the code, and reproduced by the L05
wave itself before it stopped. Each is written up in full — with the command that establishes it and
what its repair must hold — in `docs/archive/features/maquette-l05/plan/phase-08-pr-fixes-cycle-1.md`, which
is on `main`. **That file is the source of truth and these entries are the index into it**; a phase
plan is archived with its wave, and a defect that outlives the wave has to be findable after that.
The four blocking ones (B-043 to B-046) were known before the merge and merged anyway, so they are
on `main` now.

- **B-043** — a deep address to a media sheet opens the screen but leaves `state.page = 404`
  underneath, so Back reads « Adresse introuvable ». It is a **regression** against the tree before
  the wave, on the wave's own headline feature, and R75 stays green because the screen covers the
  frame.
- **B-044** — a 404's address recomposes to `/`, so a mistyped link becomes a real page on the Back
  after a cold load. R69's fourth hold measures only the cold load and cannot see it.
- **B-045** — `?panel=follows`, with no colon, is accepted as a genre because the separator search
  returns −1, and an unknown subject fabricates a media that does not exist, labelled « à jour » and
  now reachable from a URL.
- **B-046** — the fallback port moved onto the one `switchover.py` uses. That script swallows its
  bind error, so a port collision would surface as R73 reporting a broken sign-in — a rule giving a
  confident wrong reason, which is worse than a rule that fails.
- **B-047** — the navigation-failure flag those sign-in guards are meant to raise is not raised by
  them, and **no rule reads it** — not after the wave and not before it. That is why they passed: a
  flag nothing reads cannot fail. Same family as B-038 and B-039.
- **B-048** — the ninth arm of `check-frontend-boundaries.py` reports clean over a tree with
  `addresses.ts` deleted (`0 dial(s), 0 page(s)`). A guard that stays green on a tree it cannot read
  is the shape its own neighbour's docstring names. Same family as B-041.

All six are repaired on `fix/maquette-l05` and land with **#484**, each with the hold that falls
when it comes back.

**B-049 — a rule class reads live operator data, and a cron makes it red on schedule.**
The follow fixture mirrors the operator's `acquire.db`; the watcher cron that resolves searches
moves that database independently of any wave (twice inside 24 h during the L05 repair). The
rule reads the mismatch as a defect and regenerating the fixture only holds until the next cron
run. Not a code defect — a class question: whether a rule that reads live data belongs in a gate
at all, and if so, on what cadence it re-syncs. Raised by the L05 repair wave (PR #484's open
points), not decided there. **Recurred during L06** (`content.py` reddened by the
operator's search cron; fixture regenerated from `acquire.db` again, same class, same
non-fix) — the second occurrence inside two waves, and the question is still not decided.

**B-050 — the guard that watches module size has itself grown past comfortable.**
`scripts/check-frontend-boundaries.py` reached 883 lines during the L05 repair (nine arms). The
module-size ratchet (invariant 6) does not exempt guard scripts. Split before the next arm lands,
not as an emergency — the file is not yet over the hard ceiling, only past the point where one
more addition should pause and ask.

**The 883 was the figure on the day it was written, and it was read as the state for two waves.**
Re-measured on `main` at `2a3f2576`: **921** non-blank lines, 79 from the hard ceiling, not 117.
The entry above is kept as it was written — this paragraph is the correction, because a figure
silently overwritten teaches nothing about the figure that will go stale next. Whoever closes
this bug re-runs the command rather than trusting either number.

<sub>`python3 scripts/check-module-size.py --root scripts`</sub>

**B-059 — the token guard is 58 lines from the ceiling, with 14 of L07's 16 phases to run.**
`scripts/check-css-tokens.py` was **815** non-blank lines on `main` and is **942** on
`feat/maquette-l07` at `dfb6ee42` — +13 in phase 1, +114 in phase 2 and its follow-up fix. The
hard ceiling is 1 000, it is enforced over `scripts/` (`check-module-size.py --root scripts`, in
`make check` and in CI's `guards` job), and exceeding it exits 1. Fourteen phases remain, and
**phase 4 plans another arm inside this very file** — `--arm motion-classes`, which the phase
document argues is not optional because nothing else in the repository would catch a
`duration-<n>` off the scale.

**The plan does not name this anywhere**: no phase document, neither `DESIGN.md` nor
`plan/INDEX.md`, mentions module size — the file is cited only as a command to run green. So the
wave is on course to redden a gate through a channel its own plan never forecast, and the phase
that trips it will look like the phase at fault rather than the accumulation. Not this steward's
to repair: reported so the split is planned rather than discovered at a red CI. The measurement
belongs to the wave; what belongs here is that it was never measured.

**IT HAPPENED, AND EXACTLY WHERE THIS ENTRY SAID IT WOULD** — at phase 4, the phase that adds
`--arm motion-classes` to this same file. The wave carried **1 016** non-blank lines at
`3e1f1ce5` and **1 022** at `2634de86`, two commits over a ceiling that exits 1, and the guard
that caught it was the repository's own — `check-module-size.py --root scripts`, in `make check`
and in the `guards` job — not anything the wave had planned. `777ec798` repaired it: the sign-in
gate's arm left for `scripts/csstokens_login.py` on a SUBJECT split, the four shared patterns
kept in one module so the first copy to drift cannot do so in silence, and the file is **851**
lines on the wave's tip.

Closed as `fixed #494` rather than `closed`: it is repaired on the branch, not on `main`. Rule 3
is met by the gate that already exists and already bit — the mutation was not staged, it was
lived. **What this entry did NOT get right** is its own forecast of the deadline: it read « phase
3 » from a two-phase slope, and the crossing came at phase 4. The mechanism was right, the
extrapolation was decoration — a rate measured over two points is a rate that has not been
measured.

<sub>`for c in $(git log --format=%h --reverse origin/main..origin/feat/maquette-l07); do printf '%s %s\n' "$c" "$(git show $c:scripts/check-css-tokens.py | grep -c '[^[:space:]]')"; done`</sub>

**B-051 — a feature-owned reader escapes the boundaries arm.**
`toFollows()` carries its page identity in a query parameter, inside a feature file the ninth
arm's inline-`validateSearch` reader does not reach (it reads route files, not every function
that shapes a query). D1's rule — path carries identity, query carries state — is not enforced
here by any guard; only readable by a human diff.

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

**B-055 — the a11y floor certifies one of two themes.** `a11y.py` drives the 83 named
states in the default (dark) theme only; no `data-theme` handling exists anywhere in the
harness. Found during L06 phase 5 by a sub-agent who drove `data-theme="light"` by hand and
re-ran axe — not by the gate, which has no arm that would. After phase 5's own repairs (the
light `--primary-foreground` at 2.14:1 across 19 consumers, `--primary` as a label at 2.16:1
on three sites), a full light-theme sweep still reads **154 occurrences over 115 rows in 34
states** — dominated by `--primary` used as a label colour on a light surface (~40 sites),
the `warning`/`success`/`info` tones repeating the same fill-versus-label confusion, and one
`.tsx` inline re-skin (`add-screen.tsx:185-191`). A remediation campaign, not a call-site fix;
needs its own design and plan (`docs/archive/features/maquette-l06/drafts/a11y-floor-measures-one-theme.md`
carries the full inventory). Not decided here: whether the audit runs both themes (doubling
its runtime) or a lighter arm audits palette pairs alone in light.

**B-056 — a French name sits where no arm reads it.** `refonte.html` names a keyframe
`splashremplit` (used by `.splashbar i`). A keyframe name is a name someone chose — code,
under the English-names rule — and none of `check-no-french.py`'s fourteen arms reads
`@keyframes` names, so the gate is green over it. Found during L06 sub-phase 1.3, not fixed:
outside the lot's letter, which folds values onto a scale and refuses any naming change
beyond D-L06-4's publisher move. Fixing it needs both ends moved in one step (the
`@keyframes` declaration and every `animation`/`animation-name` reading it) through the
rename discipline, plus a fifteenth arm so the next one does not sit the same way.

**B-057 — a hold that measures nothing reads as a hold that passed.** `audit2.py:65`'s
`measure()` returns silently when its selector finds nothing. `.resbtn` is one of five
contexts R12 names, and it is absent from the state the rule visits (`acq-add-results`), so
only four primaries are ever measured while the rule believes it holds five. The exact family
of hole `type_scale.py` was written to refuse — a gate proves what it READS. Found while
repairing R12's pinned size during L06; not fixed there, a rule-shape change outside the
lot's letter. Fix: either the rule visits a state that paints `.resbtn`, or `measure()`
refuses an empty selection the way `type_scale.py` does; mutation-tested either way (hide the
element, watch the rule fall).

**B-058 — the AI-attribution check can fire on prose that quotes what it looks for.**
`hooks/commit-msg`'s second alternative, `generated with .*claude`, carries no `^` anchor —
unlike the other two real-trailer alternatives — so it matches the phrase ANYWHERE in the
message, including inside a sentence documenting the rule itself. Found writing the commit
that fixed B-058's sibling: a French sentence quoting « generated with claude » in guillemets,
to explain what the hook forbids, tripped the hook it was describing. Not fixed here — the two
real alternatives are anchored to a line start on purpose (a trailer, not prose), and giving
this one the same anchor needs its own mutation test to confirm it still catches a genuine
footer while releasing a quoting sentence; a same-commit reflex fix on a compliance-relevant
guard is exactly the haste this register exists to slow down.

**B-060 — the tool `CLAUDE.md` mandates for renames could not perform one, and said so as success.**
`scripts/rename-identifiers.py` is the only sanctioned way to rename an identifier in this
repository. Asked to move the CSS custom property `--card` to `--color-card` it touched **zero
files** and printed « 0 file(s) touched » — its normal success line. The cause is one character
class: every mode anchored its pattern on `\b`, and a word boundary cannot precede `--`, so the
name was unmatchable by construction. A tool that cannot fail loudly is a tool whose report means
nothing; this one was believed twice before the diff was read, which is why `CLAUDE.md` already
says the tool is not the proof. **Repaired in #494** (L07 phase 3): a custom-property mode anchored
on the FORM (`--name`) rather than on the word, with five tests under
`tests/scripts/test_rename_identifiers.py`.
<sub>`python3 scripts/rename-identifiers.py --help` names the mode · the five tests are `pytest tests/scripts/test_rename_identifiers.py -k propert`</sub>

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

**B-062 — a class name emitted by a `cva()` base string wears no `class=`, and three readers looked for `class=`.**
The markup-contract readers learn what a class NAME is from the sites that emit one, and they
knew three such sites: `class="…"` in a document, `className="…"` in a component, and the engine's
string writes. A fourth arrived with L07: `cva("fback flex items-center …")` emits `fback` as
surely as `className="fback"` ever did, and carries no attribute for the readers to find. So the
vocabulary the guards police silently stopped covering every surface this wave converted.
**Repaired in #494** (`777ec798`): both readers take the first token of a `cva` base string — the
identity class, by this wave's convention — and both match `*variants.ts` as a FAMILY rather than
one exact name, because the vocabulary split into a directory the same day and a reader pinned to
one filename would have gone quiet again.

**B-063 — the maquette's gate tiers do not include the repository's own guards, and three invariant breaches lived across phases.**
`frontend/maquette/harness/run.sh` has a cheap tier and a full tier, and the wave's cadence runs
the cheap one per phase and the full one once before the merge. **Neither tier runs `make check`**,
which is where `scripts/check-frontend-boundaries.py`, the module-size ceiling and the French guard
live. So invariant 7 of `docs/reference/frontend-architecture.md` (« `ui/` never imports a feature.
Two features never import each other ») was broken **three times** across L07 and stayed broken
until the pre-merge `make check`: Maintenance and Système reached into Configuration for the topic
row, and the release screen reached into Acquisition for the result count. Two files passed a hard
line ceiling in the same interval.

**The three breaches are repaired in #494** (`777ec798` — both shared pieces are in `ui/` now).
**The cadence is not**, and it is the durable half: a wave can convert eleven surfaces without any
repository guard reading the tree once. The question is a cadence one, like B-049's — whether the
per-phase tier gains a `make check`, or the boundaries guard joins the contracts tier — and it is
not this wave's to settle alone.

**B-064 — R72's mutation recipe names an environment variable that nothing reads, so following it proves nothing.**
`frontend/maquette/regions.json`'s R72 text says « `R72_SANS_BUILD=1` skips the build gate ALONE ».
`frontend/maquette/harness/shell.py` reads **`R72_SKIP_BUILD`**. The rename landed with #446 and
the rule's prose was not moved with it. The consequence is not cosmetic: `shell.py` rebuilds
before it reads, so an operator following the recorded recipe — apply a mutation to
`dist/index.html`, re-run with the documented variable — has the mutation **erased by the rebuild**
and reads a green run as « the mutation was survived ». A recipe that cannot fail certifies the
rule it was written to test. Pre-existing on `main` since #446; found while reading R72 to decide
whether it could be renegotiated. Fix: move the name, and re-run the recorded mutation with the
real variable so the recipe is seen to bite once.
<sub>`grep -rn 'R72_SANS_BUILD\|R72_SKIP_BUILD' --include='*.py' --include='*.json' frontend | grep -v node_modules`</sub>

**B-065 — a duplicated source tree is tracked, read by nothing, and has begun to drift.**
`frontend/maquette/design/frontend/maquette/design/src/` holds **11 tracked files** — nine
`features/*/reference.ts`, `lib/engine-drawing.ts`, `lib/engine-queue.ts` — a copy of the real
tree nested under its own path. It landed with **#478** (L04, « les frontières et l'arbre »), the
wave that moved every file, and has been on `main` since. Nothing reads it: `tsconfig.json`'s
`include` is `["src"]`, and every harness and script reader roots at `design/src`. So it does not
lie to a gate — it is dead weight.

**It has started to diverge, which is what makes it worth an entry rather than a `git rm`.** Three
of the eleven now differ from their live counterparts: `features/media/reference.ts` is missing
the six lines §11's address contract added (`titleForProviderId`, `addressIdsFor`), and
`features/maintenance/reference.ts` and `features/system/reference.ts` carry an import shape their
originals no longer have. A stale copy of a contract file, sitting at a plausible path, is
something a future search will find and read. Fix is a deletion — outside L07's letter, and it
should carry the one thing that would refuse the next one: a guard that no path under
`design/` repeats `design/` .
<sub>`git ls-files 'frontend/maquette/design/frontend' | wc -l` → 11 · `git log --oneline --diff-filter=A -- 'frontend/maquette/design/frontend/**'` → the commit that added them</sub>

**B-066 — the scale arm can now see two declarations, and neither is its to fix.**
Widening the arm to the shipped stylesheets (#494) exposed what it had never read: `.skip-link`
declares `padding: 10px 16px` and `border-radius: 0 0 10px 10px`, and `.visually-hidden` declares
`margin: -1px`. All three came out of the prototype's HARNESS block — never under the scale rule —
and entered the shipped base layer when that block was cut, so they are debt this wave inherited
rather than debt it wrote. Two of the four found were repaired in the same commit because the fix
was free: `body`'s `font-size: 14px` IS `--text-5`, and `--spacing-0` was a step declared one line
outside the markers.

**These two are not free.** The spacing ramp reads 14 then 18 — there is no 16 — and the radius
ramp reads 8 then 12, so honouring the scale means CHANGING what a keyboard user sees when the
skip link takes focus. That is a design call. `margin: -1px` is not a design constant at all: it
is the one-pixel clip idiom, and no step of any ramp would do. Both are named exemptions in
`scripts/check-css-tokens.py`'s `EXEMPTIONS`, each with its reason, which is what lets the arm go
green over what it CAN answer for — and this entry exists so the exemption does not become the
answer.
<sub>`python3 scripts/check-css-tokens.py --arm scale` → 0, with the two selectors skipped by name</sub>

**B-067 — a variant that can be edited and changes nothing.**
`src/styles/legacy.css` is deliberately UNLAYERED so it wins over `@layer utilities` — the right
call for markup the engine draws, and the wave says so in the file. It also lands on markup
COMPONENTS draw: seven shared identity anchors carry both a residue rule and a typed variant —
`.empty`/`emptyNote`, `.surferr`/`surfaceError`, `.panel`/`factsPanel`, `.pip`/`statusDot`,
`.sec`/`section`, `.sechead`/`sectionHead`, and the sheet's `open` branches. Unlayered normal
declarations beat every cascade layer whatever the specificity, so on those elements the utility
loses.

**Nothing renders wrong today**, and the wave recorded that plainly rather than counting the
surfaces as converted: the declarations are identical term for term, and the oracle says so. The
defect is the one nobody is holding — **the day a variant DRIFTS from the rule it shadows,
editing it changes nothing on screen and no gate speaks.** TypeScript passes, the build passes,
`make check` passes, the rendering does not move. The shape of the fix is a guard cross-checking
each variant's identity anchor against the residue's selectors and refusing a divergence; the
alternative is scoping the residue to the engine's instances, which is L13's work.

**B-068 — the wave's prose drifted in forty small places, and the inventory is kept.**
An adversarial doc-accuracy review over #494 re-measured every figure the wave asserts. **Most
are right** — 2 739 measurements, 530 rules, 4 136 lines, 30 colours, 8 shadows, 55 rules, 936
bytes leaked, and D-L07-1's six line ranges are exact. What is not right is written up, item by
item, in `docs/archive/features/maquette-l07/drafts/documentation-drift-inventory.md`, which travels with
the wave into `docs/archive/features/`. **That file is the source and this entry is the index**,
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

**B-069 — the residue's licence to exist points at a document about to be archived.**
`src/styles/legacy.css` justifies itself with « D-L07-5, arbitrated by the operator on
2026-08-24 », and D-L07-5 is defined in `docs/archive/features/maquette-l07/DESIGN.md` and nowhere else.
That directory was archived when #494 landed, so **the only definition of the decision keeping a
2 470-line stylesheet alive is now in frozen history** — and `docs/archive/` is never revised. Its sibling deferral (the
prototype fragment, ACC-14/ACC-19) already has a durable home in
`docs/reference/frontend-architecture.md` § L13. This one needs the same: the decision moves
there, and the stylesheet's header cites the durable address.

**B-070 — the rename tool passed the soft ceiling, and it is the same family as B-050.**
`scripts/rename-identifiers.py` reads **829 non-blank lines** against a soft warning at 800 and a
hard ceiling at 1 000. It stood at 716 before L07, 786 after the custom-property mode landed, and
crossed on the no-op refusal (#494). `check-module-size.py` warns and exits 0, so nothing is
blocked — which is exactly what B-050 says about its own file: split before the next addition,
not as an emergency, and the moment to pause is the crossing rather than the ceiling. The subject
line is visible: the mapping validation, the span readers and the three apply modes are three
subjects behind one entry point.
<sub>`python3 scripts/check-module-size.py --root scripts`</sub>

**B-071 — a toggle for an overlay that was deleted.**
D-L07-1 deleted the design-notes overlay with BLOCK 1, correctly: `:root.notes .note` was harness
CSS and it must not ship. `src/engine/legacy.js:11414-11419` still toggles the `notes` class,
still flips `aria-pressed`, and still toasts « Notes de conception affichées. » — reporting
success for a class nothing reads. A contract with three ends and two of them gone, which is the
shape `CLAUDE.md` names about `data-*` names: the markup that emits it, the code that reads it,
and the rules that tap it move in ONE step. Left here rather than fixed because the third end is
inside the dying engine, where an edit is L13's to make; it is written down so L13 does not
rediscover it as a live feature.

**B-072 — the command that proves the surface partition no longer runs.**
`docs/archive/features/maquette-l07/DESIGN.md:281` names `build-surface-manifest.py` as the builder that
asserts the partition of BLOCK 2's 530 rules into 38 surfaces is TOTAL. Run today it raises
`IndexError` at line 79: it reads `refonte.html`, which is 120 lines and holds no rule. The
committed `plan/surface-manifest.json` is correct — it was built when the fragment still carried
the stylesheet — so nothing downstream is wrong. What is gone is the ability to re-derive it: a
proof that ran once and cannot run again is a sentence in a merged pull request, which is
precisely what B-041 says from the other end.

**B-036 — the English campaign missed two state ids, and no arm reads them.**
`window.__states()` returns **`system-panne`** and **`acq-follows-groupe`**. Both are NAMED STATE
IDS, which `CLAUDE.md` §Language settles explicitly: « a NAMED STATE id is a name someone chose
(`window.__go("acq-now-idle")`), and 51 of the maquette's 82 were French until 2026-08-20 because
« it is a value » was accepted as an answer ». These two are survivors of that campaign
(#455/#456).

Found while driving the 82 states for L01, not by a guard — which is the point worth recording:
`scripts/check-no-french.py` has fourteen arms and none of them reads the state table, so the
count went from 51 to 2 and then stopped moving with nothing to notice. A rule with no arm is a
sentence in a file.

**Not fixed here, deliberately.** A state id has more than three ends — `states.js`, every
harness script that drives it, `regions.json`'s records, and this repository's dated documents —
and L01 is the lot that must not move anything: its whole value is a reference recorded against
an unchanged prototype. Renaming them would land in the same wave as the instrument that would
have to prove the rename. **Its fix belongs to the wave after this one, and it should carry the
missing arm rather than only the two renames.**

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

---

## B-021 — Signing out leaves the bottom panel on top

**Reported** 1× (2026-08-15). **Status** `to confirm` — `harness/bugs.py` checks 9/9b.

**What the operator sees.** From the user panel, reach the profile, sign out: the panel never
seems to leave the foreground.

**What actually happens**, measured on the journey: tapping « Profil et préférences » in the
user sheet changed the page to `?page=profil` UNDER the sheet and left the sheet on top
(`elementFromPoint` said `sheet`). Everything tapped from there happens under a stuck panel.
The sign-out itself, measured alone, closes the sheet and lands on the entry screen — the
stuck panel comes from the step BEFORE it.

**Why.** The `data-go` handler predates the layer rules: it navigated (`state.page`, `render`,
`noterLeChemin`) without closing the layer it may sit in, and pushed its nav entry ON TOP of
the layer's buried history entry. The drawer already had the settled pattern for exactly this
(`data-navgo`): close every layer WITHOUT touching history, and the destination TAKES the
layer's entry through `remplacer` — an unwind-then-push would race, the asynchronous pop
landing after the push.

**The fix.** The `data-go` handler now follows the drawer's pattern: `fermerTiroir(true)`,
`closeSheet(true)`, screen stack emptied then `closeScreen(true)`, render, then `remplacer`
when a layer entry was on top, `noterLeChemin` otherwise.

**Why no rule caught it.** `bugs.py` check 3 proves the BOTTOM BAR closes layers on
navigation (`data-page` calls `hideLayers()`), and every driven state reaches pages directly —
nothing walked a `data-go` control INSIDE a layer.

**Mutation.** Removing `closeSheet(true)` from the block → checks 9 and 9b fall naming the
stuck sheet. Pushing instead of replacing → check 9b alone falls (back no longer reaches the
page one stood on before the sheet). Both executed, both restored.

**Observation recorded, not fixed here**: `data-page` (bottom bar) hides layers but does not
settle their buried history entries either — masked because the DOM closes. Unreported, left
open deliberately; SP4's ownership law re-founds this bookkeeping.

---

## B-022 — « Voir mes suivis » in the add search is inert

**Reported** 1× (2026-08-15). **Status** `to confirm` — `harness/bugs.py` checks 10/10b.

**What the operator sees.** On the add-media screen, after adding a media, the « Voir mes
suivis → » footer link answers a tap with nothing.

**What actually happens.** Same defect as B-021, other layer: the footer's `data-go="acq"`
changed the page to Acquisition UNDER the still-open add screen. The page did move — behind
a screen that never left, which reads as « nothing happened ».

**The fix.** The shared `data-go` fix above. The journey test walks the real path: results →
card body → panel → « Ajouter » (confirming the replace dialog when the result is owned) →
footer appears → tap → the screen leaves and Acquisition renders.

**Mutation.** Covered by the B-021 mutations — the same handler, measured on this journey by
checks 10/10b.

---

## Requested evolutions (not defects — recorded here so they are not lost)

- **E-001 — Médiathèque sort inversion** (2026-08-15): every sort type must be reversible —
  A→Z and Z→A each way. An evolution, so it is maquette-first: drawn and measured in the
  prototype before any conversion work touches it. **Arbitrated by the operator
  (2026-08-15): folded into the Médiathèque wave of SP4**, where that page is drawn into
  its final component.
  **Drawn, and held by a rule of its own (R78, `harness/library_sort.py`).** The panel offers
  the six directions explicitly, each carrying its own NAME — « Ajout récent » / « Ajout
  ancien », « A → Z » / « Z → A », « Les plus incomplets » / « Les plus complets » — rather
  than an arrow bolted onto a shared one; exactly one is marked; the control on the count line
  reads the direction in force; and the reversal is measured on the ROWS DRAWN, over a library
  narrowed until the whole set fits on one page (the list draws 24 of 260, so reversing the
  order and taking the first page again gives the last rows of the other end — right, and not
  the reverse of what was drawn). MUTATION: the direction stops being applied, in the served
  copy alone — the three reversal holds fall, each naming its sort, while every hold about the
  NAMES stays green. **The ruling against the alternative — tapping the already-chosen sort to
  flip it — is recorded in `regions.json` under R78 and is open to contest**: it halves the
  rows but is invisible, and a row that reads « A → Z » and answers Z → A is the opposite of
  showing what the machine will do.

- **Ouvert opérateur — the 240 ms dead delay on `data-next`** (2026-08-16, SP4c; the attribute
  was named `data-suivante` when this was written and #455 renamed it): the
  "Passer à la suivante" action in the arbitration screen still carries a `setTimeout(240)`
  before its resolution call. It was once a cover for the legacy screen closing under it;
  the screen migrated to a router-owned route in SP4c and no longer plays a close animation
  there, so the delay is now a frozen quarter-second with nothing left for it to cover. Kept
  byte-identical rather than removed — the binding constraint on this wave was
  behaviour-preserving migration, not a UX pass — so this is flagged, not fixed. The operator
  may want it dropped.

---

## B-013 — The drawer's entries lead nowhere

**Reported** 2× — the second time this surface has been reported inert. **Status** `to confirm` — R65, `harness/drawer.py`.

**What the operator sees.** The navigation drawer opens, and its entries are not clickable: a tap
on a menu entry goes nowhere.

**What actually happens**, measured on the journey rather than read: tapping « Médiathèque » left
the bar's current tab on « Acquisition » at +60 ms and again at +560 ms. The entry was never
inert — the page changed and was put back.

**Why.** The close unwound the drawer's own history entry with `history.back()`, which is
**asynchronous**. Its pop therefore landed AFTER the arrival had rendered, and the popstate
handler read that pop as a back gesture: it applied the entry underneath, which describes where
one already was. One frame of Médiathèque, then Acquisition again.

A second cause, on one entry only: « Config » pointed at an id `PAGES_OF` does not carry, and
answered a tap with a message saying the page was out of scope. Réglages exists and is drawn; the
entry now names it.

**Why no rule caught it.** R59 covers the back gesture and was green throughout. It drives named
states; nothing walked the journey of opening the drawer and tapping an entry.

**And it is the SECOND time this surface has been reported inert.** `regions.json` →
`$reportedDefects` already carries `inert-drawer`: « the hamburger opened nothing and the drawer
links were not clickable: event delegation looked only at `<button>`, and a navigation link is an
`<a>` ». That cause was fixed and a comment left beside it. A different cause produced the same
symptom, and nothing had been left behind that would notice — the fix was recorded, the BEHAVIOUR
was not. That is precisely the difference between a note and a rule.

**The fix.** The destination TAKES the drawer's history entry (`replaceState`) instead of the
close unwinding and the arrival pushing in the same task. And our own unwind now announces itself,
so the popstate handler consumes it rather than interpreting it.

**Mutation.** Point an entry at an id no page carries → « chaque entrée nomme une page qui
existe » falls, naming `config`.

---

## B-014 — The drawer's current entry is unreadable

**Reported** 1×. **Status** `to confirm` — R65, `harness/drawer.py`.

**What the operator sees.** The entry marking where one currently is cannot be read.

**What actually happens.** Its label and its background are the **same colour** —
`oklch(0.808 0.158 79)` on `oklch(0.808 0.158 79)`. Contrast **1.00**. A label written in
invisible ink.

**Why.** `background: var(--sidebar-accent, var(--primary))`, and `--sidebar-accent` is defined
nowhere — so the background falls back to `--primary`, which is what the label is coloured with.

**Why no rule caught it.** This is the family of B-007, and R61 exists for it — but R61 forbids
only **bare** `var()`. A fallback makes a phantom token look like a considered choice, and the
rule looks away. Two other `--sidebar-*` references had the same shape with harmless fallbacks;
they are gone too, because a landmine that has not gone off is still a landmine.

**The fix.** « You are here » is the brand colour on the label — the mark the bottom bar already
uses — over a **tint** of that mark rather than the mark itself. Measured: contrast **7.66**,
above AA and above AAA.

**Mutation.** Restore the fallback → the contrast check falls at 1.0, naming the current entry.

---

## B-015 — Back reopens the drawer that was just closed

**Reported** 1×. **Status** `to confirm` — R65, `harness/drawer.py`.

**What the operator sees.** Close the drawer, then use the back gesture: the drawer comes back.
« Ce n'est pas une route. »

**What could not be reproduced.** The drawer never reopened under measurement — five ways of
closing it, on Chromium **and** WebKit, `go_back()` after each. That is recorded rather than
hidden: what follows fixes the bookkeeping the report points at, and only the operator's phone
can say whether it was the whole of it.

**What was found instead**, on every one of those paths: after using the drawer, ONE back landed
on the root-exit warning. The drawer had eaten the operator's navigation history — its entry sat
between the page and everywhere they had been.

**The fix.** The drawer leaves nothing behind: the destination replaces its entry, so a back from
there reaches where one was before opening it. Closing it without going anywhere restores the
history exactly as it was.

**Mutation.** Make the destination push instead of replace → `from « <entry> », back returns to the start` falls on
all four entries.

---

## B-016 — Swiping a row right, then left, makes it jump

**Reported** 1×. **Status** `to confirm` — R64 extended, `harness/drag.py`.

**What the operator sees.** Swipe a card right, then swipe it left: the card jumps. What it should
do is settle back to rest, so that a second, deliberate left swipe is what reveals the actions on
that side.

**Measured.** The row rests at **+84**; the finger's first 15-pixel step puts it at **−168**. A
leap of **252 pixels** — the width of both drawers — before the finger has travelled a centimetre.

**Why.** A drag beginning on an open row has to resume from where the row IS. The origin was
deduced from a side instead of read from the row — `-largeurTiroir(sw, -1)`, the right drawer's
width, whichever side the row was actually open on. A row open on the LEFT therefore started its
travel from the far side.

**Why no rule caught it.** R64 covers one swipe in one direction, and both of its ends were
correct. A jump is a **discontinuity**: a probe that reads only the resting positions certifies
it. The rule now samples during the gesture.

**The fix.** The resting offset is recorded when it is set, and the drag resumes from it. And an
open row can only be CLOSED by a drag — its travel is clamped between where it rests and zero —
so a swipe the other way settles it back instead of crossing rest and opening the opposite drawer
in one gesture. That is the operator's own prescription: « elle devrait se replacer normalement et
je reswipe à gauche si je veux voir les actions à gauche ».

A third instance of the same class was found while fixing it: the quick-action buttons cleared the
row's transform by hand without clearing what was RECORDED about it, so the next drag resumed from
a drawer that was no longer open. They close through the shared close now.

**Mutation.** Restore the deduced origin → « an open row follows the finger without leaping » falls at 252. Remove the clamp → « the reverse drag settles it back at rest, without opening the other side » falls.

---

## B-018 — On a desktop, dragging a row opens the bottom panel

**Reported** 1×. **Status** `to confirm` — R64 strengthened, `harness/mouse.py`.

**What the operator sees.** On a DESKTOP, dragging a row left or right opens the bottom panel
instead of revealing the row's actions. The drag is read as a tap.

**Measured.** On a library row dragged to the right, a click reaches the document with
`defaultPrevented: false` — **the click is not swallowed**. On the same row dragged left, and on a
follows row either way, it is.

**Why.** The guard that stops a drag from also firing the tap was armed on how far the ROW moved:
`|dx - depart| > 4`. A row is free to refuse to move — a library row has no drawer on its left, so
a right drag ends exactly where it started — and then nothing is armed, the click goes through, and
the panel opens over the row.

**Two ways in, and only one is mine.** The right drag on a row with no left drawer has behaved this
way from the beginning. The fix for B-016 added the second: since an open row can now only be
CLOSED by a drag, dragging one further in the same direction also ends where it started. Calling
the whole thing a regression, as this entry first did, was wrong.

**Why no rule caught it — and this is the part worth keeping.** Two reasons, and they compound.

1. **After a touch drag, the browser suppresses the click by itself.** Every finger measurement was
   therefore green over the hole. Only a mouse can see it, and R64 already knew that — its own text
   says a touch probe cannot tell a swallowed click from one that never happened.
2. **`mouse.py` asserted the weaker thing.** It checked that no panel appeared. A panel can fail to
   appear because the release landed a few pixels off the card, which is exactly what happened in
   the first four attempts to reproduce this: the click went through, unswallowed, and hit a `div`.
   The rule now asserts the click was **actively swallowed**, which is the property that was
   promised.

**The fix.** The guard is armed on what the FINGER travelled, never on what the row moved. The
distinction between a drag and a tap belongs to the pointer.

**Mutation.** Restore the row-displacement test → « une ligne de médiathèque, glissé droite : le
clic n'est pas avalé » falls. Disarm the guard entirely → all four fall.

---

## B-017 — Closing a panel sends the list back to its top

**Reported** by nobody. **Status** `to confirm` — R65, `harness/drawer.py`.

**What happens.** Open a bottom panel from a card halfway down a list, close it: the page
underneath is rebuilt and the list is scrolled home. Measured — a marker planted in the view was
gone, and the scroll offset went 22 → 0.

**Why.** The same root cause as B-013, seen from the other side. Closing any layer popped its own
history entry; the handler read that pop as a back gesture and re-applied the state underneath,
which re-renders the page one is standing on.

**How it was found.** By the mutation proving R65 bites. The first pass of that mutation did NOT
fell the rule, which said the guard it targeted was load-bearing for nothing — so under « what no
mutation can fell is removed », it was about to be deleted. Measuring whether it was load-bearing
for the OTHER layers is what turned a deletion into a defect.

**Mutation.** Remove the unwind guard → four checks fall, naming both the rebuilt page and the
lost scroll offset, on the panel and on the drawer.

## Closed entries — index

The bodies of these entries — what each one did, why no rule had seen it, and what proves it now —
were moved verbatim to [`BUGS-CLOSED.md`](BUGS-CLOSED.md) so the open ones stay legible. Nothing
was reworded, renumbered or dropped; the protocol and the counts stay in this file.

**Thirteen were confirmed in ONE batch on 2026-08-20**, on the operator's instruction (« Ferme
tous les bugs en attente de VOTRE confirmation, sauf B-030 »). Each had already been fixed, its
rule green and its mutation proven — `to confirm` in this register means waiting for the
operator, not waiting for work. Recorded as a batch rather than thirteen separate dates because
that is what happened: one instruction, one moment, and inventing thirteen dates would be a
record of something nobody did.

- B-013 — The drawer's entries lead nowhere (closed 2026-08-20, batch)
- B-014 — The drawer's current entry is unreadable (closed 2026-08-20, batch)
- B-015 — Back reopens the drawer that was just closed (closed 2026-08-20, batch)
- B-016 — Swiping a row right, then left, makes it jump (closed 2026-08-20, batch)
- B-017 — Closing a panel sends the list back to its top (closed 2026-08-20, batch)
- B-018 — On a desktop, dragging a row opens the panel (closed 2026-08-20, batch)
- B-021 — Signing out leaves the bottom panel on top (closed 2026-08-20, batch)
- B-022 — « Voir mes suivis » in the add search is inert (closed 2026-08-20, batch)
- B-025 — The screen half of the `data-go` fix has no Back rule (closed 2026-08-20, batch)
- B-026 — A silent `catch {}` can let URL and UI disagree (closed 2026-08-20, batch)
- B-027 — `resync.py` trusts `t:` first-match + naive braces (closed 2026-08-20, batch)
- B-028 — `resync.py` says « 0 correction » for unknown titles (closed 2026-08-20, batch)
- B-029 — Counter rule misses suffix drift (« 1 » in « 11 ») (closed 2026-08-20, batch)
- B-019 — Many media sheets have lost their visual (closed, date not recorded)
- B-020 — Actor portraits on media sheets are broken (closed, date not recorded)
- B-023 — Médiathèque « Incomplets »: every visual broken (closed, date not recorded)
- B-001 — The list poster is still too small (closed 2026-08-14)
- B-002 — The startup bar is never seen on a real load (closed 2026-08-14)
- B-003 — In Arrivées a poster does not lead where a poster leads (closed 2026-08-14)
- B-004 — Dragging the sheet handle down no longer closes the panel (closed 2026-08-14)
- B-005 — A long press on a poster raises the browser's own menu (closed 2026-08-14)
- B-006 — Two different sign-in screens: arrival and sign-out (closed 2026-08-14)
- B-007 — `--accent` referenced 11 times, defined nowhere (closed 2026-08-14)
- B-008 — The card poster should bleed to the card's edges (closed 2026-08-14)
- B-009 — Swiping a media card should reveal its quick actions (closed 2026-08-14)
- B-010 — Only one row open at a time (closed 2026-08-14)
- B-011 — The drawer renders wrong on iOS (closed 2026-08-14)
- B-012 — The startup screen plays a second time once loaded (closed 2026-08-14)

**Full bodies: [`BUGS-CLOSED.md`](BUGS-CLOSED.md)**, same order as this index.

---

## Closed

Confirmed by the operator on a real phone, on `tm-design.iznogoudatall.xyz`. What each one did,
why no rule had seen it, and what proves it now stays in `BUGS-CLOSED.md`: a closed bug whose
history has been erased is a bug that will be made again.

| ID    | Defect                                                    | Reported | Closed     |
| ----- | --------------------------------------------------------- | -------- | ---------- |
| B-001 | The list poster is still too small                        | 2×       | 2026-08-14 |
| B-002 | The startup bar is never seen on a real load              | 2×       | 2026-08-14 |
| B-003 | In Arrivées a poster does not lead where a poster leads   | 2×       | 2026-08-14 |
| B-004 | Dragging the sheet handle down no longer closes the panel | 2×       | 2026-08-14 |
| B-005 | A long press on a poster raises the browser's own menu    | 2×       | 2026-08-14 |
| B-006 | Two different sign-in screens: arrival and sign-out       | 1×       | 2026-08-14 |
| B-007 | `--accent` referenced 11 times, defined nowhere           | 1×       | 2026-08-14 |
| B-008 | The card poster should bleed to the card's edges          | 1×       | 2026-08-14 |
| B-009 | Swiping a media card should reveal its quick actions      | 1×       | 2026-08-14 |
| B-010 | Only one row open at a time                               | 1×       | 2026-08-14 |
| B-011 | The drawer renders wrong on iOS                           | 1×       | 2026-08-14 |
| B-012 | The startup screen plays a second time once loaded        | 1×       | 2026-08-14 |

**What these twelve cost, and what is worth keeping from them.** Seven had been reported
**twice** before being written down here — what was missing was this register, not memory. Four
were invisible because the rule measured a named state instead of the path actually walked: a cold
load, a real finger, a real browser menu. One — B-012 — was my own over-correction of the one
before it. And two rules had to be thrown away before one held, for the same reason both times:
asserting that a panel is open AFTER the finger lifts proves nothing, since a tap opens it too.

**B-037 — a French identifier, and a dead one, in a harness rule under a green gate.**
`frontend/maquette/harness/arrivals.py:53` reads `window.PIPELINE_UID_POUR_LA_SONDE || null`. The
name is French — a name someone chose, which CLAUDE.md §Language covers — and it sits inside a
JavaScript string, so the identifiers arm of `scripts/check-no-french.py`, which parses Python,
never sees it. And nothing under `frontend/` DEFINES that global: the expression is `null` on every
run, and R66 obtains the run uid from the text the prototype prints instead. A dead read, in French,
that fourteen arms walked past. Found by a sub-phase of L02 reading the rule it was migrating (2026-08-21),
not by a guard.

**B-038 — `arrivals.py` reads `empty` into its view and no hold consumes it.**
The rule's `READ` collects `empty` for every flux row (`classList.contains('fempty')`, now
`hasAttribute('data-empty')`), but the only holds that could use it compute the dash from the
result text and consume `blocked` alone. So the `fempty` read was dead on the class before L02 and is
dead on the attribute after it: a mutation dropping `data-empty` leaves the suite green
(`24 rules EXECUTED — no violation`), while the same mutation on `data-blocked` fells the right
hold. A hold « a row with nothing to do is marked empty » (3 of 9 rows today) closes it; it moves
R66's hold count, which is why it was not written inside the migration (2026-08-21).

**B-039 — `actions.py:81` prints whether `.freshtag` exists and asserts nothing.**
The follow flow the rule drives never produces a `fresh` descriptor, so the probe printed `False`
before L02 anchored the element as `card/fresh-tag` and prints `False` after — measured across all
83 named states: `[.freshtag, [data-part="card/fresh-tag"]] = [0, 0]`. The contract is faithful and
nothing holds it: neither end can move and fall a rule. A state that produces a fresh follow, or a
hold after a follow action, is behaviour work outside the anchoring lot (2026-08-21).

**B-040 — French names survive in files no arm of `check-no-french.py` reads.**
By design (its own docstring, arm 1), the harness's rule scripts are read for their hold LABELS
only; `states.js` and `legacy.js` are read for the declared debt alone. So five French view labels
in `sweep.py`'s `VIEWS` table (`acq/suivis`, `acq/decouvrir`, `lib/incomplets`, `lib/recents`,
`arrivees`) sat under a green gate — `arrivees` is even in `scripts/nofrench_lexicon.py:47` — until
sub-phase 6.5 of L02 turned them into screenshot file names and renamed them by hand; and
`regions.json:81` still declares the region id `arrivees/empty`, one of the oracle's 33 keys, which no
arm reads either. Same family as B-036: a name someone chose, in a file the guard does not open. The
fix is an arm over the harness's string literals and the oracle's region ids, with the lexicon it
already has; the region rename moves an oracle reference key and is not an anchoring change
(2026-08-22).

**Widened 2026-08-22 by the steward's audit of L02, because the fix above is written too narrow.**
`frontend/maquette/oracle.py` uses the French verb « entérine » three times, and line 953 is the
`--accept` HELP STRING — a message the tool prints, which `CLAUDE.md` requires to be English. An
arm over the harness's string literals and the oracle's region ids would not reach it: it is
neither.

**The mechanism is a second one, and it is the part worth fixing.** The guard reads
`frontend/maquette/` by an ENUMERATED list — `MAQUETTE / "serve.py"` and `MAQUETTE / "resync.py"`,
at three call sites — never by a glob. `oracle.py` and `fidelity.py` sit in that directory and are
in **no corpus at all**, so it is not that an arm reads them narrowly: nothing opens them. A list
hand-edited every time a sibling lands beside it goes stale, and this one did the day L01 added a
file. Widening the corpus to the directory closes both this and whatever lands there next; the
three words alone close neither.

Scope measured before reporting: three occurrences, one word, one file — `fidelity.py` is clean.
<sub>`grep -n "entérine" frontend/maquette/*.py` · `grep -n 'MAQUETTE / "' scripts/check-no-french.py`</sub>

**Precision added 2026-08-25, because the command above cannot see one of the three.** Line 637 is
inside the `$comment` this tool SERIALISES into `frontend/maquette/oracle-reference.json`, so the
word is written into a `.json` the register's own command — which globs `*.py` — will never open.
Two consequences worth the line: the scope is three occurrences in one `.py` **plus one in a
committed reference file**, and **every future `--record` rewrites the French word** into that
file, so the copy regenerates for as long as line 637 stands. Fix the source line first; the
`.json` copy then corrects itself on the next recording.
<sub>`grep -c "entérine" frontend/maquette/oracle-reference.json` → 1</sub>
