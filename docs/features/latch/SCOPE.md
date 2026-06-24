# latch — scope (skiff LITE)

**Ticket**: #113 — _Le bouton save config sur les pages sans config_
**roadmap**: `save-config-button-scope` · **bump**: patch (0.22.1 → 0.22.2)

## Problem

The config toolbar (Save · Validate · HealthPill) renders on every **board-scoped**
tab, not just the ones with editable config. `App.jsx:310` passes
`boardScope={!daemonScope}`, and `daemonScope` is true only for the three host-wide
tabs (`App.jsx:224`: `daemon | profiles | admin`). So `boardScope` is true for all
eight board tabs — `monitoring`, `board`, `issues`, `columns`, `transitions`,
`defaults`, `validation`, `yaml` (`SidebarNav.jsx:45-54`). The Save button is gated
on `boardScope` at `AppShell.jsx:124` (mobile), `:191` (mobile Validate), and `:389`
(desktop HealthPill + Validate + Save), so it shows on Monitoring / Board / Issues /
Validation / YAML — pages with no editable config. Per the ticket it should appear
only on pages with **editable config**.

Only three tabs edit config — they receive the live `draft` + `update` props and an
`onSave` that calls `api.saveConfig` (`App.jsx:255-278`, save handler `App.jsx:169-176`):
`columns`, `transitions`, `defaults`. `validation` (read-only V1–V11 findings) and
`yaml` (read-only render) do **not** edit config.

## Change

Introduce a `configScope` predicate = active tab ∈ {`columns`, `transitions`,
`defaults`} and gate the **config toolbar cluster** on it instead of `boardScope`.
The cluster (Save + Validate + HealthPill) is one semantic group already wrapped
together at `AppShell.jsx:389`; gating only Save would leave Validate ("Check the
configuration for errors") and the config-health pill stranded on no-config pages —
an incoherent half-fix. `boardScope` is retained for what is genuinely board-scoped:
the board/daemon scope **badge** (`AppShell.jsx:365`).

Read-only-view note: with unsaved edits on a config tab, navigating to `validation`
or `yaml` hides Save until you return to a config tab. Acceptable — those tabs don't
mutate the draft, and `validation`'s findings deep-link back to the offending config
tab via `onGoto` (`App.jsx:185-189`), where Save reappears.

## Checklist plan

1. `web/src/App.jsx` — add `const configScope = ["columns", "transitions",
   "defaults"].includes(active);` (near the `daemonScope` derivation, `App.jsx:224`)
   and pass `configScope={configScope}` to `<AppShell>` (alongside `boardScope`,
   `App.jsx:310`). Keep `boardScope` — the scope badge still needs it.
2. `web/src/components/AppShell.jsx` — add `configScope = false` to the destructured
   props (next to `boardScope`, `:27`). Change the three config-toolbar gates from
   `boardScope &&` to `configScope &&`: mobile Save (`:124`), mobile Validate (`:191`),
   desktop cluster (`:389`). Leave the scope badge gate (`:365`) on `boardScope`.
3. Manual verify (no JS test harness exists in `web/` — only `vite build`; CI gate is
   Python): on Monitoring/Board/Issues/Validation/YAML the Save·Validate·HealthPill
   cluster is absent while the board badge remains; on Columns/Transitions/Defaults
   the cluster shows and Save still saves; daemon-scope tabs unchanged.
4. Version bump (build stage): 0.22.1 → 0.22.2 across the 5 sync points.
