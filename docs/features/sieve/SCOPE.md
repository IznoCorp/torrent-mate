# sieve — status filter on the Issues list (KanbanMateUI)

- **Ticket**: #92 · **track**: lite · **roadmap**: sieve · **bump**: minor (0.22.5 → 0.23.0)

## Problem

The Issues hub (`web/src/panels/IssuesPanel.jsx`) renders a flat list of every board ticket, each
row already showing its status as a `Badge` of `column_name` (`IssuesPanel.jsx:414`). On a busy
board the list is long and there is no way to narrow it to a single status (column). The operator
wants a selector to filter the list by status — where a ticket's "status" is the board column it
sits in (Backlog, Spec, Plan, Review, Done, Cancel, …).

## Change (bounded, mechanical)

Add a single client-side **status filter** `Select` to the LIST view toolbar. No server change, no
new dependency, no persistence — it filters the already-loaded `board` data in memory. The panel
already loads the full board via `api.monitorBoard(project)` (`IssuesPanel.jsx:43`) and already
derives the column name map from `board.columns` (`{key, name}`, `IssuesPanel.jsx:55-56`), so every
input needed already exists.

The filter operates on the stable column **key** (not the display label): the `issues` memo
(`IssuesPanel.jsx:53-64`) currently drops `column_key`, so it must also carry `column_key` through
to enable a key-based predicate. Filtering by key (not name) is robust to display renames and avoids
the label/key ambiguity.

The `Select` component (`web/src/ds/_ds_bundle.js:776-869`) accepts `options` as either `string[]` or
`{value, label, disabled}[]`, with a native `onChange` event (`e.target.value`), and `value` /
`size` / `mono` props — exactly as used in `SidebarNav.jsx:260` and `MonitoringPanel.jsx:1195`.

## Checklist plan

1. **`web/src/panels/IssuesPanel.jsx`** — add `Select` to the design-system destructure
   (currently `{ Banner, Button, Input, Badge, Tooltip }` at `:13-14`).
2. Same file — add filter state: `const [statusFilter, setStatusFilter] = React.useState("");`
   (`""` = all statuses). Place it with the other `list` state near `:27-29`.
3. Same file — in the `issues` memo (`:53-64`), include `column_key: tk.column_key` in each mapped
   object (alongside the existing `number`, `title`, `column_name`) so the filter predicate has a
   stable key to match.
4. Same file — derive the filter options + filtered list (memo or inline, in board order):
   - options: `[{ value: "", label: t("issues.filter_all", "All statuses") },
     ...(board?.columns || []).map((c) => ({ value: c.key, label: c.name }))]`.
   - filtered: when `statusFilter` is `""` show all, else
     `issues.filter((it) => it.column_key === statusFilter)`.
   Render the filtered array (not `issues`) in the list `.map` at `:372`, and feed the filtered
   length to the `issues.count` string at `:347`.
5. Same file — render the `Select` in the LIST toolbar (`:333-349`, the flex row holding the
   "+ New ticket" button and the count). Add it after the count span: controlled `value={statusFilter}`,
   `onChange={(e) => setStatusFilter(e.target.value)}`, `options={statusOptions}`, `size="sm"`,
   wrapped in a `Tooltip label={t("issues.filter_tip", …)}`. Match the existing toolbar JSX shape.
   Guard rendering on `board` being loaded (options come from `board.columns`).
6. **i18n** — add the two new strings under the `issues:` block in **both**
   `web/src/i18n/en.yaml` (`:242-267`) and `web/src/i18n/fr.yaml` (`:246-271`), mirroring the existing
   `issues.count` / `issues.new_tip` keys:
   - `issues.filter_all` — EN "All statuses" · FR "Tous les statuts"
   - `issues.filter_tip` — EN "Filter the list by status (board column)" · FR "Filtrer la liste par
     statut (colonne du board)"
   Use the `t("issues.filter_all", "All statuses")` inline-fallback form already used throughout the
   panel.

## Verification

The `web/` SPA has **no JS test framework** (only `dev`/`build`/`preview` scripts; zero `*.test.*`
files) — verification mirrors the repo's UI convention: `npm run build` succeeds, then a manual
check in the Issues panel that selecting a status narrows the list to that column and "All statuses"
restores the full list. **No Python layer is touched**, so `make lint` / `make test` are unaffected.
Per the project's version-sync rule, bump all 5 points to `0.23.0`: `VERSION`,
`pyproject.toml`, `src/kanbanmate/__init__.py`, `.claude-plugin/marketplace.json`,
`plugin/.claude-plugin/plugin.json`.

## Notes

- **Pure client-side filter**: no board write, no persistence, no concurrency — the filter only
  hides/shows already-loaded rows. Reversible and side-effect-free (confirms the triage `lite`
  sizing: no novel decision, no unknown, no risky choice).
- **Filter by key, not label**: matching on `column_key` keeps the predicate correct even if a
  column is renamed in config; the dropdown shows the human `name` but selects on `key`.
- **Not re-routable**: a purely additive UI affordance over data the panel already loads — no design
  question, no irreversible choice.
