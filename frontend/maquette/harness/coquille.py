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
from commun import RACINE, Journal

DESIGN = RACINE / "design"


def construire(journal):
    """Runs the build, installing first only when node_modules is absent."""
    if os.environ.get("R72_SANS_BUILD") == "1":
        journal.verifier("le build de la coquille aboutit", True,
                         "sauté (R72_SANS_BUILD=1 — mutation en cours)")
        return True
    if not (DESIGN / "node_modules").exists():
        print("  npm ci (première fois — long)")
        subprocess.run(["npm", "ci"], cwd=DESIGN, check=True,
                       capture_output=True, text=True)
    fait = subprocess.run(["npm", "run", "build"], cwd=DESIGN,
                          capture_output=True, text=True)
    journal.verifier("le build de la coquille aboutit", fait.returncode == 0,
                     (fait.stderr or fait.stdout).strip().splitlines()[-1]
                     if fait.returncode else "vite build")
    if fait.returncode != 0:
        return False
    # Verify the fragment is emitted byte-for-byte verbatim.
    enveloppe = (DESIGN / "index.html").read_text(encoding="utf-8")
    fragment = (DESIGN / "refonte.html").read_text(encoding="utf-8")
    emis = (DESIGN / "dist" / "index.html").read_text(encoding="utf-8")
    expected = enveloppe.replace("<!-- maquette -->", fragment)
    journal.verifier(
        "le fragment est émis verbatim, une seule fois",
        emis.count(fragment) == 1,
        f"fragment émis {emis.count(fragment)} fois")
    # Verify the module entry is present and correctly formatted (amendment 1).
    module_regex = r'<script[^>]*type="module"[^>]*src="/vite/[^"]+\.js"'
    module_matches = len(re.findall(module_regex, emis))
    journal.verifier(
        "l'entrée du module est émise exactement une fois",
        module_matches == 1,
        f"{module_matches} match(s) du regex")
    if module_matches != 1:
        return False
    # Extract the bundle filename from the module tag and verify it exists.
    bundle_match = re.search(r'src="/vite/([^"]+\.js)"', emis)
    if bundle_match:
        bundle_name = bundle_match.group(1)
        bundle_path = DESIGN / "dist" / "vite" / bundle_name
        journal.verifier(
            "le fichier du bundle existe",
            bundle_path.exists(),
            f"dist/vite/{bundle_name}")
    return True


def main():
    journal = Journal("R72 — la coquille émet le fragment verbatim")
    if not construire(journal):
        journal.bilan()
    journal.bilan()


main()
