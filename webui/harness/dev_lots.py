"""R527 — the lots progress draws every lot and every phase it is given, in each of its cases, at 390 and on a desktop.

The page `/dev/lots` reads what the design host generated — one card per lot, each phase with its state (planned, in
progress, PR open, merged), its pull requests and what blocks it — and nothing on it acts.

WHAT IS READ, at 390 in the phone frame and at 1280 out of it, on the named states:

  1. `dev-lots`: one card per lot of the sample and one row per phase, each row's state chip saying its state in
     the interface's words and in the tone the state earns; every pull request a link to its own page, opened
     apart; what blocks a lot or a phase said; each lot's optional details (description, note, dates with « ≈ » when
     estimated, duration) drawn when given and absent when not, the sample holding both cases; the long lot name
     wrapped, never cut; nothing wider than the page;
  2. `dev-lots-loading`: placeholders, no card;
  3. `dev-lots-error`: the error surface, an alert with its retry;
  4. `dev-lots-unavailable` and `dev-lots-none`: their notice, no card.

The sample's figures are read from the page's own cache, never restated here.
"""
import asyncio

from common import PHONE, Journal, browser_channel, chrome_launch_args, open_page, read_at, shot
from playwright.async_api import async_playwright

OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"
DESKTOP = {**PHONE, "viewport": {"width": 1280, "height": 900}, "is_mobile": False, "has_touch": False,
           "device_scale_factor": 1}

# The state words and the tone each state earns, as the screen draws them.
WORDS = {"planned": "Prévue", "in-progress": "En cours", "pr-open": "PR ouverte", "merged": "Fusionnée"}  # french-ok: the rendered state words
TONES = {"planned": "neutral", "in-progress": "info", "pr-open": "warning", "merged": "success"}

