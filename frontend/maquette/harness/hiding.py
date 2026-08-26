"""R86 — what the interface says is not on screen is not on screen.

Three defects with one shape, and the shape is the reason they are held by one
rule rather than three: an element the markup declares invisible went on being
laid out, painted and TAPPABLE, while every other signal said it was gone.

  the design notes  the toggle flipped a class, flipped `aria-pressed` and
                    announced « masquées » while no rule read that class. The
                    default had become « shown », and the loss was invisible
                    because the ONE surviving rule was the oracle's own
                    measuring hide — so the instrument measured a document with
                    no notes while the operator judged one full of them.
  the `hidden` bite the attribute is styled by the user-agent stylesheet, which
                    every author rule beats. Any element carrying a `display`
                    beside it was not hidden at all. The hand-maintained list
                    that answered this covered the names somebody had thought
                    of; `#nav` — the navigation drawer — and `#ptr` were not
                    among them.
  the action button the message and the button share the bottom-right corner by
                    construction, and the message paints over it. The close
                    target is 24 by 24 and sits INSIDE the button's 52 by 52
                    box, so the reader aiming at « close » is aiming at « add ».

WHAT THIS RULE DOES NOT READ, and it is written first on purpose.

It does not read the STYLESHEET. Every hold below is taken from the served
document through `getComputedStyle` and `elementFromPoint`, so a rule written
another way — a different selector, a utility, an inline style — passes here as
long as the element is really gone. That is deliberate: the defect was never
« the file lacks a line », it was « the element is still there ».

It does not read a real finger. `elementFromPoint` answers what the compositor
would hit-test at a coordinate; it cannot tell whether a tap that STARTED on a
message and ended after it vanished lands on what the message covered. That
path needs a device, and the fix does not depend on knowing which of the two
paths the operator met.

It does not read every element that could ever carry `hidden`. It reads the
five the register named plus a probe element built here, which is the half that
generalises: a fresh element wearing a display utility and the attribute proves
the RULE, where the five prove the elements as they stand today.
"""
import asyncio

from common import Journal, open_page
from playwright.async_api import async_playwright

# The five the register named. `#fab`, `#installbar` and `#installsteps` were
# already covered by the hand-maintained list; `#nav` and `#ptr` were not, and
# the entry naming all five as inert was measured against the markup and the
# import list rather than against the document. Both halves are held here, so
# the day someone narrows the base-layer rule the drawer falls with the rest.
DECLARED_HIDEABLE = ("fab", "nav", "ptr", "installbar", "installsteps")

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


READ_NOTES = """()=>{
  const notes=[...document.querySelectorAll('.note')];
  const button=document.querySelector('#notesBtn');
  return {count: notes.length,
          displays: [...new Set(notes.map(n=>getComputedStyle(n).display))],
          pressed: button ? button.getAttribute('aria-pressed') : null,
          rootClass: document.documentElement.className};
}"""

READ_MESSAGE = """()=>{
  const button=document.getElementById('fab'), message=document.getElementById('toast'),
        close=document.getElementById('toastx');
  const box=close.getBoundingClientRect();
  const hit=document.elementFromPoint(box.x+box.width/2, box.y+box.height/2);
  return {buttonHidden: button.hasAttribute('hidden'),
          buttonDisplay: getComputedStyle(button).display,
          messageShown: message.hasAttribute('data-shown'),
          atCloseTarget: hit ? (hit.closest('#fab') ? 'fab' : 'the message') : 'nothing'};
}"""


