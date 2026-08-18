// The shell's whole job is to change NOTHING: the prototype is injected
// verbatim, after Vite's own HTML processing, so no minifier and no script
// extraction ever touches it. The real conversion happens module by module
// in later sub-projects; this file is the chassis they will move into.
import { readFileSync, rmSync, symlinkSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

const ROOT = resolve(import.meta.dirname);

function injectPrototype() {
  return {
    name: "injecte-maquette",
    transformIndexHtml: {
      // "post" runs after Vite's internal transforms: the fragment below is
      // emitted untransformed — byte-for-byte the source file.
      order: "post",
      handler(html) {
        const fragment = readFileSync(resolve(ROOT, "refonte.html"), "utf8");
        return html.replace("<!-- maquette -->", () => fragment);
      },
    },
    closeBundle() {
      // The fragment's image URLs are relative `assets/...`; the build links
      // the real files in rather than copying 10 MB per build. `dist/` is
      // gitignored, so the symlink never reaches the repository.
      rmSync(resolve(ROOT, "dist/assets"), { force: true, recursive: true });
      symlinkSync("../assets", resolve(ROOT, "dist/assets"));
    },
  };
}

export default defineConfig({
  root: ROOT,
  // The prototype references `assets/...` itself; nothing else is public.
  publicDir: false,
  build: {
    outDir: "dist",
    // The symlink below owns `dist/assets`; bundled output must live under
    // another name or closeBundle would silently delete it on every build.
    assetsDir: "vite",
    emptyOutDir: true,
  },
  plugins: [injectPrototype()],
});
