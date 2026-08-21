"""R63 — a card says what the engine knows, and two tabs say it the same way.

A followed medium's card was three short lines beside a poster and the rest of
it was empty — while every fact it was missing already sat in `acquire.db`, and
« En cours » was already printing most of them for the same media. The void was
not a lack of ideas; it was two tabs describing the same objects and saying
different amounts about them.

The library's rows had the mirror problem: the year and the fraction say what a
medium IS, and nothing said what it is ABOUT. The synopsis exists — in the
`<plot>` of each medium's own NFO — and is NOT in `library.db`, which is a gap
in the read-model this script records rather than hides.

What this holds to:

  · a follow's card carries its identity, what is happening and when, and what
    tells a healthy follow from a stalled one — all read from real rows;
  · the sentence about the next search is the SAME sentence on both tabs, and
    the hour comes from the same cron the cadence line prints;
  · a library row carries the synopsis, clamped with an ellipsis, and a medium
    whose NFO has no plot shows NOTHING rather than a filler;
  · the lenses read Médias, Récents, Incomplets — everything, then what just
    arrived, then the repair list.
"""
import asyncio
import os
import pathlib
import re
import sqlite3

from common import Journal, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACQUIRE = pathlib.Path(os.path.expanduser("~/dev/PersonalScraper/.data/acquire.db"))

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


