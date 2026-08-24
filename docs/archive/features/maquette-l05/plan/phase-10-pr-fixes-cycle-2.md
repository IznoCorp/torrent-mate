# Phase 10 — PR #484 fixes, review cycle 2

Two reviewers read phase 9 (`git diff 2ea7bdd3..HEAD`) against the cycle-1 findings. Phase 9
closed what it was asked to close, and opened three things of its own — which is the review's
whole point: a fix is code nobody has read yet. Every finding below was re-verified by the
orchestrator by reading the code and, where a probe existed, by its output.

**The pull request must not merge until 10.1–10.4 are closed.** 10.5 and 10.6 ride along.

The running directives of phase 8 — « How this phase runs » in `phase-08-pr-fixes-cycle-1.md` —
apply unchanged: reproduce, fix, hold, mutation; the build+copy recipe WITH the `rm -rf`; every
`legacy.js` and `.md` edit through a Python write (the formatter hooks reformat whole files);
`ruff check` only on harness/scripts; English only; no phase, session, bug or wave reference in a
source comment. Branch `fix/maquette-l05`, same version.

## 10.1 — The reopen fires on a Back onto a BURIED sheet entry, over the wrong page · MAJOR

`onEngineBack`'s new branch (`legacy.js` ~11058) reopens a panel whenever the entry landed on
is `{ layer: "sheet" }` and no panel is open — it cannot tell a Forward from a Back, because the
bridge hands over `location.state` only. A sheet entry gets buried on a reachable walk: the tab
bar sits ABOVE the layers (`.bottombar` z-50 over `.sheet` z-47), and a `data-page` tap while a
panel is up calls `hideLayers()` (which closes the panel WITHOUT popping) then `recordPath()`
(which pushes the new page on top of the sheet entry). Walk: `/acquisition`, open
`follow:Silo`, tap « Maintenance », press Back → the panel reopens over the MAINTENANCE page, the
branch `return`s before the `tm: "nav"` state is applied, and the bar reads
`/acquisition?panel=follow%3ASilo` over a maintenance frame. Before phase 9 that Back was a silent
no-op (a wrong address); now it is a wrong interface.

Fix: the bridge passes the traversal DIRECTION to the engine — `onBack`'s callback receives
`(state, direction)` with `direction` the history action (`BACK` / `FORWARD` / `GO`; read
`shell.tsx` ~319–327, the subscription already has `action.type`). The reopen fires on FORWARD
only. On a BACK (or GO) that lands on a sheet entry with no panel open, the entry is a closed
panel's leftover: go back once more (`__bridge.back()`), announcing the extra pop to the latch the
way a layer's own unwind does (read `__announcePops` / `unwindInProgress` and use the same
mechanism), so the pop lands on the nav entry beneath and its state applies. Holds in R56: the
tab-bar walk above → after one Back the page is `acq`, no panel, address `/acquisition`, no JS
error; the existing Forward hold stays green; a second Back from there reaches the guard.
Mutation: reopen on any direction again → the tab-bar hold falls (panel open over `maint`).

## 10.2 — Two of the three boot catches are held by nothing · MAJOR

R69's init-script seam (`REFUSE_THE_BOOT_WRITE`) wraps `History.prototype.pushState` only. The
boot's three writes are `replace`, `replace`, `record` — the bridge maps `replace` to
`replaceState` — so the seam refuses the arrival-entry `record` and nothing else. Revert either
`replace` catch to bare and R69 stays green, while docstring item 10 (and D-8.5 as corrected) says
all three are broken from outside the page.

Fix: the seam wraps `replaceState` as well — one seam per write, each a separate context: refuse
the first `replaceState` whose URL carries the arrival address (the settlement), the first
`replaceState` whose state carries `tm: "garde"` (the guard), and the first `pushState` of any kind
(the record) — and each hold ALSO asserts the refused URL/state is the boot's own
(`BOOT_ADDRESS` / the guard marker), so a rot where the boot's write stops going through that
primitive while a later writer still does reads as a rotted seam, not as an unraised flag. Three
holds + three seam holds. Docstring item 10 and D-8.5 say exactly what is held. Mutation: revert
each `replace` catch in turn → its hold falls.

## 10.3 — The reader reads the wrong text and says it read a body · MAJOR + MEDIUM + MINOR

Verified over copies of the real tree, all `0 violation(s)`, all counted as « 4 bodies read »:

- `validateSearch: (raw): { page?: string } => ({ page: … })` — the `{` of the INLINE RETURN
  TYPE wins over the `=>`, the type literal is read as the body, `page?:` matches no key;
- `validateSearch: reader("page"),` + `function reader(key) { return (raw) => ({ [key]: … }) }`
  — a CALL is treated as a reference to its callee, the factory's body is read and counted;
