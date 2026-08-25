#!/usr/bin/env python3
"""Freezes the surface partition of BLOCK 2 as this wave opened it.

The manifest is a SNAPSHOT, taken once, and it is what makes each phase's scope
a fact rather than a judgement. Line numbers are recorded for provenance only:
they go stale the moment the first phase deletes a rule, so every consumer keys
on the class names instead.

Run from the repository root:
    python3 docs/features/maquette-l07/plan/build-surface-manifest.py

Writes `surface-manifest.json` beside itself.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[4]
SOURCE = ROOT / "frontend" / "maquette" / "design" / "refonte.html"
BLOCK2_FIRST_LINE = 229

# Each entry is (first line of the region, surface key, the phase that owns it).
# The boundaries were read off the stylesheet's own section comments and
# verified one by one; the two regions marked `harness` carry a comment in the
# source saying so, and they sit in BLOCK 2 by mistake rather than by design.
REGIONS = [
    (229, "tokens", "P02"),
    (415, "shell-chrome", "P05"),
    (532, "scrollport", "P05"),
    (543, "view-tabs", "P09"),
    (610, "filter-zone", "P09"),
    (774, "body-sections", "P06"),
    (832, "card", "P08"),
    (1304, "crossref", "P08"),
    (1332, "grid-tiles", "P09"),
    (1406, "discover-deck", "P10"),
    (1638, "key-value-rows", "P13"),
    (1691, "live-strip", "P07"),
    (1862, "pressable-surfaces", "P01"),
    (1878, "settings", "P14"),
    (2129, "pull-to-refresh", "P05"),
    (2156, "fab", "P05"),
    (2189, "bottom-bar", "P05"),
    (2268, "screens", "P06"),
    (2318, "bottom-sheet", "P06"),
    (2505, "media-sheet", "P12"),
    (2843, "season-matrix", "P12"),
    (3001, "airdate-popover", "P12"),
    (3050, "add-screen", "P11"),
    (3172, "action-buttons", "P06"),
    (3227, "release-screen", "P11"),
    (3322, "form-controls", "P06"),
    (3420, "dialog", "P06"),
    (3531, "toast", "P05"),
    (3575, "empty-note", "P06"),
    (3592, "surface-states", "P06"),
    (3625, "skeletons", "P06"),
    (3719, "grid-selection", "P09"),
    (3824, "harness-state-panel", "P16-delete"),
    (3883, "drawer", "P05"),
    (4009, "harness-design-notes", "P16-delete"),
    (4036, "install-proposal", "P15"),
    (4159, "login", "P16-residue"),
    (4290, "splash", "P16-residue"),
]


def main() -> None:
    """Writes the manifest and asserts the partition is total."""
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    bounds = [(start, key, phase) for start, key, phase in REGIONS]
    ends = [bounds[i + 1][0] - 1 for i in range(len(bounds) - 1)] + [len(lines)]

    surfaces = {}
    seen_rules = 0
    for (start, key, phase), end in zip(bounds, ends):
        classes, rules = [], 0
        for number in range(start, end + 1):
            line = lines[number - 1]
            head = re.match(r"^  ([^{]*)\{\s*$", line)
            if not head:
                continue
            rules += 1
            for name in re.findall(r"\.([a-zA-Z][\w-]*)", head.group(1)):
                if name not in classes:
                    classes.append(name)
        seen_rules += rules
        surfaces[key] = {
            "phase": phase,
            "lines": [start, end],
            "rules": rules,
            "classes": classes,
        }

    total = sum(
        1
        for number in range(BLOCK2_FIRST_LINE, len(lines) + 1)
        if re.match(r"^  [^{]*\{\s*$", lines[number - 1])
    )
    # The partition must be TOTAL: a rule in no region is a rule no phase owns,
    # and it would reach phase 16 unconverted with nothing having said so.
    assert seen_rules == total, f"partition covers {seen_rules} of {total} rules"

    out = {
        "what": (
            "The surface partition of BLOCK 2 as L07 opened it. Class names are "
            "the key; line numbers are provenance and go stale as the wave "
            "empties the stylesheet."
        ),
        "source": "frontend/maquette/design/refonte.html",
        "block2FirstLine": BLOCK2_FIRST_LINE,
        "rules": total,
        "surfaces": surfaces,
    }
    target = pathlib.Path(__file__).with_name("surface-manifest.json")
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"{len(surfaces)} surfaces, {total} rules, partition total")


if __name__ == "__main__":
    main()
