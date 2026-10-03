"""R523 — the library speaks provider ids and facts (K2-G1, G2, G5, G6; operator rulings Q5 A and O-5 B).

The operator, 2026-10-01 (Q5 A): provider ids ARE the identity. 2026-10-03 (O-5 B): deleting a
medium whose id names two rows or folders is refused until the duplicate is settled. 2026-10-03:
« aucun média de la médiathèque ne devrait exister sans au moins 1 identifiant » — every library
entry carries one, and the interface keeps no branch for an entry without.

1. MEMBERSHIP BY ID: the layer answers by `provider` + `providerId`; the seed's duplicate
   (« Doctor Who », two rows under one TVDB id) answers two rows; a film answers its kind; an
   unknown id is not held; a question by title alone is refused.
2. DELETION BY ID: an unknown id is refused 404 `media.not_found`, the duplicate 409
   `media.ambiguous`, any id while the pipeline holds its lock 409 `library.locked`, a body by
   title 400 — and a refusal deletes nothing.
3. THE AMBIGUOUS STATE (`lib-delete-ambiguous`): the dialog names the duplicate in its own words
   and offers nothing but to close.
4. THE LOCKED STATE (`lib-delete-locked`): the confirmed removal comes back, and the toast says
   the code's words from `fr.json`.
5. LEAVES GROUPED BY THE INTERFACE: the wire carries engine leaves with their counts and no
   label; the filter panel names each lens in `fr.json`'s words, counts « Animation » as the sum
   of its two leaves, and the listing under that lens asks for the two leaves.
6. LINES FROM FACTS: no library row on the wire carries a pre-formatted line; a tile's line is
   composed from its year and kind.
7. EVERY ENTRY IDENTIFIED: every seeded library row, recent row and incomplete show carries at
   least one provider id, and so does every row the listing serves; a row the seed once held
   without one (« Famille Pirate ») offers its removal and its tick like any other.
8. AN ACT NAMES ITS ROW'S MEDIUM (`lib-same-title`): « RoboCop » 1987 and 2014 are two films
   under two TMDB ids; the 2014 row's swipe, and a selection ticking it alone, delete TMDB 97020
   and nothing else — a title resolved to the first medium it names deleted the 1987 one. A film
   that carries a TVDB id too is deleted by its TMDB id.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
LIBRARY = json.loads((SEEDS / "library-items.json").read_text(encoding="utf-8"))
LEAVES = json.loads((SEEDS / "library-categories.json").read_text(encoding="utf-8"))

DUPLICATE = {"provider": "tvdb", "providerId": "78804"}
# A film the seed holds once, under its TMDB id.
FILM = next(row for row in LIBRARY if row["title"] == "Ninja Turtles")
FILM_REF = {"provider": "tmdb", "providerId": str(FILM["ids"]["tmdb"])}
UNKNOWN = {"provider": "tmdb", "providerId": "999999999"}
# A row the seed once held with no id, now identified (TVDB 143721): no branch sets it apart.
ONCE_UNIDENTIFIED = "Famille Pirate"
LIBRARY_SEEDS = ("library-items.json", "recent.json", "incomplete-shows.json")
ANIMATION_LEAVES = ("movies_animation", "tv_shows_animation")

ASK = """async ([method, path, body]) => {
  const answer = await fetch(path, body === null ? { method } : { method, body: JSON.stringify(body) });
  return { status: answer.status, body: await answer.json().catch(() => null) };
}"""

MEMBERSHIP = "/api/v1/library/membership?provider={provider}&providerId={providerId}"

# TWO FILMS, ONE TITLE (`lib-same-title`): « RoboCop » 1987 and 2014, each under its own TMDB id.
SAME_TITLE = "RoboCop"
PAIR = {1987: "5548", 2014: "97020"}
# A film the seed names at TMDB and TVDB both: its identity is TMDB's.
BOTH_IDS = next(row for row in LIBRARY if row["kind"] == "movie" and {"tmdb", "tvdb"} <= set(row["ids"]))

# WHAT DELETE IS SENT, read off the wire: `send` calls `globalThis.fetch` at call time.
RECORD_DELETES = """() => {
  window.__deleted = [];
  const fetchOnce = window.__fetchBeforeRecord ?? window.fetch;
  window.__fetchBeforeRecord = fetchOnce;
  window.fetch = (path, init) => {
    if (init?.method === 'DELETE' && String(path).includes('/library/items'))
      window.__deleted.push(JSON.parse(init.body));
    return fetchOnce(path, init);
  };
}"""

# TAPS the element carrying an attribute whose row is the titled one drawn with a given line.
TAP_ROW_OF = """([selector, title, line]) => {
  const one = [...document.querySelectorAll(selector)].find((element) => {
    const named = element.dataset.del ?? element.dataset.selectedTitle;
    let row = element;
    while (row && !(row.textContent ?? '').includes(line)) row = row.parentElement;
    return named === title && row !== null && row !== document.body
      && Number(row.matches(selector)) + row.querySelectorAll(selector).length === 1;
  });
  if (!one) return false;
  one.click();
  return true;
}"""


async def main():
    journal = Journal("R523 — the library speaks provider ids and facts")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def ask(method, path, body=None):
            return await page.evaluate(ASK, [method, path, body])

        async def say(key, **params):
            return await page.evaluate("([k, p])=>window.__i18n.t(k, p)", [key, params])

        await page.evaluate("()=>window.__mocks.reset()")

        # ── 1. membership by id ─────────────────────────────────────────────
        twice = await ask("GET", MEMBERSHIP.format(**DUPLICATE))
        journal.check("the duplicate's id answers held, by two rows",
                      twice["status"] == 200 and twice["body"]["inLibrary"] and twice["body"]["rows"] == 2,
                      str(twice))
        film = await ask("GET", MEMBERSHIP.format(**FILM_REF))
        journal.check(f"« {FILM['title']} » answers one row of a film",
                      film["status"] == 200 and film["body"]["rows"] == 1 and film["body"]["kind"] == "movie",
                      str(film))
        nobody = await ask("GET", MEMBERSHIP.format(**UNKNOWN))
        journal.check("an id no row holds is not held",
                      nobody["status"] == 200 and not nobody["body"]["inLibrary"] and nobody["body"]["rows"] == 0,
                      str(nobody))
        by_title = await ask("GET", "/api/v1/library/membership?title=Doctor%20Who")
        journal.check("a question by title alone is refused", by_title["status"] == 400, str(by_title))

        # ── 2. deletion by id ───────────────────────────────────────────────
        path = "/api/v1/library/items"
        unknown = await ask("DELETE", path, {"media": [UNKNOWN]})
        journal.check("an unknown id is refused 404 media.not_found",
                      unknown["status"] == 404 and (unknown["body"] or {}).get("code") == "media.not_found",
                      str(unknown))
        ambiguous = await ask("DELETE", path, {"media": [FILM_REF, DUPLICATE]})
        journal.check("the duplicate is refused 409 media.ambiguous, naming it",
                      ambiguous["status"] == 409
                      and (ambiguous["body"] or {}).get("code") == "media.ambiguous"
                      and (ambiguous["body"] or {}).get("params") == DUPLICATE,
                      str(ambiguous))
        still = await ask("GET", MEMBERSHIP.format(**FILM_REF))
        journal.check("and a refusal deleted nothing, not even the medium beside it",
                      still["body"]["rows"] == 1, str(still))
        titled = await ask("DELETE", path, {"titles": [FILM["title"]]})
        journal.check("a body naming titles is refused 400", titled["status"] == 400, str(titled))
        await page.evaluate("()=>window.__mocks.setPipelineState('running')")
        locked = await ask("DELETE", path, {"media": [FILM_REF]})
        journal.check("while the pipeline holds its lock, 409 library.locked",
                      locked["status"] == 409 and (locked["body"] or {}).get("code") == "library.locked",
                      str(locked))
        await page.evaluate("()=>window.__mocks.reset()")
        gone = await ask("DELETE", path, {"media": [FILM_REF]})
        after = await ask("GET", MEMBERSHIP.format(**FILM_REF))
        journal.check("and an identified medium held once is deleted",
                      gone["status"] == 200 and gone["body"]["deleted"] == 1 and not after["body"]["inLibrary"],
                      f"{gone} · {after}")

        # ── 3. the ambiguous state ──────────────────────────────────────────
        await page.evaluate("(id)=>window.__go(id)", "lib-delete-ambiguous")
        await page.wait_for_timeout(ACTED)
        drawn = await page.evaluate("""() => {
          const dialog = document.querySelector('#dlg[data-open]');
          return dialog ? {
            text: dialog.textContent,
            buttons: [...dialog.querySelectorAll('[data-part="dialog/button"]')].map((b) => b.textContent.trim()) } : null; }""")
        heading = await say("verbs.library.delete.blockedHeadingOne", title="Doctor Who")
        rows = await say("verbs.library.delete.heldByRows", count=2)
        close = await say("verbs.library.delete.close")
        journal.check("the duplicate's dialog names it and its two rows",
                      drawn is not None and heading in drawn["text"] and rows in drawn["text"], str(drawn))
        journal.check("and offers nothing but to close",
                      drawn is not None and drawn["buttons"] == [close], str(drawn))

        # ── 4. the locked state ─────────────────────────────────────────────
        await page.evaluate("(id)=>window.__go(id)", "lib-delete-locked")
        await page.wait_for_timeout(ACTED + SETTLED)
        toast = await page.evaluate("()=>document.querySelector('#toastmsg')?.textContent || ''")
        words = await say("refusals.library.locked")
        journal.check("the lock's refusal is said in fr.json's words", toast == words, f"{toast!r} vs {words!r}")
        held = await page.evaluate("""async () => {
          const answer = await fetch('/api/v1/library/membership?provider=tvdb&providerId=72879');
          return (await answer.json()).inLibrary; }""")
        journal.check("and « Les Animaniacs » is still held", held is True, str(held))

        # ── 5. leaves grouped by the interface ──────────────────────────────
        await page.evaluate("()=>window.__mocks.reset()")
        served = await ask("GET", "/api/v1/library/categories")
        journal.check("the wire carries engine leaves with their counts, and no label",
                      served["status"] == 200
                      and all(set(leaf) == {"id", "count"} for leaf in served["body"])
                      and {leaf["id"] for leaf in served["body"]} >= set(ANIMATION_LEAVES),
                      str(served["body"])[:300])
        await page.evaluate("(id)=>window.__go(id)", "lib-grid")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("()=>window.__panel.produce('library-filter')")
        await page.wait_for_timeout(ACTED)
        offered = await page.evaluate("()=>document.querySelector('#sheet')?.textContent || ''")
        animation = await say("screens.library.lenses.anim")
        summed = sum(leaf["count"] for leaf in LEAVES if leaf["id"] in ANIMATION_LEAVES)
        count = await say("screens.library.filterCount", count=summed)
        journal.check("the filter panel names « Animation » in fr.json's words, counted from its two leaves",
                      f"{animation}{count}" in offered.replace("\n", ""), offered[:400])
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("(id)=>window.__go(id)", "lib-grid")
        await page.evaluate("()=>{ window.__store.write({ libCat: 'anim' }); }")
        await page.wait_for_timeout(ACTED)
        # WHAT THE LISTING DRAWS under the lens: rows of its two leaves, and of both.
        drawn_titles = await page.evaluate("""() => [...document.querySelectorAll('[data-part="tile/title"]')]
          .map((one) => one.textContent)""")
        category_of = {row["title"]: row["category"] for row in LIBRARY}
        drawn_leaves = {category_of.get(title) for title in drawn_titles}
        journal.check("the listing under « Animation » draws its two leaves, and nothing else",
                      bool(drawn_titles) and drawn_leaves == set(ANIMATION_LEAVES),
                      f"{sorted(map(str, drawn_leaves))} over {len(drawn_titles)} tiles")

        # ── 6. lines from facts ─────────────────────────────────────────────
        page_one = await ask("GET", "/api/v1/library/items")
        recent = await ask("GET", "/api/v1/library/recent")
        lines = [row for row in page_one["body"]["items"] + recent["body"] if "secondaryLine" in row]
        journal.check("no library row on the wire carries a pre-formatted line",
                      not lines and all("year" in row and "kind" in row for row in page_one["body"]["items"]),
                      str(lines[:2]))
        await page.evaluate("(id)=>window.__go(id)", "lib-grid")
        await page.wait_for_timeout(SETTLED)
        first = page_one["body"]["items"][0]
        kind = await say("common.film" if first["kind"] == "movie" else "common.series")
        wanted = await say("screens.library.rowLine", year=first["year"], kind=kind)
        tile = await page.evaluate("""(title) => [...document.querySelectorAll('[data-part="tile"]')]
          .find((one) => one.querySelector('[data-part="tile/title"]')?.textContent === title)
          ?.querySelector('[data-part="tile/subtitle"]')?.textContent ?? null""", first["title"])
        journal.check(f"« {first['title']} »'s line is composed from its year and kind", tile == wanted,
                      f"{tile!r} vs {wanted!r}")
        await page.evaluate("(id)=>window.__go(id)", "lib-list")
        await page.wait_for_timeout(SETTLED)
        unnamed = await page.evaluate("""async (title) => {
          window.__store.write({ q: title });
          await new Promise((done) => setTimeout(done, 900));
          const all = [...document.querySelectorAll('[data-del]')].map((one) => one.dataset.del);
          window.__store.write({ selMode: true });
          await new Promise((done) => setTimeout(done, 600));
          const ticks = [...document.querySelectorAll('[data-selected-title]')].map((one) => one.dataset.selectedTitle);
          return { removals: all, ticks }; }""", ONCE_UNIDENTIFIED)
        journal.check(f"« {ONCE_UNIDENTIFIED} » offers its removal and its tick like any other row",
                      ONCE_UNIDENTIFIED in unnamed["removals"] and ONCE_UNIDENTIFIED in unnamed["ticks"],
                      str(unnamed))

        # 7. Every entry identified.
        unnamed_seeds = [f"{name}: {row['title']}" for name in LIBRARY_SEEDS
                         for row in json.loads((SEEDS / name).read_text(encoding="utf-8"))
                         if not any((row.get("ids") or {}).values())]
        journal.check("every seeded library row, recent row and incomplete show carries a provider id",
                      not unnamed_seeds, str(unnamed_seeds[:5]))
        served_rows = []
        for index in range(len(LIBRARY)):
            served = await ask("GET", f"/api/v1/library/items?page={index}")
            items = served["body"]["items"] if served["body"] else []
            if not items:
                break
            served_rows.extend(items)
        unnamed_rows = [row["title"] for row in served_rows if not any((row.get("ids") or {}).values())]
        journal.check("every row the listing serves carries a provider id",
                      len(served_rows) == len(LIBRARY) and not unnamed_rows, f"{len(served_rows)} rows, unnamed {unnamed_rows[:5]}")

        # ── 8. an act names its row's medium, never its title's ────────────
        seeded = sorted(str(row["ids"]["tmdb"]) for row in LIBRARY if row["title"] == SAME_TITLE)
        journal.check(f"the seed holds two films titled « {SAME_TITLE} » under two TMDB ids",
                      seeded == sorted(PAIR.values()), str(seeded))
        film_kind = await say("common.film")

        async def removal_of():
            """Confirms the removal the dialog offers and returns the bodies DELETE was sent."""
            await page.wait_for_timeout(ACTED)
            await page.evaluate("()=>document.querySelector('#dlg[data-open] [data-part=\"dialog/button\"]')?.click()")
            await page.wait_for_timeout(ACTED + SETTLED)
            return await page.evaluate("()=>window.__deleted")

        async def held(provider_id):
            answer = await ask("GET", MEMBERSHIP.format(provider="tmdb", providerId=provider_id))
            return answer["body"]["inLibrary"]

        # The swipe of the 2014 row.
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("(id)=>window.__go(id)", "lib-same-title")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(RECORD_DELETES)
        line = await say("screens.library.rowLine", year=2014, kind=film_kind)
        swiped = await page.evaluate(TAP_ROW_OF, ["[data-del]", SAME_TITLE, line])
        sent = await removal_of()
        journal.check(f"the swipe of « {SAME_TITLE} » 2014 deletes TMDB {PAIR[2014]}, and only it",
                      swiped and sent == [{"media": [{"provider": "tmdb", "providerId": PAIR[2014]}]}]
                      and not await held(PAIR[2014]) and await held(PAIR[1987]),
                      f"tapped {swiped}, sent {sent}")

        # A selection ticking the 2014 row alone.
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("(id)=>window.__go(id)", "lib-same-title")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("()=>{ window.__store.write({ selMode: true }); }")
        await page.wait_for_timeout(ACTED)
        await page.evaluate(RECORD_DELETES)
        ticked = await page.evaluate(TAP_ROW_OF, ["[data-selected-title]", SAME_TITLE, line])
        await page.wait_for_timeout(ACTED)
        pressed = await page.evaluate("""(title) => [...document.querySelectorAll('[data-selected-title]')]
          .filter((one) => one.dataset.selectedTitle === title).map((one) => one.getAttribute('aria-pressed'))""",
                                      SAME_TITLE)
        journal.check(f"ticking « {SAME_TITLE} » 2014 presses its row, not the 1987 one",
                      ticked and sorted(pressed) == ["false", "true"], f"tapped {ticked}, pressed {pressed}")
        await page.evaluate("()=>document.querySelector('[data-delsel]')?.click()")
        sent = await removal_of()
        journal.check(f"and the selection deletes TMDB {PAIR[2014]}, and only it",
                      sent == [{"media": [{"provider": "tmdb", "providerId": PAIR[2014]}]}]
                      and not await held(PAIR[2014]) and await held(PAIR[1987]),
                      f"sent {sent}")

        # A film carrying a TVDB id too is named TMDB-first.
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("(id)=>window.__go(id)", "lib-list")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("(q)=>window.__store.write({ q })", BOTH_IDS["title"])
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(RECORD_DELETES)
        film_line = await say("screens.library.rowLine", year=BOTH_IDS["year"], kind=film_kind)
        swiped = await page.evaluate(TAP_ROW_OF, ["[data-del]", BOTH_IDS["title"], film_line])
        sent = await removal_of()
        journal.check(f"« {BOTH_IDS['title']} », a film with a TVDB id too, is deleted as TMDB {BOTH_IDS['ids']['tmdb']}",
                      swiped and sent == [{"media": [{"provider": "tmdb", "providerId": str(BOTH_IDS["ids"]["tmdb"])}]}],
                      f"tapped {swiped}, sent {sent}")

        journal.check("no error was raised", not errors, " · ".join(errors[:3]))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
