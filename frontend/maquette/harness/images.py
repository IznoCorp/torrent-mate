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
from common import ROOT, Journal, design_source


def main():
    journal = Journal("R70 — no embedded image")
    # EVERY source the design is written in, not the fragment alone: the
    # 930 image references this rule exists to check live in the engine
    # module, and reading only the fragment would check none of them.
    source = design_source()

    embedded = re.findall(r"data:image/", source)
    journal.check("no data:image in the source", not embedded,
                  f"{len(embedded)} embedded")

    references = sorted(set(re.findall(r'"assets/([\w./-]+\.webp)"', source)))
    missing = [r for r in references
               if not (ROOT / "design" / "assets" / r).is_file()]
    journal.check("every assets/ reference exists on disk", not missing,
                  f"{len(references)} references"
                  + (f" · missing: {missing[:3]}" if missing else ""))
    journal.summary()


main()
