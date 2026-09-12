// THE BUILD'S IDENTITY, computed here rather than in `vite.config.mjs` so that
// it can be read WITHOUT Vite: this module imports nothing but Node's own
// standard library, which is what lets `tests/scripts/test_build_identity.py`
// drive it on a synthetic tree with no `node_modules` at all.
//
// IT IS A CONTENT HASH, not a timestamp and not the commit. A timestamp moves
// when a file is merely touched and would reload every client for nothing. The
// commit does not move at all across a whole session of edits on a dirty tree,
// which is the state the design host is normally in.
//
// AND IT HASHES WHAT GIT KNOWS, WHICH IS THE REPAIR (B-384). The walk used to
// take every file under `src/`, so the command-logging hook's
// `.claude/logs/bash-commands.log` — written under the current directory of any
// session that shells there — entered the hash: `dist/build.json` moved from
// `c133d97cc1ff` to `22c6c46fbb42` between two builds of an unchanged source,
// the two last lines of that log being the steward's own greps. « An unchanged
// build id proves an unchanged build » held only while nobody shelled there.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// The four files beside `src/` that belong to the built shell. They are named
// rather than discovered: everything else at that level is configuration, a
// lockfile, or output.
const ROOT_FILES = ["index.html", "refonte.html", "sw.js", "package.json"];

// Git hands a hook GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE, and they override
// `-C`: a build launched from inside a git hook would otherwise ask about the
// repository the outer command was aimed at.
const LEAKED_GIT_VARIABLES = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX"];

function environmentWithoutGitLeaks() {
  const environment = { ...process.env };
  for (const name of LEAKED_GIT_VARIABLES) delete environment[name];
  return environment;
}

// Every path git accounts for under `root`: tracked, plus untracked files that
// no ignore rule covers — a source file written a minute ago and not yet added
// is still source, and must still move the identity.
function pathsGitAccountsFor(root) {
  const listed = execFileSync(
    "git",
    ["-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
    { encoding: "utf8", env: environmentWithoutGitLeaks() },
  );
  return listed.split("\0").filter((path) => path !== "");
}

/**
 * The twelve hexadecimal characters that name this build.
 *
 * @param {string} root The design project's directory.
 * @returns {string} The identity, stable across a rebuild of unchanged sources.
 */
export function buildIdentity(root) {
  const base = resolve(root);
  // `.claude/` is refused by NAME as well as by the ignore rules, because the
  // ignore rule that hides it here lives in the operator's global excludes file
  // and a continuous-integration runner has no such file. A guard that holds on
  // one machine and not on the other is the shape this repository counts.
  const sources = pathsGitAccountsFor(base)
    .filter((path) => path.startsWith("src/") || ROOT_FILES.includes(path))
    .filter((path) => !path.split("/").includes(".claude"))
    .sort();

  const hash = createHash("sha256");
  for (const path of sources) {
    // The RELATIVE PATH, not the bare file name the first version hashed: two
    // files of the same name in different directories were indistinguishable to
    // it, and a move between directories left the identity where it was.
    hash.update(path).update(readFileSync(resolve(base, path)));
  }
  return hash.digest("hex").slice(0, 12);
}
