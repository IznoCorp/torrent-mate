#!/usr/bin/env python3
"""Generates the design host's icon set: the app's icons, with a yellow ring.

Three sets of icons live in `frontend/public`, and they exist so that three
entries on one home screen can be told apart at a glance:

    prod     the icons as drawn — no ring
    staging  the same, with a cyan ring
    design   the same, with a yellow ring

The ring's geometry is not chosen here: it is **read off the staging set**, so
the three belong to one family instead of resembling each other. Every pixel
staging tinted over the background is tinted again, with the same coverage, in
yellow — which reproduces the exact shape including its antialiasing.

Maskable icons are the exception, and the reason is worth stating. A launcher
crops a maskable icon to its own shape, and everything outside the centre
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

# The icons' flat background, and the colour staging's ring is drawn in. Both
# are read back from the files below and only declared here to be checked.
FOND = (26, 26, 30)
CYAN = (45, 184, 212)

# The design host's ring. Yellow rather than amber: the mark inside the icon is
# already amber, and a ring in the same hue would read as a highlight of it
# rather than as a different application.
JAUNE = (255, 212, 0)

# Icons that keep a rectangular ring, and the staging file the shape is read
# from.
BORDEES = [
    ("pwa-192.png", "pwa-192-staging.png", "pwa-192-design.png"),
    ("pwa-512.png", "pwa-512-staging.png", "pwa-512-design.png"),
    ("apple-touch-icon.png", "apple-touch-icon-staging.png", "apple-touch-icon-design.png"),
]

# Icons a launcher may crop, which take a circular ring inside the safe zone.
MASQUABLES = [
    ("maskable-192.png", "maskable-192-design.png"),
    ("maskable-512.png", "maskable-512-design.png"),
]

# The safe zone is the centre circle of 80 % diameter, so its radius is 40 % of
# the side. The ring sits inside it, and its thickness is the one measured on
# the staging set: 15/512 of the side.
RAYON_ANNEAU = 0.37
EPAISSEUR = 15 / 512


def anneau_depuis_staging(prod: Path, staging: Path, sortie: Path) -> int:
    """Repaints staging's ring in yellow over the app's icon.

    Args:
        prod: The app's icon.
        staging: The same icon with the cyan ring.
        sortie: Where to write the result.

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
    touches = 0
    for y in range(base.height):
        for x in range(base.width):
            r0, g0, b0, a0 = pixels_base[x, y]
            r1, g1, b1, _ = pixels_ref[x, y]
            # The ring is what staging painted over the BACKGROUND. Where the
            # app's icon already carries its mark, a difference is staging's
            # recolouring, which this set does not reproduce.
            if (r0, g0, b0) != FOND or (r1, g1, b1) == (r0, g0, b0):
                continue
            # How far the pixel travelled from the background towards the full
            # ring colour — that is its coverage, antialiasing included.
            numerateur = max(abs(r1 - r0), abs(g1 - g0), abs(b1 - b0))
            denominateur = max(
                abs(CYAN[0] - FOND[0]), abs(CYAN[1] - FOND[1]), abs(CYAN[2] - FOND[2])
            )
            couverture = min(1.0, numerateur / denominateur)
            pixels_base[x, y] = (
                round(r0 + couverture * (JAUNE[0] - r0)),
                round(g0 + couverture * (JAUNE[1] - g0)),
                round(b0 + couverture * (JAUNE[2] - b0)),
                a0,
            )
            touches += 1
    base.save(sortie)
    return touches


def anneau_circulaire(prod: Path, sortie: Path) -> None:
    """Draws a circular ring inside the safe zone of a maskable icon.

    Args:
        prod: The app's maskable icon.
        sortie: Where to write the result.
    """
    base = Image.open(prod).convert("RGBA")
    cote = base.width
    # Drawn at 4× and downsampled: PIL has no antialiasing of its own, and a
    # hard-edged ring reads as a jagged one at home-screen size.
    echelle = 4
    calque = Image.new("RGBA", (cote * echelle, cote * echelle), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(calque)
    rayon = RAYON_ANNEAU * cote * echelle
    epaisseur = max(1, round(EPAISSEUR * cote * echelle))
    centre = cote * echelle / 2
    dessin.ellipse(
        [centre - rayon, centre - rayon, centre + rayon, centre + rayon],
        outline=(*JAUNE, 255),
        width=epaisseur,
    )
    calque = calque.resize((cote, cote), Image.LANCZOS)
    base.alpha_composite(calque)
    base.save(sortie)


def main() -> int:
    """Writes the whole design set.

    Returns:
        Process exit status.
    """
    for prod, staging, sortie in BORDEES:
        touches = anneau_depuis_staging(PUBLIC / prod, PUBLIC / staging, PUBLIC / sortie)
        print(f"{sortie}: {touches} pixels of ring, shape read from {staging}")
    for prod, sortie in MASQUABLES:
        anneau_circulaire(PUBLIC / prod, PUBLIC / sortie)
        print(f"{sortie}: circular ring inside the safe zone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
