"""R162 — the send waits for the undo window, and the window stays honest (B-393).

WHY THE SEND WAITS. A candidate picked on the resolution card is answered by
the message with « Annuler », and the contract has no inverse for a resolve:
`continueStagedMedia` moves the folder to the pipeline and nothing puts it
back. So the queue's `pick` takes the folder out of the cache at once and holds
the send until the window closes, and « Annuler » cancels it.

WHAT IT READS — the queue's lists (`window.__queue()`) and the calls the mock
layer answered (`window.__mocks.answered()`), never the message's sentence:

  w1. THE SEND WAITS, IS STILL HELD ON THE MESSAGE'S LAST FRAME, THEN LEAVES.
      A finger picks; no `continueStagedMedia` is answered while the window is
      open, none at 6 500 ms — the last frame the undo is reachable on — and
      exactly one once the window has closed. It is also what gives the zeros
      below a meaning: a count of nothing, where nothing was ever going to
      leave, would be green over nothing.
  w2. « ANNULER » RETURNS THE FOLDER TO THE AMBIGUOUS STATE. A finger on the
      message's undo; the folder is back in « À traiter » at the place it held,
      its screen says « Candidats ambigus » again and offers its candidates, and
      nothing is sent once the window has passed. The undo does not reopen the
      screen — the rule opens it to read it.
  w3. « ASSOCIER » STILL RESOLVES AT ONCE. The manual search on a folder with
      no candidate is not a pick: its `continueStagedMedia` is answered with no
      window, and its message offers no undo.
  w4. A FRESH ANSWER INSIDE THE WINDOW LEAVES THE CARD OUT. The two keys are
      asked again; the queue's answer is proven fresh by its timestamp, and the
      picked folder is still absent from it — the server still holds it,
      because the send has not left.
  w5. A RESET INSIDE THE WINDOW SENDS NOTHING. `__go` clears the cache and
      re-seeds the layer; the pending send is cancelled with them, and no call
      is answered once the window would have closed.
  w6. ONE UNDO PUTS BACK ONE CARD. Pick A, pick B inside A's window, undo A: A
      is back at its index, B is still out, and B's send is the one that
      leaves. Driven through the queue's seam, because the interface shows only
      the LATEST message's « Annuler » — A's is out of a finger's reach once B
      has spoken — and the defect lives in the put-back, which the seam
      reaches exactly.

THE WINDOW'S LENGTH is named once below against `lib/queue.ts`'s constant. A
rule that waited less than the window would read the zeros of w2 and w5 before
a send could leave; w1 sees its ONE call after the same wait, so a window grown
past this rule's wait falls w1 and names it.

A window SHRUNK, though, was invisible to all seventeen holds — measured, with
the constant at 3 000: every wait here is `WINDOW_CLOSED`, and a shorter window
satisfies it exactly as a longer one does. The message would then offer a way
back for three seconds after the act had left. w1's reading at `LAST_FRAME` is
the floor that says so.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, SETTLED, Journal, open_page
from resolution_card import BLOCKED, CANDIDATES, SCREEN, TIED_STATE, pick_by_finger

from playwright.async_api import async_playwright

# THE UNDO WINDOW, `UNDO_WINDOW_MILLISECONDS` in `lib/queue.ts` (7 s: the
# message's own 6 s with a margin), plus an act's redraw for the send to land.
UNDO_WINDOW = 7000
WINDOW_CLOSED = UNDO_WINDOW + ACTED

# THE MESSAGE'S LAST REACHABLE FRAME, measured at 6 500 ms after the tap: from
# 7 000 ms the host is hidden and the point answers whatever is behind it. A
# send read as ABSENT here is the only thing that tells this window from a
# shorter one — every other reading below waits `WINDOW_CLOSED`, which any
# window under 7 s satisfies just as well, so a window silently brought to 3 s
# would leave the message offering a way back five seconds after the act had
# gone. Measured: with the constant at 3 000 the whole rule stayed green.
LAST_FRAME = 6500

# THE STATE WITH A FOLDER NO PROVIDER ANSWERED, where « Associer » is the way out.
LOADED_STATE = "arr-loaded"

# EVERY SEND OF A RESOLVE THE LAYER ANSWERED, by the folder it names.
SENDS = """()=>(window.__mocks?.answered() || [])
  .filter((call) => call.operationId === 'continueStagedMedia')
  .map((call) => decodeURIComponent(call.path))"""

# THE QUEUE'S LISTS, by title.
LISTS = """()=>({
  blocked: (window.__queue?.().blocked || []).map((card) => card.t),
  stuck: (window.__queue?.().stuck || []).map((card) => card.t)})"""

# WHEN THE QUEUE WAS LAST ANSWERED, in the dense scenario the tied screen uses.
QUEUE_ANSWERED_AT = """()=>window.__queries?.getQueryCache()
  .find({queryKey: ['/api/acquisition/to-handle', 'loaded'], exact: true})?.state.dataUpdatedAt ?? 0"""

# THE RESOLUTION SCREEN'S OWN REASON AND ITS CANDIDATES, once reopened. The
# reason is the chip under the folder's heading, a direct child of the screen's
# body — never a chip inside a card: the settled decisions below carry « Candidats
# ambigus » too, and reading them would hold the folder to somebody else's reason.
REOPENED = """() => {
  const screen = """ + SCREEN + """;
  return {
    reasons: [...screen.querySelectorAll(
      '[data-region="screen-resolution/body"] > [data-part="card/meta"] > [data-part="chip"]')]
      .map((chip) => chip.textContent.trim()),
    candidates: screen.querySelectorAll('[data-part="card"][data-resolve]').length,
  };
}"""

# ONE ELEMENT FOUND BY SELECTOR (and, when given, a word of its label), brought
# to the centre of the screen as a hand would.
SCROLL_TO = """([selector, word]) => {
  const one = [...document.querySelectorAll(selector)]
    .find((element) => !word || (element.textContent || '').includes(word));
  one?.scrollIntoView({block: 'center'});
}"""

# WHERE A FINGER AIMS on that element, and whether it would land on it.
AIM_AT = """([selector, word]) => {
  const one = [...document.querySelectorAll(selector)]
    .find((element) => !word || (element.textContent || '').includes(word));
  if (!one) return {found: false};
  const box = one.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, label: (one.textContent || '').trim(),
          reachable: !!hit && (hit === one || one.contains(hit)),
          covering: hit === null ? 'nothing' : hit.tagName};
}"""

# THE OPERATOR TYPES, through the field's own setter: React holds the input, and
# assigning `.value` directly is a write React never hears.
TYPE = """(text)=>{
  const field = document.querySelector('#addq');
  if (!field) return false;
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(field, text);
  field.dispatchEvent(new Event('input', {bubbles: true}));
  return true;
}"""


async def tap(page, selector, word=""):
    """Taps the element a selector finds, by a finger at its own centre.

    Args:
        page: The page.
        selector: Where the element is looked for.
        word: A word its label carries, when the selector finds several.

    Returns:
        What the aim read, with `tapped` saying whether a finger went down.
    """
    await page.evaluate(SCROLL_TO, [selector, word])
    await page.wait_for_timeout(SETTLED)
    aim = await page.evaluate(AIM_AT, [selector, word])
    aim["tapped"] = bool(aim.get("found") and aim.get("reachable"))
    if aim["tapped"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
    return aim


async def send_waits_then_leaves(page, journal):
    """w1 — no send while the window is open, one once it has closed.

    THE READING AT `LAST_FRAME` IS THE WINDOW'S LENGTH, and it is why this
    scenario waits in two steps rather than one: the send must still be held on
    the last frame a finger can reach the undo on, which no other hold reads.
    """
    screen, _ = await pick_by_finger(page)
    folder = screen["folder"]
    early = await page.evaluate(SENDS)
    await page.wait_for_timeout(LAST_FRAME - ACTED)
    on_the_last_frame = await page.evaluate(SENDS)
    await page.wait_for_timeout(WINDOW_CLOSED - LAST_FRAME)
    late = await page.evaluate(SENDS)
    journal.check("the pick's send waits while the window is open", early == [], str(early))
    journal.check("and is still held on the message's last reachable frame",
                  on_the_last_frame == [], f"at {LAST_FRAME} ms: {on_the_last_frame}")
    journal.check("and leaves once, for the folder, when the window closes",
                  len(late) == 1 and late[0].endswith(f"/{folder}/continue"), str(late))


async def undo_returns_the_folder(page, journal):
    """w2 — « Annuler » under a finger puts the folder back, and nothing is sent."""
    await page.evaluate("(id)=>window.__go(id)", TIED_STATE)
    await page.wait_for_timeout(SETTLED)
    before = await page.evaluate(BLOCKED)
    screen, _ = await pick_by_finger(page)
    folder = screen["folder"]
    undo = await tap(page, "#toastundo")
    await page.wait_for_timeout(ACTED)
    after = await page.evaluate(BLOCKED)
    journal.check("the message's « Annuler » is under the finger", undo["tapped"],
                  f"found {undo.get('found')}, covered by {undo.get('covering')}")
    journal.check("the folder is back in « À traiter », at the place it held",
                  folder in before and folder in after
                  and after.index(folder) == before.index(folder), f"{before} → {after}")
    await page.evaluate("(folder)=>window.__screens.resolution(folder)", folder)
    await page.wait_for_timeout(SETTLED)
    reopened = await page.evaluate(REOPENED)
    journal.check("its screen says « Candidats ambigus » again and offers its candidates",
                  "Candidats ambigus" in reopened["reasons"] and reopened["candidates"] >= 2,
                  str(reopened))
    await page.wait_for_timeout(WINDOW_CLOSED)
    journal.check("and nothing is sent once the window has passed",
                  await page.evaluate(SENDS) == [], str(await page.evaluate(SENDS)))


async def associate_resolves_at_once(page, journal):
    """w3 — the manual path's « Associer » is answered with no window and no undo."""
    await page.evaluate("(id)=>window.__go(id)", LOADED_STATE)
    await page.wait_for_timeout(SETTLED)
    steps = [await tap(page, '[data-part="card/foot"]', "Résoudre")]
    await page.wait_for_timeout(ACTED)
    steps.append(await tap(page, "[data-manual]"))
    await page.wait_for_timeout(ACTED)
    await page.evaluate(TYPE, "star wars")
    await page.wait_for_timeout(ACTED)
    steps.append(await tap(page, '[data-part="result/list"] [data-part="card/body"]'))
    await page.wait_for_timeout(ACTED)
    steps.append(await tap(page, '#sheet [data-part="sheet/action"][data-tone="primary"]',
                           "Associer"))
    await page.wait_for_timeout(ACTED)
    await page.evaluate("()=>window.__mocks?.quiet()")
    sends = await page.evaluate(SENDS)
    offers_undo = await page.evaluate("()=>!!window.__toast?.read().message?.undo")
    journal.check("the walk to « Associer » is taken by a finger at every step",
                  all(step["tapped"] for step in steps),
                  str([step.get("label", step.get("covering"))[:30] for step in steps
                       if not step["tapped"]]))
    journal.check("« Associer » resolves at once — its send answered with no window",
                  len(sends) == 1, str(sends))
    journal.check("and its message offers no undo", not offers_undo)


