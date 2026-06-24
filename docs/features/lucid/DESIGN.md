# lucid — readable, self-documenting tooltips

> **Ticket**: #76 (Tooltips) · **Codename**: `lucid` · **Branch**: `feat/lucid` (to be created)
> **Type**: bugfix + enhancement (UI only — `web/`; no engine/Python change) · **Bump**: patch→minor
> (contrast bug = patch; exhaustive coverage + a11y + i18n surface = treat as **minor**).

`lucid` = legibility (dark-mode contrast) + a clear, self-documenting interface.

---

## 1. Problem

From the ticket (operator, FR):

1. **Dark-mode tooltips are black-on-black, unreadable** ("noir sur noir illisible").
2. **Tooltip coverage is sparse** — many buttons/actions have no explanatory hint. The stated goal:
   *the interface should be its own user manual* ("l'interface soit son propre manuel d'utilisation").

`DONE` = the bug class is eliminated (tooltips readable in **light and dark**), there is **one**
tooltip mechanism, coverage is comprehensive so common actions are self-explaining, **all** tooltip
text is i18n'd FR/EN, and there is **no mobile/a11y regression**.

---

## 2. Root cause (verified in source)

The shared design-system `Tooltip` styles its bubble with `background: var(--surface-inverse)` and
`color: var(--text-inverse)`:

- Source of truth (gitignored skill): `.claude/skills/kanbanmate-design/components/feedback/Tooltip.jsx:29`.
- Shipped compiled form (committed): `web/src/ds/_ds_bundle.js:2068-2069`.

The two inverse tokens are defined in `web/src/ds/tokens/colors.css`:

| Token | Light `:root` | Dark `.dark, [data-theme="dark"]` |
|---|---|---|
| `--surface-inverse` | `var(--foreground)` — dark (`oklch 0.21`) — `colors.css:165` | **repurposed** to `oklch(0.12 0.004 95)` near-black — `colors.css:275` |
| `--text-inverse` | `var(--background)` — light (`oklch 0.992`) — `colors.css:174` | **not overridden** → still `var(--background)` = `oklch(0.16)` near-black |

- **Light mode**: light text (`0.992`) on dark surface (`0.21`) → fine. ✓
- **Dark mode**: `--surface-inverse` was deliberately repurposed to a near-black so the terminal/YAML
  **inset panels** stay dark (comment at `colors.css:272-275`), but `--text-inverse` was *not* given a
  matching dark value — it stays `var(--background)`, which in dark resolves to `oklch(0.16)` (also
  near-black). Result: **near-black text on near-black surface** — the reported "noir sur noir". ✗

The defect is a **token collision**: the tooltip shares `--surface-inverse` with the terminal-panel
surface, and that token was tuned for the panels (dark in dark mode) without re-pairing the matching
text token. Any future repurposing of `--surface-inverse` can re-break the tooltip — so the fix must
**decouple** the tooltip from these shared inverse tokens.

Other `--surface-inverse` consumer: `web/src/ds/bridge.css:130`
(`background: var(--surface-inverse, #1e1e1e)` — a code/terminal panel surface, with its own
`#1e1e1e` fallback). It is **unaffected** by introducing tooltip-specific tokens; we do not touch
`--surface-inverse`.

---

## 3. Current state — coverage audit (verified counts)

Measured on this worktree (`rg` over `web/src`, excluding `src/ds/`):

| Metric | Count | How verified |
|---|---|---|
| DS `<Tooltip>` consumers | **24** | `rg -n '<Tooltip' src -g '*.jsx' -g '!src/ds/**'` |
| Raw `title=` occurrences | **71** | `rg -n 'title=' …` |
| → on **DS component props** (`<Banner title=…>`, `<PageIntro title=…>`, `<Dialog title=…>`) | **32** | `rg '<[A-Z][A-Za-z]*[^>]*\btitle='` — these are **headings, not tooltips**; LEAVE them |
| → **native HTML `title=`** on intrinsic DOM elements (browser tooltip) | **39** | the migration target set (§5) |
| Existing `tip:` i18n namespace keys | **23** in `en.yaml`, **23** in `fr.yaml` | `web/src/i18n/{en,fr}.yaml` (`tip:` block at `en.yaml:517`) |
| Existing `t("tip.*", "fallback")` call sites | 16 | `rg 't\("tip\.'` |

**Two corrections to the brainstorm** (which were grounded only by a coarse count):

