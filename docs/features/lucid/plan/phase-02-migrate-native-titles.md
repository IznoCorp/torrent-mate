# Phase 2 — Migrate 39 native `title=` to `<Tooltip>`

> Covers DESIGN §5.3 (single mechanism migration). Every native HTML `title=` on an intrinsic DOM
> element in `web/src` (excluding `web/src/ds/`) is replaced with the DS `<Tooltip>` component +
> `t("tip.<key>", "EN fallback")`. The 32 DS-component `title=` **props** (`Banner`/`PageIntro`/
> `Dialog` headings) are explicitly excluded (§3).

## Gate

**Phase 1 must have produced:** `--tooltip-bg`/`--tooltip-text` tokens present in both themes;
Tooltip component in `_ds_bundle.js` uses the new tokens, has `useId`+`cloneElement` a11y, and
tap-to-open; `make test` passes; contract test green.

---

> **Inventory corrected at implementation time (the `lucid` build).** Walking each `title=` to its
> real opening tag (not the line-based proxy) shows **17 native** intrinsic-DOM `title=` across **8
> files**, not 39/15 — the proxy mis-bucketed 22 multi-line component-prop `title=` as native (DESIGN
> §3 correction). `WizardPanel`, `AdminPanel`, `ProfilesPanel`, `SyncBoardDialog`, `SidePanels`,
> `ColumnsPanel`, `FilePicker` have **no** native site and are excluded. All 17 already used `t()` or
> carried dynamic data ⇒ **no new `tip.*` keys** introduced by the migration (sub-phase 2.3 is a no-op
> for it; new keys come from Phase 3).

### Sub-phase 2.1 — Migrate the high-count panels (10 sites, 2 files)

**DESIGN:** §3 inventory table, §5.3 migration rules. Files and counts:

| File | Native `title=` count |
|---|---|
| `web/src/panels/MonitoringPanel.jsx` | 5 |
| `web/src/panels/BoardPanel.jsx` | 5 |

**Approach per file:**

1. Run `rg -n 'title=' <file> | rg -v '<[A-Z]'` to get the current line numbers (they shift after
   each edit — work bottom-up to preserve line anchors).
2. For each native `title=` site: replace the native attribute with a `<Tooltip>` wrapper.

**Pattern — before (native `title=` on a DOM element):**
```jsx
<button title="Reload the board" onClick={handleRefresh}>…</button>
```

**Pattern — after (DS `<Tooltip>` + i18n):**
```jsx
<Tooltip label={t("tip.board_refresh", "Reload the board from the server")}>
  <button onClick={handleRefresh}>…</button>
</Tooltip>
```

**Rules (from DESIGN §5.3):**
- Reuse existing `tip.*` keys where text matches (e.g. `board_refresh`, `logout`, `install`…).
- For new hint text not yet in the `tip:` namespace, use a new key name + English fallback; the
  i18n key entries are added in sub-phase 2.3.
- Wrap the smallest element that preserves layout (`Tooltip` renders `display: inline-flex`).
- Never touch `<Banner title=…>`, `<PageIntro title=…>`, `<Dialog title=…>` — these are headings.
- `ThemeSwitcher.jsx` (line 12, 1 native title=): the `<span title role="img" aria-label>` emoji
  glyph — convert to `<Tooltip>` with label text that explains the theme toggle action. It already
  has `aria-label`; keep it and add `describedby` for the tooltip.

**Tooltip strings produced (approximate — derive exact wording from the native `title=` text):**

For each site, extract the existing `title=` string, convert to terse imperative form (~≤6 words,
verb-first, no period), and assign a `tip.<key>`:

| Native `title=` example (from current source) | New `tip.<key>` | EN fallback |
|---|---|---|
| `title="Reload the board"` | `tip.board_refresh` | *(existing key — reuse)* |
| `title="Collapse"` | `tip.board_collapse` | Collapse column |
| `title={<…>}` (dynamic) | `tip.monitor_detail` | Show ticket detail *(example)* |
| *(span marker hint)* | `tip.monitor_marker_roadmap` | View roadmap document *(example)* |

> **Note:** Exact key names and English fallback text are derived from the current `title=` value
> at implementation time. Above is illustrative — the implementer reads each `title=` attribute
> inline and transforms it. Every key must be a valid YAML identifier under `tip:` (lowercase
> snake_case).

**Commit:** `feat(lucid): migrate native title= on high-count panels (24 sites)`

---

### Sub-phase 2.2 — Migrate the remaining panels/components (7 sites, 6 files)

**DESIGN:** §3 inventory table. Files and counts:

| File | Native `title=` count |
|---|---|
| `web/src/panels/TransitionsPanel.jsx` | 2 |
| `web/src/components/RichPromptEditor.jsx` | 1 |
| `web/src/components/ThemeSwitcher.jsx` | 1 |
| `web/src/components/SidebarNav.jsx` | 1 |
| `web/src/components/MarkdownField.jsx` | 1 |
| `web/src/components/AppShell.jsx` | 1 |

Same pattern as sub-phase 2.1: `rg -n 'title=' <file> | rg -v '<[A-Z]'` → replace each with
`<Tooltip label={t("tip.<key>", "EN fallback")}>…</Tooltip>`.

Work bottom-up within each file (highest line number first) to preserve line anchors.

**Commit:** `feat(lucid): migrate native title= on remaining panels/components (15 sites)`

---

### Sub-phase 2.3 — Add i18n keys for all new `tip.*` strings

**DESIGN:** §5.4 (i18n), §3 (existing 23 keys at `en.yaml:517`, `fr.yaml:528`).

**Files:** Modify `web/src/i18n/en.yaml`, `web/src/i18n/fr.yaml`

1. Collect every `t("tip.<key>", "…")` call introduced in sub-phases 2.1–2.2 that uses a key NOT
   already in the `tip:` namespace.
2. Add each new key + its English fallback text to the `tip:` block in `en.yaml` (following the
   existing alphabetical ordering or append).
3. Add each new key + its French translation to the `tip:` block in `fr.yaml`. **Every key in
   `en.yaml` MUST have a matching entry in `fr.yaml`** — a missing key silently falls back to
   English for FR users (`web/src/i18n/index.jsx:53`).

**FR wording convention** (DESIGN §5.4): terse imperative, verb-first, no trailing period, ≤ ~6
words. Mirror the existing keys at `fr.yaml:528` ("Enregistre vos modifications", "Se
déconnecter", "Lance un agent Claude sur ce ticket").

**Commit:** `feat(lucid): add i18n keys for migrated native title tooltips (en+fr parity)`

---

### Phase 2 quality gate (before moving to Phase 3)

- [ ] **0** native intrinsic-DOM `title=` remain — verified by a **tag-aware** scan that walks each
  `title=` to its opening tag (the line proxy `rg ... | rg -v '<[A-Z]'` is invalid; it false-positives
  multi-line component-prop `title=` — DESIGN §3/§7 gate 2). Component-prop `title=` (Capitalised
  owner) are expected and left.
- [ ] Tip key-set parity: collect all keys under `tip:` from `en.yaml` and `fr.yaml`, diff them —
  sets must be identical.
- [ ] `make lint` passes (no JSX parse errors from the migration).
- [ ] `make test` passes (contract test + any other tests).
