// The shell's whole job is to change NOTHING: the prototype is injected
// verbatim, after Vite's own HTML processing, so no minifier and no script
// extraction ever touches it. The real conversion happens module by module
// in later sub-projects; this file is the chassis they will move into.
import { createHash } from "node:crypto";
import { mkdirSync, readdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
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

// THE BUILD'S IDENTITY, COMPUTED ONCE AND READ BY THREE. The running bundle
// has to know what it is, the worker has to name its cache after it, and
// `/build.json` has to publish it — and if any two of those were computed
// separately they would eventually disagree, which is the only way a freshness
// check can go wrong without anybody noticing.
//
// IT IS A CONTENT HASH, not a timestamp and not the commit. A timestamp moves
// when a file is merely touched and would reload every client for nothing. The
// commit does not move at all across a whole session of edits on a dirty tree,
// which is the state the design host is normally in — that is the same reading
// that put the SOURCE stamp rather than the commit at the centre of this lot.
function buildIdentity() {
  const hash = createHash("sha256");
  const walk = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true }).sort(
      (a, b) => (a.name < b.name ? -1 : 1),
    )) {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) walk(path);
      else hash.update(entry.name).update(readFileSync(path));
    }
  };
  walk(resolve(ROOT, "src"));
  for (const root of ["index.html", "refonte.html", "sw.js", "package.json"]) {
    hash.update(root).update(readFileSync(resolve(ROOT, root)));
  }
  return hash.digest("hex").slice(0, 12);
}

const BUILD_ID = buildIdentity();

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
      //
      // THE DIRECTORY IS CREATED FIRST, and this hook assumed it existed. It
      // does on a machine that has built before, and on a fresh checkout it
      // exists only once the write has finished — so the hook was racing the
      // output it links into. The race was invisible while the bundle was
      // small and lost the moment it grew: three continuous-integration jobs
      // failed at once with `ENOENT: symlink '../assets'`, on a runner, for a
      // reason that had nothing to do with the change under test.
      const output = resolve(ROOT, "dist");
      mkdirSync(output, { recursive: true });
      rmSync(resolve(output, "assets"), { force: true, recursive: true });
      symlinkSync("../assets", resolve(output, "assets"));
    },
  };
}

// The icon and page routes the DESIGN HOST serves and the harness host does
// not. They are the optional tier of the precache for exactly that reason: the
// harness serves the built copy alone, and requiring them would mean the worker
// could never install on the one host every rule measures.
const OPTIONAL_ASSETS = [
  "/manifest.webmanifest",
  "/apple-touch-icon.png",
  "/favicon.svg",
  "/pwa-192.png",
  "/pwa-512.png",
  "/maskable-192.png",
  "/maskable-512.png",
  "/offline.html",
];

function buildWorker() {
  return {
    name: "build-worker",
    // AFTER `injectPrototype`'s own `closeBundle`, which is why this plugin is
    // listed after it: both read `dist/`, and this one needs the bundles to be
    // on disk before it can name them.
    closeBundle() {
      const output = resolve(ROOT, "dist");
      // THE BUNDLE NAMES ARE READ, NEVER WRITTEN BY HAND. They carry content
      // hashes, so a list kept in the worker source would be wrong the moment
      // anything changed — and wrong in the silent direction, precaching a file
      // that no longer exists while the one that does goes uncached.
      const bundles = readdirSync(resolve(output, "vite"))
        .filter((name) => name.endsWith(".js") || name.endsWith(".css"))
        .sort()
        .map((name) => `/vite/${name}`);
      if (bundles.length === 0) {
        // Loud, and it has to be: an empty shell would precache the document
        // alone, install cleanly, and serve a blank page offline.
        throw new Error("build-worker: dist/vite holds no bundle to precache");
      }
      // The document FIRST — `sw.js` uses `SHELL[0]` as the navigation
      // fallback, and that contract is written here because this is where the
      // order is decided.
      const shell = ["/", ...bundles];
      const worker = readFileSync(resolve(ROOT, "sw.js"), "utf8")
        .replace("__BUILD__", BUILD_ID)
        .replace("__SHELL__", JSON.stringify(shell))
        .replace("__EXTRAS__", JSON.stringify(OPTIONAL_ASSETS));
      if (worker.includes("__BUILD__") || worker.includes("__SHELL__")
          || worker.includes("__EXTRAS__")) {
        throw new Error("build-worker: a placeholder survived substitution");
      }
      writeFileSync(resolve(output, "sw.js"), worker);
      // The built identity, for the update discipline to compare against what
      // the host serves. It is written beside the worker rather than baked into
      // the bundle so that the page and the worker read ONE number.
      writeFileSync(resolve(output, "build.json"),
                    JSON.stringify({ build: BUILD_ID }, null, 2) + "\n");
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
    // WHAT THIS BUNDLE IS. The update discipline compares it against what
    // `/build.json` serves; the worker names its cache after the same value, so
    // the three cannot drift apart.
    __BUILD_ID__: JSON.stringify(BUILD_ID),
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
  plugins: [tailwindcss(), injectPrototype(), buildWorker()],
});
