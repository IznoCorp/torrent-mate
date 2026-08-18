#!/usr/bin/env python3
"""Generates the design host's icon set: the app's icons, with a yellow ring.

Three sets of icons exist so that three entries on one home screen can be told
apart at a glance. Two of them — prod and staging — live in `frontend/public`,
which Vite copies whole into the bundle. The DESIGN set does not: it dresses a
host production never serves, and shipping it would put 56 kB of nothing in the
bundle. It sits beside the prototype, in `frontend/maquette/assets`.

    prod     the icons as drawn — no ring
    staging  the same, with a cyan ring
    design   the same, with a yellow ring

The ring's geometry is not chosen here: it is **read off the staging set**, so
the three belong to one family instead of resembling each other. Every pixel
staging tinted over the background is tinted again, with the same coverage, in
yellow — which reproduces the exact shape including its antialiasing.

Maskable icons are the exception, and the reason is worth stating. A launcher
crops a maskable icon to its own shape, and everything outside the center
circle of 80 % diameter may be cut. The staging set answers that by carrying no
ring at all on its maskable variants — it can afford to, because it also
recolours the mark. This set does not recolour anything, so a ringless maskable
icon would be byte-identical to the app's, and Android prefers the maskable one
for the home screen: the very icon the operator would see would be the one that
tells them nothing. The ring is therefore drawn as a CIRCLE inside the safe
zone, which no mask shape can remove.

Run from `frontend/`:

    python3 scripts/make-design-icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parent.parent / "public"
# Read from `public` (the app's own icons are the model), written beside the
# prototype so the bundle never carries them.
OUTPUT = Path(__file__).resolve().parent.parent / "maquette" / "assets"

# The icons' flat background, and the colour staging's ring is drawn in. Both
# are read back from the files below and only declared here to be checked.
BACKGROUND = (26, 26, 30)
CYAN = (45, 184, 212)

# The design host's ring. Yellow rather than amber: the mark inside the icon is
# already amber, and a ring in the same hue would read as a highlight of it
# rather than as a different application.
YELLOW = (255, 212, 0)

# Icons that keep a rectangular ring, and the staging file the shape is read
# from.
BORDERED = [
    ("pwa-192.png", "pwa-192-staging.png", "pwa-192-design.png"),
    ("pwa-512.png", "pwa-512-staging.png", "pwa-512-design.png"),
    ("apple-touch-icon.png", "apple-touch-icon-staging.png", "apple-touch-icon-design.png"),
]

# Icons a launcher may crop, which take a circular ring inside the safe zone.
MASKABLE = [
    ("maskable-192.png", "maskable-192-design.png"),
    ("maskable-512.png", "maskable-512-design.png"),
]

# The safe zone is the center circle of 80 % diameter, so its radius is 40 % of
# the side. The ring sits inside it, and its thickness is the one measured on
# the staging set: 15/512 of the side.
RING_RADIUS = 0.37
RING_WIDTH = 15 / 512


def ring_from_staging(prod: Path, staging: Path, output: Path) -> int:
    """Repaints staging's ring in yellow over the app's icon.

    Args:
        prod: The app's icon.
        staging: The same icon with the cyan ring.
        output: Where to write the result.

    Returns:
        The number of pixels the ring covers.

    Raises:
        SystemExit: When the two icons do not have the same size, which would
            mean the sets have drifted apart and the shape can no longer be
            read from one for the other.
    """
    base = Image.open(prod).convert("RGBA")
    ref = Image.open(staging).convert("RGBA")
    if base.size != ref.size:
        sys.exit(f"{prod.name} and {staging.name} differ in size — the sets have drifted")

    pixels_base = base.load()
    pixels_ref = ref.load()
    touched = 0
    for y in range(base.height):
        for x in range(base.width):
            r0, g0, b0, a0 = pixels_base[x, y]
            r1, g1, b1, _ = pixels_ref[x, y]
            # The ring is what staging painted over the BACKGROUND. Where the
            # app's icon already carries its mark, a difference is staging's
            # recolouring, which this set does not reproduce.
            if (r0, g0, b0) != BACKGROUND or (r1, g1, b1) == (r0, g0, b0):
                continue
            # How far the pixel travelled from the background towards the full
            # ring colour — that is its coverage, antialiasing included.
            numerator = max(abs(r1 - r0), abs(g1 - g0), abs(b1 - b0))
            denominator = max(
                abs(CYAN[0] - BACKGROUND[0]), abs(CYAN[1] - BACKGROUND[1]), abs(CYAN[2] - BACKGROUND[2])
            )
            coverage = min(1.0, numerator / denominator)
            pixels_base[x, y] = (
                round(r0 + coverage * (YELLOW[0] - r0)),
                round(g0 + coverage * (YELLOW[1] - g0)),
                round(b0 + coverage * (YELLOW[2] - b0)),
                a0,
            )
            touched += 1
    base.save(output)
    return touched


def circular_ring(prod: Path, output: Path) -> None:
    """Draws a circular ring inside the safe zone of a maskable icon.

    Args:
        prod: The app's maskable icon.
        output: Where to write the result.
    """
    base = Image.open(prod).convert("RGBA")
    side = base.width
    # Drawn at 4× and downsampled: PIL has no antialiasing of its own, and a
    # hard-edged ring reads as a jagged one at home-screen size.
    scale = 4
    layer = Image.new("RGBA", (side * scale, side * scale), (0, 0, 0, 0))
    drawing = ImageDraw.Draw(layer)
    radius = RING_RADIUS * side * scale
    width = max(1, round(RING_WIDTH * side * scale))
    center = side * scale / 2
    drawing.ellipse(
        [center - radius, center - radius, center + radius, center + radius],
        outline=(*YELLOW, 255),
        width=width,
    )
    layer = layer.resize((side, side), Image.LANCZOS)
    base.alpha_composite(layer)
    base.save(output)


def main() -> int:
    """Writes the whole design set.

    Returns:
        Process exit status.
    """
    for prod, staging, output in BORDERED:
        touched = ring_from_staging(PUBLIC / prod, PUBLIC / staging, OUTPUT / output)
        print(f"{output}: {touched} pixels of ring, shape read from {staging}")
    for prod, output in MASKABLE:
        circular_ring(PUBLIC / prod, OUTPUT / output)
        print(f"{output}: circular ring inside the safe zone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
