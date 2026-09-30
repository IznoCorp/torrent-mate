"""R161 — the candidate card is the gesture (B-393).

THE RULING. The operator, on a phone reading « Candidats ambigus » for « Lucky »:
« Le bouton de sélection prend trop de place, c'est toute la carte média qui
doit être cliquable. » The candidate card is therefore ONE button carrying
`data-resolve`, and what stays at its right edge is a decorative affordance —
never the full-width pill it was.

THE SECOND RULING (B-500). A check mark on every candidate read as « already
selected », and nothing said the card was there to be chosen. The operator chose
the affordance: « Choisir » on every candidate — primary, a finger's height —
and no check mark before the pick. It is the interface's primary action button
(R-conformity-p, `hold_one_primary_action` below), no longer a pill of its own.

WHAT IT READS, and each hold fails differently:

  h4. EVERY TIED CANDIDATE OFFERS THE ACT. « Lucky » ties four of its five
      candidates, which is the reason a human is asked at all; each card's
      « Choisir » is a button carrying ITS OWN title in `data-resolve`, and a
      finger at its centre lands inside that button. Held first, because the
      tap below is taken on one of them. RE-AIMED with B-578's end (his 09-29
      word, « seul le bouton « Choisir » choisit »): it read the body.
  h2. EVERY CARD OFFERS THE « CHOISIR » PILL, AND NO CARD IS MARKED. RE-AIMED,
      and said so: this hold used to read ONE affordance held to the icon
      button's size — the check mark B-500 retired. It now reads EVERY
      candidate card: its `card/pick` says the word `fr.json` holds for it, is
      drawn (a box, not made invisible) at least a finger tall, is painted in
      the primary ground (compared with a probe wearing `bg-primary`, so no
      colour is written here), and is a BUTTON of its own — it was a mark
      inside the body's button, `aria-hidden`, until B-578's end made it the
      only control that picks. And no pill carries a drawing: the check mark
      inside it is the « already selected » the ruling removed, whatever else
      the pill says.
  h12. A FINGER ON A CANDIDATE'S POSTER, OR ON ITS BODY, OPENS ITS SHEET, AND
      PICKS NOTHING (B-578). The operator touched a candidate's poster « en
      espérant en savoir plus » and it picked it; his 09-29 word: « toucher
      l'affiche ou la carte d'un candidat OUVRE SA FICHE ». For each of the two,
      the finger at its centre lands on a button carrying the candidate's title
      in `data-mediasheet`, the tap opens the medium's sheet, and the folder is
      still in « À traiter » after it. And Retour from that sheet comes back to
      the resolution screen (§ 16: a link inside a page stacks). RE-AIMED with
      B-578's end: it read the poster alone, and « a touch on its body still
      picks » is what his word retired.
  h10. EVERY CARD IS AT LEAST A FINGER TALL. The act is the whole card now, so
      the card IS the touch target and it owes the 44 px every other one in this
      harness owes. It measures 126, and a floor is written for the day the room
      goes: nothing else in the suite would have caught a card of 20 px.
  h11. AND EACH HOLDS EXACTLY THREE FOCUSABLE ELEMENTS — ITS POSTER, ITS BODY
      AND ITS PICK. RE-AIMED twice, and said so: the card was one button and
      held exactly one; with B-578's poster it held two; with its end, the
      poster and the body open the sheet and « Choisir » picks, and a fourth
      would be a control nobody asked for. Counted, not asserted: every
      focusable inside the card, `tabindex="-1"` and disabled controls left out
      because neither takes a tab.
  h9. EVERY PICK IS ANNOUNCED BY ITS WORD, ITS TITLE AND ITS YEAR, and by
      nothing longer. The card being the button, its name used to be its whole
      text — up to 521 characters, opening on the poster fallback's initial
      where the provider had no picture, and identical in substance from one
      candidate to the next after the first few words; five « Choisir » alone
      would be five identical names. Every pick is read, not the first. The
      name is computed by the browser through the devtools protocol's
      accessibility tree, and the expected one is assembled from the word and
      the two data the card displays.
  h1. A TAP AT THE CENTRE OF « CHOISIR » RESOLVES THE FOLDER. By a finger,
      never `element.click()` — the element under it is (or has as ancestor)
      the `button` the engine's delegation answers, carrying the card's title in
      `data-resolve`, and the folder leaves « À traiter ». RE-AIMED with B-578's
      end: it tapped the body.

WHERE THE AFFORDANCE IS LOOKED FOR, and why two names. Before this rule the
act's mark on the card was the pill (`card/foot`); after it, the affordance
(`card/pick`). Reading both is what lets a head without the repair fail on the
pill's own box rather than on an absence nobody can read.

THE SEND IS NOT THIS RULE'S. What follows the tap — the window, the undo, the
send — is `resolution_window.py`'s (R162). This rule stops at the folder leaving
the queue, which the pick does at once.

RE-AIMED when the queue's cards took the contract's names: a card's title is
read as `title` (it was the engine's `t`). The holds and what they compare are
unchanged.

R-conformity-p — ONE PRIMARY ACTION (`hold_one_primary_action`, in its own
context): the pick and the settings' save are one button.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, SETTLED, Journal, open_page, read_at, chrome_launch_args

from playwright.async_api import async_playwright

# THE SCREEN WITH TIED CANDIDATES: « Lucky », four of five at the same score.
TIED_STATE = "acq-resolution-tie"

# THE WORD THE PILL SAYS, read from the resource the interface reads it from.
CHOOSE = json.loads((pathlib.Path(__file__).resolve().parents[1] / "design" / "src"
                     / "i18n" / "fr.json").read_text(encoding="utf-8"))[
    "screens"]["resolution"].get("choose")

# WHAT A FINGER NEEDS, and it is the figure every touch-target rule in this
# harness holds: 44 px. The card measures 126 today, so this is a floor with
# eighty px of room — a floor's job is to be there when the room goes.
TOUCH_FLOOR = 44

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
      // THE PICK IS THE BUTTON CARRYING `data-resolve` — « Choisir » since
      // B-578's end, the body before it, the card itself before that.
      tag: (card.matches('[data-resolve]') ? card : card.querySelector('[data-resolve]'))?.tagName ?? null,
      resolve: (card.matches('[data-resolve]') ? card : card.querySelector('[data-resolve]'))?.dataset.resolve ?? null,
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
          sheet: button?.dataset.mediasheet ?? null,
          buttonPart: button?.dataset.part ?? null,
          covering: hit === null ? 'nothing'
            : hit.tagName + '[' + (hit.dataset?.part || '') + ']'};
}"""

