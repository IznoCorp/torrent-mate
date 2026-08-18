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

ROOT = pathlib.Path(__file__).resolve().parent
# BOTH things this tool rewrites live in the engine, not in the fragment: the
# `FOLLOWS` block is data the engine declares, and the drawer footer is markup
# the engine emits. They moved together when the engine became a module, and
# the fragment kept only the stylesheet and the app shell. A stale path here
# would not corrupt anything — `main` reports « FOLLOWS block not found » and
# writes nothing — but it would stop correcting, which is the same as being
# wrong on the day a counter drifts.
ENGINE = ROOT / "design" / "src" / "engine" / "legacy.js"
ACQUIRE = pathlib.Path(os.path.expanduser(
    "~/dev/PersonalScraper/.data/acquire.db"))
# The drawer's « Version déployée » names what PRODUCTION runs — the deploy
# checkout is where that truth lives, not this working tree.
DEPLOYMENT = pathlib.Path(os.path.expanduser("~/deploy/torrentmate"))


def real_counters() -> dict[str, int]:
    """Returns, per followed title, the search count the engine really holds."""
    db = sqlite3.connect(f"file:{ACQUIRE}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    real = {}
    for follow in db.execute("SELECT title, media_ref_json FROM followed_series"):
        attempts = db.execute(
            "SELECT sum(attempts) att FROM wanted WHERE media_ref_json = ?",
            (follow["media_ref_json"],)).fetchone()
        real[follow["title"]] = attempts["att"] or 0
    db.close()
    return real


def block_objects(block: str) -> list[tuple[int, int]]:
    """Returns the [start, end) spans of the array's top-level objects."""
    spans, depth, start = [], 0, 0
    for index, char in enumerate(block):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                spans.append((start, index + 1))
    return spans


def main() -> int:
    """Rewrites every drifted counter, plus the drawer's footer.

    Returns:
        Process exit status: 1 when a title was never looked up (nothing is
        written in that case), 0 otherwise.
    """
    if not ACQUIRE.is_file():
        print(f"database absent: {ACQUIRE}")
        return 1
    real = real_counters()
    text = ENGINE.read_text(encoding="utf-8")
    i = text.find("const FOLLOWS = [")
    j = text.find("\n  ];", i)
    if i < 0 or j < 0:
        print(f"FOLLOWS block not found in {ENGINE.name}")
        return 1
    block = text[i:j]

    corrections = []
    unmatched = []
    pieces, previous = [], 0
    for a, b in block_objects(block):
        obj = block[a:b]
        # Anchored on the object's opening brace: the title must be the FIRST
        # key, not merely the first `t: "…"` found anywhere in the object —
        # a stray `t:`-shaped key elsewhere would otherwise win silently.
        title_match = re.match(r'\s*\{\s*t:\s*"((?:[^"\\]|\\.)*)"', obj)
        if not title_match:
            raise ValueError(
                f'FOLLOWS object whose first key is not "t": {obj[:80]!r}')
        title = title_match.group(1).replace('\\"', '"')
        searches_match = re.search(r"recherches: (\d+)", obj)
        # A title with no `recherches:` key is just as malformed as one with
        # no `t:` key (B-027's own case) — skipping it silently would leave
        # its counter stale forever without a single line saying so.
        if not searches_match:
            raise ValueError(
                f'FOLLOWS object "{title}" has no "recherches" key: {obj[:80]!r}')
        embedded = int(searches_match.group(1))
        if title in real:
            if real[title] != embedded:
                corrections.append((title, embedded, real[title]))
                obj = obj.replace(
                    f"recherches: {embedded},",
                    f"recherches: {real[title]},", 1)
        else:
            unmatched.append(title)
        pieces.extend((block[previous:a], obj))
        previous = b
    pieces.append(block[previous:])

    for title, before, after in corrections:
        print(f"  {title} : {before} -> {after}")

    # An unmatched title reads exactly like « already in sync » unless it is
    # named here — silence is the bug (B-028), not a valid outcome. And the
    # corrections just printed above were computed, never written: the script
    # returns before reaching `ENGINE.write_text` below, so the output
    # must say so explicitly rather than let those lines read as applied.
    if unmatched:
        print(f"nothing written — {len(unmatched)} title(s) never "
              f"looked up: " + ", ".join(unmatched))
        return 1

    if corrections:
        text = text[:i] + "".join(pieces) + text[j:]

    footer = sync_footer(text)
    if footer:
        text = footer
        corrections.append(("drawer footer", "", ""))

    if corrections:
        ENGINE.write_text(text, encoding="utf-8")
    print(f"{len(corrections)} correction(s)")
    return 0


def deployed_version() -> tuple[str, str] | None:
    """Returns production's (version, short sha), or None when unreadable.

    Read from the deploy checkout — the drawer's footer claims what is
    DEPLOYED, and this working tree is often ahead of it.
    """
    init = DEPLOYMENT / "personalscraper" / "__init__.py"
    if not init.is_file():
        return None
    found = re.search(r'__version__ = "([^"]+)"', init.read_text(encoding="utf-8"))
    if not found:
        return None
    sha = subprocess.run(
        ["git", "-C", str(DEPLOYMENT), "rev-parse", "--short=8", "HEAD"],
        capture_output=True, text=True)
    if sha.returncode != 0:
        return None
    return found.group(1), sha.stdout.strip()


def sync_footer(text: str) -> str | None:
    """Rewrites the drawer footer's version and build, or returns None.

    The footer was once a hand-written snapshot and aged invisibly — no rule
    compares it to anything. Reading production keeps it a real datum.
    """
    real = deployed_version()
    if real is None:
        print(f"drawer footer: deployment unreadable ({DEPLOYMENT}), unchanged")
        return None
    version, sha = real
    updated = re.sub(
        r'(<p class="vv">)[^<]*(</p>)',
        rf"\g<1>{version}\g<2>", text, count=1)
    updated = re.sub(
        r'(<p class="vc">build )[0-9a-f]+([^<]*</p>)',
        rf"\g<1>{sha}\g<2>", updated, count=1)
    if updated == text:
        return None
    print(f"  drawer footer: version {version}, build {sha}")
    return updated


if __name__ == "__main__":
    sys.exit(main())