# What the open screen draws, against what the page's cache holds for it.
READING = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open][data-key="dev-lots"]');
  if (!screen) return null;
  const served = window.__queries?.getQueryData(['/dev/lots.json']) ?? null;
  const port = screen.querySelector('[data-part="viewport"]');
  const wider = [...screen.querySelectorAll('*')].filter((one) => {
    const box = one.getBoundingClientRect();
    return box.width > 0 && port && box.right > port.getBoundingClientRect().right + 1;
  }).map((one) => one.getAttribute('data-part') ?? one.tagName.toLowerCase());
  const phases = [...screen.querySelectorAll('[data-part="lots/phase"]')].map((row) => {
    const chip = row.querySelector('[data-part="chip"]');
    return {state: row.dataset.state, word: chip?.textContent.trim() ?? null, tone: chip?.dataset.tone ?? null};
  });
  const links = [...screen.querySelectorAll('a[data-part="lots/pr"]')].map((link) => ({
    href: link.getAttribute('href'), target: link.getAttribute('target'), rel: link.getAttribute('rel')}));
  const names = [...screen.querySelectorAll('[data-part="lots/lot-name"]')].map((name) => ({
    cut: name.scrollWidth > name.clientWidth + 1 || getComputedStyle(name).textOverflow === 'ellipsis',
    lines: Math.round(name.getBoundingClientRect().height / parseFloat(getComputedStyle(name).lineHeight))}));
  const details = [...screen.querySelectorAll('[data-part="lots/lot"]')].map((card) => {
    const text = (part) => card.querySelector(`[data-part="${part}"]`)?.textContent.trim() ?? null;
    return {id: card.dataset.lot, description: text('lots/description'), note: text('lots/note'),
            dates: text('lots/dates'), duration: text('lots/duration')};
  });
  return {
    served, details,
    lots: screen.querySelectorAll('[data-part="lots/lot"]').length,
    phases, links, names, wider: wider.slice(0, 4),
    blockers: screen.querySelectorAll('[data-part="lots/blocker"]').length,
    skeletons: screen.querySelectorAll('[data-skeleton]').length,
    alert: !!screen.querySelector('[data-part="surface-error"][role="alert"] [data-part="surface-error/retry"]'),
    unavailable: !!screen.querySelector('[data-part="lots/unavailable"]'),
    none: !!screen.querySelector('[data-part="lots/none"]'),
    stamp: !!screen.querySelector('[data-part="lots/stamp"]'),
  };
}"""


def expected_details(lot):
    """The optional details one lot was given, as the card should draw them.

    Args:
        lot: One lot of the document in the page's cache.

    Returns:
        The description, the note and the dates as drawn, and the duration; None for what the lot does not give.
    """
    start, end = lot.get("start"), lot.get("end")
    dates = None
    if start or end:
        dates = f"{start} → {end}" if start and end else (f"{start} →" if start else f"→ {end}")
        dates = f"≈ {dates}" if lot.get("estimated") else dates
    return lot.get("description"), lot.get("note"), dates, lot.get("duration")


def expected_counts(served):
    """The lots, phases, pull requests and blockers the page was given.

    Args:
        served: The document in the page's cache.

    Returns:
        The four counts.
    """
    lots = served["lots"]
    phases = [phase for lot in lots for phase in lot["phases"]]
    blockers = sum(1 for lot in lots if lot["blockedBy"]) + sum(1 for phase in phases if phase["blockedBy"])
    return len(lots), len(phases), sum(len(phase["prs"]) for phase in phases), blockers


async def read_cases(journal, page, width):
    """Reads every case of the page at one width.

    Args:
        journal: Where the verdicts go.
        page: The Playwright page.
        width: The width's name, for the verdicts.
    """
    seen = await read_at(page, "dev-lots", READING)
    if not journal.check(f"{width} dev-lots: the screen is open on the sample", seen and seen["served"], f"{seen and seen['lots']}"):
        return
    lots, phases, prs, blockers = expected_counts(seen["served"])
    journal.check(f"{width} dev-lots: one card per lot, one row per phase", (seen["lots"], len(seen["phases"])) == (lots, phases),
                  f"{seen['lots']} cards of {lots}, {len(seen['phases'])} rows of {phases}")
    journal.check(f"{width} dev-lots: the four states are all drawn", {one["state"] for one in seen["phases"]} == set(WORDS),
                  f"{sorted({one['state'] for one in seen['phases']})}")
    wrong = [one for one in seen["phases"] if one["word"] != WORDS.get(one["state"]) or one["tone"] != TONES.get(one["state"])]
    journal.check(f"{width} dev-lots: each state chip says its state, in its tone", not wrong, f"{wrong[:3]}")
    apart = [one for one in seen["links"] if not (one["href"] or "").startswith("https://") or one["target"] != "_blank"
             or "noreferrer" not in (one["rel"] or "")]
    journal.check(f"{width} dev-lots: every pull request is a link to its page, opened apart",
                  len(seen["links"]) == prs and not apart, f"{len(seen['links'])} of {prs}, {apart[:2]}")
    wrong = []
    for lot, seen_lot in zip(seen["served"]["lots"], seen["details"]):
        description, note, dates, duration = expected_details(lot)
        drawn = (seen_lot["description"], seen_lot["note"], seen_lot["dates"])
        # The duration reads « Durée : <text> »: the words are the interface's, the text is the lot's.
        duration_ok = (seen_lot["duration"] is None) if duration is None else (seen_lot["duration"] or "").endswith(duration)
        if drawn != (description, note, dates) or not duration_ok:
            wrong.append((lot["id"], drawn, seen_lot["duration"]))
    with_details = [lot for lot in seen["served"]["lots"] if any(expected_details(lot))]
    journal.check(f"{width} dev-lots: each lot draws the details it is given and nothing of those it is not, the sample holding both",
                  not wrong and 0 < len(with_details) < lots, f"{wrong[:2]}, {len(with_details)} of {lots} give some")
    journal.check(f"{width} dev-lots: what blocks is said", seen["blockers"] == blockers, f"{seen['blockers']} of {blockers}")
    journal.check(f"{width} dev-lots: no lot name is cut, the longest wraps",
                  not any(one["cut"] for one in seen["names"]) and max(one["lines"] for one in seen["names"]) >= (2 if width == "390" else 1),
                  f"{seen['names']}")
    journal.check(f"{width} dev-lots: nothing is wider than the page", seen["wider"] == [], f"{seen['wider']}")
    journal.check(f"{width} dev-lots: when the progress was generated is said", seen["stamp"])
    # The harness's own welcome hint is no part of the page: the capture is taken without it.
    await page.evaluate("()=>window.__toast?.hide()")
    await page.wait_for_timeout(400)
    await shot(page, f"dev_lots-{width}")

    seen = await read_at(page, "dev-lots-loading", READING)
    journal.check(f"{width} dev-lots-loading: placeholders, no card", seen and seen["skeletons"] > 0 and seen["lots"] == 0, f"{seen and seen['skeletons']}")
    seen = await read_at(page, "dev-lots-error", READING)
    journal.check(f"{width} dev-lots-error: the error surface, an alert with its retry", seen and seen["alert"] and seen["lots"] == 0)
    seen = await read_at(page, "dev-lots-unavailable", READING)
    journal.check(f"{width} dev-lots-unavailable: the notice, no card", seen and seen["unavailable"] and seen["lots"] == 0)
    seen = await read_at(page, "dev-lots-none", READING)
    journal.check(f"{width} dev-lots-none: the notice, no card", seen and seen["none"] and seen["lots"] == 0)


async def main():
    journal = Journal("R527 — the lots progress draws every lot and every phase it is given, in each of its cases")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await read_cases(journal, page, "390")
        await context.close()

        context, page = await open_page(browser, **DESKTOP)
        await context.add_init_script(OUT_OF_FRAME)
        await page.reload(wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        page.on("pageerror", lambda error: errors.append(str(error)))
        await read_cases(journal, page, "1280")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
