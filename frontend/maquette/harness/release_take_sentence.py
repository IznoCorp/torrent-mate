"""R137 — choosing a release says ONE sentence, and it says both halves.

B-322. Taking a release wrote TWO messages into the single message element:
`actionTake`'s « … récupéré — suivez-le dans « En vol ». » and, immediately
after it, « « res src lang » retenue — récupération lancée. » The second
overwrote the first inside the same task, so WHICH ONE THE OPERATOR READ WAS A
RACE — and each of the two carried only half of what they needed to know.

**RED WITH NO MUTATION NEEDED against a build that still writes both.** Two
writes are observable there, and neither surviving sentence carries both facts.

WHY IT WATCHES THE ELEMENT AND NOT THE SEAM. A hold that read the message
after the gesture sees ONE sentence whether one or two were written — which is
the whole defect, so such a hold measures nothing. This one records every
value the element carries ACROSS the gesture, through a MutationObserver
installed before the tap: an overwrite is a second record, and a lost sentence
leaves its trace there even though nothing on screen ever showed it.

Counting calls into `window.__toast.show` would have been easier and worse. It
would measure the seam rather than the element, and it would require patching
the thing under measurement — a rule that alters what it reads.

WHAT IT READS, and each fails differently:

  1. THE SCREEN REALLY OFFERS RELEASES, so the rest is not measuring an empty
     list.
  2. EXACTLY ONE SENTENCE IS WRITTEN across the whole gesture. Two is the
     defect; none would mean the act said nothing at all.
  3. AND THAT SENTENCE CARRIES BOTH HALVES — the release RETAINED and the
     medium it was retained for. Without this hold, « one sentence » is
     satisfied by deleting either message, which loses half of what the
     operator just decided. The two halves are read OFF THE SCREEN before the
     tap rather than typed here, so the hold follows the data instead of
     agreeing with a sentence somebody wrote.
  4. AND NO ERROR IS RAISED.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# THE RELEASE PICKER, as a named state the oracle also measures.
RELEASES_STATE = "screen-releases"

# EVERY VALUE THE MESSAGE ELEMENT CARRIES, from now until it is read back.
#
# The observer is on `#toast` and not on `#toastmsg`: the host re-renders, and
# an observer bound to a node the renderer replaces stops recording without
# ever saying so. Consecutive identical readings are collapsed — React commits
# more often than the message changes — so what comes back is the SEQUENCE of
# distinct sentences the element held, which is what « two writes » means.
WATCH = """()=>{
  const host = document.querySelector('#toast');
  if (!host) return false;
  window.__sentences = [];
  const readNow = () => {
    const said = (document.querySelector('#toastmsg')?.textContent || '').trim();
    const seen = window.__sentences;
    if (said !== '' && said !== seen[seen.length - 1]) seen.push(said);
  };
  readNow();
  window.__sentenceWatch = new MutationObserver(readNow);
  window.__sentenceWatch.observe(host, {
    childList: true, subtree: true, characterData: true});
  return true;}"""

SAID = """()=>{
  window.__sentenceWatch?.disconnect();
  return window.__sentences || [];}"""

# WHAT THE FIRST ROW OFFERS AND WHOM IT IS FOR, both read before the tap so
# the sentence can be held against them afterwards.
#
# THE CANDIDATE COMES FROM THE SEAM the picker itself indexes into, not from
# the row's markup. The row draws its resolution in a chip that carries no
# naming attribute, and reaching for it by class is the one thing a rule may
# never do — a class in a selector dies with the class, and nothing can then
# say whether the anchor or the styling was at fault. The list is the same one
# the verb reads, so the rule and the interface cannot disagree about what was
# offered.
#
# THE SUBJECT comes from the OPEN picker's bar, selected through the screen's
# own key so a bar belonging to some other screen cannot answer.
#
# THE ROW IS FOUND BY `data-part` AND ITS VERB READ FROM THE DATASET, never
# selected by `[data-pick-release]`'s presence. The value is an INDEX and the
# picker writes one on every row by design, so a presence selector would enrol
# it in `check-markup-contracts`'s derived list of BOOLEAN states — where the
# refusal is that the attribute must vanish when false, which is not a thing an
# index does.
THE_OFFER = """()=>{
  const offered = (window.__releases?.() || [])[0];
  const screen = [...document.querySelectorAll(
                    '[data-part="screen"][data-open]')]
                 .find((one) => (one.dataset.key || '').startsWith('releases:'));
  const foot = [...document.querySelectorAll('[data-part="card/foot"]')]
               .find((one) => 'pickRelease' in one.dataset);
  if (!offered || !screen || !foot) return null;
  const bar = screen.querySelector('[data-part="screen/bar"]');
  return {resolution: offered.res,
          subject: (bar?.textContent || '').trim()};}"""

TAP = """()=>{
  [...document.querySelectorAll('[data-part="card/foot"]')]
    .find((one) => 'pickRelease' in one.dataset).click();}"""


async def main():
    journal = Journal("R137 — choosing a release says one sentence, carrying both halves")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", RELEASES_STATE)
        await page.wait_for_timeout(SETTLED)

        offer = await page.evaluate(THE_OFFER)
        journal.check(
            "the picker really offers a release to choose, and says which "
            "medium it is choosing for — the rest of this rule reads both",
            offer is not None and offer["resolution"] != ""
            and offer["subject"] != "",
            str(offer))
        if offer is None or not offer["resolution"] or not offer["subject"]:
            await context.close()
            await browser.close()
            journal.summary()
            return

        watching = await page.evaluate(WATCH)
        journal.check(
            "the message element is being watched BEFORE the tap — a sentence "
            "overwritten by the next one is invisible to anything that looks "
            "afterwards",
            watching, str(watching))

        await page.evaluate(TAP)
        await page.wait_for_timeout(ACTED)
        said = await page.evaluate(SAID)

        journal.check(
            "EXACTLY ONE sentence is written across the whole gesture — two is "
            "B-322, and which of them the operator read was a race",
            len(said) == 1, f"{len(said)} sentence(s): {said}")

        journal.check(
            "and it carries BOTH halves: the release retained, and the medium "
            "it was retained for. « One sentence » is otherwise satisfied by "
            "deleting either of the two, which loses half of the decision",
            len(said) == 1
            and offer["resolution"] in said[0]
            and offer["subject"] in said[0],
            f"« {said[0] if said else ''} » against resolution "
            f"« {offer['resolution']} » and subject « {offer['subject']} »")

        journal.check("and choosing raised no error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
