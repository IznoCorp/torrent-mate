# Phase 5 — Live regions and states

## Gate

Produced by Phase 4:

- The focus manager is installed and its rule holds: focus enters a layer, the background is
  inert, `Escape` closes, focus is restored.
- Full harness suite green, oracle at 0 divergence.

Focus before announcements: a live region that fires while focus is lost announces into nowhere.

## What this phase does

Today a screen reader says nothing about what the application is doing. The pipeline advances,
a scan loads, a delete succeeds, a request fails — and the interface reports all of it visually
and only visually.

This phase is small in markup and large in consequence, and it is last among the content phases
because it names states the previous three phases gave a place to.

## Sub-phases

### 5.1 — The toast is announced

`#toast` becomes `role="status"` (polite, so it does not interrupt), and its dismiss button keeps
the name Phase 3 gave it. The toast is the interface's one general-purpose « something happened »
channel, so it is the highest-value single attribute in the lot.

One trap, and it is why this is its own sub-phase: a live region must exist in the DOM *before*
the text lands in it, or nothing is announced. `#toast` is in `index.html` and is filled by
`select("#toastmsg").innerHTML = …` (`legacy.js:10725`), which is the correct order already —
this must be confirmed by the rule, not assumed from the markup.

Commit: `feat(maquette-l03): the toast is announced instead of only shown`

### 5.2 — Loading surfaces are busy

Loading states carry `aria-busy="true"` while they load and lose it when they settle. The
prototype has loading states in most of its 83 named states — the `*-chargement` family — so this
is a well-bounded, enumerable set rather than a judgement call.

Commit: `feat(maquette-l03): a surface that is loading says so`

### 5.3 — Errors are announced

The error states (`*-erreur`, `*-panne`) announce rather than merely render. `role="alert"` where
the error interrupts a task; `role="status"` where it is informational. The distinction is
decided per state and recorded in the sub-phase's commit body.

Commit: `feat(maquette-l03): an error reaches a listener, not only a reader`

## Verification

| ID | Command | Expected |
| --- | --- | --- |
| ACC-12 | `python3 frontend/maquette/a11y.py --check --rules aria-valid-attr-value,aria-required-attr,region` | 0 violations over 83 states |
| — | `python3 frontend/maquette/oracle.py --check` | 0 divergence |
| — | `frontend/maquette/harness/run.sh` | no rule falls |

## A note on what cannot be automated here

axe verifies that a live region is *well formed*. It cannot verify that it *announced* — that
requires a screen reader, and no automated gate in this repository has one. The honest statement
in the wave's PR is therefore: the regions are correct and correctly ordered; whether the
announcement is useful is judged by the operator, not by a green command. **Saying that plainly
is the point.** A gate proves what it reads.

## Out of scope for this phase

Making the floor hard, the mutation checks, and the L06 handover (Phase 6).
