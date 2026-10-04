// The shell builds `index.html` and `src/`: the document is Vite's own, and
// nothing is injected into it any more.
import { mkdirSync, readdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";
import { buildIdentity } from "./build-identity.mjs";
import { pushTexts, substituteWorker } from "./worker-source.mjs";
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
// It lives in its own module because it must be readable without Vite: see
// `build-identity.mjs` for what it hashes, and for why it asks git rather than
// walking the directory (B-384).
const BUILD_ID = buildIdentity(ROOT);

function injectPrototype() {
  return {
    name: "inject-prototype",
    // `writeBundle`, never `closeBundle`: rolldown may close the bundle before
    // its files are on disk, and on a tree never built the hooks below then met
    // no `dist/` at all (B-318).
    writeBundle() {
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
    // AFTER `injectPrototype`'s own `writeBundle`, which is why this plugin is
    // listed after it: both read `dist/`, and this one needs the bundles to be
    // on disk before it can name them — `writeBundle` is the hook that runs once
    // they are, where `closeBundle` read the PREVIOUS build's `dist/vite` when
    // one was left, and failed when none was (B-318).
    writeBundle() {
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
      // Every placeholder written, or the build stops (`worker-source.mjs`).
      const worker = substituteWorker(readFileSync(resolve(ROOT, "sw.js"), "utf8"), {
        build: BUILD_ID,
        shell,
        extras: OPTIONAL_ASSETS,
        push: pushTexts(JSON.parse(readFileSync(resolve(ROOT, "src/i18n/fr.json"), "utf8"))),
      });
      writeFileSync(resolve(output, "sw.js"), worker);
      // The built identity, for the update discipline to compare against what
      // the host serves. It is written beside the worker rather than baked into
      // the bundle so that the page and the worker read ONE number.
      writeFileSync(resolve(output, "build.json"),
                    JSON.stringify({ build: BUILD_ID }, null, 2) + "\n");
    },
  };
}

export default defineConfig(({ mode }) => ({
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
    // B-572: tm-design's OWN build passes `--mode design-host` so the operator's
    // cold boot opens on the dense world instead of the real one, where
    // `movingReel` is empty by design. Every other build — the harness's
    // `run.sh` (`npm run build`, no mode), the unit suite — keeps Vite's default
    // mode and therefore the real world, unchanged.
    __DESIGN_HOST_START_DENSE__: JSON.stringify(mode === "design-host"),
    // WHETHER THIS IS THE DESIGN HOST'S OWN BUILD (the operator, 2026-10-04;
    // Q1 = A, Q6 = B). On tm-design the operations v1 serves go to the real
    // server (`mocks/passthrough.ts`) and the page reads the real clock. Every
    // other build — the harness's, the unit suite's, continuous integration's —
    // is false: full mocks, frozen clock, and the passthrough dropped from the
    // bundle with its document.
    __DESIGN_HOST__: JSON.stringify(mode === "design-host"),
  },
  // The prototype references `assets/...` itself; nothing else is public.
  publicDir: false,
  build: {
    outDir: "dist",
    // The symlink below owns `dist/assets`; bundled output must live under
    // another name or writeBundle would silently delete it on every build.
    assetsDir: "vite",
    emptyOutDir: true,
  },
  // Tailwind FIRST: it must have generated its sheet before the prototype
  // fragment is injected, and the injection deliberately runs `post`.
  plugins: [tailwindcss(), injectPrototype(), buildWorker()],
}));
