# Phase 1 — Tokens & Tooltip component

> Covers DESIGN §5.1 (contrast fix) and §5.2 (Tooltip component: tokens + a11y + touch).
> After this phase the Tooltip is fixed in both themes but no consumer has migrated yet.

## Gate

**Previous phase must have produced:** DESIGN §1–§5 written and reviewed (DESIGN.md exists on
branch). This is Phase 1 — the DESIGN preconditions are the only gate.

---

### Sub-phase 1.1 — Dedicated tooltip tokens in `colors.css`

**DESIGN:** §5.1, §2 root cause at `colors.css:165,174` (light) / `colors.css:275` (dark).

**Files:** Modify `web/src/ds/tokens/colors.css`

Add two new custom properties in both theme scopes. The tokens point to `var(--foreground)` /
`var(--background)` which flip with the theme, making the tooltip the true inverse of the current
surface in both modes.

**Step 1: Add tokens in `:root` (light)**

Insert after the existing `--surface-inverse` / `--text-inverse` block (~line 174):

```css
/* Tooltip — self-inverting bubble that always contrasts with the page surface.
 * Decoupled from --surface-inverse so terminal-panel repurposing can never collide again. */
--tooltip-bg:   var(--foreground);   /* dark bubble in light mode  */
--tooltip-text: var(--background);   /* light text  in light mode  */
```

**Step 2: Add tokens in `.dark, [data-theme="dark"]`**

Insert after the `--surface-inverse` dark override at line 275:

```css
/* Tooltip — defined explicitly in dark (operator decision: "both themes").
 * Values are inherited-identical to :root (--foreground/--background), but explicit
 * definition immunises against any future :root-only repurposing of these tokens. */
--tooltip-bg:   var(--foreground);   /* light bubble in dark mode  */
--tooltip-text: var(--background);   /* dark text   in dark mode   */
```

**Verification:** `rg '--tooltip-bg' web/src/ds/tokens/colors.css` returns 2 matches (one in
`:root`, one in `.dark,[data-theme="dark"]`). Same for `--tooltip-text`.

**Commit:** `fix(lucid): add dedicated --tooltip-bg / --tooltip-text tokens in both themes`

---

### Sub-phase 1.2 — Update Tooltip in `_ds_bundle.js` (shipped artifact)

**DESIGN:** §5.2, §4 (build model — compiled form only). Bundle Tooltip at `_ds_bundle.js:2008-2095`;
token refs at lines 2068-2069.

**Files:** Modify `web/src/ds/_ds_bundle.js` (lines 2068-2069, plus new a11y + tap logic)

Three changes inside the `Tooltip({ label, children, placement = "top", style })` function:

**Change A — Tokens (line 2068-2069)**

Replace the two style properties:
- `background: "var(--surface-inverse)"` → `background: "var(--tooltip-bg)"`
- `color: "var(--text-inverse)"` → `color: "var(--tooltip-text)"`

**Change B — Accessible name (`aria-describedby` + `aria-label`)**

After the `const pos = …` block (~line 2042), add:

```js
const tipId = React.useId(); // React 18.3.1 — package.json:19
```

Replace the wrapper `<span>` opening (~line 2044) to add `onClick`/`onPointerDown` (Change C) and
the `aria-describedby` wiring. Then wrap `children` in `React.cloneElement`:

```js
// Around line 2056, replace bare `children,` with:
React.isValidElement(children)
  ? React.cloneElement(children,
      Object.assign(
        { "aria-describedby": tipId },
        typeof label === "string" && children.props && !children.props["aria-label"]
          ? { "aria-label": label }
          : {}
      )
    )
  : children,
```

Add `id: tipId` to the bubble span (the `role="tooltip"` element ~line 2061).

**Guard:** The `React.isValidElement` check + `children.props` safeguard prevents crash on
non-element children (§5.2.2). DS `IconButton` spreads `...rest` onto `<button>` at
`_ds_bundle.js:435→473` — attributes reach the DOM.

**Change C — Tap-to-open (mobile, §5.2.3)**

Add to the wrapper `<span>` props (~line 2045):

```js
onClick: () => setShow(!show),
```

The bubble already has `pointerEvents: "none"` (line 2067) — taps pass through to the trigger.
`onMouseLeave`/`onBlur` (lines 2047,2049) already close — touch dismissal is handled.

**Commit:** `fix(lucid): update Tooltip in _ds_bundle.js — new tokens, aria, tap-to-open`

---

### Sub-phase 1.3 — Update Tooltip.jsx JSX source (durability)

**DESIGN:** §4 (both artifacts), §5.2. Source at
`.claude/skills/kanbanmate-design/components/feedback/Tooltip.jsx:7-41`.

**Files:** Modify `.claude/skills/kanbanmate-design/components/feedback/Tooltip.jsx` (gitignored —
durability hygiene, not a shipping dependency).

Apply the same three changes as sub-phase 1.2 but in JSX form (this file allows JSX):

1. **Tokens:** `background: 'var(--surface-inverse)'` → `'var(--tooltip-bg)'`,
   `color: 'var(--text-inverse)'` → `'var(--tooltip-text)'`.
2. **A11y:** `const tipId = React.useId()`, `aria-describedby={tipId}` on bubble,
   `React.cloneElement(children, …)` with conditional `aria-label`.
3. **Tap:** `onClick={() => setShow(!show)}` on wrapper span.

This file is in the gitignored `.claude/` dir — edit locally, no commit to this repo.
The `.claude/` skill repo has its own commit workflow; note the change for that repo's tracking.

**Verification:** Confirm the JSX source matches the bundle's logic by inspection (same three
concerns applied).

**Commit (skill repo only, separate):** `fix: Tooltip — new tokens, aria, tap-to-open`

---

### Phase 1 quality gate (before moving to Phase 2)

- [ ] `make test` — `tests/web/test_design_system_contract.py` passes (Tooltip still exported at
  `_ds_bundle.js:2088` + `4673` — we edited only its body, not the `__ds_scope.Tooltip` export).
- [ ] `rg '--surface-inverse' web/src/ds/_ds_bundle.js -g '*Tooltip*'` inside the Tooltip function
  returns **0** matches (only the new `--tooltip-bg`/`--tooltip-text` appear).
- [ ] `rg '--tooltip-bg' web/src/ds/tokens/colors.css` returns exactly 2 matches (one per theme).
- [ ] `rg '--tooltip-text' web/src/ds/_ds_bundle.js` inside the Tooltip function returns `> 0`.
- [ ] `.claude/skills/kanbanmate-design/components/feedback/Tooltip.jsx` edited (gitignored, local verify only).
