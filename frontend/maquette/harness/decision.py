"""R57 — the arbitration screen, and what a decision is.

A scrape decision is a FOLDER the scrape could not name. Everything on this
screen follows from that, and every check here is one of the ways the drawing
could quietly stop being true:

  · the card's subject is the folder, set in the mono face and never cleaned
    up — recognising what is on disk is the whole point;
  · a decision is not a medium, so it promises neither a sheet nor a panel,
    the same way a release candidate promises neither;
  · the reason it is waiting is said in words, never in the engine's token;
  · the score is printed only when it SEPARATES. « Lucky » is the case that
    settles it: four of its five candidates came back at exactly the same
    score, and printing it four times would suggest a ranking that does not
    exist — which is the opposite of what the screen is asking for;
  · there are always three ways out, and the third used to be missing: pick a
    candidate, search by hand, or leave the folder as it is. Without the last,
    one could only ever disagree with the machine, never agree with it;
  · a folder with no pending decision borrows nobody's candidates. Showing
    another folder's would be the worst possible lie on the one screen whose
    job is to name what is on disk;
  · and answering takes the folder out of the queue, on BOTH lists it appears
    on. « À traiter » on the acquisition side used to keep it forever.
"""
import asyncio

from common import Journal, open_page
from playwright.async_api import async_playwright

# The engine's own words. None of them may reach a screen.
TOKENS = ["below_threshold", "mid_band", "ambiguous", "manual", "dismissed",
          "superseded", "resolved", "pending", "search_override", "staging_path"]

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


SCREEN = """() => {
  // The arbitration screen left `#screen` for a real route
  // (`/resolution/$dossier`, rendered inside `#coquille`), so it answers to
  // its own identity now, the way the fiche and the add screen already do.
  // The identity rather than a bare `.screen.open`: two screens can carry
  // `open` at once, and this rule must measure THIS one. An absent screen
  // reads as an empty one, so every check below falls on its own number —
  // readable — instead of on a TypeError, which is not.
  const s = document.querySelector('.screen.open[data-cle^="resolution:"]')
    ?? document.createElement('div');
  const cards = [...s.querySelectorAll('.card')];
  const decisions = cards.filter(c => c.dataset.nonmedia === 'decision');
  const candidates = cards.filter(c => c.dataset.nonmedia === 'candidat');
  return {
    title: (s.querySelector('.h2') || {}).textContent || '',
    titleMono: !!s.querySelector('.h2 code'),
    candidates: candidates.map(c => ({
      title: (c.querySelector('.ctitle') || {}).textContent || '',
      confidence: (c.querySelector('.chip') || {}).textContent || null,
      posterButton: (c.querySelector('.poster') || {}).tagName === 'BUTTON',
      panel: (c.querySelector('.cbody') || {}).dataset?.panel || null,
      poster: (c.querySelector('.poster img') || {}).src || null,
      noPoster: !!c.querySelector('.poster .pfall'),
      plot: (c.querySelector('.cov') || {}).textContent || null,
      link: c.querySelectorAll('a, [data-fiche]').length,
    })),
    decisions: decisions.map(c => ({
      folder: (c.querySelector('.ctitle') || {}).textContent || '',
      mono: !!c.querySelector('.ctitle code'),
      posterButton: (c.querySelector('.poster') || {}).tagName === 'BUTTON',
      panel: (c.querySelector('.cbody') || {}).dataset?.panel || null,
      chips: [...c.querySelectorAll('.chip')].map(x => x.textContent.trim()),
    })),
    exits: [...s.querySelectorAll('.sact, .cfoot')].map(x => x.textContent.trim()),
    text: (s.textContent || '').replace(/\\s+/g, ' '),
  };
}"""


