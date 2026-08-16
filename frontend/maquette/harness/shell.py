"""R72 — the Vite shell emits the prototype verbatim in the built envelope.

`design/` carries a Vite project whose one job is to emit the prototype
verbatim inside a real envelope, unminified and unextracted. A shell that
transformed anything — an inline script, a re-written attribute, an asset
URL that stopped resolving — would make every later conversion step start
from a lie. The rule verifies that: (a) the prototype fragment (refonte.html)
is emitted byte-for-byte verbatim, exactly once, in the built output; (b)
the module entry for the shell is present (Vite rewrites the src path); (c)
the named bundle file exists on disk under dist/vite/. The build gate and
the fragment hold keep source and build interchangeable for every later
measurement. R72_SANS_BUILD=1 skips the build gate so a mutation applied to
dist/ survives the run — mutation runs only, never a way to pass the build
check.
"""
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, Journal

DESIGN = ROOT / "design"


def construire(journal):
    """Runs the build, installing first only when node_modules is absent."""
    if os.environ.get("R72_SANS_BUILD") == "1":
        journal.check("le build de la coquille aboutit", True,
                         "sauté (R72_SANS_BUILD=1 — mutation en cours)")
        return True
    if not (DESIGN / "node_modules").exists():
        print("  npm ci (première fois — long)")
        subprocess.run(["npm", "ci"], cwd=DESIGN, check=True,
                       capture_output=True, text=True)
    fait = subprocess.run(["npm", "run", "build"], cwd=DESIGN,
                          capture_output=True, text=True)
    journal.check("le build de la coquille aboutit", fait.returncode == 0,
                     (fait.stderr or fait.stdout).strip().splitlines()[-1]
                     if fait.returncode else "vite build")
    return fait.returncode == 0


def verifier_holds(journal):
    """Run the three holds on the built output. Called after build succeeds."""
    emis = (DESIGN / "dist" / "index.html").read_text(encoding="utf-8")
    fragment = (DESIGN / "refonte.html").read_text(encoding="utf-8")

    # Hold 1: Fragment emitted verbatim, exactly once
    journal.check(
        "le fragment est émis verbatim, une seule fois",
        emis.count(fragment) == 1,
        f"fragment émis {emis.count(fragment)} fois")

    # Hold 2: the module entry is present. Read attribute by attribute rather
    # than as one pattern: the emitted tag's attribute order is the bundler's
    # business, and a rule that fixed it would fail on a bundler upgrade while
    # the envelope was still correct.
    script_tags = re.finditer(r"<script\b[^>]*>", emis)
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
        "l'entrée du module est émise exactement une fois",
        matching_tags == 1,
        f"{matching_tags} match(s) trouvé(s)")

    # Hold 3: the named bundle exists on disk. It reports either way — a hold
    # that vanished when the hold above it failed would drop the run's count
    # without a line saying so, and a rule is read by its count.
    if bundle_name:
        bundle_path = DESIGN / "dist" / "vite" / bundle_name
        journal.check(
            "le fichier du bundle existe",
            bundle_path.exists(),
            f"dist/vite/{bundle_name}")
    else:
        journal.check(
            "le fichier du bundle existe",
            False,
            "aucun bundle nommé — l'entrée du module n'a pas été trouvée")


def main():
    journal = Journal("R72 — la coquille émet le fragment verbatim")
    if not construire(journal):
        journal.summary()
    # Run holds only after successful build (unless R72_SANS_BUILD)
    verifier_holds(journal)
    journal.summary()


main()