1. The brainstorm reported "71 native `title=` to migrate". In fact **32 of the 71 are DS component
   `title=` props** (section headings on `Banner`/`PageIntro`/`Dialog`) — those are **not** native
   browser tooltips and must be **left alone**. The genuine native-tooltip target is **39** across
   **15 files**.
2. The brainstorm reported "0 real `tip.*` keys live in the yaml files yet". In fact a **`tip:`
   namespace already exists** with **23 keys in both `en.yaml` and `fr.yaml`**
   (`en.yaml:517`, `fr.yaml:528`), and 16 call sites already use `t("tip.key", "English fallback")`.
   `lucid` **extends** that namespace; it does not create it. The `t(key, fallback)` form is a
   documented, supported convention (`web/src/i18n/index.jsx:54-61`) — fallback is used only when the
   key is absent from **both** bundles.

### Native-tooltip migration inventory (per file)

> **Correction landed at implementation time (the `lucid` build).** The pre-implementation count of
> "39 native over 15 files" was derived from the line-based proxy `rg 'title=' | rg -v '<[A-Z]'`,
> which **mis-classifies a `title=` prop on a *multi-line* DS component** (where `<Component` sits on a
> previous line) as native. Walking each `title=` to its **actual opening tag** (a lowercase intrinsic
> element ⇒ native; a Capitalised component ⇒ prop) shows the real split: **17 native** intrinsic-DOM
> `title=` across **8 files**, and **54** component-prop `title=` (the 32 single-line ones the proxy
> already excluded **plus 22 multi-line ones the proxy wrongly bucketed as native**). 17 + 54 = 71
> raw ✓. Only the **17** are migrated; the 54 component props (`Banner`/`PageIntro`/`Dialog`/
> `StepBody`/`RuleList`/`DocLink`/`MarkdownReader`/`Button` headings & forwarded props) are left.

| # native `title=` | File |
|---:|---|
| 5 | `web/src/panels/MonitoringPanel.jsx` |
| 5 | `web/src/panels/BoardPanel.jsx` |
| 2 | `web/src/panels/TransitionsPanel.jsx` |
| 1 | `web/src/components/RichPromptEditor.jsx` |
| 1 | `web/src/components/ThemeSwitcher.jsx` |
| 1 | `web/src/components/SidebarNav.jsx` |
| 1 | `web/src/components/MarkdownField.jsx` |
| 1 | `web/src/components/AppShell.jsx` |
| **17** | **8 files** |

(`WizardPanel.jsx`, `AdminPanel.jsx`, `ProfilesPanel.jsx`, `SyncBoardDialog.jsx`, `SidePanels.jsx`,
`ColumnsPanel.jsx`, `FilePicker.jsx` carry **only** component-prop `title=` — no native site — and
are correctly excluded, as are `App.jsx`, `DaemonPanel.jsx`, `IssuesPanel.jsx`, `MarkdownReader.jsx`.)

All 17 native sites already routed their text through `t()` (or carried dynamic data such as a file
path / ticket number / column name), so the migration is **pure wrapping** — it introduced **no new
`tip.*` i18n keys**; the new keys come from the §5.4 coverage audit, not this migration.

---

## 4. Build & durability model (the brainstorm's #1 open question, resolved)

**There is no automated DS re-bundler in this repo.** Verified: the only repo files referencing the
bundle are `web/src/main.jsx` and `web/src/ds/react-global.js` (consumers), plus the contract test
`tests/web/test_design_system_contract.py`. No script regenerates `web/src/ds/_ds_bundle.js`.

The DS has two artifacts:

