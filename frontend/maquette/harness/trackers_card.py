"""R-L16bis-d, -e, -f — a torrent is a media card: its name whole, its facts, its taps, its swipe.

The operator, 2026-09-29 (16:4x, points 4 and 5): the torrent card says the full
file name, its size, its state, its down / up, its popularity and its date added,
and takes the media card's style and gestures — the poster to the medium's sheet,
the rest to a bottom panel, a swipe. His Q1: the volumes by default, a bar and the
download rate while downloading, the upload rate alone while uploading.

R-L16bis-d — the card says it all, whole:
1. every card of `torrents-list` reads its entry's `name` WHOLE as its title, then
   its state in the state's own word, its size, its ratio;
2. `torrent-card-long-name` — the 132-character name — is whole and never clipped
   nor ellipsised, at 369 and at 390 px;
3. an absent figure is said: `torrents-list` (the client's figures never read)
   says the volumes, the sources and the date unknown; `torrent-card-no-popularity`
   says « Sources inconnues », never a « 0 »;
4. the three transfer states: `torrent-card-volumes` the volumes and no bar,
   `torrent-card-downloading-progress` the bar at the entry's progress and the
   download rate, `torrent-card-uploading-rate` the upload rate alone, no bar;
   `torrent-card-volumes` also says the sources and the date from their fields.

R-L16bis-e — the card's taps:
5. a linked card's poster names its medium's sheet; a finger on it opens that sheet,
   and Retour lands back on « Torrents »;
6. `torrent-card-film` — a film's poster opens the FILM's sheet;
7. `torrent-card-unlinked` wears no poster: the folder, addressing the entry's panel;
8. a finger on a card's body opens the torrent's panel — never the sheet — and its
   facts equal the entry's fields (`torrent-panel-episode`: the medium fact names
   the series and its SxxEyy);
9. `torrent-panel-unlinked` offers « Identifier » on the entry's folder;
   `torrent-panel-unlinked-no-folder` says there is no folder to identify;
   `torrent-panel-partial` says every figure unknown.

R-L16bis-f — the swipe removes only through its confirmation:
10. a finger's swipe to the left uncovers « Retirer » and no left drawer (no
    cross-seed side before its verb exists);
11. a tap on it opens L16's confirmation and nothing is removed before
    « Confirmer »; « Annuler » removes nothing;
12. `torrent-swipe-remove` rests with the right drawer open.

RE-AIMED OUT LOUD — the successor of `trackers_page.py`, `trackers_removal.py`,
`trackers_roster.py`, `follow_offered.py` and `paths_to_sheets.py` reads of the old
row: its title was a text button to the sheet (`torrents/title`), now the poster
and `card/title`; its « Retirer de qBittorrent » a text button on the row, now the
panel's action, the swipe's drawer a second door.

Red before the move: no named state of the card exists, and the row carries no
`card/title`, no poster, no panel, no drawer.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
DOWNLOADS = json.loads((SOURCE / "mocks/seeds/downloads.json").read_text(encoding="utf-8"))
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["torrents"]
PANEL_WORDS = WORDS.get("panel", {})
LONG_NAME = ("Stuart.Fails.to.Save.the.Universe.S01E07.Spoiler.Dexys.Midnight.Runners.Get.a.Royalty.Payment"
             ".MULTi.1080p.WEB.SDR.EAC3.5.1.x265-BYOR")
PRESIDENT = DOWNLOADS[0]
FILM_TITLE = "On l'appelait Robin des Bois"
FILM_TMDB = "1284465"
# The two narrow widths the name is read at: the operator's phone and order 60's.
WIDTHS = (369, 390)

CARDS = """() => [...document.querySelectorAll('#view [data-part="torrents/row"]')].map(row => {
  const text = (part) => row.querySelector(`[data-part="${part}"]`)?.textContent.trim() ?? null;
  const title = row.querySelector('[data-part="card/title"]');
  const bar = row.querySelector('[data-part="card/progress"]');
  return {
    entry: row.dataset.entry, tracker: row.dataset.tracker,
    title: title?.textContent ?? null,
    clipped: title ? title.scrollWidth > title.clientWidth + 1 || getComputedStyle(title).textOverflow === 'ellipsis'
      || title.getBoundingClientRect().right > row.getBoundingClientRect().right + 1 : null,
    state: row.querySelector('[data-part="card/meta"] [data-part="chip"]')?.textContent.trim() ?? null,
    size: text("torrents/size"), ratio: text("torrents/ratio"),
    transfer: text("torrents/transfer"),
    mode: row.querySelector('[data-part="torrents/transfer"]')?.dataset.transfer ?? null,
    sources: text("torrents/sources"), added: text("torrents/added"),
    bar: bar ? Number(bar.value) : null,
    poster: row.querySelector('[data-part="card/poster"]')?.dataset.mediasheet ?? null,
    folder: row.querySelector('[data-part="card/folder"]')?.dataset.panel ?? null,
    body: row.querySelector('[data-part="card/body"]')?.dataset.panel ?? null,
    sides: [...row.querySelectorAll('[data-part="swipe/side"]')].map(side => side.dataset.side),
  };
})"""
PANEL = """() => {
  const sheet = document.querySelector('#sheet');
  if (!sheet || !sheet.hasAttribute('data-open')) return null;
  return {
    title: sheet.querySelector('[data-part="sheet/title"]')?.textContent.trim() ?? null,
    facts: Object.fromEntries([...sheet.querySelectorAll('[data-part="key-value"]')]
      .map(row => [...row.children].map(cell => cell.textContent.trim()))),
    actions: [...sheet.querySelectorAll('[data-part="sheet/action"]')].map(action => ({
      text: action.textContent.trim(), resolution: action.getAttribute('data-resolution')})),
    text: sheet.textContent,
  };
}"""
DIALOG = """() => document.querySelector('[data-part="dialog"][data-open]')?.textContent ?? null"""
PRESS = """(danger) => {
  const buttons = [...document.querySelectorAll('[data-part="dialog"][data-open] [data-part="dialog/button"]')];
  const button = buttons.find(one => (one.dataset.tone === 'danger') === danger);
  if (!button) return false; button.click(); return true;
}"""
REMOVED = """() => (window.__mocks?.answered() || []).filter(call => call.operationId === 'removeDownload').length"""
OPEN_ROW = """() => { const card = document.querySelector('#view [data-part="torrents/row"] [data-part="card"]');
  return card ? new DOMMatrix(getComputedStyle(card).transform).m41 : null; }"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def one_card(page, state):
    """Drives a card's named state and reads its only card; None when it draws none."""
    answer = await enter(page, state)
    cards = await page.evaluate(CARDS)
    return answer, (cards[0] if len(cards) == 1 else None)


