"""R486 — Système, a run and Maintenance on a desktop: the sections in the column, the log keeps its wrap (phase 7).

The operator, 2026-10-01 — DECIDED 1 = C (a reading column ≈ 760 px) and DECIDED 3 = C (the panel a side
sheet on the right, ≈ 440 px). `docs/features/maquette-desktop/DESIGN.md` § 1.3: Système drew the longest
prose lines of the app (225 characters at 1280); a run was « the one surface the width serves », its log
lines fitting whole; Maintenance put a title on the left and a count at the window's far right.

WHAT IS READ, out of the harness's phone frame, at 1024, 1280 and 1440:

  1. on every named state of Système, a run and Maintenance, every box of the page or the screen's content
     inside the column, the column no wider than its cap;
  2. on a run's raw output, the log still WRAPPED: no line scrolls sideways, and a line longer than the
     column breaks onto the next (§ 12 « nothing scrolls sideways, a log included » holds at every width);
  3. a destructive command's panel, every row inside its 440 px side sheet;
  4. at 390, the log keeps the same wrap.
"""
import asyncio

from common import PANEL_IN, PHONE, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

COLUMN = 760
SIDE = 440
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"

# Système's page and its tabs, a run's screen, Maintenance and its topics: every state they name.
STATES = (
    "system", "system-outage", "system-loading", "system-error", "system-services-unavailable",
    "system-disks-unavailable", "system-index-unavailable", "system-dependencies-unavailable",
    "levers-running", "runs-list", "runs-empty", "runs-degraded", "watch-running",
    "run-detail", "run-detail-running", "run-detail-failed", "run-detail-log", "run-detail-no-log",
    "run-detail-maintenance", "run-not-found",
    "maintenance", "maintenance-topic", "maintenance-loading",
)


def desktop(width):
    """A desktop window of WIDTH, out of the frame, pointer only."""
    return {**PHONE, "viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False,
            "device_scale_factor": 1}


# The reading box: the open screen's content (its bar spans the window by design), else the page.
COLUMN_HOLDS = """(cap) => {
  const screen = [...document.querySelectorAll('[data-part="screen"][data-open]')].pop();
  const port = screen ? screen.querySelector('.port') : null;
  const column = port ? [...port.children].find((c) => c.getBoundingClientRect().width > 0) : document.querySelector('#view');
  if (!column) return null;
  const box = column.getBoundingClientRect();
  const out = [...column.querySelectorAll('*')].filter((e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && (r.right > box.right + 1 || r.left < box.left - 1);
  }).map((e) => `${e.tagName.toLowerCase()}[${e.getAttribute('data-part') ?? ''}] ${Math.round(e.getBoundingClientRect().right)}`);
  return {width: Math.round(box.width), boxes: column.querySelectorAll('*').length, out: out.slice(0, 4),
          capped: box.width <= cap + 1};
}"""

# The log: wrapped (pre-wrap), never wider than what holds it, and a long line seen on more than one line.
LOG = """() => {
  const log = document.querySelector('[data-part="screen"][data-open] pre[data-part="run/log"]');
  if (!log) return null;
  const line = parseFloat(getComputedStyle(log).lineHeight);
  const lines = log.textContent.split('\\n');
  const longest = Math.max(...lines.map((l) => l.length));
  const style = getComputedStyle(log);
  return {wrap: style.whiteSpace, sideways: log.scrollWidth - log.clientWidth, width: Math.round(log.clientWidth),
          longest, drawnLines: Math.round(log.scrollHeight / line), textLines: lines.length};
}"""

WITHIN = """([selector, cap]) => {
  const layer = document.querySelector(selector);
  if (!layer) return null;
  const box = layer.getBoundingClientRect();
  const out = [...layer.querySelectorAll('*')].map((e) => e.getBoundingClientRect())
    .filter((r) => r.width > 0 && (r.right > box.right + 1 || r.left < box.left - 1)).length;
  return {width: Math.round(box.width), out, within: box.width <= cap + 1};
}"""


def log_wraps(seen):
    """The log is wrapped: nothing scrolls sideways, and its text takes more lines than it has."""
    return (seen is not None and seen["wrap"] == "pre-wrap" and seen["sideways"] <= 0
            and seen["drawnLines"] > seen["textLines"])


async def main():
    journal = Journal("R486 — Système, a run and Maintenance on a desktop: the sections in the column, the log keeps its wrap")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for width in (1024, 1280, 1440):
            context, page = await open_page(browser, **desktop(width))
            await context.add_init_script(OUT_OF_FRAME)
            await page.reload(wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            page.on("pageerror", lambda error: errors.append(str(error)))
            for state in STATES:
                seen = await read_at(page, state, COLUMN_HOLDS, COLUMN)
                journal.check(f"{width} {state}: every box inside the column, the column ≤ {COLUMN} px",
                              seen is not None and seen["boxes"] > 0 and seen["capped"] and seen["out"] == [], f"{seen}")
            seen = await read_at(page, "run-detail-log", LOG)
            journal.check(f"{width}: the run's log keeps its wrap — nothing sideways, a long line broken", log_wraps(seen),
                          f"{seen}")
            seen = await read_at(page, "maintenance-delete", WITHIN, ["#sheet[data-open]", SIDE], wait=PANEL_IN)
            journal.check(f"{width}: a destructive command's panel, every row within its {SIDE} px side sheet",
                          seen is not None and seen["within"] and seen["out"] == 0, f"{seen}")
            await context.close()

        context, page = await open_page(browser)
        seen = await read_at(page, "run-detail-log", LOG)
        journal.check("390: the run's log keeps the same wrap", log_wraps(seen), f"{seen}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
