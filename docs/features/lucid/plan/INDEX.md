# lucid Implementation Plan

> **Codename**: `lucid` · **Ticket**: #76 · **Type**: bugfix + enhancement (UI only — `web/`)
> **Design**: `docs/features/lucid/DESIGN.md`

**Goal:** Make tooltips legible in all themes (fix dark-mode black-on-black bug), migrate all native
`title=` attributes to the single DS `<Tooltip>` mechanism with full i18n (FR/EN), and achieve
exhaustive coverage so the interface is self-documenting — no engine/Python change.

**Architecture:** Pure `web/` change. Phase 1 introduces dedicated tooltip tokens that decouple from
the terminal-panel repurposing of `--surface-inverse` (§5.1) and updates the Tooltip component in
both artifacts with a11y + touch support (§5.2). Phase 2 migrates all 39 native `title=` sites
across 15 files to `<Tooltip>` + `t("tip.*")` (§5.3). Phase 3 completes the coverage audit and all
5 verification gates including staging build/deploy (§5.4 + §7).

**Tech Stack:** React 18.3.1 (no new dependency), CSS custom properties, i18next via
`web/src/i18n/`, vite build, compiled `_ds_bundle.js` (no JSX bundler).

## Global Constraints

- No Python/engine/core change — `web/` only.
- No new third-party dependency (no `pyproject.toml` or CI install change).
- `make lint` and `make test` stay green throughout.
- Commit scope: `(lucid)`; Conventional Commits enforced.
- Tooltip wording: terse imperative hint, verb-first, no trailing period, ≤ ~6 words; FR mirrors.
- Every tooltip key present in BOTH `en.yaml` and `fr.yaml` (key-set parity required).
- Bundle edits in **compiled** `React.createElement(…)` form, NOT JSX.
- DS component `title=` props (`Banner`/`PageIntro`/`Dialog`) are headings — NEVER migrate.

## Phases

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | Tokens & Tooltip component | phase-01-tokens-and-component.md | [ ] |
| 2 | Migrate 39 native `title=` | phase-02-migrate-native-titles.md | [ ] |
| 3 | Coverage audit & verification gates | phase-03-coverage-and-gates.md | [ ] |
