"""R172 — two picks in one undo window, walked by a finger (B-396).

WHAT WAS UNREACHABLE. The seed offered exactly ONE queued folder with candidate
cards — « Lucky » — so « pick A, then pick B inside A's window » could not be
attempted at all: the second folder's resolution screen had nothing to tap. The
design's most delicate claim (§ 4.3, « « Annuler » puts back ONE card ») was
proved through `window.__queueActions` alone, which R162's w6 does and says it
does. A seam is not a finger, and the path where the put-back's index, a second
pending send and « only the latest message carries an undo » all meet was proved
by neither.

WHAT THE SEED GAINED, and it gained nothing a card did not already promise.
« S.W.A.T. » sits in the loaded staging queue and its own card reads « Deux
correspondances possibles — TVDB 328724 (2017) et TVDB 71663 (1975). Il faut
choisir. » — a folder whose reason states two candidates over a screen that
offered none. It now carries exactly those two as a pending decision. No queue
count moves, no named state's subject changes, and the two candidates are the
two the seed's own sentence names: a fixture that contradicted its own reason
would be B-369's shape wearing a new coat.

THE WALK, and every act in it is a real touch:

  t1. PICK A on « Lucky », by a finger on a candidate's body. The folder leaves
      the queue at once and its send is held for the undo window.
  t2. REACH B'S SCREEN and PICK B inside A's window, by a finger. Two sends are
      now pending at once, which nothing before this could produce. The screen
      is REACHED through the navigation seam and not by a finger, because
      neither way in works today — see `open_resolution_of`, and B-474.
  t3. ONLY THE LATEST MESSAGE CARRIES AN UNDO. A's way back is out of a finger's
      reach once B has spoken — that is the interface's own rule, and it is what
      makes the seam the only door to A's undo.
  t4. « ANNULER » ON THE LATEST PUTS BACK ONE CARD, AND ONE ONLY. B returns to
      the list it left, at the index it held; A stays out.
  t5. AND A'S SEND STILL LEAVES. The undo of B cancels B's send and nothing
      else: after the window, exactly one `continueStagedMedia` is answered, and
      it names A.
  t6. THE PUT-BACK ON A LIST THAT HAS REALLY MOVED. A third folder is settled —
      « Laisser tel quel », by a finger, through the layer's own operation —
      between the pick and the undo, so the list the card is restored into is
      SHORTER than the one it left. This is the case B-396 records as reasoned
      and not read: `putOneBack` splices at the index the card held in the
      BEFORE snapshot and `slice` absorbs an overflow. What the card must never
      do is vanish or arrive twice, and that is what is held; WHERE it lands on
      a shortened list is READ and printed, because a rule that asserted a
      position nobody has decided would be inventing a contract.

      ITS PUT-BACK GOES THROUGH THE SEAM, and t3 is the reason: the third act
      speaks, its message replaces the pick's, and the pick's way back is out of
      a finger's reach by the interface's own rule. t4 walks the undo with a
      finger on the ordinary case; what B-396 says was missing here is not the
      finger but a list that has really MOVED under the splice.

WHAT IT DOES NOT READ. The window's length and the send's waiting — R162 holds
both, with a control at the message's last reachable frame. This rule is about
what TWO picks do to one another, which is the half a single subject made
unreachable.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, SETTLED, Journal, open_page
from resolution_card import SCREEN, TIED_STATE, aim_at

from playwright.async_api import async_playwright

# THE UNDO WINDOW, `UNDO_WINDOW_MILLISECONDS` in `lib/queue.ts` (7 s), plus an
# act's redraw for a send to land. R162 owns the reading that keeps this number
# honest; here it is only « long enough that everything has settled ».
UNDO_WINDOW = 7000
WINDOW_CLOSED = UNDO_WINDOW + ACTED

# THE SECOND AMBIGUOUS FOLDER, and the list it is queued in. Its card's own
# reason names its two candidates, which is why it was chosen over inventing a
# subject.
SECOND_FOLDER = "S.W.A.T."

# THE THIRD FOLDER, left as it is so the list moves under the put-back. It is
# the one the seed describes as beyond arbitration — « Aucun arbitrage n'y
# changera rien » — so « Laisser tel quel » is the act its own card asks for,
# and it settles AT ONCE with no window of its own (`lib/queue.ts`'s `leave`
# calls `settle` directly), which is what makes it usable here.
THIRD_FOLDER = "doc_fr_2026_final"

# THE QUEUE'S TWO LISTS, by title, as the surfaces are drawn from.
LISTS = """()=>({
  blocked: (window.__queue?.().blocked || []).map((card) => card.t),
  stuck: (window.__queue?.().stuck || []).map((card) => card.t)})"""

# EVERY RESOLVE THE LAYER ANSWERED, by the folder it names.
SENDS = """()=>(window.__mocks?.answered() || [])
  .filter((call) => call.operationId === 'continueStagedMedia')
  .map((call) => decodeURIComponent(call.path).split('/').at(-2))"""

# WHETHER A PICK IS STILL WAITING, and its key. `window.__queueActions.pick`
# answers an undo the CALLER keeps; a pick taken by a finger hands that undo to
# the message, and the message is the only holder. So this is how the rule knows
# a send is still held without reading the message's own words.
HELD_KEYS = """()=>Object.keys(window.__mocks?.arrivalsByKey?.() || {})"""

# WHAT THE MESSAGE ON SCREEN OFFERS: its sentence, and whether it has a way back.
# `#toast` ALONE: a second selector `[data-part="message"]` stood beside it and no
# source emits that value, so `check-markup-contracts.py` refused it — a rule
# selecting a value nothing draws is a rule selecting nothing.
MESSAGE = """()=>({
  text: (document.querySelector('#toast')?.textContent || '').trim(),
  undo: !!document.querySelector('#toastundo')})"""

# THE FOLDER THE OPEN RESOLUTION SCREEN IS ABOUT.
OPEN_FOLDER = """()=>{
  const screen = """ + SCREEN + """;
  return (screen.dataset.key || '').replace(/^resolution:/, '');
}"""

# ONE ELEMENT CARRYING AN ATTRIBUTE WITH A GIVEN VALUE, aimed at as a hand would.
AIM_ATTRIBUTE = """([attribute, value]) => {
  const one = document.querySelector(`[${attribute}="${value}"]`);
  if (!one) return {found: false};
  one.scrollIntoView({block: 'center'});
  const box = one.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, label: (one.textContent || '').trim(),
          reachable: !!hit && (hit === one || one.contains(hit))};
}"""


async def tap_attribute(page, attribute, value):
    """Taps the one element carrying `attribute="value"`, by a finger.

    Args:
        page: The page.
        attribute: The attribute's full name, `data-` prefix included.
        value: The value it must carry.

    Returns:
        What the aim read, with `tapped` saying whether a finger went down.
    """
    await page.evaluate(AIM_ATTRIBUTE, [attribute, value])
    await page.wait_for_timeout(SETTLED)
    aim = await page.evaluate(AIM_ATTRIBUTE, [attribute, value])
    aim["tapped"] = bool(aim.get("found") and aim.get("reachable"))
    if aim["tapped"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
        await page.wait_for_timeout(ACTED)
    return aim


async def pick_first_candidate(page):
    """Taps the first candidate's body on whatever resolution screen is open."""
    aim = await aim_at(page, 0, "card/body")
    if aim.get("found"):
        await page.touchscreen.tap(aim["x"], aim["y"])
    await page.wait_for_timeout(ACTED)
    return aim


