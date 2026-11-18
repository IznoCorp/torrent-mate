// WHAT THE APP BUILD LEAVES OUT, AND THE CHECK THAT IT DID.
//
// `vite build --mode app` is the build that ships: no mock layer, no harness,
// no phone frame. Every other build — the harness's plain `npm run build`, the
// design host's `--mode design-host`, the unit suite — keeps the maquette as it
// is. Vite's own default build mode is already named `production` and the
// harness builds with it, which is why the shipped build has a name of its own.
//
// Pure functions, read by two callers: `vite.config.mjs` (what it keeps of the
// frame stylesheet, the module guard) and this file's own command line,
// which reads a built `dist/` and fails on any leak. The suite proves both.
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

// THE NEEDLES, each a pattern only the left-out layer writes. A needle has to
// miss the app's own code, or the check would refuse the app itself: every one
// below was counted in a maquette build (present) and in an app build (absent)
// before it was written here.
//
// THE FRAME IS READ BY ITS POSITIVE SCOPE, and that is the one subtle needle.
// The app's own stylesheets (`theme.css`, `base.css`) name the switch too, as
// `:has(#desktop-switch:not(:checked))` — « no switch left unchecked », true
// when there is no switch at all, which is how the app's desktop variants hold
// both out of the frame and in the app. That form is inert without the control
// and ships by design; `#desktop-switch:checked` is the frame's own scope.
export const LEAKS = [
  { needle: /no mock route/, what: "the mock layer's fetch seam" },
  { needle: /__mocks\b/, what: "the mock layer's window seam" },
  { needle: /__states\b/, what: "the harness's named states" },
  { needle: /__measure\b/, what: "the harness's measuring switch" },
  { needle: /[`"']harness\//, what: "a harness part (data-part harness/...)" },
  { needle: /\.desktop-switch\b|id="desktop-switch"|tm-desktop-switch/, what: "the phone frame's way out" },
  { needle: /#desktop-switch:checked/, what: "a phone frame declaration" },
];

// The source directories and the stylesheet that may not reach an app chunk.
// Read on the module ids the bundler reports, so a module that leaks without
// carrying any needle is still refused.
const LEFT_OUT_MODULES = [/\/src\/mocks\//, /\/src\/harness\//, /\/src\/styles\/harness\.css$/];

/**
 * The leaks found in a set of built files.
 *
 * Args:
 *     files: `{ name, text }` for every file of the built bundle.
 *
 * Returns:
 *     One `{ file, needle, what }` per needle found in a file; empty when the
 *     bundle is clean.
 */
export function findLeaks(files) {
  const found = [];
  for (const { name, text } of files) {
    for (const { needle, what } of LEAKS) {
      if (needle.test(text)) found.push({ file: name, needle: needle.source, what });
    }
  }
  return found;
}

/**
 * Whether a module belongs to a left-out layer.
 *
 * Args:
 *     id: A module id, as the bundler names it.
 *
 * Returns:
 *     True for a module under `src/mocks/` or `src/harness/`, and for
 *     `harness.css`.
 */
export function isLeftOut(id) {
  return LEFT_OUT_MODULES.some((pattern) => pattern.test(id));
}

/**
 * The left-out modules a chunk still renders.
 *
 * A chunk lists every module it met, dropped ones included, so a module counts
 * only when it renders at least one byte.
 *
 * Args:
 *     modules: A chunk's `modules` record, id to `{ renderedLength }`.
 *
 * Returns:
 *     The ids of the left-out modules that render code.
 */
export function leftOutModules(modules) {
  return Object.entries(modules)
    .filter(([id, { renderedLength }]) => renderedLength > 0 && isLeftOut(id))
    .map(([id]) => id);
}

// WHAT THE APP KEEPS OF THE FRAME STYLESHEET: three unscoped blocks, nothing
// else. Every declaration the frame contributes is scoped on the desktop
// switch; the unscoped `.stage` and `.device` blocks are the shell's own root and
// outlive the way out of the frame (`webui/harness/desktop_frame.py` holds that
// split). The app build is the app out of the frame, so it keeps those two.
//
// AND `.note`, for its DEFAULT. The design notes are the harness's, but the
// surfaces draw them, and the one rule that hides them until a reader asks is
// in this file: without it every page of the app would carry the prototype's
// annotations (the shown default this file's own comment already warns of).
// The block is kept, its `:root.notes` opener is not, and nothing in the app
// sets that class — so a note is never shown.
//
// Read from the file rather than copied, so they cannot drift.
const KEPT = ["stage", "device", "note"];

/**
 * The blocks of the frame stylesheet the app build keeps.
 *
 * Args:
 *     harnessCss: The text of `src/styles/harness.css`.
 *
 * Returns:
 *     The `.stage`, `.device` and `.note` blocks, in that order, as the file
 *     writes them.
 *
 * Raises:
 *     Error: When a block is missing or written twice — the build stops rather
 *         than ship a shell with no root layout or with its notes shown.
 */
export function keptBlocks(harnessCss) {
  return KEPT.map((name) => {
    const blocks = harnessCss.match(new RegExp(`^\\.${name} \\{[^}]*\\}`, "gm")) ?? [];
    if (blocks.length !== 1) {
      throw new Error(`app build: harness.css holds ${blocks.length} unscoped .${name} blocks, expected 1`);
    }
    return blocks[0];
  }).join("\n");
}

/**
 * Text files under one directory, as the leak check reads them.
 *
 * Args:
 *     root: The directory the names are relative to.
 *     names: The files to read.
 *
 * Returns:
 *     `{ name, text }` per file.
 */
export function readSources(root, names) {
  return names.map((name) => ({ name, text: readFileSync(resolve(root, name), "utf8") }));
}

/**
 * Every text file of a built `dist/` worth reading: the document, the worker
 * and the bundles.
 *
 * Args:
 *     dist: The build's output directory.
 *
 * Returns:
 *     `{ name, text }` per file.
 */
export function readBuilt(dist) {
  const bundles = readdirSync(resolve(dist, "vite"))
    .filter((name) => name.endsWith(".js") || name.endsWith(".css"))
    .map((name) => `vite/${name}`);
  return readSources(dist, ["index.html", "sw.js", ...bundles]);
}

// THE COMMAND LINE: `node app-bundle.mjs [dist]`, exit 1 on any leak.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const dist = resolve(process.argv[2] ?? "dist");
  const leaks = findLeaks(readBuilt(dist));
  if (leaks.length > 0) {
    for (const { file, needle, what } of leaks) {
      console.error(`app-bundle: ${file} carries ${what} (/${needle}/)`);
    }
    console.error(`app-bundle: ${leaks.length} leak(s) — build with \`npm run build:app\``);
    process.exit(1);
  }
  console.log(`app-bundle: ${dist} carries no mock, harness or frame`);
}