- **Canonical JSX source** — `.claude/skills/kanbanmate-design/components/feedback/Tooltip.jsx`. This
  lives in the **gitignored** `.claude/` skill repo (CLAUDE.md: "portable Claude config lives in
  `.claude/` … gitignored by this repo"), so it is **not committed by this repo**.
- **Shipped compiled bundle** — `web/src/ds/_ds_bundle.js` (committed). This is the
  JSX-compiled-to-`React.createElement` form (Tooltip at lines `2008-2095`). It is the **input to the
  vite build** (`web/vite.config.js:10`, `outDir: "../src/kanbanmate/webui"`), so it is what actually
  ships. The skill bundle (`3272` lines) and the web bundle (`4682` lines) **differ** — the web
  bundle is a superset that also embeds the app's `ui_kits/config/*` panels — confirming the web
  bundle is **hand-maintained**, not a verbatim copy of the skill bundle.

**Decision — patch both, ship from the committed bundle.** The Tooltip code change is applied to:

1. `web/src/ds/_ds_bundle.js` (the **shipped** artifact — the compiled `React.createElement` form, the
   one that must be correct for the fix to deploy), **and**
2. `.claude/skills/kanbanmate-design/components/feedback/Tooltip.jsx` (the JSX **source of truth**, so
   any future manual re-bundle preserves the fix). This edit is local/uncommitted (the dir is
   gitignored) — it is durability hygiene, **not** a shipping dependency.

The token change (§4.1) lives in `web/src/ds/tokens/colors.css` (committed, a vite build input) and
needs no bundle edit.

> **Constraint**: `web/src/ds/_ds_bundle.js` is authored in **compiled** form
> (`React.createElement(...)`, no JSX). The Tooltip patch in the bundle must be written in that same
> compiled style (mirroring the surrounding code at lines `2008-2095`), not as JSX. The JSX source
> file is where JSX is allowed.

---

## 5. Design

Four work-streams, matching the operator-confirmed brainstorm decisions.

### 5.1 Contrast fix — dedicated, self-inverting tooltip tokens

Introduce tooltip-specific tokens that **decouple** from `--surface-inverse`/`--text-inverse`, in
`web/src/ds/tokens/colors.css`:

```css
/* :root (light) */
--tooltip-bg:   var(--foreground);   /* dark surface in light mode  */
--tooltip-text: var(--background);   /* light text  in light mode   */
```

```css
/* .dark, [data-theme="dark"] — defined EXPLICITLY (operator decision: "both themes") */
--tooltip-bg:   var(--foreground);   /* light surface in dark mode  */
--tooltip-text: var(--background);   /* dark text   in dark mode    */
```

**Why this resolves the bug and can't regress:** `--foreground`/`--background` **flip** with the
theme (`colors.css:33,30` light; `192,191` dark). Pairing the tooltip bg/text to that pair makes the
tooltip the *true inverse of the current surface* in **both** modes — light mode → dark bubble + light
text; dark mode → light bubble + dark text — always high contrast. Because the tooltip no longer
reads `--surface-inverse` at all, the terminal-panel repurposing at `colors.css:275` can never collide
with it again. We define the tokens **explicitly in both scopes** (honouring the operator's "both
themes" decision and immunising against any future `:root`-only repurposing of these tokens), even
though the dark values are inherited-identical.

> **Contrast check (oklch L):** light mode L 0.992 text on L 0.21 surface (Δ≈0.78); dark mode L 0.16
> text on L 0.97 surface (Δ≈0.81). Both well above the legibility floor — and both are the *intended*
> inverse look the component had before `--surface-inverse` was repurposed.

`--surface-inverse` and `--text-inverse` are **left untouched** (terminal/YAML panels and
`bridge.css:130` keep their current behaviour).

### 5.2 Tooltip component — point at the new tokens + a11y + touch

Edit the Tooltip in **both** artifacts (§4). Current shape: a wrapping `<span>` with
`onMouseEnter/Leave` + `onFocus/Blur` toggling a `show` state, rendering an absolutely-positioned
`role="tooltip"` bubble (`Tooltip.jsx:7-41`; bundle `2015-2087`).

Changes:

1. **Tokens** — bubble style: `background: var(--tooltip-bg)`, `color: var(--tooltip-text)`
   (replacing `--surface-inverse`/`--text-inverse`). Everything else (position map, font/size,
   `--radius-xs`, `--shadow-md`, `km-tip` keyframe, `--dur-fast`/`--ease-out`) is unchanged — all
   those tokens are verified to exist (`spacing.css:29,46,61,62`; `typography.css:18,23`).
2. **Accessible name (`aria-*`)** — give screen-reader and touch users the hint that native `title=`
   used to provide. The bubble already has `role="tooltip"`; wire it properly:
   - generate a stable id with `React.useId()` (React 18.3.1 — `package.json:19`),
   - render the bubble with `id={tipId}`,
   - `React.cloneElement` the **single** child (every consumer passes one element — verified, e.g.
     `AgentTerminal.jsx:393-395` wraps one `<Button>`) to inject `aria-describedby={tipId}` and,
     **only when** `typeof label === "string"` **and** the child has no existing `aria-label`,
     `aria-label={label}`. DS `IconButton` spreads `...rest` onto the underlying `<button>`
     (`_ds_bundle.js:435` → `473`), so these attributes reach the DOM; the migration verifies the
     wrapped trigger forwards unknown props (else the hint is set on the wrapper span fallback).
   - Guard: if `children` is not a single valid React element, skip `cloneElement` and fall back to
     `aria-label={label}` on the wrapper span (no crash).
3. **Open on tap/focus (mobile)** — keep hover & focus; **add tap**. On a touch device there is no
   hover, so add an `onClick`/`onPointerDown` handler on the wrapper that toggles `show`, and close on
   `onMouseLeave`/`onBlur` (already present). Tapping a wrapped button still fires the button's own
   `onClick` (event continues to the child) — the wrapper toggle is additive. This restores, for
   touch, the discoverability that dropping native `title=` would otherwise remove.

   > The bubble keeps `pointerEvents: "none"` so it never intercepts the tap meant for the trigger.

4. **No new dependency, no API break.** Signature stays `Tooltip({ label, children, placement, style })`.
   All 24 existing consumers keep working unchanged; new behaviour is purely additive.

**Out of scope for `lucid` (brainstorm open question — decided):** viewport **collision-flip** /
edge-clipping auto-placement. The `placement` prop already lets callers pick a side; automatic
flip is a separate, larger enhancement. Recorded as a follow-up in §9, not built here.

### 5.3 Single mechanism — migrate the 39 native `title=` to `<Tooltip>`

For each of the 39 native `title=` sites (§3 inventory), replace the native attribute with the DS
component:

```jsx
// before
<button title="Reload the board" onClick={...}>…</button>
// after
<Tooltip label={t("tip.board_refresh", "Reload the board from the server")}>
  <button onClick={...}>…</button>
</Tooltip>
```

Rules for the migration:

- **Reuse existing keys** where the text already maps to a `tip.*` key (e.g. `board_refresh`,
  `logout`, `install`…); add new keys (§5.4) otherwise.
- The DS component requires a real wrapping element with a layout context; where a `title=` sat on a
  self-closing/inline element, wrap the smallest element that preserves layout (the component renders
  `display: inline-flex`, so it is layout-neutral for inline triggers).
- **Do not** convert DS component `title=` **props** (`Banner`/`PageIntro`/`Dialog`) — those are
  headings (the 32 excluded).
- `ThemeSwitcher.jsx:12` (`<span title role="img" aria-label>`) is an emoji glyph label, not a control
  hint — convert to `<Tooltip>` only if it carries an explanatory hint; otherwise keep the existing
  `aria-label` (it already has an accessible name). Decide per-site during implementation; default is
  to migrate so the hint is themed and visible on hover/tap.

After migration, **0** native `title=` remain on intrinsic DOM elements in `web/src` (excluding
`src/ds/`) — the verification gate (§7).

### 5.4 Coverage + i18n — exhaustive audit, real FR/EN keys

- **Audit every button/action in every panel** (the 15 migration files + the rest of `web/src/panels`
  and `web/src/components`) for **icon-only or ambiguous controls with no hint**, and add a
  `<Tooltip>` so the interface is self-documenting. This is additive coverage beyond the 39
  migrations.
- **Every** tooltip string routes through `t("tip.<key>", "<English fallback>")`, and **every key**
  gets a real entry in **both** `web/src/i18n/en.yaml` and `web/src/i18n/fr.yaml`, under the existing
  `tip:` namespace. Adding to both bundles is mandatory — a key present in `en.yaml` but missing from
  `fr.yaml` silently falls back to English for FR users (`index.jsx:53`), which would defeat the FR
  requirement. The plan must assert **key-set parity**: `keys(tip) in en.yaml == keys(tip) in fr.yaml`.
- **Wording convention** (brainstorm open question — decided): tooltip copy is a **terse imperative
  hint** — verb-first, no trailing period, ≤ ~6 words — matching the existing keys
  ("Reload the board from the server", "Send the Enter key", "Sign out"). FR mirrors the imperative
  ("Recharger le tableau", "Envoyer la touche Entrée", "Se déconnecter"). The plan codifies this so
  copy stays consistent across the new keys.

---

## 6. Files touched

| File | Change | Committed? |
|---|---|---|
| `web/src/ds/tokens/colors.css` | add `--tooltip-bg`/`--tooltip-text` in `:root` and `.dark,[data-theme="dark"]` | ✅ |
| `web/src/ds/_ds_bundle.js` | Tooltip bubble → new tokens; `useId` + `cloneElement` a11y; tap-to-open (compiled form) | ✅ (shipped) |
| `.claude/skills/kanbanmate-design/components/feedback/Tooltip.jsx` | same change in JSX source-of-truth | ⛔ gitignored (durability only) |
| 15 panel/component files (§3) | replace 39 native `title=` with `<Tooltip>` + `t("tip.*")` | ✅ |
| additional panels/components | add missing tooltips on icon-only/ambiguous controls | ✅ |
| `web/src/i18n/en.yaml` | extend `tip:` namespace (new keys, EN) | ✅ |
| `web/src/i18n/fr.yaml` | extend `tip:` namespace (same keys, FR) | ✅ |

No `src/kanbanmate/**` Python change. No `core/`/`app/`/`adapters/` change. No new third-party
dependency (no `pyproject.toml` / CI install change). The Python layering rules and dependency rules
do not apply — this is a pure `web/` change.

---

## 7. Verification (gates)

All must pass before the feature PR:

1. **Lint/test (repo)** — `make lint` and `make test` stay green; in particular
   `tests/web/test_design_system_contract.py` (Tooltip stays exported by the bundle — we only edit its
   body, not its `__ds_scope.Tooltip` export at `_ds_bundle.js:2088`/`4673`).
2. **No native `title=` left on DOM elements.** The line-based proxy
   `rg -n 'title=' web/src -g '*.jsx' -g '!web/src/ds/**' | rg -v '<[A-Z]'` is **not** a valid gate —
   it reports the 22 multi-line component-prop `title=` as false positives (see §3 correction). The
   real gate walks each `title=` to its opening tag and asserts **0** sit on a lowercase intrinsic
   element; the component-prop `title=` (Capitalised owner) are expected and left. Verified at
   implementation time: **0** native intrinsic-DOM `title=` remain, **45** component-prop `title=`
   left in the 15 audited files (54 total across `web/src` incl. excluded files).
3. **i18n key-set parity** — the `tip:` keys in `en.yaml` and `fr.yaml` are identical sets; every
   `t("tip.<k>", …)` call site has a matching key in both. (A small test or script asserts this.)
4. **Tokens present** — `colors.css` defines `--tooltip-bg`/`--tooltip-text` in both `:root` and the
   dark selector; the bundle Tooltip references `var(--tooltip-bg)`/`var(--tooltip-text)` and **no
   longer** references `--surface-inverse`/`--text-inverse`.
5. **Live visual check (staging)** — build (`npm run build` → `web/` vite, outDir
   `src/kanbanmate/webui`) and deploy to staging (`scripts/deploy-staging.sh`); confirm in a real
   browser, **both themes**: tooltip text is legible (light bubble/dark text in dark mode; dark
   bubble/light text in light mode); hover **and** tap open a tooltip; a screen reader announces the
   hint on a previously icon-only control. `web/`-built `webui/` is gitignored — never hand-build;
   ship via `scripts/deploy*.sh` (CLAUDE.md "Deployment").

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Bundle edit drifts from JSX source (gitignored) | Patch **both** (§4); the committed bundle is the shipping authority, the skill JSX keeps future re-bundles correct. |
| `cloneElement` on a non-element child crashes | Guard: only clone a single valid React element; else fall back to `aria-label` on the wrapper span (§5.2.2). |
| Tap-to-open swallows the trigger's own click | Wrapper toggle is additive; bubble keeps `pointerEvents:none`; the child's `onClick` still fires (§5.2.3). |
| FR key missing → silent English fallback | Gate 3 asserts en/fr `tip:` key-set parity. |
| Migrating a DS component `title=` prop by mistake (breaks a heading) | Migration rule excludes `<Capitalized title=…>`; the 32 component props are explicitly out of scope (§3, §5.3). |
| Dark tooltip (light bubble) too close to light surfaces | High L-contrast text (§5.1); `--shadow-md` + the bubble's own surface separate it; collision-flip deferred (§9). |

---

## 9. Follow-ups (out of scope for `lucid`)

- **Collision-flip / viewport-edge auto-placement** for `<Tooltip>` (currently caller picks
  `placement`). Worth a dedicated enhancement once broad coverage surfaces real clipping.
- **Auto-bundler** for the DS: a script that regenerates `web/src/ds/_ds_bundle.js` from the skill
  JSX sources would remove the hand-patch step (§4). Infrastructure, not part of this fix.

---

## 10. Done criteria (maps to the ticket)

- ✅ Tooltips legible in **light and dark** (token decoupling — §5.1).
- ✅ **One** tooltip mechanism (39 native `title=` migrated to DS `<Tooltip>` — §5.3; gate 2).
- ✅ **Comprehensive** coverage so common actions are self-explaining (audit + additions — §5.4).
- ✅ **All** tooltip text i18n'd FR/EN under the `tip:` namespace with key-set parity (§5.4; gate 3).
- ✅ **No mobile/a11y regression** — `aria` accessible name + tap/focus open replace what native
  `title=` provided (§5.2; gate 5).
