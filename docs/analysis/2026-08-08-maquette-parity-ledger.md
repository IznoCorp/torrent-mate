# Maquette parity ledger — Acquisition UI

Mission contract: `docs/superpowers/handoffs/2026-08-08-maquette-parity-handoff.md`.
Method: `docs/superpowers/specs/2026-08-08-maquette-parity-method-design.md`
(operator-approved 2026-08-08; hybrid probe/overlay/flows; headless Playwright
driver addendum). Tools live in the session scratchpad `parity/` (probe.js,
probe_diff.py, overlay_diff.py, harness.py, allowlist.json, fixtures.js);
their source is reproduced or referenced in the plan
(`docs/superpowers/plans/2026-08-08-maquette-parity-execution.md`).

Entry format — one entry per fix loop: deployed sha (+ /api/version proof),
probe result (divergence table or « 0 divergences on N selectors »), overlay
% + heatmap path, flows exercised, gate outputs. The DOM probe is the hard
gate; the allowlist is explicit and every allowed pair is justified inline
in `allowlist.json` (never silent).

---

## Entry 1 — L0 calibration (probe + differ) and the two findings

**Setup verified**: staging token re-minted (expires +24 h); maquette served
at `127.0.0.1:8801` (debug copy; prototype file untouched); two isolated
headless contexts, both `documentElement.clientWidth === 390`, DPR 2, mobile,
touch; app context authenticated (`/api/version` → `0.87.0 staging @
dd2ff60e`), service workers blocked (kills the PWA stale-bundle trap for
measurements).

**Calibration probe** (regions: `.viewtabs`, `.seg > button`, `.more`) —
first run surfaced, as designed (tool validated on supposedly-at-zero
regions):

1. **UA-default noise** (maquette has no CSS reset; the app has Tailwind
   preflight): `.more` fontSize 13.33→14, UA button paddings 1px/6px→0 —
   all on an icon-only 40×40 grid-centered button, rendering-identical.
   → documented in `allowlist.json` (7 entries + 2 zero-width-border
   entries on `.viewtabs`).
2. **REAL finding — font mismatch**: in the same browser, `line-height:
   normal` at 13 px resolved 17.55 px (maquette) vs 18 px (app): the
   maquette runs the system stack, the app runs **Geist** (brand webfont).
   Letter widths and every `normal` line box diverge structurally.
   **Operator arbitration 2026-08-08: Geist is canonical** for the
   Acquisition surface; the maquette's system stack is a prototype
   artifact. Measurement consequence: the harness injects Geist at runtime
   into MY headless maquette rendering (file untouched) so both sides
   measure under the same font.
3. **REAL finding — stale pins**: the app hard-pinned `height: 36px` +
   `line-height: 18px` (tabs) and `line-height: 18px` (`.sact`) — values
   measured under the PREVIOUS environment's system font. Under
   Geist-on-both-sides they diverge from the maquette's intrinsic boxes
   (35.5 vs 36 on `.seg > button`, cascading 61.5 vs 62 on `.viewtabs`).
   **Fix `963b2922`**: pins removed; the maquette's verbatim declarations
   (padding 9/0, font 13/600, `line-height: normal` via the parity block)
   now produce identical boxes by construction in any environment that
   loads Geist.

**Gates**: `npx tsc -b --noEmit` OK; `npx eslint src` 0 errors (1
pre-existing warning); `npx vitest run` **1274/1274**.

**Deploy**: branch pushed; staging ours-merge `16621507` pushed;
post-deploy re-probe recorded in Entry 2.

---

## Entry 2 — L0 closed: base typography fixed, all three tools calibrated at zero

**Second real finding**: after unpinning, the app measured 35 vs maquette
35.5 — the « line-height parity » block (`normal`) mis-read the maquette.
Ground truth: the maquette's `.device` declares `font: 14px/1.35
var(--sans)` and `font: inherit` propagates **1.35** everywhere
(13 × 1.35 = 17.55 — font-INDEPENDENT, which the isolated-span experiment
proved: identical 17.0 struts under literal `Geist` on both pages).
**Fix `9f328b91`**: `.mq { font-size: 14px; line-height: 1.35 }` (the
verbatim `.device` base) replaces the `normal` block. App base was
14px/1.5 (preflight) inside `.mq` before this.

**Deploy**: staging ours-merge `3afae935`; `/api/version` = `staging @
3afae935…` verified in the measuring context (service workers blocked).

**Probe (hard gate)**: calibration region (`.viewtabs`, `.seg > button`,
`.more`) → **`0 divergences on 4 selectors`**, with 8 allowlisted pairs
(UA-default noise + zero-width-border props, each justified in
`allowlist.json`).

**Overlay (net)**: `fixtures.js` mirror payloads (maquette demo data
reshaped as real API envelopes, injected via init-script into the app
context only) make the tab badge show « 4 » on both sides. Element
screenshots of `.viewtabs` → **`diff_pct=1.37`** (< 2 target), heatmap
`ov-tabs.heat.png`: glyph antialiasing + sub-pixel edges on the badge and
« ⋮ » dots, no structural hotspot.

**L0 exit state**: probe + differ + allowlist + overlay + mirror fixtures
all validated on the deployed build. Known forward notes: the mirror
fixtures already carry post-L3 fields (`season`/`episode` on to-handle,
`eta_seconds`, `last_search_at/best`) — inert until the UI reads them.