async def main():
    global _journal
    _journal = Journal("R57 — the resolution screen")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        # ── with candidates: the tie, and what it forbids ──────────────────
        await pg.evaluate("()=>window.__go('arr-decision')")
        await pg.wait_for_timeout(420)
        with_ = await pg.evaluate(SCREEN)

        check("the folder is the subject, in the mono face", with_["titleMono"], with_["title"][:40])
        check("the five real candidates are there", len(with_["candidates"]) == 5,
              str(len(with_["candidates"])))
        check("no candidate promises a sheet or a panel",
              not any(c["posterButton"] or c["panel"] for c in with_["candidates"]))

        # The four that tie carry no percentage; the fifth, which differs, does.
        without_score = [c for c in with_["candidates"] if not c["confidence"]]
        with_score = [c for c in with_["candidates"] if c["confidence"]]
        check("the tied ones show no score", len(without_score) == 4,
              f"{len(without_score)} without a score")
        check("the one that stands out shows its own", len(with_score) == 1,
              str([c["confidence"] for c in with_score]))
        check("and the screen says why it does not rank",
              "ne tranche pas" in with_["text"])

        # A candidate wearing a neighbour's poster is the one mistake this
        # screen cannot make: four of these five are DIFFERENT series with
        # nearly the same name, and the picture is what tells them apart.
        # « Lucky (2006) » was showing « Lucky (2026) »'s poster while its own
        # line said the provider had none.
        posters = [c["poster"] for c in with_["candidates"] if c["poster"]]
        check("no candidate wears another's poster",
              len(posters) == len(set(posters)),
              f"{len(posters)} posters, {len(set(posters))} distinct")
        # What actually separates four series with nearly the same name is what
        # they are about. Without it, the only way to decide was to leave the
        # screen — and leaving loses the queue.
        check("every candidate says what it is about",
              all(c["plot"] for c in with_["candidates"]),
              str([c["title"] for c in with_["candidates"] if not c["plot"]]))
        check("and nothing invites leaving the screen to decide",
              not any(c["link"] for c in with_["candidates"]))
        check("the one the provider does not illustrate shows the substitute",
              sum(1 for c in with_["candidates"] if c["noPoster"]) == 1,
              str([c["title"] for c in with_["candidates"] if c["noPoster"]]))

        # ── the three ways out ────────────────────────────────────────────
        check("one can pick a candidate",
              sum(1 for x in with_["exits"] if "celui-ci" in x) == 5)
        check("one can search by hand",
              any("manuellement" in x for x in with_["exits"]))
        check("one can leave it as it is",
              any("Laisser tel quel" in x for x in with_["exits"]))

        # ── the settled ones, and what they are ───────────────────────────
        check("the settled decisions are recalled", len(with_["decisions"]) >= 5,
              str(len(with_["decisions"])))
        check("each one shows the FOLDER, in the mono face",
              all(d["mono"] for d in with_["decisions"]))
        check("none promises a sheet or a panel",
              not any(d["posterButton"] or d["panel"] for d in with_["decisions"]))
        check("each says its reason AND what became of it",
              all(len(d["chips"]) >= 2 for d in with_["decisions"]),
              str([d["chips"] for d in with_["decisions"]][:2]))

        # ── no engine token ever reaches a screen ─────────────────────────
        leaks = [j for j in TOKENS if j in with_["text"]]
        check("no engine token on screen", not leaks, ", ".join(leaks))

        # ── without candidates: nothing is borrowed ───────────────────────
        await pg.evaluate("()=>window.__go('arr-resolution')")
        await pg.wait_for_timeout(420)
        without = await pg.evaluate(SCREEN)
        check("a folder with no decision borrows no candidate",
              len(without["candidates"]) == 0, str(len(without["candidates"])))
        check("it says the providers returned nothing",
              "aucun candidat" in without["text"].lower())
        check("and it keeps its two other ways out",
              any("manuellement" in x for x in without["exits"])
              and any("Laisser tel quel" in x for x in without["exits"]))

        # ── answering empties the queue, on BOTH lists ────────────────────
        for state_, list_, exit_ in (
            ("arr-decision", "blocked", "[data-resolve]"),
            ("arr-repos", "stuck", "[data-laisser]"),
        ):
            await pg.evaluate("(s)=>window.__go(s)", state_)
            await pg.wait_for_timeout(420)
            if state_ == "arr-repos":
                await pg.evaluate(
                    "()=>[...document.querySelectorAll('.cfoot')]"
                    ".find(x=>x.textContent.includes('Résoudre')).click()")
                await pg.wait_for_timeout(420)
            before = await pg.evaluate(f"()=>derived.{list_}().length")
            # Without the way out there is nothing to click, and clicking
            # nothing raises instead of naming the defect. A crash is a
            # failure nobody can read.
            if not await pg.evaluate("(s)=>document.querySelector(s)!==null", exit_):
                check(f"answering empties the « {list_} » queue", False,
                      f"{exit_} absent from the screen")
                continue
            await pg.evaluate("(s)=>document.querySelector(s).click()", exit_)
            await pg.wait_for_timeout(700)
            after = await pg.evaluate(f"()=>derived.{list_}().length")
            check(f"answering empties the « {list_} » queue", after == before - 1,
                  f"{before} → {after}")

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
