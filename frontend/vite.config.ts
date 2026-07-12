import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'

// TorrentMateUI dev/build config.
// https://vite.dev/config/  ·  https://vitest.dev/config/
//
// The dev server proxies the API and WebSocket to the `personalscraper web`
// backend (default 127.0.0.1:8710, see DESIGN §4.3) so the SPA can run under
// Vite (`npm run dev`) while talking to the real FastAPI process.
//
// PWA (DESIGN §5.4): installable, auto-updating shell. Only the static app
// shell is precached; `/api` and `/ws` are NetworkOnly so live data and the
// event WebSocket are never served stale from a cache. The DS near-black
// `--background` (oklch(0.165 0.004 286) → #0e0e10) drives theme/background.
//
// `registerType: 'prompt'` (not 'autoUpdate'): under 'autoUpdate' the plugin
// silently activates the new SW and `useRegisterSW`'s `needRefresh` never fires,
// so the DESIGN §5.4 «toast → reload» UX is unreachable. With 'prompt' the fresh
// SW installs and *waits*; `usePwa` observes `needRefresh`, raises the toast, and
// calls `updateServiceWorker(true)` (posts SKIP_WAITING → single reload). We keep
// `clientsClaim` + `cleanupOutdatedCaches` explicitly (the plugin only injects
// them automatically for 'autoUpdate') so an activated SW still claims all
// clients and prunes stale precaches.
const dsBackground = '#0e0e10'

export default defineConfig({
  // `__BUILD_COMMIT__` is baked into the bundle so the running SPA knows which
  // git SHA it was built from. The deploy script (phase 8) exports
  // `TM_BUILD_COMMIT=<sha>` before `npm run build`; without it (local dev,
  // Vitest) the value is `"dev"`, which `usePwa`/`shouldForceUpdate` read as
  // "unstamped" and never use to force a service-worker update.
  define: {
    __BUILD_COMMIT__: JSON.stringify(process.env.TM_BUILD_COMMIT ?? 'dev'),
  },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // A fresh service worker installs and *waits*; `usePwa` surfaces the
      // update toast and activates it (SKIP_WAITING → single reload). Under
      // 'autoUpdate' the SW would self-activate and `needRefresh` would never
      // fire, making the toast/reload UX dead code (audit B2).
      registerType: 'prompt',
      // Icons are already precached via the `png` glob below; skip the manifest
      // auto-inclusion so each icon lands in the precache list exactly once.
      includeManifestIcons: false,
      // Manifest mirrors the design-system app-icons set
      // (.claude/skills/design-system/assets/app-icons/manifest.webmanifest).
      manifest: {
        name: 'TorrentMate',
        // The installed home-screen icon label uses short_name — keep it the
        // full brand ("TorrentMate"), never the "TM" abbreviation.
        short_name: 'TorrentMate',
        description:
          'Interface de supervision du pipeline média self-hosted TorrentMate.',
        lang: 'fr',
        dir: 'ltr',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        categories: ['utilities', 'productivity'],
        theme_color: dsBackground,
        background_color: dsBackground,
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: '/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Precache the app shell only — never any runtime API payload. The
        // web manifest is injected into the precache by vite-plugin-pwa itself,
        // so it is intentionally left out of these globs to avoid a duplicate.
        globPatterns: ['**/*.{html,js,css,woff2,svg,png}'],
        // An activated SW claims every open client immediately and prunes any
        // precache from a previous build. Set explicitly because the plugin only
        // auto-injects these for `registerType: 'autoUpdate'` (audit B2).
        clientsClaim: true,
        cleanupOutdatedCaches: true,
        // SPA navigations are served the precached `index.html` via the
        // Workbox NavigationRoute this generates. That route is registered
        // *first* in the built `sw.js`, so it is the reachable handler for every
        // shell navigation; `/api` and `/ws` are denied here so navigations to
        // them fall through to the NetworkOnly routes below instead of being
        // answered by the shell (audit B3).
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
        runtimeCaching: [
          // NO navigation NetworkFirst route: the navigateFallback
          // NavigationRoute above already handles (and shadows) every shell
          // navigation, so a NetworkFirst navigate route is both unreachable for
          // shell navigations AND the only route that would ever cache an
          // `/api` navigation (mode 'navigate', excluded from the denylist above
          // but NOT from a bare `request.mode === 'navigate'` matcher). Dropping
          // it makes the NetworkOnly routes below the sole handlers for
          // `/api` + `/ws` in every request mode (audit B3).
          {
            // REST API is dynamic and auth-guarded: never cached, never stale.
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkOnly',
          },
          {
            // Event-stream WebSocket handshake: never intercept or cache.
            urlPattern: ({ url }) => url.pathname.startsWith('/ws/'),
            handler: 'NetworkOnly',
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split the heavy, rarely-changing vendor libraries into their own
        // chunks so an app-only deploy does not invalidate them in the PWA
        // precache — the browser reuses the cached vendor chunks and only
        // re-fetches the small app chunk. Also lands the single-bundle size
        // under the 500 kB advisory warning.
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/.test(id)) {
            return 'vendor-react'
          }
          if (id.includes('@radix-ui')) return 'vendor-radix'
          if (id.includes('@tanstack')) return 'vendor-tanstack'
          return 'vendor'
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8710',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://127.0.0.1:8710',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    css: false,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // `virtual:pwa-register/react` is a build-time virtual module with no
    // real file on disk; under Vitest it is redirected to an inert stub so
    // tests never pull the Workbox register glue (which needs a service-worker
    // environment jsdom lacks). Tests that drive the flow override it via
    // `vi.mock('virtual:pwa-register/react', …)`.
    alias: {
      'virtual:pwa-register/react': fileURLToPath(
        new URL('./src/test/pwaRegisterMock.ts', import.meta.url),
      ),
    },
  },
})