# THE CANDIDATE CARDS, by a selector the protocol can take: the screen's own
# identity, then the cards, because a candidate card exists on other screens too
# and the protocol answers a document-wide query.
CANDIDATE_CARDS = ('[data-part="screen"][data-open][data-key^="resolution:"] '
                   '[data-part="card"][data-nonmedia="candidat"] [data-resolve]')

# WHAT EACH CANDIDATE'S PICK SHOULD BE ANNOUNCED BY, read from the card itself
# and the resource. The year is the subtitle's first segment; the kind and the
# provider that follow it are not part of a name. Nothing is retyped here: the
# expected name is the pick's word, then the two data the card displays.
NAME_SUBJECTS = """(choose) => {
  const screen = """ + SCREEN + r""";
  const cards = [...screen.querySelectorAll('[data-part="card"][data-nonmedia="candidat"]')];
  return cards.map((card) => {
    const title = (card.querySelector('[data-part="card/title"]')?.textContent || '').trim();
    const subtitle = (card.querySelector('[data-part="card/subtitle"]')?.textContent || '').trim();
    const year = (subtitle.match(/^(\d{4})\s*·/) || [])[1] || '';
    return choose + ' ' + (year ? title + ' ' + year : title);
  });
}"""

# EACH CANDIDATE CARD'S OWN BOX, and what can take a finger or a keyboard
# inside it: the poster and the body, each opening the sheet, and the pick.
CARD_BOXES = """() => {
  const screen = """ + SCREEN + """;
  const cards = [...screen.querySelectorAll('[data-part="card"][data-nonmedia="candidat"]')];
  const FOCUSABLE = 'a[href], button, input, select, textarea, [tabindex], [contenteditable]';
  return cards.map((card) => {
    const box = card.getBoundingClientRect();
    const inside = [...card.querySelectorAll(FOCUSABLE)]
      .filter((one) => one.getAttribute('tabindex') !== '-1' && !one.disabled);
    return {
      height: box.height, width: box.width,
      tag: card.tagName,
      focusable: (card.matches(FOCUSABLE) ? 1 : 0) + inside.length,
      sheets: card.querySelectorAll('button[data-mediasheet]').length,
      pick: !!card.querySelector('button[data-resolve]'),
      within: inside.map((one) => one.tagName + '[' + (one.dataset.part || '') + ']'),
    };
  });
}"""

# EVERY CANDIDATE'S PILL, beside a probe wearing the primary ground.
PILLS = """() => {
  const screen = """ + SCREEN + """;
  const cards = [...screen.querySelectorAll('[data-part="card"][data-nonmedia="candidat"]')];
  const probe = document.createElement('span');
  probe.className = 'bg-primary';
  document.body.appendChild(probe);
  const primary = getComputedStyle(probe).backgroundColor;
  probe.remove();
  return cards.map((card) => {
    const pill = card.querySelector('[data-part="card/pick"]');
    const box = pill?.getBoundingClientRect();
    return {title: (card.querySelector('[data-part="card/title"]')?.textContent || '').trim(),
            tag: pill?.tagName ?? null,
            text: (pill?.textContent || '').trim(),
            hidden: pill?.getAttribute('aria-hidden') === 'true',
            drawn: !!pill && getComputedStyle(pill).visibility !== 'hidden'
                   && !!box && box.width > 0 && box.height > 0,
            height: box?.height ?? 0,
            primary: !!pill && getComputedStyle(pill).backgroundColor === primary,
            drawing: !!pill?.querySelector('svg')};
  });
}"""

