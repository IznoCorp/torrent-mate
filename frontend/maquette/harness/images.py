"""R70 — no image is embedded in the prototype source.

Every image lives in `design/assets/` as a real file the server can cache and
git can store once. A data URI that slips back in silently regrows the
single-file weight this rule exists to keep off; a reference to a file that
does not exist renders as a broken image only at runtime. Both are source
properties, so this rule reads the SOURCE — the DOM only shows what loaded.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import RACINE, Journal


def main():
    journal = Journal("R70 — aucune image embarquée")
    source = (RACINE / "design" / "refonte.html").read_text()

    incrustees = re.findall(r"data:image/", source)
    journal.verifier("aucun data:image dans la source", not incrustees,
                     f"{len(incrustees)} incrustée(s)")

    references = sorted(set(re.findall(r'"assets/([\w./-]+\.webp)"', source)))
    absentes = [r for r in references
                if not (RACINE / "design" / "assets" / r).is_file()]
    journal.verifier("chaque référence assets/ existe sur disque", not absentes,
                     f"{len(references)} références"
                     + (f" · absentes : {absentes[:3]}" if absentes else ""))
    journal.bilan()


main()
