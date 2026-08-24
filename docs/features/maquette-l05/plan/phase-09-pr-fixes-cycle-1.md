# Phase 9 — PR #484 fixes, review cycle 1

Four adversarial reviewers read PR #484 (phase 8); none had written the code. Every finding
below was re-verified by the orchestrator against the branch — by reading, by a Node replay of
the engine's string logic, or by a probe walk on the served copy — before it was retained. Two
are MAJOR and both say the same thing about phase 8: a hold that cannot see the defect's own
shape is a hold that certifies it.

**The pull request must not merge until 9.1–9.8 are closed.** 9.9 is a batch of minors that
ride along, and one of them (a phase-decision id inside a source comment) is a rule violation.

The running directives of phase 8 — « How this phase runs », the four beats, the build+copy
recipe WITH the `rm -rf`, the struck gates, the language rules — apply unchanged. Read them in
`phase-08-pr-fixes-cycle-1.md` before any sub-phase. Branch `fix/maquette-l05`, same version.

## 9.1 — `knownMedium` says yes to names the interface does not hold · MAJOR

`legacy.js` `knownMedium` reads four sources; three are exact `===` on arrays, the fourth is
`sheetFor(title) != null`, which is not: `SHEETS_RAW[title]` is a bracket lookup on a plain object
(so `constructor`, `toString`, `__proto__` resolve through `Object.prototype`), and its last branch
matches any ≥ 7-character PREFIX of a catalogue key. Replayed against the real 259-key fixture:
`"American"` (prefix of « American Dad! »), `"president"`, `"constructor"`, `"Silo (2023)"` and
`"silo"` all resolve — and `openFollowSheet` then finds none of them in `world.follows` or
`INCOMPLETE` and builds `{ t: title, k: "show", st: "up_to_date" }`. A panel titled « American »,
labelled « à jour », from an address. The one value the new hold tries (« Ceci N'Existe Pas »)
misses both bypasses, so R56 is green over the defect it was written for. `journey`'s `resolves`
starts with `knownMedium`, so it is open the same way.

Fix: `resolves` for `follow` and `journey` is EXACT membership in the sources the opener itself
matches exactly — `world.follows`, `INCOMPLETE`, `LIBRARY` (and `INFLIGHT` for a journey) — and
never `sheetFor`. A title that only has a sheet is not a follow, and the opener would synthesise
it. Holds in R56: `follow:constructor`, `follow:American`, `follow:Silo%20(2023)` and
`follow:silo` each open nothing and name nothing; `follow:Silo` still reopens.
Mutation: put `sheetFor` back into `knownMedium` → the prefix/prototype holds fall.

## 9.2 — The not-found address loses its query, so the first Back still rewrites it · MEDIUM

`destinationOf` records `notFound: pathname` — the path only. `addressOf(NOT_FOUND_PAGE)` returns
it verbatim, so a cold `/typo?x=1` shows `/typo?x=1`, and the first Back (guard → `recordPath`)
re-pushes `/typo`. The operator's link is rewritten, exactly the class R69 hold 4 forbids; the
hold uses `/nimportequoi`, which carries no query, so it is green.

Fix: `notFound` carries the address AS ASKED, query included (leading `?` normalised). R69 hold 4's
cold load and Back use an address with a query and assert it survives both.
Mutation: drop the query from `notFound` → the Back hold falls.

## 9.3 — A cold `?panel=` over a SCREEN path tears the screen down · MEDIUM

Since 8.1 a screen address carries `panel`; the reopen goes through `openPanel`, which composes the
layer entry from `state.page` — `HOME_PAGE` under a screen — so a cold
`/media/tvdb/403245?panel=follow:Silo` pushes `/acquisition?panel=follow%3ASilo`, the router stops
matching `/media/$provider/$id`, and the DOIT-11 sheet the operator linked to unmounts behind the
panel. Reproduced on the served copy (orchestrator's probe). The same mechanism fires IN-APP: an
addressed panel opened while a screen route shows pushes the page's path and closes the screen
(pre-existing on `main`, where it composed `/`).

Fix, per D1 read literally — the query says how THIS surface is looked at, and under a screen the
surface is the screen: `openPanel` composes the panel's address over the CURRENT path when that
path is a screen path (`isScreenPath(location.pathname)` → `pathname + ?panel=…`, other query
verbatim), and over `addressOf(state.page, …)` otherwise. A panel over the NOT-FOUND page is
refused at the boot (the address model already says it is not a state anyone links to) with the
same `console.warn`. Holds: cold `screen?panel=` → screen open AND panel open, address is the
screen path with `panel=`; Back → panel closed, screen still open, address the screen path;
in-app: open the media sheet, open a follow panel → the sheet stays; cold `/nimportequoi?panel=…`
→ no panel. Mutation: compose from `state.page` again → the screen hold falls.

## 9.4 — Forward after Back re-enters the panel's entry with no panel · MEDIUM

After R56's own new walk (cold `?panel=follow:Silo`, Back closes the panel), a FORWARD lands on
the `{ layer: "sheet" }` entry: `onEngineBack` finds no layer open, no `tm`, and returns — the
address reads `/acquisition?panel=follow:Silo` with nothing open, and a reload at it reopens the
panel. Invariant 1 broken in the one direction nothing walks. Pre-existing class, made reachable
from a pasted link by this wave.

Fix: the boot's « read `panel=`, ask `resolves`, open » becomes ONE function the boot and the back
handler share; on a pop onto a `layer: "sheet"` entry with no panel open, that function reopens
the panel the ADDRESS names (under `pilotage`, pushing nothing — the entry exists). A value that no
longer resolves leaves the entry alone and logs. Holds in R56: Back then Forward → panel open
again, same title, address with `panel=`; a second Back → closed, `panel=` gone.
Mutation: make the Forward branch a no-op again → the hold falls.

## 9.5 — The B-046 hold tolerates the defect it was written for · MAJOR

`start_server(0, …)` yields an ephemeral port, but the hold asserts only `port != 0` and
`port not in RESERVED_PORTS` — and 8917/8918 are not reserved. `PROOF_PORT = 8918` put back into a
rule passes it. The mutation phase 8 ran (both servers INSIDE one rule forced onto 8918) is not the
defect's shape (two rules, one socket, in parallel).

Fix: a scratch server takes NO port — `start_server(root)` binds 0 always and yields the port;
both callers adapt; the docstring stops inviting a fixed one. One offline hold in `server.py`'s own
rule: every `start_server(` call site in `harness/*.py` passes a single argument (read the files
with a regex, name any offender). Mutation: give `screen_addresses.py` a second argument → falls.

## 9.6 — `hideSignIn`'s catch is unheld · MEDIUM

R69 restores the bridge BEFORE calling `hideSignIn()`, so reverting that catch to the bare one
leaves the rule green; the commit reports mutation (i) on `showSignIn` only. Fix: a fresh context,
gate raised normally, then the bridge broken, then `hideSignIn()` → the flag is raised. Mutation:
bare catch on `hideSignIn` → falls.

## 9.7 — The inline reader closes one shape and three equivalents still read clean · MEDIUM

Verified by running `arm_addressing` over mutated copies, all `0 violation(s)`: a method shorthand
`validateSearch(raw) { … }`; a helper reference `validateSearch: readSearch,` (the brace scan then
grabs the NEXT `=>` anywhere in the file — an unrelated block, which can also yield a FALSE
violation on a legitimate refactor); a return type not named `*SearchParams`
(`(s): AddQuery => …`); an object literal whose `page` key is not first (the key reader takes only
the first key). A page declared in `PAGE_PATHS` with no route file is also green.

Fix: (a) the body search is bounded to the member — the `=>`/`function`/`(` must sit right after
`validateSearch` (shorthand included); a reference to a name is resolved to that name's function
in the same file, and a reference that resolves to nothing is a VIOLATION (« cannot read »), never
silence; (b) the type read is the validateSearch's declared return type, whatever it is called,
plus `*SearchParams*`; (c) every key of every object literal in the body; (d) the summary line
prints how many `validateSearch` bodies were read; (e) a page path with no route is a violation
naming the page. Tests for each shape in `tests/scripts/test_check_frontend_boundaries.py`, each
seen red first.

Landed with two departures, recorded here rather than left to be re-derived. The source this
section wrote for the not-first-key case ends `page: String(raw.page ?? "")`, which the reader
ALREADY caught through `raw.page`: the case would have been green on arrival and measured
nothing, so its key is written `page: "acq"`, which is the key reader alone. And two cases join
the six, both on the bound: a resolved reference with an unrelated `{ page: … }` literal below it
must read CLEAN — the false violation this finding names, and the only case that measures it —
and a member shape the reader cannot follow must say « cannot read » instead of reading that
literal. The second was red before the fix; the first was not, because the old key reader was too
weak to produce even the false positive, so it is held by mutation instead. Seven mutations, one
per branch — member anchor, bound, reference resolution, return type, all-keys, page-without-
route, and the report of an unread body — each felling its own case and nothing else.

## 9.8 — The boot's three bare catches contradict « raised by every writer » · MEDIUM

R69's new docstring says the flag is raised by every writer. The boot's `__bridge.replace(nav,
arrivalAddress)`, `__bridge.replace({ tm: "garde" })` and `__bridge.record(nav, arrivalAddress)`
still swallow bare — and since phase 8 the panel's own entry is stacked on the last of them: a
failed `record` puts the panel's entry on the guard, the first Back spends it, and nothing says so.
B-026's recorded justification (« boot-time, pre-render ») is false on this branch: `render()` and
`__loadingDone()` both run before those writes. The `reopenPanel()` catch logs but does not flag.

Fix: the three catches and the reopen's log AND raise the flag, in English, like every other
writer. BUGS.md: B-026's residual note says it is closed here; B-043…B-048 move to `fixed`,
naming #484. Hold: R69's end-of-walk « no navigation write failed » already reads the flag; add
one that breaks `__bridge.record` from the page BEFORE a cold load cannot be done (the boot runs
first) — so the proof is the mutation: revert one catch, inject a throwing `record` through a
`page.add_init_script`, confirm the flag, restore. Write the init-script hold if it costs under
fifteen lines; otherwise the mutation run in the commit body is the proof.

## 9.9 — Smaller, confirmed

- `scripts/check-frontend-boundaries.py` ~651: « (D-8.2 — …) » — a phase-decision id in a source
  comment, forbidden by the phase's own directive. Say the reason without the tag.
- `withoutPanel` compares RAW parameter names while `destinationOf` decodes: `%70anel=` reopens
  the panel and survives the strip. Compare decoded names, keep the verbatim re-emission.
- R69: three sites crash the rule instead of felling a hold when a fixture rots
  (`sheet_ids[...]` after a falsy check, `INFLIGHT[0]`/`allSettings()[0]` in-page, `topics[0]`).
  Guard each so the failure reads as a fallen hold, not a traceback.
- R69: the `screens` list is a hand-written copy of `SCREEN_PATHS`; derive it from the model like
  the dials and the pages.
- R69 docstring: « the home page's path » → « the bare root » (item 4); « four addresses » → three.
- `addressOf` JSDoc `Args:` lacks `panel`; `arm_addressing`'s one-line summary omits the
  page-table hold; `withoutPanel`'s « verbatim » also drops empty pairs — say so.
- `server.py`: the second-server `except OSError` labels any `urllib` error « refused »; narrow the
  label to the connection error and let the rest say what they are.
- Two drops are silent: an empty `?panel=` and `/login?panel=…` are stripped with no warning. Log.
- Plan file phase 8: D-8.3 (« stripped in BOTH branches » — one branch strips, the other never
  composes), D-8.5 (three holds plus the end-of-walk read, not one), D-8.6 (six mutations, not
  four). Correct the decisions to what the code does.

## Ignored, with reason — recorded so the search is visible

- Bug numbers and wave names in OLD comments beside the changed code (`B-026`, `B-024`,
  « RENEGOTIATED BY L05 », « (Task 8) »), the README's `/profile/$title` row, the French
  `recordPath` message and the `__navEchec` name: pre-existing, inside the engine's declared debt
  or outside this wave's files. Open, not this phase's.
- `switchover.py`'s `stderr=PIPE`: rejected by two reviewers — `serve.py` silences per-request
  logging and the build's output never reaches the child's stderr.
- A second Back after closing a COLD screen reaches the exit guard (toast, then the document is
  left): the documented guard design, unchanged from `main`. Whether a cold screen should behave
  like the panel (its own entry, the guard untouched) is a design question for the operator.
