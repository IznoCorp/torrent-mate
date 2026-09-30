"""R63 — a card says what the engine knows, and two tabs say it the same way.

A followed medium's card was three short lines beside a poster and the rest of
it was empty — while every fact it was missing already sat in the acquisition data, and
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

RE-AIMED when the library, the maintenance actions and the account took the
contract's names: a library row's title is read as `title`, where they were the
engine's short keys. The holds and what they compare are unchanged.
"""
import asyncio
import json
import pathlib
import re

from common import Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
# The versioned data set the mock layer serves — never the operator's live
# `acquire.db`: a gate judges the code that changes, not data that moves on its
# own (a daemon incremented one show's count from 10 to 11 and turned a suite
# red with no code change). `scripts/refresh-maquette-fixture.py --apply`
# refreshes this file from the database when the data is worth refreshing.
FOLLOWS_SEED = ROOT / "design" / "src" / "mocks" / "seeds" / "follows.json"

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


def seeded_facts():
    """Returns, per followed title, the numbers the versioned data set holds.

    Returns:
        A dict title → {searches, series}.
    """
    held = json.loads(FOLLOWS_SEED.read_text(encoding="utf-8"))
    return {entry["title"]: {"searches": entry.get("searches", 0),
                             "series": entry.get("showStatus")}
            for entry in held}