async def main():
    global _journal
    _journal = Journal("R86 — what is declared invisible is invisible")

    async with async_playwright() as page_browser:
        browser = await page_browser.chromium.launch(channel="chrome")
        _, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # 1. THE DESIGN NOTES, BOTH WAYS. A hold on the pressed state alone
        #    would have passed on the broken tree: the notes were visible in
        #    both positions, so « pressing shows them » was true and useless.
        #    The default is the half that fell, and it is read first.
        default = await page.evaluate(READ_NOTES)
        check("the prototype has design notes to hide", default["count"] > 0, str(default["count"]))
        check("hidden by default, before anyone asks",
              default["displays"] == ["none"], str(default))
        check("and the button says so", default["pressed"] == "false", str(default["pressed"]))

        await page.evaluate("()=>document.querySelector('#notesBtn').click()")
        await page.wait_for_timeout(200)
        pressed = await page.evaluate(READ_NOTES)
        check("pressing the button shows them",
              pressed["displays"] == ["block"], str(pressed))
        check("and the class the rule reads is the class the engine writes",
              "notes" in pressed["rootClass"].split(), repr(pressed["rootClass"]))

        await page.evaluate("()=>document.querySelector('#notesBtn').click()")
        await page.wait_for_timeout(200)
        released = await page.evaluate(READ_NOTES)
        check("releasing it hides them again",
              released["displays"] == ["none"] and released["pressed"] == "false",
              str(released))

        # 2. `hidden` BITES, on every element that also wears a display.
        #    Measured by SETTING the attribute and reading the computed value
        #    back, then restoring — never by reading the stylesheet.
        bites = await page.evaluate("""(ids)=>ids.map(id=>{
            const element=document.getElementById(id);
            if (!element) return {id, missing:true};
            const had=element.hasAttribute('hidden');
            element.setAttribute('hidden','');
            const display=getComputedStyle(element).display;
            if (!had) element.removeAttribute('hidden');
            return {id, display, wore: getComputedStyle(element).position};
        })""", list(DECLARED_HIDEABLE))
        for row in bites:
            check(f"« hidden » hides #{row['id']}",
                  row.get("display") == "none", str(row))

        # A probe the markup has never met. The five above prove the elements as
        # they stand; this proves the RULE, which is what the hand-maintained
        # list could not do — it could only ever cover a name somebody had
        # already decided to hide.
        probe = await page.evaluate("""()=>{
            const element=document.createElement('div');
            element.className='grid place-items-center';
            element.setAttribute('hidden','');
            element.style.setProperty('display','flex');   // an INLINE display, the strongest case
            document.body.appendChild(element);
            const display=getComputedStyle(element).display;
            element.remove();
            return display;
        }""")
        check("and hides an element the markup has never met, inline display included",
              probe == "none", probe)

        # `until-found` is spared, because a browser sets it to reveal content it
        # is scrolling to. Hiding it would break find-in-page, which is the one
        # thing preflight's own form is careful about.
        found = await page.evaluate("""()=>{
            const element=document.createElement('div');
            element.setAttribute('hidden','until-found');
            document.body.appendChild(element);
            const display=getComputedStyle(element).display;
            element.remove();
            return display;
        }""")
        check("and spares « hidden=until-found », which the browser sets itself",
              found != "none", found)

        # 3. THE ACTION BUTTON IS NOT UNDER THE MESSAGE'S CLOSE TARGET.
        #    The boot hint is left to expire first: a message already on screen
        #    would make the « quiet » reading say what the next one is meant to.
        await page.wait_for_timeout(2600)
        await page.evaluate("()=>document.getElementById('toastx').click()")
        await page.wait_for_timeout(400)
        quiet = await page.evaluate(READ_MESSAGE)
        check("with no message, the page's action button is on screen",
              not quiet["buttonHidden"] and quiet["buttonDisplay"] != "none", str(quiet))
        # The collision itself, stated as a measurement rather than as a claim:
        # with nothing on top, the message's close coordinates ARE the button.
        check("and the message's close target sits over it — the collision, measured",
              quiet["atCloseTarget"] == "fab", str(quiet["atCloseTarget"]))

        await page.evaluate("()=>window.toast('essai')")
        await page.wait_for_timeout(250)
        during = await page.evaluate(READ_MESSAGE)
        check("a message on screen takes the action button away",
              during["messageShown"] and during["buttonHidden"]
              and during["buttonDisplay"] == "none", str(during))
        check("so closing the message cannot reach it",
              during["atCloseTarget"] == "the message", str(during["atCloseTarget"]))

        await page.evaluate("()=>document.getElementById('toastx').click()")
        await page.wait_for_timeout(60)
        leaving = await page.evaluate(READ_MESSAGE)
        check("and it does not come back while the message is still leaving",
              not leaving["messageShown"] and leaving["buttonHidden"], str(leaving))

        await page.wait_for_timeout(400)
        back = await page.evaluate(READ_MESSAGE)
        check("it comes back once the message has gone",
              not back["buttonHidden"] and back["buttonDisplay"] != "none", str(back))

        # The page's OWN answer is not erased by the message's. A page with no
        # primary action must not acquire one when a message closes — which is
        # what a second writer of `hidden` would have done.
        await page.evaluate("()=>window.__go('system')")
        await page.wait_for_timeout(300)
        pageless = await page.evaluate(READ_MESSAGE)
        await page.evaluate("()=>window.toast('essai')")
        await page.wait_for_timeout(250)
        await page.evaluate("()=>document.getElementById('toastx').click()")
        await page.wait_for_timeout(500)
        after = await page.evaluate(READ_MESSAGE)
        check("a page with no action does not acquire one when a message closes",
              pageless["buttonHidden"] and after["buttonHidden"],
              f"before {pageless['buttonHidden']}, after {after['buttonHidden']}")

        await browser.close()

    _journal.summary(errors)


asyncio.run(main())
