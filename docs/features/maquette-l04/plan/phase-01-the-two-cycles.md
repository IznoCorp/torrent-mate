# Phase 1 — The two cycles break

**This is the only real code change in the lot, and it lands alone.** Everything after it changes
where a file sits; this changes what a module resolves to. Separated, a divergence has one
possible cause — which is the whole reason L04 depends on L01.

## What is wrong, exactly

The graph reports **three simple cycles over two back-edges**. The distinction matters when the
fix is verified: removing one edge removes two cycles.

```
components/panel.tsx  →  data.ts  →  components/panel.tsx
components/panel.tsx  →  settings-labels.ts  →  data.ts  →  components/panel.tsx
screens/add.tsx       →  shell.tsx  →  screens/add.tsx
```

| Back-edge                        | Its two halves                                                                                                      |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `data.ts → components/panel.tsx` | `data.ts:6` imports `type PanelDescriptor`; `panel.tsx:24` imports `useReference`, `type Setting`, `type Reference` |
| `shell.tsx → screens/add.tsx`    | `shell.tsx:46` imports `AddScreen`; `add.tsx:42` imports `go`                                                       |

## The change

**1. `PanelDescriptor` gets its own module, at its FINAL path.** The descriptor is the contract
between a panel PRODUCER and the panel RENDERER — it belongs to neither. It moves to
`ui/panel/descriptor.ts`, which both sides import and which imports nothing from either.
`seams.ts` (which also imports the type) follows to the same module in the same commit.

**2. `go()` leaves `shell.tsx` for `lib/navigate.ts`.** It takes a path and params, knows no
domain and renders nothing, so `lib/` is its home by the lot's own placement rule. The router
instance reaches it through a live binding filled at boot — the pattern `seams.ts` already proves
here — so `lib/` never imports `app/` and no cycle is reintroduced.

**Files land at their TARGET path, not at an interim one.** The lot's own reason for existing is
« deciding afterwards means moving them twice »; creating these two at their final home now is
strictly cheaper than moving them in phase 4.

## The three ends that move with `go()`

`go()` is pinned by NAME in a harness rule, and a rule left pointing at an old home is a rule that
stops measuring.

| End                  | Where                                                                                             | What changes               |
| -------------------- | ------------------------------------------------------------------------------------------------- | -------------------------- |
| The function         | `shell.tsx:470`                                                                                   | moves to `lib/navigate.ts` |
| The rule             | `harness/navigation.py` — `if file.name != "shell.tsx"` and `cleaned.find("export function go(")` | reads the new file name    |
| The rule's own prose | `navigation.py`'s header, which states « once inside `go()`'s own body in `shell.tsx` »           | states the new home        |

R76's SUBSTANCE does not change: exactly one `navigate(` call outside the engine, inside `go()`'s
own body, followed immediately by a flush. Only its address does.

## Proof

- The cycle arm of the new guard reports 0. It does not exist yet — phase 1 writes **only that
  arm**, as a standalone check, and phase 5 folds it into the seven-arm script with the rest. A
  cycle broken with nothing able to say so is a fix nobody can defend.
- **Mutation**: restore `data.ts`'s import of `PanelDescriptor`, confirm the arm falls and names
  that edge; restore. Same for the `add.tsx → shell.tsx` edge.
- `npm run typecheck` exits 0.
- **The oracle reports 0 divergence.** This is the phase's real proof: a code change that moved no
  rendering.
- `python3 frontend/maquette/harness/navigation.py` exits 0, and is seen RED first with the rule
  still naming `shell.tsx` — which proves the rule was actually reading the file it names.

## Trap met here

**A failed command is an edit that did not happen.** The rename of `go()`'s call sites goes
through `scripts/rename-identifiers.py` where it is a rename, and the diff is re-read afterwards —
not the tool's « N file(s) touched » line. Two corruptions in this repository were found exactly
that way.
