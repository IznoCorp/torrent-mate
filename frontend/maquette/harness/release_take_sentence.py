"""R137 — choosing a release says ONE sentence, and it says both halves.

B-322. Taking a release wrote TWO messages into the single message element:
`actionTake`'s « … récupéré — suivez-le dans « En vol ». » and, immediately
after it, « « res src lang » retenue — récupération lancée. » The second
overwrote the first inside the same task, so WHICH ONE THE OPERATOR READ WAS A
RACE — and each of the two carried only half of what they needed to know.

**RED WITH NO MUTATION NEEDED against a build that still writes both.** Two
writes are observable there, and neither surviving sentence carries both facts.

WHY IT COUNTS AT THE SEAM, AND WHY THE ELEMENT CANNOT ANSWER THIS.

The first version of this rule watched the message ELEMENT across the gesture
with a MutationObserver, on the reasoning that an overwrite would leave a second
record. **A mutation proved that reasoning wrong**: a second message written
deliberately into the verb made only the « both halves » hold fall, and « exactly
one sentence » stayed green over two writes — the hold that exists for this
defect, vacuous against the defect itself.

The cause is that both writes land in ONE task. The message host is a component,
so the two are batched into a single render and the DOM never holds the first
value at all; an observer's callback then reads a document that has only ever
shown the second. **Nothing that reads the element can distinguish two writes
from one** — which is exactly why B-322's own entry records « sampled every
180 ms, only the second is ever observed ». That sentence describes the limit of
the instrument the entry was written with, and repeating it here would have
reproduced it.

So the count is taken where the writes exist: `window.__toast.show` is wrapped
for the duration of the gesture and forwards every call unchanged. A spy that
alters nothing is not « patching the thing under measurement » — and the
objection this docstring used to make against it was written before the
mutation, which is the whole reason a rule is mutated rather than reasoned about.

THE ELEMENT IS STILL READ, for the other half. What the operator ends up seeing
is a question about the document, and only the document can answer it.

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

# THE PROTOTYPE'S WELCOME HINT IS SPENT FIRST, and this rule fell over it.
#
# The engine offers « touch the ⓘ » through the SAME message element, on a
# timer after boot, and that timer outlived this rule's opening: the hint
# landed AFTER the take's own sentence and was counted as a second write, so a
# perfectly correct message read as B-322 itself. An instrument that cannot
# tell the application's voice from the prototype's is measuring the harness.
#
# It is spent through the engine's OWN contract — the welcome hint disappears
# on first interaction — by making that interaction happen before the watch
# begins. Waiting out its delay instead would have meant copying the engine's
# constant into this file, and a constant copied into a rule is right on the
# day it is typed and silently wrong ever after.
SPEND_THE_HINT = """()=>{
  document.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
  window.__toast?.hide();}"""

# EVERY SENTENCE WRITTEN INTO THE MESSAGE LAYER, from now until it is read back.
#
# It FORWARDS every call unchanged and records what was said. Two writes in one
# task are indistinguishable at the document — the host batches them and only
# the second is ever rendered — so this is the one place where « how many times
# did the interface speak » has an answer at all.
#
# It wraps ONCE: a rule that installed two wrappers would count every sentence
# twice and report a defect the interface does not have.
WATCH = """()=>{
  const layer = window.__toast;
  if (!layer || layer.__counted) return false;
  window.__sentences = [];
  const underneath = layer.show;
  layer.show = (descriptor) => {
    window.__sentences.push(String(descriptor?.message ?? '').trim());
    return underneath(descriptor);
  };
  layer.__counted = true;
  return true;}"""

SAID = """()=>window.__sentences || []"""

# AND WHAT THE OPERATOR IS LEFT LOOKING AT. The count above says how many times
# the interface spoke; this says what it left on screen, which is a question
# about the document and can be answered nowhere else.
SHOWN = """()=>(document.querySelector('#toastmsg')?.textContent || '').trim()"""

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
# own key so a bar belonging to some other screen cannot answer — AND THE WAY
# BACK IS SUBTRACTED FROM IT. The bar holds two things: the back action and the
# medium's name. Read whole it answers « Retour Silo », which appears in no
# sentence, and this rule fell on a message that was correct. The back action
# carries a naming attribute; the name does not, so the name is what is left of
# the bar once the way back is taken out of it.
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
  const back = bar?.querySelector('[data-part="screen/back"]');
  const whole = (bar?.textContent || '').trim();
  const wayBack = (back?.textContent || '').trim();
  return {resolution: offered.res,
          subject: (wayBack ? whole.replace(wayBack, '') : whole).trim()};}"""

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

        await page.evaluate(SPEND_THE_HINT)
        await page.wait_for_timeout(SETTLED)
        watching = await page.evaluate(WATCH)
        journal.check(
            "every sentence the interface says is counted BEFORE the tap — two "
            "writes in one task never both reach the document, so counting "
            "them anywhere else answers « one » to either",
            watching, str(watching))

        await page.evaluate(TAP)
        await page.wait_for_timeout(ACTED)
        said = await page.evaluate(SAID)
        shown = await page.evaluate(SHOWN)

        journal.check(
            "the interface speaks EXACTLY ONCE across the whole gesture — two "
            "is B-322, and which of them the operator read was a race",
            len(said) == 1, f"{len(said)} sentence(s): {said}")

        journal.check(
            "and what it LEFT ON SCREEN carries both halves: the release "
            "retained, and the medium it was retained for. « Once » is "
            "otherwise satisfied by dropping either of the two, which loses "
            "half of the decision",
            offer["resolution"] in shown and offer["subject"] in shown,
            f"« {shown} » against resolution « {offer['resolution']} » and "
            f"subject « {offer['subject']} »")

        journal.check("and choosing raised no error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
