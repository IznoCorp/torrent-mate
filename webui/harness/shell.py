"""R72 — the Vite shell emits its module entry, and the bundle it names exists.

`design/` carries a Vite project that builds the prototype into a real envelope.
The rule verifies that (b) the module entry for the shell is emitted exactly
once (Vite rewrites the src path) and (c) the bundle that entry names exists on
disk under dist/vite/. Hold (a) — the prototype fragment emitted byte-for-byte
verbatim, exactly once — was retired when the fragment was deleted: nothing is
injected into the document any more, so there is nothing to find verbatim. The
letters are kept so R72's recorded history still lines up with them.
R72_SKIP_BUILD=1 skips the build gate so a mutation applied to dist/ survives
the run — mutation runs only, never a way to pass the build check.
"""
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, Journal

DESIGN = ROOT / "design"


def build(journal):
    """Runs the build, installing first only when node_modules is absent."""
    if os.environ.get("R72_SKIP_BUILD") == "1":
        journal.check("the shell build succeeds", True,
                      "skipped (R72_SKIP_BUILD=1 — a mutation is in flight)")
        return True
    if not (DESIGN / "node_modules").exists():
        print("  npm ci (first time — slow)")
        subprocess.run(["npm", "ci"], cwd=DESIGN, check=True,
                       capture_output=True, text=True)
    done = subprocess.run(["npm", "run", "build"], cwd=DESIGN,
                          capture_output=True, text=True)
    journal.check("the shell build succeeds", done.returncode == 0,
                  (done.stderr or done.stdout).strip().splitlines()[-1]
                  if done.returncode else "vite build")
    return done.returncode == 0


def run_holds(journal):
    """Run the two holds on the built output. Called after build succeeds."""
    emitted = (DESIGN / "dist" / "index.html").read_text(encoding="utf-8")

    # Hold (b): the module entry is present. Read attribute by attribute rather
    # than as one pattern: the emitted tag's attribute order is the bundler's
    # business, and a rule that fixed it would fail on a bundler upgrade while
    # the envelope was still correct.
    script_tags = re.finditer(r"<script\b[^>]*>", emitted)
    matching_tags = 0
    bundle_name = None
    for tag_match in script_tags:
        tag_text = tag_match.group(0)
        has_module = 'type="module"' in tag_text
        src_match = re.search(r'src="/vite/([^"]+\.js)"', tag_text)
        if has_module and src_match:
            matching_tags += 1
            bundle_name = src_match.group(1)

    journal.check(
        "the module entry is emitted exactly once",
        matching_tags == 1,
        f"{matching_tags} match(es) found")

    # Hold (c): the named bundle exists on disk. It reports either way — a hold
    # that vanished when the hold above it failed would drop the run's count
    # without a line saying so, and a rule is read by its count.
    if bundle_name:
        bundle_path = DESIGN / "dist" / "vite" / bundle_name
        journal.check(
            "the bundle file exists",
            bundle_path.exists(),
            f"dist/vite/{bundle_name}")
    else:
        journal.check(
            "the bundle file exists",
            False,
            "no bundle named — the module entry was not found")


def main():
    journal = Journal("R72 — the shell emits its module entry and its bundle")
    if not build(journal):
        # `summary()` RAISES SystemExit(1) as soon as any hold has failed, and a
        # failed build is exactly that — so this is the exit, not a fall-through:
        # the holds below never run against a stale or absent build. Spelled out
        # because the shape reads like one (a reviewer read it as one).
        journal.summary()
    run_holds(journal)
    journal.summary()


if __name__ == "__main__":
    main()
