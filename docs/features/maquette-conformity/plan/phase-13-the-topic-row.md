# Phase 13 — The topic row (D.1 #11)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "minWidth: 0, flex: 1" -g '*.tsx' frontend/maquette/design/src` → **5** lines (the report's
  « six compositions »: `features/system/page.tsx:133`, `features/maintenance/page.tsx:114`,
  `features/settings/page.tsx:287, 295, 304`, one composition spanning two); `rg -n "\"rt\"|\"rs\"|\"rn\""
  -g '*.tsx'` → the bare classes.
- **Points ≈ 11.** `ui` `TopicRow` (title, subtitle, trailing value) ≈ 35 lines new (4); six compositions converted
  (≈ 25 lines, 5); R-conformity-k (the count → 0, geometry held by the oracle's region comparison) (2).
- **Readers.** `topics.py`, `settings.py`, `machine.py`, `levers.py`, `locks.py` and others read `topic` parts — kept.

## Red today

R-conformity-k: `minWidth: 0, flex: 1` outside `ui/` → **5**.

## Mutation

Re-type one composition inline → falls by name.

## Oracle: states that diverge, declared by name

None expected — `settings`, `maintenance`, `system` unchanged in geometry. A divergence is STOP A.

## Commit

`refactor(maquette-conformity): one topic row component, six hand compositions gone`
