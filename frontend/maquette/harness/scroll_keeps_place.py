"""R175 — the in-flight list keeps the reader's place, and one gesture moves one container.

B-490, reported by the operator: « double scroll systématique sur
Acquisition › En cours ; dès que le scroll arrive au niveau de Lucky on remonte
automatiquement en haut de la page ». Two facts in one sentence, and two
mechanisms under them.

THE JUMP (B-490) is the scroll restoration's late re-application. A return to
the page (« Résoudre → » on Lucky's card, then Back) restores the remembered
offset and then subscribes to the `load` of every poster not yet complete, to
put the offset back once late content has settled. The posters below the fold
load LAZILY, so the last of them loads when the reader scrolls down to it — and
its `load` wrote the arrival offset over the reader's own. Lucky is the card the
detour starts from, and the first unloaded posters sit just below it: the
operator's reading was exact.

THE DOUBLE SCROLL (B-491) is the desktop frame. Out of it, `.device` stops
clipping, and the closed sheet — translated below the bottom edge with its drag
band — gives the DOCUMENT 89 px of scrollable overflow beside `#port`. A wheel
over the header then moves the document; a wheel over the list moves the port.

WHAT IT HOLDS, by finger and by wheel, at the phone width, at a desktop width in
the frame (both paths) and out of it (the fresh arrival and the header):

  the walk      a downward gesture repeated from the top of « En cours » to the
                end of the list, past Lucky's card, on a FRESH arrival and on a
                RETURN from the resolution. The port never goes back up under a
                downward gesture, not even after the last poster has loaded.
  one container every gesture moves at most one scroll container, and it is
                `#port`.
  the header    a gesture over the shell's header moves no container: the
                document has nothing to scroll.
  the detour    the return really went through the restoration with posters
                still to load — without it the walk's holds would pass over a
                path that cannot jump.

WHAT IT DOES NOT READ: the restoration's own promise on a return (R94's), the
retry budget, or a layer's offset. A real finger on a real phone is not a
synthesised gesture; the gesture here is the browser's own scroll gesture over
CDP, which is the closest a harness gets.
"""
import asyncio
import json
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PAGE_PATHS, PHONE, PROTOTYPE, SETTLED, Journal, open_page  # noqa: E402

# The desktop the operator reads the prototype on, out of the frame (B-344).
# Two contexts per width, because a context that declares touch is not the
# desktop a wheel comes from.
DESKTOP_WHEEL = {"viewport": {"width": 1440, "height": 900},
                 "is_mobile": False, "has_touch": False, "color_scheme": "dark"}
DESKTOP_FINGER = {**DESKTOP_WHEEL, "has_touch": True}
LABEL = '[data-part="harness/desktop-switch-label"]'

PORT = "#port"
HEADER = '[data-part="shell/header"]'
# The blocked card — Lucky in the operator's report — found by the title its own
# seed carries, read here rather than typed, so the rule follows the fixture.
BLOCKED_SEED = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds/blocked.json"
BLOCKED_TITLE = json.loads(BLOCKED_SEED.read_text(encoding="utf-8"))[0]["title"]

# One gesture's length. The operator's report is a scroll, not a fling; forty
# pixels is short enough that the jump lands between two readings, never inside
# one gesture.
STEP = 40
# Enough steps for the longest list at the narrowest width, with room to spare.
MOST_STEPS = 80
# A gesture has settled when the scroll and any image it brought into range
# have: the jump was measured 1 ms after a poster's `load`.
GESTURE_SETTLED = 300
# The walk is not over when the port reaches its end: the last lazy poster may
# still be arriving, and its `load` is what used to move the port.
LATE = 1200

# Every element's offset, keyed by an identity that survives the reading. The
# key is a counter kept in a WeakMap, so reading adds nothing to the markup.
OFFSETS = """() => {
  window.__scrollIdentity ??= { map: new WeakMap(), next: 0 };
  const identity = window.__scrollIdentity;
  const name = (element) => {
    if (!identity.map.has(element)) identity.map.set(element, identity.next++);
    const part = element.getAttribute("data-part");
    return `${identity.map.get(element)}:${element.tagName.toLowerCase()}`
      + (element.id ? `#${element.id}` : "") + (part ? `[${part}]` : "");
  };
  const offsets = { document: document.scrollingElement.scrollTop };
  for (const element of document.querySelectorAll("body *"))
    if (element.scrollTop > 0) offsets[name(element)] = element.scrollTop;
  const port = document.querySelector("#port");
  return {
    offsets,
    port: port.scrollTop,
    portName: name(port),
    end: port.scrollHeight - port.clientHeight,
    documentOverflow: document.scrollingElement.scrollHeight
      - document.scrollingElement.clientHeight,
  };
}"""