async def open_resolution_of(page, journal, folder):
    """Opens one folder's resolution screen, and it is NAVIGATION, not an act.

    NEITHER WAY IN CAN BE WALKED BY A FINGER TODAY, and both were tried:

      · the card's own « Résoudre → » carries `data-act="resolve"`, whose engine
        branch calls `screens.resolution()` with NO argument — it answers the
        FIRST stuck folder whatever card was tapped (`lib/queue.ts` says so in
        its own words);
      · the folder PANEL's « Résoudre → » carries `data-resolve="<folder>"`, and
        the engine's `dataset.resolve` branch reads that attribute as the CHOSEN
        CANDIDATE for `currentState().resolveTarget` — so pressing it resolves
        whatever screen was last opened, naming the folder as the pick. Measured
        here before it was filed: with « Lucky »'s screen current, a finger on
        « S.W.A.T. »'s panel act answered « Identifié comme « S.W.A.T. » » about
        « Lucky ». Filed as **B-474**; the engine's branch ORDER is not this
        wave's to change (D5).

    So the screen is reached through `window.__screens.resolution`, which is
    NAVIGATION and the seam every rule in this harness navigates with. What
    B-396 asks to be a finger is the PICK, and every pick below is one.

    Args:
        page: The page.
        journal: Where the verdict goes.
        folder: The folder wanted.

    Returns:
        The folder the open screen is about.
    """
    await page.evaluate("(name)=>window.__screens.resolution(name)", folder)
    await page.wait_for_timeout(SETTLED)
    opened = await page.evaluate(OPEN_FOLDER)
    journal.check(
        f"« {folder} »'s own resolution screen opens",
        opened == folder,
        f"the open screen is about {opened!r}",
    )
    return opened