async def fresh_answer_leaves_the_card_out(page, journal):
    """w4 — the two keys asked again inside the window; the folder stays out."""
    screen, _ = await pick_by_finger(page)
    folder = screen["folder"]
    answered_before = await page.evaluate(QUEUE_ANSWERED_AT)
    await page.evaluate("""()=>Promise.all([
      window.__queries.refetchQueries({queryKey: ['/api/acquisition/to-handle'], type: 'all'}),
      window.__queries.refetchQueries({queryKey: ['/api/staging/media'], type: 'all'})])""")
    await page.evaluate("()=>window.__mocks?.quiet()")
    await page.wait_for_timeout(SETTLED)
    answered_after = await page.evaluate(QUEUE_ANSWERED_AT)
    blocked = await page.evaluate(BLOCKED)
    journal.check("the queue is answered afresh inside the window",
                  answered_after > answered_before, f"{answered_before} → {answered_after}")
    journal.check("and the picked folder is still out of « À traiter »",
                  folder != "" and folder not in blocked, f"{folder!r} in {blocked}")


async def reset_sends_nothing(page, journal):
    """w5 — a named state inside the window cancels the pending send."""
    screen, _ = await pick_by_finger(page)
    folder = screen["folder"]
    picked = folder not in await page.evaluate(BLOCKED)
    await page.evaluate("(id)=>window.__go(id)", "arr-idle")
    await page.wait_for_timeout(WINDOW_CLOSED)
    sends = await page.evaluate(SENDS)
    journal.check("the pick had taken the folder out when the reset came", picked, folder)
    journal.check("and a reset inside the window sends nothing afterwards", sends == [], str(sends))


