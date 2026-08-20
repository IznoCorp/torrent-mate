"""R51 — the install offer, and WHO gets asked.

The banner existed and nothing ever showed it: it was reachable only by driving
to its named state, so on a real phone it never appeared at all. Two platforms,
two entirely different mechanisms, and neither is optional:

  · Android and desktop fire `beforeinstallprompt`. It must be captured AND its
    default prevented, or the browser posts its own proposal in its own place
    and ours never gets a turn. It is then replayed on a gesture, which is the
    only moment a browser accepts a prompt.

  · iOS Safari fires nothing and offers no API. There is no event to await, so
    the page cannot know whether it is installable; what it CAN know is that it
    is Safari on iOS and not already standalone. There the banner IS the guide.

And nobody is asked while already installed, or over the entry screen — there
is nothing to install yet there, and the banner would cover the only field.

The offer is driven here by a synthetic `beforeinstallprompt`, which is exactly
what Chrome dispatches; the iOS half is driven by a context that says it is an
iPhone. Neither can be observed on a desktop headless run any other way.
"""
import asyncio

from common import Journal
from playwright.async_api import async_playwright

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


# What Chrome dispatches, with the two members a page is allowed to use.
FIRE = """() => {
  const e = new Event('beforeinstallprompt');
  e.prompt = () => { window.__prompt = (window.__prompt || 0) + 1; };
  e.userChoice = Promise.resolve({ outcome: 'accepted', platform: 'web' });
  const realPrevent = e.preventDefault.bind(e);
  e.preventDefault = () => { window.__prevented = true; realPrevent(); };
  window.__prompt = 0; window.__prevented = false;
  window.dispatchEvent(e);
}"""

BANNER = """() => {
  const b = document.querySelector('#installbar');
  return {
    visible: !b.hidden && getComputedStyle(b).display !== 'none',
    button: !document.querySelector('#installgo').hidden,
    steps: !document.querySelector('#installsteps').hidden,
    sub: !document.querySelector('#installsub').hidden,
    text: (b.textContent || '').replace(/\\s+/g, ' ').trim(),
  };
}"""


async def open_proto(p, **kwargs):
    """Opens the prototype in a fresh context, past the startup screen."""
    ctx = await p.new_context(viewport={"width": 390, "height": 844},
                              device_scale_factor=2, is_mobile=True, has_touch=True,
                              **kwargs)
    pg = await ctx.new_page()
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    return ctx, pg


async def main():
    global _journal
    _journal = Journal("R51 — the invitation to install")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # ── Android / desktop: the event is captured, kept, and replayed ────
        ctx, pg = await open_proto(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        before = await pg.evaluate(BANNER)
        check("nothing is offered unless the browser announces it",
                 not before["visible"], str(before["visible"]))

        await pg.evaluate(FIRE)
        await pg.wait_for_timeout(200)
        after = await pg.evaluate(BANNER)
        check("the browser's announcement raises the banner", after["visible"])
        check("its default is prevented, or the browser keeps the hand",
                 await pg.evaluate("()=>window.__prevented"))
        check("it offers a BUTTON, not a set of steps",
                 after["button"] and not after["steps"], str(after))

        await pg.click("#installgo")
        await pg.wait_for_timeout(250)
        check("the button replays the captured event",
                 await pg.evaluate("()=>window.__prompt") == 1,
                 str(await pg.evaluate("()=>window.__prompt")))
        check("and the banner withdraws", not (await pg.evaluate(BANNER))["visible"])

        # Refused once, not asked again in the same session.
        await pg.evaluate(FIRE)
        await pg.wait_for_timeout(150)
        await pg.click("#installclose")
        await pg.evaluate(FIRE)
        await pg.wait_for_timeout(200)
        check("a refusal is not asked again in the same session",
                 not (await pg.evaluate(BANNER))["visible"])
        check("no JS error", not errors, str(errors))
        await ctx.close()

        # ── iOS Safari: no event exists, so the banner IS the guide ─────────
        ctx, pg = await open_proto(b, user_agent=IPHONE)
        await pg.wait_for_timeout(1600)
        ios = await pg.evaluate(BANNER)
        check("on iOS the banner appears on its own", ios["visible"], str(ios))
        check("it gives the STEPS TO FOLLOW, with no install button",
                 ios["steps"] and not ios["button"], str(ios))
        check("and it names the three real gestures",
                 all(word in ios["text"] for word in ("Partager", "écran d'accueil", "Ajouter")),
                 ios["text"][:110])
        await ctx.close()

        # ── Already installed: nothing is proposed at all ───────────────────
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True,
                                  user_agent=IPHONE)
        pg = await ctx.new_page()
        # A standalone launch, declared the way a launcher declares it.
        await pg.add_init_script(
            "Object.defineProperty(navigator, 'standalone', { get: () => true });")
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg.evaluate("()=>document.querySelector('#toastx').click()")
        await pg.wait_for_timeout(1600)
        installed = await pg.evaluate(BANNER)
        check("nothing is offered to someone who already installed it",
                 not installed["visible"], str(installed["visible"]))
        await ctx.close()

        # ── Over the entry screen: never ────────────────────────────────────
        ctx, pg = await open_proto(b)
        await pg.evaluate("()=>window.__go('signin')")
        await pg.wait_for_timeout(200)
        await pg.evaluate(FIRE)
        await pg.wait_for_timeout(200)
        gate = await pg.evaluate(BANNER)
        check("nothing is offered over the entry screen",
                 not gate["visible"], str(gate["visible"]))
        await ctx.close()
        await b.close()

    _journal.summary()

asyncio.run(main())
