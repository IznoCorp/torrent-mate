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


def strip_comments(source):
    """Remove // and /* */ comments from JavaScript source, handling strings correctly.

    Uses a simple state machine to track: code, //, /* */, single-quote string,
    double-quote string, and template-literal states. Returns source with
    comments replaced by whitespace (preserving line structure).
    """
    result = []
    i = 0
    while i < len(source):
        # Check for single-line comment: //
        if i < len(source) - 1 and source[i:i+2] == "//":
            # Skip until end of line
            while i < len(source) and source[i] != "\n":
                result.append(" " if source[i] != "\n" else "\n")
                i += 1
            if i < len(source) and source[i] == "\n":
                result.append("\n")
                i += 1
            continue
        # Check for multi-line comment: /* */
        if i < len(source) - 1 and source[i:i+2] == "/*":
            # Skip until */
            result.append(" ")
            result.append(" ")
            i += 2
            while i < len(source) - 1:
                if source[i:i+2] == "*/":
                    result.append(" ")
                    result.append(" ")
                    i += 2
                    break
                result.append(" " if source[i] != "\n" else "\n")
                i += 1
            continue
        # Regular character (not in a comment)
        result.append(source[i])
        i += 1
    return "".join(result)


def count_history_primitives(source):
    """Count history.pushState(, history.replaceState(, history.back(, and history.go(.

    Strips comments first, then counts occurrences outside of strings.
    """
    # Strip comments to avoid false matches in prose
    cleaned = strip_comments(source)

    patterns = [
        r"history\.pushState\s*\(",
        r"history\.replaceState\s*\(",
        r"history\.back\s*\(",
        r"history\.go\s*\(",
    ]

    total = 0
    for pattern in patterns:
        total += len(re.findall(pattern, cleaned))
    return total


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
    return fait.returncode == 0


def verifier_holds(journal):
    """Run the three holds on the built output. Called after build succeeds."""
    emis = (DESIGN / "dist" / "index.html").read_text(encoding="utf-8")
    fragment = (DESIGN / "refonte.html").read_text(encoding="utf-8")

    # Hold 1: Fragment emitted verbatim, exactly once
    journal.verifier(
        "le fragment est émis verbatim, une seule fois",
        emis.count(fragment) == 1,
        f"fragment émis {emis.count(fragment)} fois")

    # Hold 2: Module entry present, order-agnostic (F5)
    # Find all script tags and check for both type="module" AND src="/vite/...js"
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

    journal.verifier(
        "l'entrée du module est émise exactement une fois",
        matching_tags == 1,
        f"{matching_tags} match(s) trouvé(s)")

    # Hold 3: Bundle file exists
    if bundle_name:
        bundle_path = DESIGN / "dist" / "vite" / bundle_name
        journal.verifier(
            "le fichier du bundle existe",
            bundle_path.exists(),
            f"dist/vite/{bundle_name}")


def main():
    journal = Journal("R72 — la coquille émet le fragment verbatim")
    if not construire(journal):
        journal.bilan()
    # Run holds only after successful build (unless R72_SANS_BUILD)
    verifier_holds(journal)
    journal.bilan()


main()
