import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// TorrentMateUI dev/build config.
// https://vite.dev/config/  ·  https://vitest.dev/config/
//
// The dev server proxies the API and WebSocket to the `personalscraper web`
// backend (default 127.0.0.1:8710, see DESIGN §4.3) so the SPA can run under
// Vite (`npm run dev`) while talking to the real FastAPI process.
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