async def one_undo_puts_back_one_card(page, journal):
    """w6 — pick A, pick B, undo A: A at its index, B out and sent alone."""
    await page.evaluate("(id)=>window.__go(id)", TIED_STATE)
    await page.wait_for_timeout(SETTLED)
    before = await page.evaluate(LISTS)
    first = before["blocked"][0] if before["blocked"] else ""
    second = before["stuck"][0] if before["stuck"] else ""
    seam = await page.evaluate("""([first, second]) => {
      const actions = window.__queueActions;
      if (typeof actions?.pick !== 'function') return false;
      window.__undoFirstPick = actions.pick(first, first);
      actions.pick(second, second);
      if (typeof window.__undoFirstPick !== 'function') return false;
      window.__undoFirstPick();
      return true;
    }""", [first, second])
    await page.wait_for_timeout(SETTLED)
    after = await page.evaluate(LISTS)
    sends_now = await page.evaluate(SENDS)
    journal.check("the queue's pick answers an undo", seam)
    journal.check("undoing the first pick puts it back at its index",
                  seam and first in after["blocked"]
                  and after["blocked"].index(first) == before["blocked"].index(first),
                  f"{before['blocked']} → {after['blocked']}")
    journal.check("while the second stays out, its send still waiting",
                  seam and second not in after["stuck"] and sends_now == [],
                  f"{after['stuck']}, sent {sends_now}")
    await page.wait_for_timeout(WINDOW_CLOSED)
    sends_later = await page.evaluate(SENDS)
    journal.check("and the second's send is the one that leaves",
                  seam and len(sends_later) == 1 and sends_later[0].endswith(f"/{second}/continue"),
                  str(sends_later))


async def main():
    """Runs the six holds, each from a named state of its own."""
    journal = Journal("R162 — the send waits for the undo window")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await send_waits_then_leaves(page, journal)
        await undo_returns_the_folder(page, journal)
        await associate_resolves_at_once(page, journal)
        await fresh_answer_leaves_the_card_out(page, journal)
        await reset_sends_nothing(page, journal)
        await one_undo_puts_back_one_card(page, journal)
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