async def main():
    global _journal
    _journal = Journal("R63 — what a card says")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
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

        # Compared against the DATA SET the mock layer serves, not against
        # itself: a card printing a number the data never held would pass.
        seeded = seeded_facts()
        wrong = []
        for s in follows:
            r = seeded.get(s["title"])
            if not r:
                continue
            # Word-boundary match, not substring: « 1 recherche » must not
            # pass against a card actually printing « 11 recherches ».
            if not re.search(rf"\b{r['searches']}\s+recherche", s["facts"]):
                wrong.append(f"{s['title']} : « {s['facts']} » vs {r['searches']}")
        check("every follow card prints the search count of the data set",
              not wrong, str(wrong[:3]))

        # The cron the follows tab was given, read while the tab is still the one
        # drawn — the acquisition status in the query cache. It was the dying
        # engine's `CADENCE_CRON` literal until that left it, and was re-aimed at
        # the answer the tab draws from. The next state resets the cache.
        cron = await pg.evaluate(
            "()=>window.__queries.getQueryData(['/api/acquisition/status'])?.cadence ?? null")

        # ── a fruitless search is said on the follow, and only there ────────
        # INVERTED, SAID OUT LOUD: « En cours » had the sentence and « Suivis »
        # had to phrase it the same way. « Cherché, rien trouvé » left « En
        # cours », which holds « En vol » alone: what was not found reads on the
        # follow. The hold whose subject died now reads its absence.
        await pg.evaluate("()=>window.__go('acq-now-loaded')")
        await pg.wait_for_timeout(420)
        running = await pg.evaluate("""()=>[...document.querySelectorAll('#view [data-part="card/reason"]')]
          .map(e => e.textContent)""")
        phrase = "Aucune release conforme"
        check("« En cours » no longer explains a fruitless search",
              not any(phrase in r for r in running), str(running[:1]))
        check("« Suivis » explains it",
              any(phrase in s["reason"] for s in follows),
              str([s["reason"] for s in follows][:1]))

        # The hour is derived from the cron the cadence line prints, so the two
        # can never disagree about when the next search happens. The cron is
        # the one the follows tab was given, read above.
        hour = await pg.evaluate("(cron)=>nextSearchFR(cron, new Date())", cron)
        cadence = await pg.evaluate("(cron)=>cadenceFR(cron)", cron)
        check("the hour announced is the cadence's own",
              bool(hour) and hour in cadence, f"{hour} in « {cadence} »")
        check("and the cards announce it",
              any(hour in s["reason"] for s in follows if s["reason"]),
              hour or "no hour")

        # ── the library says what a medium is ABOUT ─────────────────────────
        for lens, name in (("cat", "Médias"), ("rec", "Récents")):
            await pg.evaluate("(l)=>{window.__store.write({page: 'lib',"
                              " libLens: l, libMode: 'list'}); window.__store.touch();}", lens)
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
                  /* THE SYNOPSIS IS A FIELD OF A ROW SINCE L09 — `SYNOPSIS` was a global
                     map keyed by title, and the library row carries its own `overview`. */
                  const title=(c.querySelector('[data-part="card/title"]')||{}).textContent;
                  return e && !((window.__queries.getQueryCache().getAll().filter(q=>q.queryKey[0]==='/api/library/items').sort((l,r)=>r.state.dataUpdatedAt-l.state.dataUpdatedAt)[0]?.state.data?.pages||[]).flatMap(p=>p.items).find(r=>r.title===title)||{}).overview;
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
              st.textContent = '[data-part="card/overview"]{-webkit-line-clamp:'
                               + n + ' !important}';}""", n)
            await pg.evaluate("()=>{window.__store.write({page: 'lib',"
                              " libLens: 'cat', libMode: 'list'}); window.__store.touch();}")
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
                          " libLens: 'cat', libMode: 'list'}); window.__store.touch();}")
        await pg.wait_for_timeout(520)

        # A clamped line must SAY it is clamped rather than stop mid-word.
        dots = await pg.evaluate(
            """()=>getComputedStyle(document.querySelector('#libitems [data-part="card/overview"]')).textOverflow""")
        check("and the cut shows — an ellipsis",
              dots == "ellipsis", dots)

        # A medium whose NFO carries no plot shows nothing rather than a filler.
        # Reading only the rows on screen proves nothing — the first two dozen
        # all have a plot — so the LAYER is walked page by page for a title
        # known to lack one. The engine held the whole library in memory and
        # this read it there; a cache holds the pages that were asked for, and
        # « none of the 24 loaded rows lacks a plot » is not the same statement.
        missing = await pg.evaluate("""async ()=>{
          const found = [];
          for (let page = 0; page < 40; page += 1) {
            const answer = await (await window.fetch(
              `/api/library/items?page=${page}`)).json();
            if (!answer.items.length) break;
            for (const row of answer.items) if (!row.overview) found.push(row.title);
          }
          return found;}""")
        check("a medium without a synopsis exists in the library",
              len(missing) > 0, f"{len(missing)} without a plot: {missing[:3]}")
        if missing:
            # AND THE ROW IS THE ONE THE SURFACE DRAWS. This used to call the
            # engine's `libRowHTML` on a detached node — a markup producer
            # answering about itself. The title is searched for instead, so
            # what is read is the row the operator would be looking at.
            await pg.evaluate("""(title)=>{
              const field = document.querySelector('#libq');
              const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
              setter.call(field, title);
              field.dispatchEvent(new Event('input', {bubbles:true}));}""", missing[0])
            await pg.wait_for_timeout(700)
            drawn = await pg.evaluate("""(title)=>{
              const rows = [...document.querySelectorAll('#libitems [data-part="card"]')];
              const row = rows.find(x => x.textContent.includes(title));
              if (!row) return {found: false};
              const overview = row.querySelector('[data-part="card/overview"]');
              return {found: true, filler: overview ? overview.textContent : null};}""",
              missing[0])
            check("and its row shows no filler text",
                  drawn["found"] and not drawn["filler"], str(drawn))
            await pg.evaluate("""()=>{
              const field = document.querySelector('#libq');
              const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
              setter.call(field, "");
              field.dispatchEvent(new Event('input', {bubbles:true}));}""")
            await pg.wait_for_timeout(500)

        # ── the list starts at the same height on all three lenses ─────────
        # Each put its context line somewhere else — outside the body, inside
        # it, inside a section of its own — so switching tabs made the page
        # jump. Checked in both modes, because a grid and a list are two
        # different first elements and only one of them was ever looked at.
        for mode in ("list", "grid"):
            starts = {}
            for lens in ("cat", "rec", "inc"):
                await pg.evaluate("([l, m])=>{window.__store.write({page: 'lib',"
                                  " libLens: l, libMode: m}); window.__store.touch();}", [lens, mode])
                await pg.wait_for_timeout(620)
                starts[lens] = await pg.evaluate("""()=>{
                  const frame = document.querySelector('#device').getBoundingClientRect();
                  const p = document.querySelector('#view [data-part="card"], #view [data-part="tile"]');
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


if __name__ == "__main__":
    asyncio.run(main())
