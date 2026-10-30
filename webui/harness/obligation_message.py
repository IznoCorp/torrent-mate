"""R520 — an obligation met or released says so ON ITS TORRENT, and its push lands there.

The operator, 2026-10-03: « On peut remplacer le canal Telegram par des notifications FCM,
parce qu'elles devront être implémentées, et des messages in-app sur le torrent en question. »
An obligation MET (seconds seeded ≥ the floor, OR ratio ≥ the floor plus 0.1) or RELEASED (its
torrent gone from the client, by « Retirer de qBittorrent » or by any other way) is told by a push
AND by a message on the torrent concerned. The push's tap lands on that torrent's panel.

R520-a — the message, one per outcome, each with its date and its why:
1. `torrent-panel-obligation-met-time` — the panel LEADS with the outcome block, `data-outcome`
   « met », `data-reason` « seedTime », its lead the met word and its why the 72 h;
2. `torrent-panel-obligation-met-ratio` — « met », « ratio », the why naming 1,10;
3. `torrent-panel-obligation-released-here` — the torrent gone from the client, its panel still
   open from its obligation: « released », « removedHere », the gone note, said early;
4. `torrent-panel-obligation-released-after-met` — « released » after « met »: the why says the
   obligation was already met, never early;
5. `torrent-panel-obligation-released-by-hand` — « released », « goneFromClient »;
6. a running obligation's panel (`torrent-panel-episode`) carries no outcome block.

R520-b — the panel is an ADDRESS, the push's landing (D1's second tier):
7. opened, the panel writes `panel=torrent:<hash>:<tracker>` into the address;
8. that address typed cold opens the torrent's panel over « Trackers », and Back closes it onto
   the page, never leaving it.

Red before the change: none of the five named states exists, the panel carries no outcome block
and no address, and a typed `panel=torrent:` is refused as a kind the address table does not carry.
"""
import asyncio
import json
import pathlib
import urllib.parse

from common import PANEL_IN, PROTOTYPE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["torrents"]
# THE WORDS MAY BE ABSENT — on the build before the change they are: each missing one reads as a
# placeholder no drawn message holds, so the rule FAILS on behaviour rather than crashing.
ABSENT = "<no words>"
OUTCOME = WORDS.get("outcome", {})
OBLIGATIONS = json.loads((SOURCE / "mocks/seeds/obligations.json").read_text(encoding="utf-8"))
SEASON = "e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb"
EPISODE = "66e23ab395c438b7db4f7c855bd451d8bb1f0046"
TRACKER = "c411"


def lead_word(key):
    """The words of a lead before its date placeholder.

    Args:
        key: The lead's key under the outcome's words.

    Returns:
        The lead's fixed words.
    """
    return OUTCOME.get(key, ABSENT).split("{{")[0].strip()


def why_word(key):
    """The longest fixed run of a why, the words between its placeholders.

    Args:
        key: The why's key under the outcome's words.

    Returns:
        The run a drawn why must contain.
    """
    words = OUTCOME.get(key, ABSENT)
    return max((part.split("}}")[-1] for part in words.split("{{")), key=len).strip(" .;,")


SHEET = """() => {
  const sheet = document.querySelector('#sheet');
  if (!sheet || !sheet.hasAttribute('data-open')) return null;
  const block = sheet.querySelector('[data-part="torrents/obligation-outcome"]');
  const firstFact = sheet.querySelector('[data-part="key-value"]');
  return {
    title: sheet.querySelector('[data-part="sheet/title"]')?.textContent.trim() ?? null,
    outcome: block?.dataset.outcome ?? null,
    reason: block?.dataset.reason ?? null,
    message: block?.textContent ?? null,
    leads: block !== null && firstFact !== null
      && Boolean(block.compareDocumentPosition(firstFact) & Node.DOCUMENT_POSITION_FOLLOWING),
    text: sheet.textContent,
    search: location.search,
    path: location.pathname,
  };
}"""