# WHAT « À TRAITER » HOLDS, read where the surfaces read it.
BLOCKED = "()=>(window.__queue?.().blocked || []).map((card) => card.title)"


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
    """Opens the tied screen and taps the first candidate's « Choisir » with a finger.

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
    aim = await aim_at(page, 0, "card/pick")
    if aim.get("found"):
        await page.touchscreen.tap(aim["x"], aim["y"])
    await page.wait_for_timeout(ACTED)
    return screen, aim


async def hold_opens_the_sheet(page, journal, cards, part, said):
    """h12 — a finger on one part of the first candidate opens its sheet, picks nothing.

    Args:
        page: The page.
        journal: The rule's journal.
        cards: The candidates as read on the tied screen.
        part: The `data-part` aimed at (`card/poster` or `card/body`).
        said: How the journal names that part.
    """
    await page.evaluate("(id)=>window.__go(id)", TIED_STATE)
    await page.wait_for_timeout(SETTLED)
    before = await page.evaluate(BLOCKED)
    first = cards[0]["title"] if cards else None
    aim = await aim_at(page, 0, part)
    journal.check(f"the finger on a candidate's {said} lands on the button naming its sheet",
                  first is not None and aim.get("sheet") == first and aim.get("resolve") is None,
                  f"lands on {aim.get('covering')}, sheet {aim.get('sheet')!r}, "
                  f"pick {aim.get('resolve')!r} for {first!r}")
    if aim.get("found"):
        await page.touchscreen.tap(aim["x"], aim["y"])
    await page.wait_for_timeout(ACTED)
    opened = await page.evaluate(
        """()=>document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]')?.dataset.key ?? null""")
    after = await page.evaluate(BLOCKED)
    journal.check(f"and the tap on its {said} opens the candidate's sheet, the folder still to be resolved",
                  opened is not None and first is not None and first in opened
                  and set(before) == set(after),
                  f"sheet {opened!r}; « À traiter » {before} → {after}")
    back = await page.evaluate(
        """()=>{const control=document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"] [data-part="screen/back"]');
          if(!control) return null; const box=control.getBoundingClientRect();
          return {x:box.left+box.width/2, y:box.top+box.height/2};}""")
    if back:
        await page.touchscreen.tap(back["x"], back["y"])
    await page.wait_for_timeout(ACTED)
    returned = await page.evaluate(
        """()=>document.querySelector('[data-part="screen"][data-open][data-key^="resolution:"]') !== null
          && document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]') === null""")
    journal.check(f"and Retour from the sheet its {said} opened comes back to the resolution screen",
                  bool(back) and returned, f"back control {back}; resolution open again: {returned}")


