"""Rewrites the prototype's fast-moving counters from the live database.

The prototype embeds REAL data — a copy taken from the running system. The
system keeps running: the scheduler searches twice a day and increments each
follow's attempt counter in `acquire.db`, so the embedded copy ages by design.
The rule that guards data honesty (`harness/content.py`) compares the cards
against the live database and goes red on the first drift — rightly.

This tool closes that gap the only honest way: it reads the live counters and
rewrites the embedded ones. It touches nothing else. Run it when the suite
names a drift, review the diff, commit it as data.
"""
import os
import pathlib
import re
import sqlite3
import subprocess
import sys

RACINE = pathlib.Path(__file__).resolve().parent
PROTOTYPE = RACINE / "design" / "refonte.html"
ACQUIRE = pathlib.Path(os.path.expanduser(
    "~/dev/PersonalScraper/.data/acquire.db"))
# The drawer's « Version déployée » names what PRODUCTION runs — the deploy
# checkout is where that truth lives, not this working tree.
DEPLOIEMENT = pathlib.Path(os.path.expanduser("~/deploy/torrentmate"))


def compteurs_reels() -> dict[str, int]:
    """Returns, per followed title, the search count the engine really holds."""
    db = sqlite3.connect(f"file:{ACQUIRE}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    reels = {}
    for f in db.execute("SELECT title, media_ref_json FROM followed_series"):
        w = db.execute(
            "SELECT sum(attempts) att FROM wanted WHERE media_ref_json = ?",
            (f["media_ref_json"],)).fetchone()
        reels[f["title"]] = w["att"] or 0
    db.close()
    return reels


def objets_du_bloc(bloc: str) -> list[tuple[int, int]]:
    """Returns the [start, end) spans of the array's top-level objects."""
    spans, prof, debut = [], 0, 0
    for i, ch in enumerate(bloc):
        if ch == "{":
            if prof == 0:
                debut = i
            prof += 1
        elif ch == "}":
            prof -= 1
            if prof == 0:
                spans.append((debut, i + 1))
    return spans


def principal() -> int:
    if not ACQUIRE.is_file():
        print(f"base absente : {ACQUIRE}")
        return 1
    reels = compteurs_reels()
    texte = PROTOTYPE.read_text(encoding="utf-8")
    i = texte.find("const FOLLOWS = [")
    j = texte.find("\n  ];", i)
    if i < 0 or j < 0:
        print("bloc FOLLOWS introuvable dans le prototype")
        return 1
    bloc = texte[i:j]

    corrections = []
    introuvables = []
    morceaux, prec = [], 0
    for a, b in objets_du_bloc(bloc):
        objet = bloc[a:b]
        # Anchored on the object's opening brace: the title must be the FIRST
        # key, not merely the first `t: "…"` found anywhere in the object —
        # a stray `t:`-shaped key elsewhere would otherwise win silently.
        mt = re.match(r'\s*\{\s*t:\s*"((?:[^"\\]|\\.)*)"', objet)
        if not mt:
            raise ValueError(
                f"objet FOLLOWS sans « t » en première clé : {objet[:80]!r}")
        titre = mt.group(1).replace('\\"', '"')
        mr = re.search(r"recherches: (\d+)", objet)
        # A title with no `recherches:` key is just as malformed as one with
        # no `t:` key (B-027's own case) — skipping it silently would leave
        # its counter stale forever without a single line saying so.
        if not mr:
            raise ValueError(
                f"objet FOLLOWS « {titre} » sans « recherches » : {objet[:80]!r}")
        embarque = int(mr.group(1))
        if titre in reels:
            if reels[titre] != embarque:
                corrections.append((titre, embarque, reels[titre]))
                objet = objet.replace(
                    f"recherches: {embarque},",
                    f"recherches: {reels[titre]},", 1)
        else:
            introuvables.append(titre)
        morceaux.extend((bloc[prec:a], objet))
        prec = b
    morceaux.append(bloc[prec:])

    for titre, avant, apres in corrections:
        print(f"  {titre} : {avant} -> {apres}")

    # An unmatched title reads exactly like « already in sync » unless it is
    # named here — silence is the bug (B-028), not a valid outcome. And the
    # corrections just printed above were computed, never written: the script
    # returns before reaching `PROTOTYPE.write_text` below, so the output
    # must say so explicitly rather than let those lines read as applied.
    if introuvables:
        print(f"aucune écriture — {len(introuvables)} titre(s) jamais "
              f"retrouvé(s): " + ", ".join(introuvables))
        return 1

    if corrections:
        texte = texte[:i] + "".join(morceaux) + texte[j:]

    corrections_pied = synchroniser_pied(texte)
    if corrections_pied:
        texte = corrections_pied
        corrections.append(("pied du tiroir", "", ""))

    if corrections:
        PROTOTYPE.write_text(texte, encoding="utf-8")
    print(f"{len(corrections)} correction(s)")
    return 0


def version_deployee() -> tuple[str, str] | None:
    """Returns production's (version, short sha), or None when unreadable.

    Read from the deploy checkout — the drawer's footer claims what is
    DEPLOYED, and this working tree is often ahead of it.
    """
    init = DEPLOIEMENT / "personalscraper" / "__init__.py"
    if not init.is_file():
        return None
    m = re.search(r'__version__ = "([^"]+)"', init.read_text(encoding="utf-8"))
    if not m:
        return None
    sha = subprocess.run(
        ["git", "-C", str(DEPLOIEMENT), "rev-parse", "--short=8", "HEAD"],
        capture_output=True, text=True)
    if sha.returncode != 0:
        return None
    return m.group(1), sha.stdout.strip()


def synchroniser_pied(texte: str) -> str | None:
    """Rewrites the drawer footer's version and build, or returns None.

    The footer was once a hand-written snapshot and aged invisibly — no rule
    compares it to anything. Reading production keeps it a real datum.
    """
    reel = version_deployee()
    if reel is None:
        print(f"pied du tiroir : déploiement illisible ({DEPLOIEMENT}), inchangé")
        return None
    version, sha = reel
    neuf = re.sub(
        r'(<p class="vv">)[^<]*(</p>)',
        rf"\g<1>{version}\g<2>", texte, count=1)
    neuf = re.sub(
        r'(<p class="vc">build )[0-9a-f]+([^<]*</p>)',
        rf"\g<1>{sha}\g<2>", neuf, count=1)
    if neuf == texte:
        return None
    print(f"  pied du tiroir : version {version}, build {sha}")
    return neuf


if __name__ == "__main__":
    sys.exit(principal())
