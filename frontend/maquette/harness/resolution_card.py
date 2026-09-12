"""R161 — the candidate card is the gesture (B-393).

THE RULING. The operator, on a phone reading « Candidats ambigus » for « Lucky »:
« Le bouton de sélection prend trop de place, c'est toute la carte média qui
doit être cliquable. » The candidate card is therefore ONE button carrying
`data-resolve`, and what stays at its right edge is a decorative affordance at
the icon size the button system offers — never the full-width pill it was.

WHAT IT READS, and each hold fails differently:

  h4. EVERY TIED CANDIDATE OFFERS THE ACT. « Lucky » ties four of its five
      candidates, which is the reason a human is asked at all; each card is a
      button carrying ITS OWN title in `data-resolve`, and a finger at the
      centre of its body lands inside that button. Held first, because the tap
      below is taken on one of them.
  h2. THE AFFORDANCE IS THE ICON SIZE, no larger AND no smaller, it is drawn,
      and it is a mark rather than a control. Its rendered box is compared with
      a probe wearing `iconButton`'s own classes, read from the factory's
      declaration through `residue.py`'s reader — so no pixel count is written
      here, and a size the component does not offer cannot pass. A button inside
      the card's button would be invalid markup and a control nobody can name,
      hence the last half.

      THE FLOOR IS HALF THE HOLD, and it was missing. A ceiling alone —
      `width <= iconWidth` — is satisfied by zero, so the whole hold stayed
      green over an affordance given `display: none`: the arithmetic ran over a
      0 × 0 box and the nature hold read a tag and an attribute a hidden node
      still carries. The only visible sign that a candidate card is an act
      could have gone with nothing in the suite falling. So the size is held
      both ways, and a second hold reads that a box exists at all and that
      `visibility` has not taken it away.
  h9. EVERY CARD IS ANNOUNCED BY ITS TITLE AND ITS YEAR, and by nothing longer.
      The card being the button, its name used to be its whole text — up to 521
      characters, opening on the poster fallback's initial where the provider
      had no picture, and identical in substance from one candidate to the next
      after the first few words. Every card is read, not the first: only the
      ones without a picture wear that initial. The name is computed by the
      browser through the devtools protocol's accessibility tree, and the
      expected one is assembled from the two data the card displays.
  h1. A TAP AT THE CENTRE OF THE CARD'S BODY RESOLVES THE FOLDER. Not the
      poster, not the affordance: the body, where a finger reading the synopsis
      lands. By a finger, never `element.click()` — the element under it has a
      `button` ancestor, the one the engine's delegation answers, carrying the
      card's title in `data-resolve`, and the folder leaves « À traiter ».

WHERE THE AFFORDANCE IS LOOKED FOR, and why two names. Before this rule the
act's mark on the card was the pill (`card/foot`); after it, the affordance
(`card/pick`). Reading both is what lets a head without the repair fail on the
pill's own box rather than on an absence nobody can read.

THE SEND IS NOT THIS RULE'S. What follows the tap — the window, the undo, the
send — is `resolution_window.py`'s (R162). This rule stops at the folder leaving
the queue, which the pick does at once.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, SETTLED, Journal, open_page
from residue import read_factories

from playwright.async_api import async_playwright

# THE SCREEN WITH TIED CANDIDATES: « Lucky », four of five at the same score.
TIED_STATE = "arr-decision"

# THE FACTORY WHOSE ONE SIZE THE AFFORDANCE IS HELD TO.
ICON_FACTORY = "iconButton"

# A RENDERED BOX IS FRACTIONAL; a box equal to the probe's must not fall on a
# rounding of the layout engine.
SUBPIXEL = 0.5

# WHAT A LISTENER CAN HOLD IN ONE HEARING. The name a candidate card announced
# before it was labelled ran 521 characters — the whole card, the poster's
# initial included — and a name that long is a name nobody waits for.
NAME_CEILING = 80

# THE SCREEN, by its own identity. An absent screen reads as an empty one, so a
# hold falls on its own number rather than on a TypeError.
SCREEN = """document.querySelector(
  '[data-part="screen"][data-open][data-key^="resolution:"]') ?? document.createElement('div')"""

# THE CANDIDATE CARDS, and what each one offers.
CANDIDATES = """() => {
  const screen = """ + SCREEN + """;
  const cards = [...screen.querySelectorAll('[data-part="card"][data-nonmedia="candidat"]')];
  return {
    folder: (screen.dataset.key || '').replace(/^resolution:/, ''),
    cards: cards.map((card) => ({
      title: (card.querySelector('[data-part="card/title"]') || {}).textContent || '',
      confidence: (card.querySelector('[data-part="chip"]') || {}).textContent || null,
      tag: card.tagName,
      resolve: card.dataset.resolve ?? null,
    })),
  };
}"""

# ONE PART OF ONE CARD, brought to the centre of the screen as a hand would.
SCROLL = """([index, part]) => {
  const screen = """ + SCREEN + """;
  const card = screen.querySelectorAll('[data-part="card"][data-nonmedia="candidat"]')[index];
  card?.querySelector('[data-part="' + part + '"]')?.scrollIntoView({block: 'center'});
}"""

# WHERE A FINGER AIMS on that part, and what it would land on.
AIM = """([index, part]) => {
  const screen = """ + SCREEN + """;
  const card = screen.querySelectorAll('[data-part="card"][data-nonmedia="candidat"]')[index];
  const target = card?.querySelector('[data-part="' + part + '"]');
  if (!target) return {found: false};
  const box = target.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  const button = hit?.closest('button') ?? null;
  return {found: true, x, y,
          inside: !!hit && card.contains(hit),
          resolve: button?.dataset.resolve ?? null,
          buttonPart: button?.dataset.part ?? null,
          covering: hit === null ? 'nothing'
            : hit.tagName + '[' + (hit.dataset?.part || '') + ']'};
}"""

# THE CANDIDATE CARDS, by a selector the protocol can take: the screen's own
# identity, then the cards, because a candidate card exists on other screens too
# and the protocol answers a document-wide query.
CANDIDATE_CARDS = ('[data-part="screen"][data-open][data-key^="resolution:"] '
                   '[data-part="card"][data-nonmedia="candidat"]')

# WHAT EACH CANDIDATE SHOULD BE ANNOUNCED BY, read from the card itself. The
# year is the subtitle's first segment; the kind and the provider that follow it
# are not part of a name. Nothing is retyped here: the expected name is
# assembled from the two data the card displays.
NAME_SUBJECTS = """() => {
  const screen = """ + SCREEN + r""";
  const cards = [...screen.querySelectorAll('[data-part="card"][data-nonmedia="candidat"]')];
  return cards.map((card) => {
    const title = (card.querySelector('[data-part="card/title"]')?.textContent || '').trim();
    const subtitle = (card.querySelector('[data-part="card/subtitle"]')?.textContent || '').trim();
    const year = (subtitle.match(/^(\d{4})\s*·/) || [])[1] || '';
    return year ? title + ' ' + year : title;
  });
}"""

# THE ACT'S MARK ON THE FIRST CANDIDATE, beside a probe wearing the icon size.
AFFORDANCE = """(classes) => {
  const screen = """ + SCREEN + """;
  const card = screen.querySelector('[data-part="card"][data-nonmedia="candidat"]');
  const mark = card?.querySelector('[data-part="card/pick"], [data-part="card/foot"]');
  const probe = document.createElement('span');
  probe.className = classes;
  document.body.appendChild(probe);
  const icon = probe.getBoundingClientRect();
  probe.remove();
  const box = mark?.getBoundingClientRect();
  return {part: mark?.dataset.part ?? null, tag: mark?.tagName ?? null,
          hidden: mark?.getAttribute('aria-hidden') === 'true',
          drawn: !!mark && getComputedStyle(mark).visibility !== 'hidden',
          width: box?.width ?? null, height: box?.height ?? null,
          iconWidth: icon.width, iconHeight: icon.height};
}"""

# WHAT « À TRAITER » HOLDS, read where the surfaces read it.
BLOCKED = "()=>(window.__queue?.().blocked || []).map((card) => card.t)"


def icon_classes():
    """Reads the classes `iconButton` declares: its base and its one size.

    Returns:
        The class list as one string, or an empty string when the button
        system declares no such factory.
    """
    factories = read_factories()[0]
    for factory in factories.values():
        if factory["name"] == ICON_FACTORY:
            sizes = [token for tokens in factory["branches"].values() for token in tokens]
            return " ".join(factory["base"] + sizes)
    return ""


async def announced_names(context, page, selector):
    """Reads what the browser announces each matching element as.

    NOT AN ATTRIBUTE, AND NOT PLAYWRIGHT'S OWN GUESS. The name is Chrome's, read
    out of the devtools protocol's accessibility tree — the same computation an
    assistive technology receives, so a name assembled from an element's whole
    text is read here exactly as it would be heard. `page.accessibility` was the
    obvious door and it is gone from Playwright 1.62; this is the door that is
    still open, and it says which node it answered for rather than trusting an
    ordering.

    EVERY MATCH, NOT THE FIRST. Only the candidates the provider has no picture
    for wear the poster's initials fallback, and those are the cards whose name
    ran longest — a hold reading the first card alone would have been green over
    the very case that opened this finding.

    Args:
        context: The browsing context, which opens the protocol session.
        page: The page.
        selector: Where the elements are looked for.

    Returns:
        One announced name per match, in document order; an empty string where
        an element has no name.
    """
    protocol = await context.new_cdp_session(page)
    await protocol.send("Accessibility.enable")
    document = await protocol.send("DOM.getDocument")
    found = await protocol.send("DOM.querySelectorAll",
                                {"nodeId": document["root"]["nodeId"], "selector": selector})
    names = []
    for node_id in found.get("nodeIds", []):
        described = await protocol.send("DOM.describeNode", {"nodeId": node_id})
        wanted = described["node"]["backendNodeId"]
        tree = await protocol.send("Accessibility.getPartialAXTree",
                                   {"nodeId": node_id, "fetchRelatives": False})
        heard = ""
        for node in tree.get("nodes", []):
            if node.get("backendDOMNodeId") == wanted:
                heard = (node.get("name") or {}).get("value", "")
                break
        names.append(heard)
    return names


async def aim_at(page, index, part):
    """Aims a finger at the centre of one part of one candidate card.

    THE SCROLL IS LET SETTLE BEFORE THE BOX IS READ: a rectangle measured in the
    same turn as the scroll answers a point the part has already left.

    Args:
        page: The page.
        index: The candidate's position among the screen's candidate cards.
        part: The `data-part` of the element aimed at, inside that card.

    Returns:
        What the aim read: the point, and what a finger there lands on.
    """
    await page.evaluate(SCROLL, [index, part])
    await page.wait_for_timeout(SETTLED)
    return await page.evaluate(AIM, [index, part])


async def pick_by_finger(page, state=TIED_STATE):
    """Opens the tied screen and taps the first candidate's body with a finger.

    Args:
        page: The page.
        state: The named state that opens the resolution screen.

    Returns:
        A `(screen, aim)` pair: the candidates as read before the tap, and what
        the finger was aimed at.
    """
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(SETTLED)
    screen = await page.evaluate(CANDIDATES)
    aim = await aim_at(page, 0, "card/body")
    if aim.get("found"):
        await page.touchscreen.tap(aim["x"], aim["y"])
    await page.wait_for_timeout(ACTED)
    return screen, aim


async def main():
    """Runs the three holds against the tied screen."""
    journal = Journal("R161 — the candidate card is the gesture")
    classes = icon_classes()
    journal.check("the button system offers an icon size", bool(classes),
                  classes or f"no {ICON_FACTORY} factory is declared")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", TIED_STATE)
        await page.wait_for_timeout(SETTLED)
        screen = await page.evaluate(CANDIDATES)
        cards = screen["cards"]

        # ── h4: every tied candidate offers the act ───────────────────────
        tied = [index for index, card in enumerate(cards) if not card["confidence"]]
        journal.check("the screen ties at least two candidates", len(tied) >= 2,
                      f"{len(tied)} tied of {len(cards)}")
        offers = []
        for index in tied:
            aim = await aim_at(page, index, "card/body")
            card = cards[index]
            offers.append({
                "title": card["title"], "tag": card["tag"], "resolve": card["resolve"],
                "landsOn": aim.get("resolve"), "covering": aim.get("covering"),
                "offered": card["tag"] == "BUTTON" and card["resolve"] == card["title"]
                and bool(aim.get("inside")) and aim.get("resolve") == card["title"],
            })
        journal.check("every tied card is a button a finger reaches, carrying its own title",
                      len(tied) >= 2 and all(offer["offered"] for offer in offers),
                      str([{key: offer[key] for key in ("title", "tag", "landsOn", "covering")}
                           for offer in offers if not offer["offered"]][:2]))

        # ── h2: the affordance, its size and its nature ───────────────────
        mark = await page.evaluate(AFFORDANCE, classes)
        journal.check(
            "the affordance IS the icon size the system offers, no larger and no smaller",
            mark["width"] is not None and mark["iconWidth"] > 0
            and abs(mark["width"] - mark["iconWidth"]) <= SUBPIXEL
            and abs(mark["height"] - mark["iconHeight"]) <= SUBPIXEL,
            f"{mark['part']} {mark['width']}×{mark['height']} against "
            f"{mark['iconWidth']}×{mark['iconHeight']}")
        journal.check(
            "and it is drawn — a box of its own, and not made invisible",
            bool(mark["width"]) and bool(mark["height"]) and mark["drawn"],
            f"{mark['part']} {mark['width']}×{mark['height']}, "
            f"visible {mark['drawn']}")
        journal.check("the affordance is a mark, not a control of its own",
                      mark["tag"] is not None and mark["tag"] != "BUTTON" and mark["hidden"],
                      f"{mark['part']} is a {mark['tag']}, aria-hidden {mark['hidden']}")

        # ── h9: what the card is announced by ─────────────────────────────
        # THE NAME IS COMPUTED BY THE BROWSER, never read off an attribute: a
        # name assembled from the card's whole text reads here exactly as an
        # assistive technology would hear it.
        expected = await page.evaluate(NAME_SUBJECTS)
        heard = await announced_names(context, page, CANDIDATE_CARDS)
        journal.check("every card is announced by its title and its year",
                      bool(expected) and heard == expected,
                      str([{"heard": one[:70], "for": want}
                           for one, want in zip(heard, expected) if one != want][:2])
                      or f"{len(heard)} names for {len(expected)} cards")
        journal.check("and by nothing longer than a listener waits for",
                      bool(heard) and all(0 < len(one) <= NAME_CEILING for one in heard),
                      str(sorted((len(one) for one in heard), reverse=True))
                      + f" against {NAME_CEILING}")

        # ── h1: a finger on the card's body resolves the folder ───────────
        before = await page.evaluate(BLOCKED)
        tapped = await pick_by_finger(page)
        after = await page.evaluate(BLOCKED)
        folder = tapped[0]["folder"]
        first = tapped[0]["cards"][0]["title"] if tapped[0]["cards"] else None
        aim = tapped[1]
        journal.check("the finger on the card's body lands on the button carrying its title",
                      first is not None and aim.get("resolve") == first,
                      f"lands on {aim.get('covering')}, whose button carries "
                      f"{aim.get('resolve')!r} for {first!r}")
        journal.check("and the tap takes the folder out of « À traiter »",
                      folder in before and folder not in after, f"{before} → {after}")

        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
