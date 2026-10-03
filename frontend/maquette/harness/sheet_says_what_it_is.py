"""R408 — the media sheet says what the medium is (L24, DOIT-11).

DOIT-11's content half was unproved: the hero draws the year and the trailer
with their failure words, R119 reads the sheet's parts IN FLIGHT and R63 the
library rows' synopsis — no rule read DOIT-11's fields on the sheet AT REST.

WHAT IS READ, on each sheet named below, every field against the sheet the layer
answered (`/api/v1/media/{provider}/{id}` in the query cache) — the field, or the
words that say it is missing, never nothing:

  - title, year, synopsis, trailer — every medium;
  - the director (a film) or the creator (a series);
  - for a series: its status, and its catalogue — seasons and episodes.
"""
import asyncio
import json
import pathlib

from common import PANEL_IN, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
MEDIA = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["media"]

STATES = ("mediasheet-movie", "mediasheet-series", "mediasheet-no-trailer", "mediasheet-suggestion-series")

READ = """(words) => {
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
  const [, , provider, id] = location.pathname.split('/');
  const sheet = window.__queries.getQueryData(['/api/v1/media', provider, decodeURIComponent(id ?? '')]) ?? null;
  const text = (node) => node?.textContent.replace(/\\s+/g, ' ').trim() ?? null;
  const synopsisHeading = [...(screen?.querySelectorAll('[data-part="heading"]') ?? [])]
    .find((heading) => heading.textContent.trim() === words.synopsis);
  const rows = Object.fromEntries([...(screen?.querySelectorAll('[data-part="key-value"]') ?? [])]
    .map((row) => [text(row.querySelector(':scope > span')), text(row.querySelectorAll(':scope > span')[1])]));
  return {
    sheet,
    title: text(screen?.querySelector('[data-part="hero/title"]')),
    meta: text(screen?.querySelector('[data-part="hero/content"] p')),
    synopsis: text(synopsisHeading?.parentElement?.querySelector('p')),
    trailer: !!screen?.querySelector('[data-part="media/trailer"]'),
    seasonRows: screen?.querySelectorAll('[data-part="season"]').length ?? 0,
    body: text(screen),
    rows,
  };
}"""


def one_of(value, *accepted):
    """Whether a drawn value is one of the accepted words.

    Args:
        value: What was drawn.
        *accepted: The field's value, then the words that say it is missing.

    Returns:
        True when the value is one of them.
    """
    return value is not None and any(word and value == str(word) for word in accepted)


async def main():
    journal = Journal("R408 — the media sheet says what the medium is")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state in STATES:
            seen = await read_at(page, state, READ, MEDIA, wait=PANEL_IN + SETTLED + SETTLED)
            sheet = seen["sheet"]
            if not journal.check(f"{state}: the sheet the layer answered is in the cache", sheet is not None):
                continue
            film = sheet.get("kind") == "movie"
            journal.check(f"{state}: the title", seen["title"] == str(sheet["title"]).split(" (")[0], repr(seen["title"]))
            journal.check(f"{state}: the year, or its missing words",
                          seen["meta"] is not None and any(str(word) in seen["meta"] for word in
                                                           (sheet.get("year") or MEDIA["yearUnknown"],)),
                          repr(seen["meta"]))
            journal.check(f"{state}: the synopsis, or its missing words",
                          one_of(seen["synopsis"], sheet.get("overview"), MEDIA["synopsisUnknown"]),
                          repr((seen["synopsis"] or "")[:60]))
            credit = MEDIA["director"] if film else MEDIA["creator"]
            journal.check(f"{state}: the {'director' if film else 'creator'}, or its missing word",
                          one_of(seen["rows"].get(credit), sheet.get("director" if film else "creator"),
                                 MEDIA["unknown"]), repr(seen["rows"].get(credit)))
            journal.check(f"{state}: the trailer, or its missing words",
                          seen["trailer"] if sheet.get("trailerVideo") else MEDIA["noTrailer"] in seen["body"],
                          str({"drawn": seen["trailer"], "served": bool(sheet.get("trailerVideo"))}))
            if not film:
                if sheet.get("status"):
                    status = MEDIA["seriesStatus"].replace("{{statut}}", str(sheet["status"]).lower())
                    journal.check(f"{state}: the series' status", status in seen["meta"], repr(seen["meta"]))
                seasons = seen["rows"].get(MEDIA["seasons"]) or ""
                catalogue = next((value for key, value in seen["rows"].items()
                                  if key and key.startswith(MEDIA["catalogue"])), "") or ""
                journal.check(f"{state}: its seasons and episodes — counted, or its catalogue",
                              (any(ch.isdigit() for ch in seasons) and seen["seasonRows"] > 0)
                              or MEDIA["episodes"] in catalogue,
                              str({"seasons": seasons, "rows": seen["seasonRows"], "catalogue": catalogue}))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
