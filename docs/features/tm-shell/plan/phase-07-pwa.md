# Phase 7 — PWA (installable, auto-updating)

## Gate

- Phase 6 complete: dashboard renders with live event feed, health/version
  cards, all TanStack references proven.
- Frontend builds (`npm run build`) → `dist/` output.
- DS logo assets (`logo-icon.svg`, `logo-maskable.svg`) available in
  `frontend/src/assets/`.

## Sub-phases

### 7.1 — Manifest + Service Worker + precaching

**Commit**: `feat(tm-shell): add PWA manifest, service worker, and shell precache`

**Files**:

| Action | Path                      |
| ------ | ------------------------- |
| Modify | `frontend/vite.config.ts` |
| Modify | `frontend/index.html`     |
| Modify | `frontend/package.json`   |

**Work**:

1. Install `vite-plugin-pwa`. Configure in `vite.config.ts`:
   - `manifest`: name `"TorrentMate"`, short `"TM"`, `theme_color` / `bg_color`
     `"#0b0a08"`, `display: "standalone"`. Icons: 192 + 512 from DS logo,
     maskable + apple-touch-icon variants.
   - `workbox`: `globPatterns` for shell precache only (HTML/JS/CSS/fonts).
     `/api/*` → NetworkOnly, `/ws/*` → NetworkOnly, navigation → NetworkFirst.
   - `registerType: 'autoUpdate'`.
2. `index.html` — `<link rel="manifest">`, `<meta name="theme-color">`,
   apple-touch-icon link.
3. Verify `dist/` output: manifest.webmanifest + sw.js present, sw.js < 50 KB.

**Verification**: `cd frontend && npm run build` → manifest + SW in `dist/`;
Chrome DevTools Application → SW registered, precache populated.

**Implementation notes (shipped 7.1)**:

- `theme_color` / `background_color` resolve to **`#0e0e10`** — the exact sRGB of
  the DS `--background` (`oklch(0.165 0.004 286)`), not the `#0b0a08`-ish
  placeholder. `index.html` `theme-color` meta matches.
- Icons committed under `frontend/public/` (rendered once from `logo-icon.svg`
  via `rsvg-convert`, no `sharp`/assets-generator devDep): `pwa-192x192.png`,
  `pwa-512x512.png` (both `purpose: any`), `pwa-maskable-512x512.png`
  (`purpose: maskable`, DS-background padded safe zone), `apple-touch-icon.png`
  (180). The repo-root `*.png` ignore is negated with `!public/*.png` in
  `frontend/.gitignore` (mirrors the existing `!*.ts`).
- `includeManifestIcons: false` + `globPatterns` `{html,js,css,woff2,svg,png}`
  keep the precache list free of duplicates (11 entries, shell-only).
- `/api/*` and `/ws/*` are `NetworkOnly` runtime routes **and** in the
  `navigateFallback` denylist (`[/^\/api\//, /^\/ws\//]`); navigation is
  `NetworkFirst`. `registerType: 'autoUpdate'` → SW `skipWaiting` +
  `clientsClaim` + `cleanupOutdatedCaches`.
- `vite-plugin-pwa/client` + `/react` type refs added to `src/vite-env.d.ts`
  so the 7.2 `virtual:pwa-register/react` import typechecks.

### 7.2 — Auto-update toast + install prompts

**Commit**: `feat(tm-shell): add PWA auto-update and install prompt UI`

**Files**:

| Action | Path                                        |
| ------ | ------------------------------------------- |
| Create | `frontend/src/hooks/usePwa.ts`              |
| Create | `frontend/src/components/UpdateToast.tsx`   |
| Create | `frontend/src/components/InstallBanner.tsx` |
| Modify | `frontend/src/main.tsx`                     |

**Work**:

1. `usePwa.ts` — hook:
   - Wraps `vite-plugin-pwa`'s `useRegisterSW` (check on load + 15 min +
     visibilitychange).
   - Polls `/api/version` every 5 min; compares `build_commit` to baked
     `__BUILD_COMMIT__` (Vite `define`). Mismatch → forces SW update.
   - Captures `beforeinstallprompt` (Android/desktop) → exposes
     `{showInstallPrompt, canInstall}`.
   - iOS detection: `navigator.standalone === false` + iOS UA → flag.
2. `UpdateToast.tsx` — sonner: « Nouvelle version disponible… » →
   installing → « Nouvelle version installée — rechargement… » →
   `window.location.reload()`.
3. `InstallBanner.tsx` — Android/desktop: « Installer TorrentMate » button.
   iOS: Partager → « Sur l'écran d'accueil » instruction. Dismissals
   remembered in localStorage.
4. `main.tsx` — mount `<UpdateToast />` + `<InstallBanner />` at root.

**Verification**: `npx tsc --noEmit && npm run lint && npm run test` green;
Chrome DevTools → Manifest → installable; redeploy → update toast within
15 min or on visibility change.

## Verification

```bash
cd frontend && npx tsc --noEmit && npm run lint && npm run test -- --run
cd frontend && npm run build                      # dist/ with manifest + SW
```

**Manual**: Lighthouse PWA audit ≥ 90; Android install banner → install →
standalone launch; iOS instruction visible; redeploy → toast → reload →
`/api/version` shows new commit.
