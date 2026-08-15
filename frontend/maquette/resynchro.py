"""Rewrites the prototype's fast-moving counters from the live database.

The prototype embeds REAL data — a copy taken from the running system. The
system keeps running: the scheduler searches twice a day and increments each
follow's attempt counter in `acquire.db`, so the embedded copy ages by design.
The rule that guards data honesty (`harness/contenu.py`) compares the cards
against the live database and goes red on the first drift — rightly.

This tool closes that gap the only honest way: it reads the live counters and
rewrites the embedded ones. It touches nothing else. Run it when the suite
names a drift, review the diff, commit it as data.
"""
import os
import pathlib
import re
import sqlite3
import sys

RACINE = pathlib.Path(__file__).resolve().parent
PROTOTYPE = RACINE / "design" / "refonte.html"
ACQUIRE = pathlib.Path(os.path.expanduser(
    "~/dev/PersonalScraper/.data/acquire.db"))


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
    morceaux, prec = [], 0
    for a, b in objets_du_bloc(bloc):
        objet = bloc[a:b]
        mt = re.search(r't: "((?:[^"\\]|\\.)*)"', objet)
        mr = re.search(r"recherches: (\d+)", objet)
        if mt and mr:
            titre = mt.group(1).replace('\\"', '"')
            embarque = int(mr.group(1))
            if titre in reels and reels[titre] != embarque:
                corrections.append((titre, embarque, reels[titre]))
                objet = objet.replace(
                    f"recherches: {embarque},",
                    f"recherches: {reels[titre]},", 1)
        morceaux.extend((bloc[prec:a], objet))
        prec = b
    morceaux.append(bloc[prec:])

    for titre, avant, apres in corrections:
        print(f"  {titre} : {avant} -> {apres}")
    if corrections:
        PROTOTYPE.write_text(texte[:i] + "".join(morceaux) + texte[j:],
                             encoding="utf-8")
    print(f"{len(corrections)} correction(s)")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
