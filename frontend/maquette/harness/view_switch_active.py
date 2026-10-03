"""R521 — a view switch says which view is shown: one option marked, and drawn (B-692).

« Sélecteur de type de liste on voit pas quel type de liste est sélectionné
actuellement » (the operator, Android, Acquisition › Suivis, grid view): the three
icons right of « Tout · Urgence » all looked the same while the grid was shown.
THE MECHANISM: `viewSwitchButton` drew the pressed segment for its `text` size
only; the `icon` size — Suivis, Médiathèque, Découvrir — had no pressed drawing at
all, though `aria-pressed` was already on the button.

WHAT IS READ, for every view switch of the census, each in every view it offers,
reached by its named state:
  1. exactly ONE button of the switch is marked active (`aria-pressed="true"`),
     and it is the view the state shows;
  2. the button says so to the harness as well (`data-active`), the same one;
  3. it is DRAWN active: its background differs from every other button's — the
     catalogue's selected segment (`bg-background` on the `bg-muted` track), the
     one the tabs and the text switches wear.

THE CENSUS, every `viewSwitch()` of `design/src/`: Suivis (list, group, grid),
Médiathèque (list, grid — the incomplete lens and the recent lens share its head),
Découvrir (list, posters, deck), the « + » screen's kinds and providers, and the
drawer's appearance. The last three are `text` switches that drew the pressed
segment already; they are held here so that no switch loses it.
"""
import asyncio

from common import Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

# Every view switch visible in a root, as what each button says and wears.
READ = """(root) => {
  const layer = document.querySelector(root);
  if (!layer) return null;
  layer.querySelectorAll('details').forEach((fold) => { fold.open = true; });
  return [...layer.querySelectorAll('[data-part="view/switch"]')]
    .filter((group) => group.getClientRects().length > 0)
    .map((group) => ({
      buttons: [...group.querySelectorAll('button')].map((button) => ({
        view: button.dataset.fmode ?? button.dataset.lmode ?? button.dataset.sugmode ?? button.textContent.trim(),
        pressed: button.getAttribute('aria-pressed'),
        active: button.dataset.active ?? null,
        background: getComputedStyle(button).backgroundColor,
      })),
    }));
}"""

# (state, the root to read in, the view the state shows, which switch of the root).
HOLDS = (
    ("acq-follows-list", "#view", "list", "Suivis"),
    ("acq-follows-group", "#view", "group", "Suivis"),
    ("acq-follows-grid", "#view", "grid", "Suivis"),
    ("lib-list", "#view", "list", "Médiathèque"),
    ("lib-grid", "#view", "grid", "Médiathèque"),
    ("lib-incomplete", "#view", None, "Médiathèque (incomplete lens)"),
    ("discover-header", "#view", "list", "Découvrir"),
    ("discover-posters", "#view", "poster", "Découvrir"),
    ("discover-deck", "#view", "deck", "Découvrir"),
)


async def main():
    journal = Journal("R521 — a view switch says which view is shown")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state, root, shown, name in HOLDS:
            switches = await read_at(page, state, READ, root)
            journal.check(f"{state}: {name} draws a view switch", bool(switches), str(switches))
            for group in switches or []:
                buttons = group["buttons"]
                marked = [button for button in buttons if button["pressed"] == "true"]
                journal.check(f"{state}: exactly one option is marked active", len(marked) == 1,
                              str([(b["view"], b["pressed"]) for b in buttons]))
                if len(marked) != 1:
                    continue
                if shown is not None:
                    journal.check(f"{state}: the marked option is the view shown ({shown})",
                                  marked[0]["view"] == shown, marked[0]["view"])
                journal.check(f"{state}: `data-active` agrees with `aria-pressed`",
                              [b["active"] for b in buttons] == ["true" if b["pressed"] == "true" else "false"
                                                                 for b in buttons],
                              str([b["active"] for b in buttons]))
                others = {b["background"] for b in buttons if b["pressed"] != "true"}
                journal.check(f"{state}: the active option is drawn apart from the others",
                              marked[0]["background"] not in others,
                              f"active {marked[0]['background']} · others {sorted(others)}")

        # The « + » screen's choices and the drawer's appearance: switches that
        # already drew the segment, held so no one loses it.
        for state, root in (("acq-add-empty", '[data-part="screen"][data-open]'),
                            ("drawer-navigation", "#drawer[data-open]")):
            switches = await read_at(page, state, READ, root)
            journal.check(f"{state}: its switches are read", bool(switches), str(switches))
            for group in switches or []:
                buttons = group["buttons"]
                marked = [button for button in buttons if button["pressed"] == "true"]
                others = {b["background"] for b in buttons if b["pressed"] != "true"}
                journal.check(f"{state}: one option marked and drawn apart ({[b['view'] for b in buttons]})",
                              len(marked) == 1 and marked[0]["background"] not in others,
                              str([(b["view"], b["pressed"], b["background"]) for b in buttons]))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