CENTRE_OF = """(selector) => {
  const box = document.querySelector(selector).getBoundingClientRect();
  return { x: Math.round(box.x + box.width / 2),
           y: Math.round(box.y + Math.min(box.height / 2, 400)) };
}"""

BLOCKED_CARD = """(title) => [...document.querySelectorAll('#port [data-part="card"]')]
  .find((card) => card.querySelector('[data-part="card/title"]')?.textContent.trim() === title)"""

CARD_BOTTOM = """(title) => {
  const port = document.querySelector("#port");
  const card = (""" + BLOCKED_CARD + """)(title);
  if (!card) return null;
  return Math.round(card.getBoundingClientRect().bottom
    - port.getBoundingClientRect().top + port.scrollTop);
}"""


async def gesture(page, session, kind, selector):
    """Performs one downward gesture over an element.

    Args:
        page: The page.
        session: A CDP session on the page, for the finger.
        kind: « finger » or « wheel ».
        selector: What the gesture starts over.
    """
    centre = await page.evaluate(CENTRE_OF, selector)
    if kind == "wheel":
        await page.mouse.move(centre["x"], centre["y"])
        await page.mouse.wheel(0, STEP)
    else:
        await session.send("Input.synthesizeScrollGesture", {
            "x": centre["x"], "y": centre["y"], "yDistance": -STEP,
            "gestureSourceType": "touch", "speed": 800, "preventFling": True})
    await page.wait_for_timeout(GESTURE_SETTLED)


def moved_containers(before, after):
    """Names the containers whose offset changed between two readings.

    Args:
        before: The offsets before the gesture.
        after: The offsets after it.

    Returns:
        The sorted names of the containers that moved.
    """
    names = set(before) | set(after)
    return sorted(name for name in names if before.get(name, 0) != after.get(name, 0))