async def open_second_screen(page, journal):
    """Opens the second ambiguous folder's resolution screen."""
    return await open_resolution_of(page, journal, SECOND_FOLDER)


async def open_third_screen(page, journal):
    """Opens the third folder's resolution screen."""
    return await open_resolution_of(page, journal, THIRD_FOLDER)


async def two_picks(page, journal):
    """t1–t5 — two picks in one window, the undo, and the surviving send."""
    await page.evaluate("() => window.__mocks.reset()")
    await page.evaluate("(id)=>window.__go(id)", TIED_STATE)
    await page.wait_for_timeout(SETTLED)
    before = await page.evaluate(LISTS)
    first_folder = await page.evaluate(OPEN_FOLDER)

    # ── t1 ──────────────────────────────────────────────────────────────────
    first = await pick_first_candidate(page)
    after_first = await page.evaluate(LISTS)
    journal.check("the first folder is picked by a finger", first.get("found", False),
                  f"{first_folder!r}")
    journal.check(
        "and it leaves the queue at once",
        first_folder not in after_first["blocked"] + after_first["stuck"],
        f"{before['blocked']} → {after_first['blocked']}",
    )

    # ── t2 ──────────────────────────────────────────────────────────────────
    await open_second_screen(page, journal)
    index_before = await page.evaluate(LISTS)
    second = await pick_first_candidate(page)
    after_second = await page.evaluate(LISTS)
    sends_now = await page.evaluate(SENDS)
    journal.check("the second folder is picked INSIDE the first one's window",
                  second.get("found", False), f"{SECOND_FOLDER!r}")
    journal.check(
        "and both are out with neither send gone",
        first_folder not in after_second["blocked"] + after_second["stuck"]
        and SECOND_FOLDER not in after_second["stuck"]
        and sends_now == [],
        f"stuck {after_second['stuck']}, sent {sends_now}",
    )

    # ── t3 ──────────────────────────────────────────────────────────────────
    message = await page.evaluate(MESSAGE)
    journal.check(
        "only the latest message carries a way back",
        message["undo"] and SECOND_FOLDER.split(".")[0] in message["text"],
        f"{message['text']!r}, undo {message['undo']}",
    )

    # ── t4 ──────────────────────────────────────────────────────────────────
    undo = await tap_attribute(page, "id", "toastundo")
    restored = await page.evaluate(LISTS)
    journal.check("« Annuler » is under the finger", undo["tapped"],
                  f"found {undo.get('found')}")
    journal.check(
        "the latest pick comes back at the index it held",
        SECOND_FOLDER in restored["stuck"]
        and restored["stuck"].index(SECOND_FOLDER)
        == index_before["stuck"].index(SECOND_FOLDER),
        f"{index_before['stuck']} → {restored['stuck']}",
    )
    journal.check(
        "and ONE card comes back, not two",
        first_folder not in restored["blocked"] + restored["stuck"],
        f"{first_folder!r} is back in {restored} — one undo, one card",
    )

    # ── t5 ──────────────────────────────────────────────────────────────────
    await page.wait_for_timeout(WINDOW_CLOSED)
    sends_later = await page.evaluate(SENDS)
    journal.check(
        "and the first pick's send is the one that leaves",
        sends_later == [first_folder],
        f"{sends_later} — the undo cancels its own send and no other",
    )