async def main():
    """Runs the three holds against the tied screen."""
    journal = Journal("R161 — the candidate card is the gesture")
    journal.check("the resource holds the pill's word", bool(CHOOSE),
                  f"screens.resolution.choose = {CHOOSE!r}")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
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
            aim = await aim_at(page, index, "card/pick")
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

        # ── h2: every card offers the pill, and no card is marked ─────────
        pills = await page.evaluate(PILLS)
        journal.check(
            "every candidate card offers « Choisir », the primary action, drawn at a finger's height",
            bool(pills) and all(pill["text"] == CHOOSE and pill["drawn"]
                                and pill["height"] >= TOUCH_FLOOR for pill in pills),
            str([{key: pill[key] for key in ("title", "text", "drawn", "height")}
                 for pill in pills if not (pill["text"] == CHOOSE and pill["drawn"]
                                           and pill["height"] >= TOUCH_FLOOR)][:2])
            or f"{len(pills)} pills")
        journal.check(
            "and in the primary ground, a button of its own that no assistive technology is kept from",
            bool(pills) and all(pill["primary"] and pill["tag"] == "BUTTON"
                                and not pill["hidden"] for pill in pills),
            str([{key: pill[key] for key in ("title", "tag", "primary", "hidden")}
                 for pill in pills if not (pill["primary"] and not pill["hidden"]
                                           and pill["tag"] == "BUTTON")][:2])
            or f"{len(pills)} pills")
        journal.check(
            "and no card is marked before the pick — no drawing inside any pill",
            bool(pills) and not any(pill["drawing"] for pill in pills),
            str([pill["title"] for pill in pills if pill["drawing"]])
            or f"{len(pills)} pills, none marked")

        # ── h10, h11: the card's own floor, and its single way in ─────────
        boxes = await page.evaluate(CARD_BOXES)
        journal.check("every card is at least a finger tall",
                      bool(boxes) and all(one["height"] >= TOUCH_FLOOR for one in boxes),
                      f"{[round(one['height']) for one in boxes]} against {TOUCH_FLOOR}")
        three_ways = [one["focusable"] == 3 and one["sheets"] == 2 and one["pick"] for one in boxes]
        journal.check("and each holds exactly three focusable elements — its poster, its body and its pick",
                      bool(boxes) and all(three_ways),
                      str([{"tag": one["tag"], "focusable": one["focusable"],
                            "within": one["within"]}
                           for one, held in zip(boxes, three_ways) if not held][:2]))

        # ── h9: what the card is announced by ─────────────────────────────
        # THE NAME IS COMPUTED BY THE BROWSER, never read off an attribute: a
        # name assembled from the card's whole text reads here exactly as an
        # assistive technology would hear it.
        expected = await page.evaluate(NAME_SUBJECTS, CHOOSE)
        heard = await announced_names(context, page, CANDIDATE_CARDS)
        journal.check("every pick is announced by its word, its title and its year",
                      bool(expected) and heard == expected,
                      str([{"heard": one[:70], "for": want}
                           for one, want in zip(heard, expected) if one != want][:2])
                      or f"{len(heard)} names for {len(expected)} cards")
        journal.check("and by nothing longer than a listener waits for",
                      bool(heard) and all(0 < len(one) <= NAME_CEILING for one in heard),
                      str(sorted((len(one) for one in heard), reverse=True))
                      + f" against {NAME_CEILING}")

        # ── h12: a finger on a candidate's poster or body opens its sheet ─
        for part, said in (("card/poster", "poster"), ("card/body", "body")):
            await hold_opens_the_sheet(page, journal, cards, part, said)

        # ── h1: a finger on « Choisir » resolves the folder ───────────────
        before = await page.evaluate(BLOCKED)
        tapped = await pick_by_finger(page)
        after = await page.evaluate(BLOCKED)
        folder = tapped[0]["folder"]
        first = tapped[0]["cards"][0]["title"] if tapped[0]["cards"] else None
        aim = tapped[1]
        journal.check("the finger on « Choisir » lands on the button carrying its title",
                      first is not None and aim.get("resolve") == first,
                      f"lands on {aim.get('covering')}, whose button carries "
                      f"{aim.get('resolve')!r} for {first!r}")
        journal.check("and the tap takes the folder out of « À traiter »",
                      folder in before and folder not in after, f"{before} → {after}")

        await hold_one_primary_action(browser, journal)
        await browser.close()
    journal.summary(errors)


# state → the primary actions it offers.
PRIMARY_ACTIONS = {
    "acq-resolution-tie": '[data-part="screen"][data-open] [data-part="card/pick"]',
    "settings-edited": '#savebar [data-save]',
}
PRIMARY = """(selector)=>{
  const probe = document.createElement('span');
  probe.className = 'bg-primary';
  document.body.appendChild(probe);
  const primary = getComputedStyle(probe).backgroundColor;
  probe.remove();
  return [...document.querySelectorAll(selector)].map((action) => {
    const style = getComputedStyle(action);
    return {height: Math.round(action.getBoundingClientRect().height),
            primary: style.backgroundColor === primary,
            drawing: [style.fontSize, style.fontWeight, style.borderRadius].join(' ')};
  });
}"""


async def hold_one_primary_action(browser, journal):
    """R-conformity-p — one primary action: the pick and the save are one button.

    « Choisir » was a pill of its own beside the primary action button the
    settings' save already is. On `acq-resolution-tie` every candidate's pick,
    on `settings-edited` the save: each at least a finger tall, in the primary
    ground, and all of them one drawing — type, weight, corner.

    Args:
        browser: The launched browser; the holds read a context of their own.
        journal: The rule's journal.
    """
    drawings = set()
    context, page = await open_page(browser)
    for state, selector in PRIMARY_ACTIONS.items():
        actions = await read_at(page, state, PRIMARY, selector)
        journal.check(f"{state}: the primary action is drawn", bool(actions), selector)
        journal.check(f"{state}: at least {TOUCH_FLOOR} px, in the primary ground",
                      bool(actions) and all(one["height"] >= TOUCH_FLOOR and one["primary"] for one in actions),
                      f"{actions[:2]}")
        drawings.update(one["drawing"] for one in actions)
    await context.close()
    journal.check("the pick and the save read one drawing", len(drawings) == 1, f"{sorted(drawings)}")


if __name__ == "__main__":
    asyncio.run(main())