async def swipe_left(page, selector):
    """Drags a card to the left with a mouse, the way a desktop finger does."""
    target = page.locator(selector)
    box = await target.first.bounding_box() if await target.count() else None
    if box is None:
        return
    y = box["y"] + box["height"] / 2
    await page.mouse.move(box["x"] + box["width"] - 20, y)
    await page.mouse.down()
    for step in range(1, 13):
        await page.mouse.move(box["x"] + box["width"] - 20 - 14 * step, y)
    await page.mouse.up()
    await page.wait_for_timeout(ACTED)


async def main():
    journal = Journal("R-L16bis-d/e/f — a torrent is a media card: its name whole, its facts, its taps, its swipe")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── d: the list — every name whole, then state, size, ratio ─────────
        await enter(page, "torrents-list")
        cards = await page.evaluate(CARDS)
        by_key = {f"{card['entry']}:{card['tracker']}": card for card in cards}
        wrong = [entry["name"] for entry in DOWNLOADS
                 if (by_key.get(f"{entry['infoHash']}:{entry['tracker']}") or {}).get("title") != entry["name"]]
        journal.check(f"every card of torrents-list reads its entry's name whole ({len(cards)} of {len(DOWNLOADS)})",
                      len(cards) == len(DOWNLOADS) and not wrong, str(wrong[:2]))
        misread = [card["entry"] for card, entry in (
            (by_key.get(f"{entry['infoHash']}:{entry['tracker']}") or {}, entry) for entry in DOWNLOADS)
            if card.get("state") != WORDS.get("states", {}).get(entry["state"])
            or not card.get("size") or not (card.get("ratio") or "").startswith("Ratio")]
        journal.check("each card says its state in the state's word, then its size and its ratio",
                      bool(cards) and not misread, str(misread[:2]))
        unknown = [card["entry"] for card in cards
                   if card["sources"] != WORDS.get("sourcesUnknown") or card["added"] != WORDS.get("addedUnknown")
                   or (card["mode"] == "volumes" and card["transfer"] != WORDS.get("volumesUnknown"))]
        journal.check("the client's figures never read are said unknown — volumes, sources, date",
                      bool(cards) and not unknown, str(unknown[:2]))

        # ── d: the long name, whole at 369 and 390 px ───────────────────────
        for width in WIDTHS:
            await page.set_viewport_size({"width": width, "height": 844})
            answer, card = await one_card(page, "torrent-card-long-name")
            journal.check(f"at {width} px, the 132-character name is whole and never clipped",
                          answer is None and card is not None and card["title"] == LONG_NAME and not card["clipped"],
                          answer or repr(card and {"title": card["title"], "clipped": card["clipped"]}))
        await page.set_viewport_size({"width": 390, "height": 844})

        answer, card = await one_card(page, "torrent-card-no-popularity")
        journal.check("an unknown popularity reads « Sources inconnues », never 0",
                      answer is None and card is not None and card["sources"] == WORDS.get("sourcesUnknown")
                      and "0" not in (card["sources"] or ""), answer or repr(card and card["sources"]))

        # ── d: DECIDED 1's three states ──────────────────────────────────────
        answer, card = await one_card(page, "torrent-card-volumes")
        journal.check("at rest: the volumes received and sent, no bar",
                      answer is None and card is not None and card["mode"] == "volumes" and card["bar"] is None
                      and "↓" in (card["transfer"] or "") and "↑" in (card["transfer"] or ""),
                      answer or repr(card and (card["mode"], card["transfer"], card["bar"])))
        journal.check("and the sources and the date from their fields",
                      card is not None and card["sources"] == "12 sources" and (card["added"] or "").startswith("Ajouté le "),
                      repr(card and (card["sources"], card["added"])))
        answer, card = await one_card(page, "torrent-card-downloading-progress")
        journal.check("downloading: the bar at the entry's progress and the download rate",
                      answer is None and card is not None and card["mode"] == "downloading" and card["bar"] == 0.34
                      and card["transfer"] == "↓ 2,4 Mo/s",
                      answer or repr(card and (card["mode"], card["transfer"], card["bar"])))
        answer, card = await one_card(page, "torrent-card-uploading-rate")
        journal.check("uploading: the upload rate alone, no bar",
                      answer is None and card is not None and card["mode"] == "uploading" and card["bar"] is None
                      and card["transfer"] == "↑ 310 Ko/s",
                      answer or repr(card and (card["mode"], card["transfer"], card["bar"])))

        # ── e: the poster to the sheet, and back to « Torrents » ────────────
        await enter(page, "torrents-list")
        linked = [card for card in cards if card["poster"] != next(
            entry["title"] for entry in DOWNLOADS if entry["infoHash"] == card["entry"])]
        journal.check("every linked card's poster names its medium's sheet", bool(cards) and not linked,
                      str([card["entry"] for card in linked][:2]))
        poster = page.locator(f'#view [data-part="torrents/row"][data-entry="{PRESIDENT["infoHash"]}"]'
                              f'[data-tracker="c411"] [data-part="card/poster"]')
        if await poster.count():
            await poster.first.tap()
            await page.wait_for_timeout(ACTED)
        sheet = await page.evaluate("()=>({path: location.pathname, sheet: !!document.querySelector('[data-region=\"screen-media/body\"]')})")
        journal.check(f"a finger on « {PRESIDENT['title']} »'s poster opens its sheet",
                      sheet["sheet"] and sheet["path"].startswith("/media/"), repr(sheet))
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        back = await page.evaluate("""()=>({sheet: !!document.querySelector('[data-region="screen-media/body"]'),
          tab: document.querySelector('[data-trackers-tab][aria-selected="true"]')?.dataset.trackersTab ?? null})""")
        journal.check("Retour lands back on « Torrents »", not back["sheet"] and back["tab"] == "torrents", repr(back))

        answer, card = await one_card(page, "torrent-card-film")
        if card is not None:
            await page.tap('#view [data-part="torrents/row"] [data-part="card/poster"]')
            await page.wait_for_timeout(ACTED)
        film = await page.evaluate("""()=>({path: location.pathname,
          sheet: document.querySelector('[data-region="screen-media/body"]')?.textContent ?? ''})""")
        journal.check("a film's poster opens the film's sheet",
                      answer is None and card is not None and card["poster"] == FILM_TITLE
                      and film["path"] == f"/media/tmdb/{FILM_TMDB}" and FILM_TITLE in film["sheet"],
                      answer or repr((card and card["poster"], film["path"])))

        answer, card = await one_card(page, "torrent-card-unlinked")
        journal.check("an unlinked entry wears no poster: the folder, addressing the entry's panel",
                      answer is None and card is not None and card["poster"] is None
                      and card["folder"] == f"torrent:{PRESIDENT['infoHash']}:c411",
                      answer or repr(card and (card["poster"], card["folder"])))

        # ── e: the body to the panel, its facts the entry's ──────────────────
        await enter(page, "torrents-list")
        body = page.locator(f'#view [data-part="torrents/row"][data-entry="{PRESIDENT["infoHash"]}"]'
                            f'[data-tracker="c411"] [data-part="card/body"]')
        if await body.count():
            await body.first.tap()
            await page.wait_for_timeout(ACTED)
        panel = await page.evaluate(PANEL)
        path = await page.evaluate("()=>location.pathname")
        facts = (panel or {}).get("facts", {})
        journal.check("a finger on the body opens the torrent's panel, never the sheet",
                      panel is not None and not path.startswith("/media/"), repr(path))
        journal.check("its facts equal the entry's fields",
                      facts.get(PANEL_WORDS.get("name")) == PRESIDENT["name"]
                      and facts.get(PANEL_WORDS.get("tracker")) == PRESIDENT["tracker"]
                      and facts.get(PANEL_WORDS.get("ratio")) == "0,42"
                      and facts.get(PANEL_WORDS.get("state")) == WORDS.get("states", {}).get(PRESIDENT["state"]),
                      repr(facts))
        await enter(page, "torrent-panel-episode")
        await page.wait_for_timeout(ACTED)
        panel = await page.evaluate(PANEL)
        journal.check("an episode's panel names its series and its SxxEyy",
                      panel is not None and panel["facts"].get(PANEL_WORDS.get("medium")) == "President Curtis · S01E10",
                      repr(panel and panel["facts"].get(PANEL_WORDS.get("medium"))))
        await enter(page, "torrent-panel-unlinked")
        await page.wait_for_timeout(ACTED)
        panel = await page.evaluate(PANEL)
        journal.check("an unlinked entry's panel offers « Identifier » on its folder",
                      panel is not None and any(action["text"] == PANEL_WORDS.get("identify")
                                                and action["resolution"] == "Backrooms.2026.MULTi.2160p.WEB-DL"
                                                for action in panel["actions"]),
                      repr(panel and panel["actions"]))
        await enter(page, "torrent-panel-unlinked-no-folder")
        await page.wait_for_timeout(ACTED)
        panel = await page.evaluate(PANEL)
        journal.check("with no folder, it says « Aucun dossier à identifier. » and offers no « Identifier »",
                      panel is not None and PANEL_WORDS.get("noFolder", "<no copy>") in panel["text"]
                      and not any(action["text"] == PANEL_WORDS.get("identify") for action in panel["actions"]),
                      repr(panel and panel["actions"]))
        await enter(page, "torrent-panel-partial")
        await page.wait_for_timeout(ACTED)
        panel = await page.evaluate(PANEL)
        partial = (panel or {}).get("facts", {})
        journal.check("a partial panel says every unread figure unknown, none blank",
                      panel is not None and partial.get(PANEL_WORDS.get("sources")) == WORDS.get("sourcesUnknown")
                      # « Ajouté le » labels the line, so its value is the day alone (B-614).
                      and partial.get(PANEL_WORDS.get("added")) == PANEL_WORDS.get("unknown")
                      and partial.get(PANEL_WORDS.get("transfer")) == WORDS.get("volumesUnknown")
                      and all(value for value in partial.values()), repr(partial))

        # ── f: the swipe, and only through the confirmation ──────────────────
        await enter(page, "torrents-list")
        first = '#view [data-part="torrents/row"] [data-part="card"]'
        await swipe_left(page, first)
        drawer = await page.evaluate("""()=>{const row=document.querySelector('#view [data-part="torrents/row"]');
          return {sides: [...(row?.querySelectorAll('[data-part="swipe/side"]') ?? [])].map(s=>s.dataset.side),
            words: row?.querySelector('[data-side="right"]')?.textContent.trim() ?? null};}""")
        offset = await page.evaluate(OPEN_ROW)
        journal.check("a swipe to the left uncovers « Retirer », and no left drawer",
                      offset is not None and offset < -40 and drawer["sides"] == ["right"]
                      and drawer["words"] == WORDS.get("swipeRemove"), f"offset {offset} · {drawer!r}")
        action = page.locator('#view [data-part="torrents/row"] [data-side="right"] [data-part="swipe/action"]')
        if await action.count():
            await action.first.tap()
            await page.wait_for_timeout(ACTED)
        dialog = await page.evaluate(DIALOG)
        journal.check("its tap opens the confirmation, and nothing is removed before « Confirmer »",
                      dialog is not None and PRESIDENT["title"] in dialog and await page.evaluate(REMOVED) == 0,
                      repr(dialog))
        await page.evaluate(PRESS, False)
        await page.wait_for_timeout(ACTED)
        journal.check("« Annuler » removes nothing", await page.evaluate(REMOVED) == 0
                      and await page.evaluate(DIALOG) is None, "")

        answer = await enter(page, "torrent-swipe-remove")
        await page.wait_for_timeout(ACTED)
        offset = await page.evaluate(OPEN_ROW)
        journal.check("torrent-swipe-remove rests with the right drawer open",
                      answer is None and offset is not None and offset < -40, answer or f"offset {offset}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
