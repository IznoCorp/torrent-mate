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
const dsBackground = '#0e0e10'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // New builds ship a fresh service worker that activates itself
      // (skipWaiting + clients.claim) without a manual re-register step; the
      // update-toast/reload UX lands in sub-phase 7.2.
      registerType: 'autoUpdate',
      // Icons are already precached via the `png` glob below; skip the manifest
      // auto-inclusion so each icon lands in the precache list exactly once.
      includeManifestIcons: false,
      manifest: {
        name: 'TorrentMate',
        short_name: 'TM',
        description:
          'Pilotage du pipeline TorrentMate : téléchargements, scraping et bibliothèque.',
        lang: 'fr',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        theme_color: dsBackground,
        background_color: dsBackground,
        icons: [
          { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          {
            src: '/pwa-maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
          { src: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png', purpose: 'any' },
        ],
      },
      workbox: {
        // Precache the app shell only — never any runtime API payload. The
        // web manifest is injected into the precache by vite-plugin-pwa itself,
        // so it is intentionally left out of these globs to avoid a duplicate.
        globPatterns: ['**/*.{html,js,css,woff2,svg,png}'],
        // SPA fallback document, with `/api` and `/ws` explicitly excluded so
        // those requests are never answered by the precached shell.
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
        runtimeCaching: [
          {
            // SPA navigations: always try the network first so a freshly
            // deployed shell is picked up immediately; fall back to the
            // last-good cached document only when offline.
            urlPattern: ({ request }) => request.mode === 'navigate',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'tm-shell-navigation',
              networkTimeoutSeconds: 3,
              expiration: { maxEntries: 16 },
              cacheableResponse: { statuses: [200] },
            },
          },
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
  },
})