async def arrive(browser, options, out_of_frame):
    """Opens « En cours » at its own address, in or out of the frame.

    Args:
        browser: The launched browser.
        options: The context's options.
        out_of_frame: Whether to press the desktop switch first.

    Returns:
        The (context, page) pair on the settled page.
    """
    context, page = await open_page(browser, **options)
    if out_of_frame:
        await page.click(LABEL)
        await page.wait_for_timeout(SETTLED)
    await page.goto(PROTOTYPE.rstrip("/") + PAGE_PATHS["acq"], wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.evaluate("()=>window.__mocks?.quiet?.()")
    await page.wait_for_timeout(SETTLED)
    return context, page


async def detour(page):
    """Opens the resolution from the blocked card and comes back.

    Returns:
        Where the detour went, where it came back to, and how many posters of
        the list were still to load when it came back.
    """
    await page.evaluate(
        "(title)=>(" + BLOCKED_CARD + ")(title).querySelector('[data-part=\"card/foot\"]').click()",
        BLOCKED_TITLE)
    await page.evaluate("()=>window.__mocks?.quiet?.()")
    await page.wait_for_timeout(ACTED)
    went = await page.evaluate("()=>location.pathname")
    await page.evaluate("()=>history.back()")
    await page.evaluate("()=>window.__mocks?.quiet?.()")
    # Read while the restoration is still waiting on them: this is the number
    # of `load` events that each used to be able to move the port.
    await page.wait_for_timeout(GESTURE_SETTLED)
    pending = await page.evaluate(
        "()=>[...document.querySelectorAll('#port img')].filter((image)=>!image.complete).length")
    back = await page.evaluate("()=>location.pathname")
    return {"went": went, "back": back, "pending": pending}


async def walk(page, session, kind):
    """Walks the list to its end with one downward gesture at a time.

    Returns:
        Every step's port offset and moved containers, the decreases seen, the
        largest offset reached, and the end of the list.
    """
    reading = await page.evaluate(OFFSETS)
    port_name = reading["portName"]
    steps, decreases, crossings = [], [], []
    at_end = 0
    for _ in range(MOST_STEPS):
        before = reading
        await gesture(page, session, kind, PORT)
        reading = await page.evaluate(OFFSETS)
        moved = moved_containers(before["offsets"], reading["offsets"])
        steps.append(reading["port"])
        if reading["port"] < before["port"]:
            decreases.append((before["port"], reading["port"]))
        if len(moved) > 1 or (moved and moved[0] != port_name):
            crossings.append((before["port"], moved))
        at_end = at_end + 1 if reading["port"] >= reading["end"] - 1 else 0
        if at_end >= 3:
            break
    last = reading["port"]
    await page.wait_for_timeout(LATE)
    late = await page.evaluate(OFFSETS)
    if late["port"] < last:
        decreases.append((last, late["port"]))
    return {"steps": steps, "decreases": decreases, "crossings": crossings,
            "reached": max(steps + [late["port"]]), "end": late["end"],
            "atEnd": late["port"] >= late["end"] - 1}


async def header_gesture(page, session, kind):
    """Performs one downward gesture over the shell's header.

    Returns:
        The containers that moved, and the document's scrollable overflow.
    """
    before = await page.evaluate(OFFSETS)
    await gesture(page, session, kind, HEADER)
    after = await page.evaluate(OFFSETS)
    return {"moved": moved_containers(before["offsets"], after["offsets"]),
            "overflow": after["documentOverflow"]}


async def hold(journal):
    """Walks « En cours » at both widths, by finger and by wheel, fresh and after a detour."""
    # THE JUMP IS READ WHERE IT CAN HAPPEN. Out of the frame at 1440 x 900 the
    # browser loads every lazy poster of this list at once — nothing is still
    # loading on the return, so the path there cannot fall and holding it would
    # be a green nobody earned. The phone and the desktop IN the frame, the
    # operator's default, keep posters below the fold; out of the frame is where
    # the double scroll lives, and it is walked fresh and over the header.
    both = ("fresh arrival", "return from the resolution")
    frames = (
        ("phone", {"finger": PHONE, "wheel": PHONE}, False, both),
        ("desktop in the frame",
         {"finger": DESKTOP_FINGER, "wheel": DESKTOP_WHEEL}, False, both),
        ("desktop out of the frame",
         {"finger": DESKTOP_FINGER, "wheel": DESKTOP_WHEEL}, True, ("fresh arrival",)),
    )
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        for width, contexts, out_of_frame, paths in frames:
            for kind in ("finger", "wheel"):
                for path in paths:
                    label = f"{width}, {kind}, {path}"
                    context, page = await arrive(browser, contexts[kind], out_of_frame)
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    session = await context.new_cdp_session(page)
                    if path != "fresh arrival":
                        went = await detour(page)
                        journal.check(
                            f"{label}: the return went through the restoration with posters still to load",
                            went["went"].startswith("/resolution")
                            and went["back"] == PAGE_PATHS["acq"]
                            and went["pending"] > 0,
                            f"went to {went['went']!r}, came back to {went['back']!r} "
                            f"with {went['pending']} poster(s) still loading — with "
                            "none, the late re-application has nothing to fire on "
                            "and the walk below cannot fall")
                    bottom = await page.evaluate(CARD_BOTTOM, BLOCKED_TITLE)
                    walked = await walk(page, session, kind)
                    journal.check(
                        f"{label}: the walk passed {BLOCKED_TITLE}'s card and reached the end of the list",
                        bottom is not None and walked["atEnd"]
                        and walked["reached"] > 0,
                        f"card bottom at {bottom}, reached {walked['reached']} of "
                        f"{walked['end']} in {len(walked['steps'])} gesture(s)")
                    journal.check(
                        f"{label}: the port never goes back up under a downward gesture",
                        not walked["decreases"],
                        f"decreases (from, to): {walked['decreases']} — a late "
                        "`load` writing the arrival offset over the reader's own "
                        "is B-490")
                    journal.check(
                        f"{label}: every gesture over the list moves at most one container, the port",
                        not walked["crossings"],
                        f"gestures that moved another container (at offset, moved): "
                        f"{walked['crossings'][:3]}")
                    if path == "fresh arrival":
                        header = await header_gesture(page, session, kind)
                        journal.check(
                            f"{width}, {kind}: a gesture over the header moves no container",
                            not header["moved"] and header["overflow"] <= 0,
                            f"moved {header['moved']}, the document overflows by "
                            f"{header['overflow']} px — a second scroll container "
                            "beside the port is B-491")
                    await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal("R175 — the in-flight list keeps the reader's place, one gesture moves one container")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
