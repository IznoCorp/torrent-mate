import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import yaml from "@modyfi/vite-plugin-yaml";

// Build into the Python package so the wheel ships the SPA (DESIGN §7).
// Dev server proxies /api to the running `kanban config serve` (default :8766).
// The yaml plugin lets us import the i18n bundles (en.yaml / fr.yaml) as objects.
export default defineConfig({
  plugins: [react(), yaml()],
  build: { outDir: "../src/kanbanmate/webui", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8766" } },
});
