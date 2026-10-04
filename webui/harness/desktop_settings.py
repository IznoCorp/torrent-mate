"""R487 — Réglages, Classement, Comptes, Profil and the gates on a desktop (phase 8).

The operator, 2026-10-01 — DECIDED 1 = C (a reading column ≈ 760 px, dialogs ≈ 480 px), DECIDED 3 = C (the
panel a side sheet on the right, ≈ 440 px) and DECIDED 7 = B (a bottom bar bounded to the column).
`docs/features/maquette-desktop/DESIGN.md` § 1.3: a setting's label sat at x 27 and its value at x 1 250;
the Classement's number field sat UNDER its label at the left of a 1 250 px row; the role sat at the far
right of each account; the sign-in gate was already a bounded, centred card — the precedent, kept.

WHAT IS READ, out of the harness's phone frame, at 1024, 1280 and 1440:

  1. on every named state of Réglages, the Classement, Comptes and Profil, every box of the page or the
     screen's content inside the column, the column no wider than its cap;
  2. on the Classement, every weight BESIDE its criterion: on the criterion's line, at the row's end;
  3. a setting's field and an account's detail, every row inside the 440 px side sheet;
  4. the save bar spanning the column only, « Enregistrer » inside it;
  5. the sign-in gate: a card no wider than 480 px, centred (no-access and 404 are pages, in the column).

And at 390 the phone keeps its drawing: the weight on its own line under the criterion, the save bar the
window's width.
"""
import asyncio

from common import PANEL_IN, PHONE, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

COLUMN = 760
SIDE = 440
DIALOG = 480
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"

STATES = (
    "settings", "settings-topic", "settings-search", "settings-one", "settings-edited", "settings-secrets",
    "settings-read-only", "settings-restart",
    "ranking-editor", "ranking-editor-loading", "ranking-editor-error", "ranking-editor-saving",
    "ranking-editor-save-conflict",
    "profile", "screen-profile", "profile-household", "profile-guest", "profile-ceiling", "profile-preprod",
    "accounts-roster", "accounts-roles", "accounts-forbidden", "no-access", "not-found",
)
PANELS = (
    "settings-field-boolean", "settings-field-number", "settings-field-text", "settings-field-path",
    "settings-field-list", "settings-field-duration", "settings-field-structure", "settings-field-schedule",
    "accounts-detail",
)
GATES = ("signin", "signin-password-open", "signin-error")


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

# Each weight against its criterion: beside = its middle within the name's line band and its left past the
# criterion's text; at the row's end = its right a padding from the row's.
WEIGHTS = """() => {
  return [...document.querySelectorAll('[data-part="ranking/criterion"]')].map((row) => {
    const r = row.getBoundingClientRect();
    const body = row.querySelector('.fw').getBoundingClientRect();
    const field = row.querySelector('[data-part="ranking/weight"]').getBoundingClientRect();
    const middle = (field.top + field.bottom) / 2;
    return {field: row.dataset.field, beside: middle > body.top && middle < body.bottom && field.left >= body.right - 1,
            under: field.top >= body.bottom - 1, endGap: Math.round(r.right - field.right)};
  });
}"""

WITHIN = """([selector, cap]) => {
  const layer = document.querySelector(selector);
  if (!layer) return null;
  const box = layer.getBoundingClientRect();
  const out = [...layer.querySelectorAll('*')].map((e) => e.getBoundingClientRect())
    .filter((r) => r.width > 0 && (r.right > box.right + 1 || r.left < box.left - 1)).length;
  return {width: Math.round(box.width), out, within: box.width <= cap + 1};
}"""

SAVE_BAR = """() => {
  const bar = document.querySelector('#savebar');
  const view = document.querySelector('#view');
  if (!bar || !view) return null;
  const b = bar.getBoundingClientRect(), v = view.getBoundingClientRect();
  const button = bar.querySelector('button').getBoundingClientRect();
  return {left: Math.round(b.left), right: Math.round(b.right), width: Math.round(b.width), window: innerWidth,
          columnLeft: Math.round(v.left), columnRight: Math.round(v.right),
          buttonInside: button.right <= b.right + 1 && button.left >= b.left - 1};
}"""

# The sign-in gate's card: the union of every box the gate draws inside its own full-window ground.
GATE = """() => {
  const gate = document.querySelector('#login');
  if (!gate || gate.getBoundingClientRect().width === 0) return null;
  const boxes = [...gate.querySelectorAll('*')].map((e) => e.getBoundingClientRect()).filter((r) => r.width > 0 && r.height > 0);
  const left = Math.min(...boxes.map((r) => r.left)), right = Math.max(...boxes.map((r) => r.right));
  return {width: Math.round(right - left), offCentre: Math.round(Math.abs((left + right) / 2 - innerWidth / 2))};
}"""


async def main():
    journal = Journal("R487 — Réglages, Classement, Comptes, Profil and the gates on a desktop")
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
            weights = await read_at(page, "ranking-editor", WEIGHTS)
            astray = [w for w in weights if not w["beside"] or w["endGap"] > 24]
            journal.check(f"{width}: every Classement weight beside its criterion, at the row's end",
                          len(weights) >= 5 and astray == [], f"{len(weights)} weights, astray {astray[:3]}")
            for state in PANELS:
                seen = await read_at(page, state, WITHIN, ["#sheet[data-open]", SIDE], wait=PANEL_IN)
                journal.check(f"{width} {state}: every row within the {SIDE} px side sheet",
                              seen is not None and seen["within"] and seen["out"] == 0, f"{seen}")
            seen = await read_at(page, "settings-save-bar-frame", SAVE_BAR)
            journal.check(f"{width}: the save bar spans the column only, « Enregistrer » inside it",
                          seen is not None and seen["width"] <= COLUMN + 1 and seen["buttonInside"]
                          and abs(seen["left"] - seen["columnLeft"]) <= 1 and abs(seen["right"] - seen["columnRight"]) <= 1,
                          f"{seen}")
            for state in GATES:
                seen = await read_at(page, state, GATE)
                journal.check(f"{width} {state}: the gate a card ≤ {DIALOG} px, centred",
                              seen is not None and seen["width"] <= DIALOG + 1 and seen["offCentre"] <= 2, f"{seen}")
            await context.close()

        context, page = await open_page(browser)
        weights = await read_at(page, "ranking-editor", WEIGHTS)
        journal.check("390: every weight keeps its own line under the criterion",
                      len(weights) >= 5 and all(w["under"] for w in weights), f"{weights[:2]}")
        seen = await read_at(page, "settings-save-bar-frame", SAVE_BAR)
        journal.check("390: the save bar keeps the window's width",
                      seen is not None and seen["left"] <= 0 and seen["right"] >= seen["window"], f"{seen}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