- a destructured parameter `({ page, ...rest }) => ({ ...rest })` — the parameter list is skipped;
- `raw['page']` (single quotes) and `raw?.page` — unmatched.
  And two FALSE violations: a comment `// validateSearch: the raw query is never trusted` is read as
  a member (« names « the », which this file declares nowhere ») — the gate is in `make check` and
  CI, so a legitimate comment fails the build; and `literal_keys` reads `identifier :` anywhere in a
  brace block, so `const cfg: string = ""` or `raw.x ? acq : sys` inside the body invent page keys.
  `test_m` compares the bodies-read count with the anchor regex's own count — the model against
  itself; it stayed at 4 while the wrong text was read.

Fix, tests FIRST and red: (a) strip `//` and `/* */` comments and string literals (single, double,
template) from the route text before the member scan; (b) an inline return type — a balanced
`{…}` between `):` and `=>` — is read as the TYPE (its keys, `?` tolerated) and the `=>` body is
read as the body; (c) a name followed by `(` is a CALL → the « cannot read » violation, not a
resolution; (d) the parameter list is read for destructured keys; (e) `raw['x']`, `raw?.x`,
`raw?.["x"]` match; (f) `literal_keys` reads keys only where an object-literal key can sit — after
`{` or `,` at that brace depth, and never a `?:`/ternary operand or a type annotation; (g)
`test_m` becomes non-vacuous: a copy where one member is unreadable must report `3 … read` AND a
violation; (h) the « declares nowhere » sentence is reserved for a name absent from the file; a
name present in a shape the reader does not follow gets the « does not follow » sentence. Each
shape a test case; each seen red first; each new branch mutation-tested.

## 10.4 — The `constructor` hold hangs on a console string held by nothing · MEDIUM

With `sheetFor` back in `knownMedium`, `follow:constructor` does not fabricate — the opener
crashes first (`SEASONS["constructor"].slice`), the panel stays closed, `panel=` is off the
address: every primary conjunct is GREEN, and the only thing that fells the hold is the console
text « reopening the addressed panel failed », which no rule holds against the engine. Reword the
`console.error` and the hold is vacuous against the defect it names.

Fix: since 9.8 that catch raises `window.__navEchec`; the hold reads the flag (a fresh context
starts it false), and keeps the console note as evidence only. Mutation: `sheetFor` back → falls
on the flag.

## 10.5 — The scratch-server call-site hold reads one line at a time · MEDIUM

`server.py`'s offline hold runs its regex per LINE, so a call wrapped by the formatter
(`start_server(\n    8918, ROOT\n)`) matches nothing, and `start_server(f(a, b))` would be flagged
for the inner comma. Fix: `re.finditer` over the whole file text with a balanced-parentheses
argument read; an alias import (`from server import start_server as X`) is out of scope — say so in
the hold's comment. And the second-server labels: `urlopen` wraps `ConnectionRefusedError` in
`URLError`, so the `isinstance(error, ConnectionRefusedError)` branch is unreachable from the
request and `EADDRINUSE` cannot come from a port-0 bind — drop the dead branch, keep « answered N »
/ « unreachable » / « failed to start ». Mutation: a wrapped two-argument call in a copy → falls.

## 10.6 — Smaller, confirmed

- `legacy.js` ~34502: a panel refused because the PAGE is not served (`/nimportequoi?panel=…`) is
  logged as « names nothing this interface holds » — false, Silo is held; say the address is.
- The two drop warnings (empty `?panel=`, `/login?panel=`) are read by no rule; one R69 hold per
  drop reading the console (the rule already listens to it for 9.1's crash note).
- `shell.tsx` ~551: « which is the wave's headline surface » — a wave reference in a source
  comment; drop the clause.
- `tests/scripts/test_check_frontend_boundaries.py` ~91: « The fourteen mutation cases » → the
  real count, and keep it true after 10.3's additions (or say « the mutation cases » and let the
  list speak).
- R69 seam hold: « the seam really did refuse the boot's write » must assert WHICH write (the
  refused URL equals `BOOT_ADDRESS`) — folded into 10.2.

## Ignored, with reason

- 339 of 344 `LIBRARY` titles reach `openFollowSheet`'s synthesised `{ k: "show",
st: "up_to_date" }` from an address — exactly as from the in-app door (`openDetailSheet` IS
  `openFollowSheet`), the decision D-8.3 records. The « Série » label on a film through that
  fallback is a pre-existing producer defect, recorded for the operator, not this phase's.
- `armedExit` not cleared by the reopen branch: same shape as the `panel.isOpen()` branch above
  it, pre-existing.
- Refusing `async`, a cast, a generic arrow and an imported helper as « cannot read »: the plan's
  deliberate choice — four legal TypeScript shapes are unusable in a route; recorded, not changed.