def real_facts():
    """Returns, per followed title, the numbers `acquire.db` really holds.

    Returns:
        A dict title → {searches}. Empty when the database is not present, in
        which case the comparison against it is skipped and SAID to be skipped.
    """
    if not ACQUIRE.is_file():
        return {}
    db = sqlite3.connect(f"file:{ACQUIRE}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    out = {}
    for f in db.execute("SELECT title, media_ref_json, series_status FROM followed_series"):
        w = db.execute("SELECT sum(attempts) att FROM wanted WHERE media_ref_json = ?",
                       (f["media_ref_json"],)).fetchone()
        out[f["title"]] = {"searches": w["att"] or 0, "series": f["series_status"]}
    db.close()
    return out


async def main():
    global _journal
    _journal = Journal("R63 — what a card says")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        # ── a follow's card is not empty ────────────────────────────────────
        await pg.evaluate("()=>window.__go('acq-follows-list')")
        await pg.wait_for_timeout(420)
        follows = await pg.evaluate("""()=>[...document.querySelectorAll('#view [data-part="card"]')].map(c => ({
          title: (c.querySelector('[data-part="card/title"]')||{}).textContent||'',
          sub: (c.querySelector('[data-part="card/subtitle"]')||{}).textContent||'',
          reason: (c.querySelector('[data-part="card/reason"]')||{}).textContent||'',
          facts: (c.querySelector('[data-part="card/caption"]')||{}).textContent||''}))""")
        check("the follows list has cards", len(follows) > 4, str(len(follows)))
        silent = [s["title"] for s in follows if not s["sub"].strip()]
        check("every follow says what it is", not silent, str(silent[:3]))
        check("and a series says whether it continues",
              any("série · " in s["sub"] for s in follows),
              str([s["sub"] for s in follows if "série" in s["sub"]][:2]))
        without_facts = [s["title"] for s in follows if "recherche" not in s["facts"]]
        check("and since when it is searched for, and how many times",
              not without_facts, str(without_facts[:3]))

        # Compared against the DATABASE, not against itself: a card printing a
        # number the engine never held would otherwise pass.
        real = real_facts()
        if not real:
            check("the numbers come from acquire.db",
                  False, f"database absent: {ACQUIRE}")
        else:
            wrong = []
            for s in follows:
                r = real.get(s["title"])
                if not r:
                    continue
                # Word-boundary match, not substring: « 1 recherche » must not
                # pass against a card actually printing « 11 recherches ».
                pattern = rf"\b{r['searches']}\s+recherche"
                if not re.search(pattern, s["facts"]):
                    wrong.append(f"{s['title']} : « {s['facts']} » vs {r['searches']}")
            check("the numbers come from acquire.db, not from the mock-up",
                  not wrong, str(wrong[:3]))

        # ── the two tabs say the same thing the same way ────────────────────
        # « En cours » already had the sentence; the follow tab had none, and
        # two tabs about the same media must not phrase the same fact twice.
        await pg.evaluate("()=>window.__go('acq-now-loaded')")
        await pg.wait_for_timeout(420)
        running = await pg.evaluate("""()=>[...document.querySelectorAll('#view [data-part="card/reason"]')]
          .map(e => e.textContent)""")
        phrase = "Aucune release conforme"
        check("« En cours » explains a fruitless search",
              any(phrase in r for r in running), str(running[:1]))
        check("and « Suivis » explains it the SAME way",
              any(phrase in s["reason"] for s in follows),
              str([s["reason"] for s in follows][:1]))

        # The hour is derived from the cron the cadence line prints, so the two
        # can never disagree about when the next search happens.
        hour = await pg.evaluate(
            "()=>nextSearchFR(CADENCE_CRON, new Date())")
        cadence = await pg.evaluate("()=>cadenceFR(CADENCE_CRON)")
        check("the hour announced is the cadence's own",
              bool(hour) and hour in cadence, f"{hour} in « {cadence} »")
        check("and the cards announce it",
              any(hour in s["reason"] for s in follows if s["reason"]),
              hour or "no hour")

        # ── the library says what a medium is ABOUT ─────────────────────────
        for lens, name in (("cat", "Médias"), ("rec", "Récents")):
            await pg.evaluate("(l)=>{window.__store.write({page: 'lib',"
                              " libLens: l, libMode: 'list'}); render();}", lens)
            await pg.wait_for_timeout(650)
            seen = await pg.evaluate("""()=>{
              const cards = [...document.querySelectorAll('#libitems [data-part="card"]')];
              return {
                n: cards.length,
                withPlot: cards.filter(c => c.querySelector('[data-part="card/overview"]')).length,
                clamped: cards.filter(c => {
                  const e = c.querySelector('[data-part="card/overview"]');
                  return e && e.scrollHeight > e.clientHeight + 1;}).length,
                overflowing: cards.filter(c => {
                  const e = c.querySelector('[data-part="card/overview"]');
                  return e && e.getBoundingClientRect().bottom >
                              c.getBoundingClientRect().bottom + 1;}).length,
                invented: cards.filter(c => {
                  const e = c.querySelector('[data-part="card/overview"]');
                  return e && !SYNOPSIS[(c.querySelector('[data-part="card/title"]')||{}).textContent];
                }).map(c => (c.querySelector('[data-part="card/title"]')||{}).textContent)};}""")
            check(f"{name}: the rows carry the synopsis",
                  seen["n"] > 4 and seen["withPlot"] == seen["n"], f"{seen['withPlot']}/{seen['n']}")
            check(f"{name}: an over-long synopsis is clamped, not spilled",
                  seen["clamped"] > 0 and seen["overflowing"] == 0,
                  f"{seen['clamped']} clamped, {seen['overflowing']} spilling")
            check(f"{name}: no invented synopsis",
                  not seen["invented"], str(seen["invented"][:3]))

        # The clamp uses the room the card HAS, and the number is not a taste:
        # it is the largest that keeps every card at its floor. Checked both
        # ways — this many fits, one more does not — so raising or lowering it
        # without re-measuring fails here. Two was inherited from a card that had
        # no floor, and left a third of the row empty.
        async def cards_that_grow(n):
            """Returns how many library cards exceed the floor at n clamped lines."""
            await pg.evaluate("""(n)=>{
              let st = document.querySelector('#clamptrial');
              if (!st) { st = document.createElement('style'); st.id = 'clamptrial';
                         document.head.appendChild(st); }
              st.textContent = '.cov{-webkit-line-clamp:' + n + ' !important}';}""", n)
            await pg.evaluate("()=>{window.__store.write({page: 'lib',"
                              " libLens: 'cat', libMode: 'list'}); render();}")
            await pg.wait_for_timeout(520)
            return await pg.evaluate(
                """()=>[...document.querySelectorAll('#libitems [data-part="card"]')]
                     .filter(c => c.getBoundingClientRect().height > 127).length""")

        lines = await pg.evaluate(
            """()=>Number(getComputedStyle(document.querySelector('#libitems [data-part="card/overview"]'))
                 .webkitLineClamp)""")
        check("the synopsis takes more than two lines", lines > 2, str(lines))
        check("and no card grows for it",
              (await cards_that_grow(lines)) == 0, f"at {lines} lines")
        check("one more line would not fit",
              (await cards_that_grow(lines + 1)) > 0, f"at {lines + 1} lines")
        await pg.evaluate("""()=>{const st = document.querySelector('#clamptrial');
                               if (st) st.remove();}""")
        await pg.evaluate("()=>{window.__store.write({page: 'lib',"
                          " libLens: 'cat', libMode: 'list'}); render();}")
        await pg.wait_for_timeout(520)

        # A clamped line must SAY it is clamped rather than stop mid-word.
        dots = await pg.evaluate(
            """()=>getComputedStyle(document.querySelector('#libitems [data-part="card/overview"]')).textOverflow""")
        check("and the cut shows — an ellipsis",
              dots == "ellipsis", dots)

        # A medium whose NFO carries no plot shows nothing rather than a filler.
        # Reading only the rows on screen proves nothing — the first two dozen
        # all have a plot — so the row is BUILT for a title known to lack one.
        missing = await pg.evaluate(
            "()=>LIBRARY.filter(x => !(x.t in SYNOPSIS)).map(x => x.t)")
        check("a medium without a synopsis exists in the library",
              len(missing) > 0, f"{len(missing)} without a plot: {missing[:3]}")
        if missing:
            empty = await pg.evaluate("""(t)=>{
              const item = LIBRARY.find(x => x.t === t);
              const d = document.createElement('div');
              d.innerHTML = libRowHTML(item, 0);
              const cov = d.querySelector('[data-part="card/overview"]');
              return cov ? cov.textContent : null;}""", missing[0])
            check("and its row shows no filler text",
                  empty is None, str(empty))

        # ── the list starts at the same height on all three lenses ─────────
        # Each put its context line somewhere else — outside the body, inside
        # it, inside a section of its own — so switching tabs made the page
        # jump. Checked in both modes, because a grid and a list are two
        # different first elements and only one of them was ever looked at.
        for mode in ("list", "grid"):
            starts = {}
            for lens in ("cat", "rec", "inc"):
                await pg.evaluate("([l, m])=>{window.__store.write({page: 'lib',"
                                  " libLens: l, libMode: m}); render();}", [lens, mode])
                await pg.wait_for_timeout(620)
                starts[lens] = await pg.evaluate("""()=>{
                  const frame = document.querySelector('#device').getBoundingClientRect();
                  const p = document.querySelector('#view [data-part="card"], #view .tile');
                  return p ? Math.round(p.getBoundingClientRect().top - frame.top) : null;}""")
            without_list = [k for k, v in starts.items() if v is None]
            gap = (max(starts.values()) - min(starts.values())) if not without_list else None
            check(f"in {mode}, every lens draws a list", not without_list,
                  str(without_list))
            if not without_list:
                check(f"and in {mode} the list starts at the same height",
                      gap <= 1, f"{starts} — gap {gap}px")

        # ── the lenses, in the order one reaches for them ───────────────────
        tabs = await pg.evaluate(
            """()=>[...document.querySelectorAll('[data-lens]')]
                 .map(e => e.dataset.lens)""")
        check("the lenses go from everything to the repair list",
              tabs == ["cat", "rec", "inc"], str(tabs))

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
