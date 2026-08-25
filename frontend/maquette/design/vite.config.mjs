// The shell's whole job is to change NOTHING: the prototype is injected
// verbatim, after Vite's own HTML processing, so no minifier and no script
// extraction ever touches it. The real conversion happens module by module
// in later sub-projects; this file is the chassis they will move into.
import { readFileSync, rmSync, symlinkSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";
// Tailwind v4 as a Vite plugin. WHAT CONFINES ITS SCAN IS `source(none)` on
// the import in `src/styles/theme.css`, and NOT the `@source` rules beside it:
// v4 scans the project root automatically, and an `@source` rule ADDS to that
// scan rather than replacing it. Naming your sources confines nothing, and
// believing otherwise is how 936 bytes of the maquette once leaked into the
// production bundle. `scripts/check-tailwind-confinement.py` holds both ends.
import tailwindcss from "@tailwindcss/vite";

const ROOT = resolve(import.meta.dirname);

function injectPrototype() {
  return {
    name: "inject-prototype",
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
  define: {
    // WHETHER THE MOCK LAYER IS BUILT IN (L08). True today, and the point is
    // that turning it off is one edit and PROVABLY removes the layer: it sits
    // behind `if (__MOCKS_BUILT_IN__)`, so a false constant makes the branch dead and
    // the bundler drops the module, its handlers and its seeds.
    //
    // MEASURED, NOT ASSERTED: 2 807 407 bytes with it on, 1 571 705 with it
    // off — five bytes over the 1 571 700 the bundle weighed before the layer
    // existed. `no mock route`, a string only the seam holds, goes from 1 to 0.
    //
    // ONE THING HAD TO CHANGE FOR THAT TO BE TRUE, and it is worth knowing:
    // `mocks/state.ts` used to build its state at module evaluation, which is a
    // side effect, and a module with one is not dropped even when nothing reads
    // it — 69 kB of unreferenced seed data survived in the switched-off build.
    // The state is built on first use now.
    //
    // On SWITCHOVER DAY the flag goes false and then the directory goes. A mock
    // layer that could not be taken out would be a mock layer shipped to the
    // operator.
    __MOCKS_BUILT_IN__: JSON.stringify(true),
  },
  // The prototype references `assets/...` itself; nothing else is public.
  publicDir: false,
  build: {
    outDir: "dist",
    // The symlink below owns `dist/assets`; bundled output must live under
    // another name or closeBundle would silently delete it on every build.
    assetsDir: "vite",
    emptyOutDir: true,
  },
  // Tailwind FIRST: it must have generated its sheet before the prototype
  // fragment is injected, and the injection deliberately runs `post`.
  plugins: [tailwindcss(), injectPrototype()],
});
