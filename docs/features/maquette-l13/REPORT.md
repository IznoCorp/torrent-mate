# L13c — what the engine was blocking: the report

Every line below is a command re-run on this branch's head, with what it printed. A claim that
cannot be re-run is not here.

## The nine phases, and what each moved

| Phase | Subject | Rule, seen red first | Mutation, by name |
| --- | --- | --- | --- |
| c·1 | A library selection survives a change of listing (B-312) | R195 `selection_survives_the_listing.py`, 14 holds — 11 FAIL on the tree | the `lens` write put back: both « the lens » holds |
| c·2 | « + » opens a fresh add screen (B-340) | R196 `add_screen_opens_fresh.py`, 7 holds — 4 FAIL | the stored query handed back (2 holds); the visit not begun (2 holds) |
| c·3 | A spent panel action is drawn as disabled (B-339) | R197 `disabled_action.py`, 5 holds — 1 FAIL (the « + » icon); the opacity half was L20's, in `60c6d9b1d` | `disabled:opacity-50` removed (3 holds); `icons.plus` handed back (1) |
| c·4 | The kind chips hide their bar (B-336) | R198 `kind_chips_scrollbar.py`, 4 holds — 2 FAIL at 390 and 369 px | the two declarations removed: both widths |
| c·4-bis | The sheet's cast strip, the same defect | R198 gains 2 holds — 1 FAIL | the declarations removed on `castList` |
| c·5 | The pull indicator follows the refresh (B-331) | R199 `pull_follows_the_refresh.py`, 5 holds — 4 FAIL at two answer times | a fixed delay restored (2 holds); `place-items-center` removed (1) |
| c·6 | The seventh scheduler (B-327) | B-327's own kept hold, restored in `machine.py` — FAIL: six drawn against seven real | the seed row removed |
| c·7 | A follow cannot be built without an identity (B-366) | R200 `follow_needs_an_identity.py`, 4 holds — 2 FAIL | the layer's refusal removed: both |
| c·8 | The library's states at rest (B-345, library half) | R128 gains 8 holds, GREEN from the start — the seeds already hold every state | a category emptied; the duplicate title made single |
| c·9 | This close | — | — |

## The register, row by row

| Row | Reading |
| --- | --- |
| B-312, B-340, B-339, B-336, B-331, B-327, B-366 | `to confirm` — each closed by its phase, with the rule's red reading and its mutation in the entry |
| B-345 | its LIBRARY half `to confirm`; the other surfaces' share is measured by nobody here and returns to the steward |
| B-337 | stays `open`: its reading is the operator's, on his device (b·8) |
| B-232, B-352 | `fixed #596` |
| B-465, B-290, B-397, B-275 | `fixed #601` |
| B-071, B-220, B-236 | `fixed #505`, `fixed #528`, `fixed #558` — DESIGN § 9.10 calls them stale to be closed; they are already closed, and the steward has nothing left to do on them |
| B-539 | filed by this wave, renumbered **B-548** at the merge of main's own B-539–B-547: named states inherit a library dial by their ORDER, and the oracle's reference records it |

## The counts, from the prototype itself

| Figure | Command | Reading |
| --- | --- | --- |
| Named states | `window.__states().length` | **114** (113 + `lib-selection-filtered`) |
| Mock routes | `window.__mocks.routes().length` | **63** — `frontend/maquette/README.md` said 54, corrected here to be counted and not written |
| Rules | `run.sh` (no flag) | **146** rules and **26** repository guards |

## The gates

| Gate | Log | Reading |
| --- | --- | --- |
| MIDPOINT full suite | `midpoint-full-suite-2.log` | 146 rules + 26 guards, no violation; a11y 114 states 0 violations, light 147 against a ceiling of 147; oracle no divergence |
| Per-phase gates | `c0*-gate*.log` | each `gate: no violation`, oracle read every time |
| Oracle acceptances | `c01-oracle-accept.log`, `c06-accept.log` | two, each verified by script: one new state (18 regions), and one state 55.4 px taller for one row |

## What this wave learned, and wrote down

- A named state RESETS the mock scenario: a latency asked for before the state is asked for nobody.
- A rule that reads « the indicator is still up » cannot read anything once the refresh it stands
  for answers instantly — two readers were re-aimed with an answer time, said in their files.
- A module CYCLE moves a boot: importing the query client into the pull indicator moved the
  outbox's own boot, and R107 caught it at the midpoint. The refresh is handed in instead.
- A pinned COUNT in a unit test moves with a seed row.
- A paged listing judged by one page, or by `total` where `loaded` is what the layer holds, invents
  holes that are not there.
- A rule asserting the OLD behaviour is a reader a phase's opening measure must list: `virtual.py`
  held « a search drops the selection », the decision the operator had overruled.