CASES = (
    ("torrent-panel-obligation-met-time", "met", "seedTime", "metLead", ["72", why_word("seedTime")]),
    ("torrent-panel-obligation-met-ratio", "met", "ratio", "metLead", ["1,10"]),
    ("torrent-panel-obligation-released-here", "released", "removedHere", "releasedLead",
     [OUTCOME.get("released", {}).get("removedHere", ABSENT), why_word("releasedEarly")]),
    ("torrent-panel-obligation-released-after-met", "released", "removedHere", "releasedLead",
     [why_word("releasedAfterMet")]),
    ("torrent-panel-obligation-released-by-hand", "released", "goneFromClient", "releasedLead",
     [OUTCOME.get("released", {}).get("goneFromClient", ABSENT)]),
)


async def main():
    journal = Journal("R520 — an obligation met or released says so on its torrent, and its push lands there")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── R520-a: the message, per outcome ────────────────────────────────
        for state, outcome, reason, lead, whys in CASES:
            known = await page.evaluate("(id)=>window.__states().includes(id)", state)
            journal.check(f"the named state {state} exists", known, state)
            if not known:
                continue
            seen = await read_at(page, state, SHEET, wait=PANEL_IN)
            if seen is None:
                journal.check(f"{state}: the torrent's panel is open", False, "no panel")
                continue
            journal.check(f"{state}: the outcome block LEADS the panel, « {outcome} » for « {reason} »",
                          seen["leads"] and seen["outcome"] == outcome and seen["reason"] == reason,
                          f"leads {seen['leads']} · {seen['outcome']} / {seen['reason']}")
            message = (seen["message"] or "").replace("\xa0", " ").replace(" ", " ")
            missing = [word for word in [lead_word(lead), *whys] if word not in message]
            journal.check(f"{state}: the message says its outcome, its date and its why", not missing,
                          f"missing {missing} in {message!r}")
            if outcome == "released":
                journal.check(f"{state}: the panel says the torrent has left the client",
                              WORDS["panel"].get("gone", ABSENT) in seen["text"], repr(seen["text"][:160]))
        after_state = "torrent-panel-obligation-released-after-met"
        after_met = (await read_at(page, after_state, SHEET, wait=PANEL_IN)
                     if await page.evaluate("(id)=>window.__states().includes(id)", after_state) else None)
        journal.check("a release after the obligation was met is never said early",
                      after_met is not None and why_word("releasedEarly") not in (after_met["message"] or ""),
                      repr(after_met and after_met["message"]))

        running = await read_at(page, "torrent-panel-episode", SHEET, wait=PANEL_IN)
        journal.check("a running obligation's panel carries no outcome block",
                      running is not None and running["outcome"] is None, repr(running and running["outcome"]))

        # ── R520-b: the panel's address, the push's landing ─────────────────
        address = f"torrent:{EPISODE}:{TRACKER}"
        written = urllib.parse.parse_qs((running or {}).get("search", "").lstrip("?")).get("panel", [None])[0]
        journal.check("the opened panel writes its address into the URL", written == address,
                      f"panel={written}")
        await context.close()

        context = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                            is_mobile=True, has_touch=True)
        page = await context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(urllib.parse.urljoin(PROTOTYPE, "trackers?panel=" + urllib.parse.quote(address)),
                        wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        cold = await page.evaluate(SHEET)
        title = next(row["title"] for row in OBLIGATIONS if row["infoHash"] == EPISODE)
        journal.check("the typed address opens the torrent's panel over « Trackers »",
                      cold is not None and cold["path"] == "/trackers" and title.split(" S")[0] in (cold["title"] or ""),
                      repr(cold and (cold["path"], cold["title"])))
        await page.go_back()
        await page.wait_for_timeout(PANEL_IN)
        back = await page.evaluate("()=>({open: !!document.querySelector('#sheet[data-open]'), path: location.pathname})")
        journal.check("Back closes the panel onto « Trackers », never leaving the page",
                      not back["open"] and back["path"] == "/trackers", repr(back))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