async def put_back_onto_a_moved_list(page, journal):
    """t6 — the put-back read on a list that has REALLY moved.

    THE PUT-BACK IS TAKEN THROUGH THE SEAM HERE, and the reason is t3's own
    reading: only the LATEST message carries a way back, so a third act
    speaking puts the pick's undo out of a finger's reach. That is the
    interface's rule and not a shortcut — t4 above already walks the undo with a
    finger, on the ordinary case. What B-396 says is missing is not the finger:
    it is a list that has really MOVED under the index the put-back splices at,
    and that is what this adds to R162's w6.
    """
    await page.evaluate("() => window.__mocks.reset()")
    await page.evaluate("(id)=>window.__go(id)", TIED_STATE)
    await page.wait_for_timeout(SETTLED)
    await open_second_screen(page, journal)
    before = await page.evaluate(LISTS)
    index_before = before["stuck"].index(SECOND_FOLDER) if SECOND_FOLDER in before["stuck"] else None

    # THE PICK IS TAKEN THROUGH THE SEAM SO ITS UNDO IS KEPT, which a finger
    # cannot do: the finger hands the undo to the message, and the message is
    # about to be replaced by the act that moves the list.
    picked = await page.evaluate("""(title) => {
      const actions = window.__queueActions;
      if (typeof actions?.pick !== 'function') return false;
      window.__undoTheSecondPick = actions.pick(title, title);
      return typeof window.__undoTheSecondPick === 'function';
    }""", SECOND_FOLDER)
    await page.wait_for_timeout(SETTLED)
    journal.check("the queue's pick answers an undo the rule can keep", picked)

    # ── the list moves, by a finger, through the layer's own operation ──────
    await open_third_screen(page, journal)
    left = await tap_attribute(page, "data-leave", THIRD_FOLDER)
    moved = await page.evaluate(LISTS)
    journal.check(
        "a third folder is left as it is, so the list really moves",
        left["tapped"] and THIRD_FOLDER not in moved["stuck"]
        and len(moved["stuck"]) < len(before["stuck"]) - 1,
        f"tapped {left['tapped']}, {before['stuck']} → {moved['stuck']}",
    )

    restored_at = await page.evaluate("""() => {
      window.__undoTheSecondPick?.();
      return true;
    }""")
    await page.wait_for_timeout(SETTLED)
    restored = await page.evaluate(LISTS)
    landed = (restored["stuck"].index(SECOND_FOLDER)
              if SECOND_FOLDER in restored["stuck"] else None)
    # WHAT IS HELD is that the card is back, exactly ONCE. WHERE it lands on a
    # list shorter than the one it left is READ and printed: nobody has decided
    # that position, and a rule asserting one would be writing a contract rather
    # than holding one. `putOneBack` splices at the index of the BEFORE snapshot
    # and `slice` absorbs an overflow, which is the reasoning B-396 records as
    # reasoning — this is the reading it asked for.
    journal.check(
        "the card comes back, exactly once, on a list that has moved",
        restored_at and restored["stuck"].count(SECOND_FOLDER) == 1,
        f"{moved['stuck']} → {restored['stuck']}: it left index {index_before} "
        f"and lands at index {landed}",
    )
    await page.wait_for_timeout(WINDOW_CLOSED)
    sends_later = await page.evaluate(SENDS)
    journal.check(
        "and nothing was sent for the card that came back",
        SECOND_FOLDER not in sends_later,
        f"{sends_later}",
    )


async def main():
    """Walks the two journeys the second subject makes reachable."""
    journal = Journal("R172 — two picks in one undo window, by a finger")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await two_picks(page, journal)
        await put_back_onto_a_moved_list(page, journal)
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
