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

from commun import Journal
from playwright.async_api import async_playwright

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

_journal = None


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.verifier(nom, condition, detail)


# What Chrome dispatches, with the two members a page is allowed to use.
POSER = """() => {
  const e = new Event('beforeinstallprompt');
  e.prompt = () => { window.__prompt = (window.__prompt || 0) + 1; };
  e.userChoice = Promise.resolve({ outcome: 'accepted', platform: 'web' });
  const vraiPrevent = e.preventDefault.bind(e);
  e.preventDefault = () => { window.__prevenu = true; vraiPrevent(); };
  window.__prompt = 0; window.__prevenu = false;
  window.dispatchEvent(e);
}"""

BANDEAU = """() => {
  const b = document.querySelector('#installbar');
  return {
    visible: !b.hidden && getComputedStyle(b).display !== 'none',
    bouton: !document.querySelector('#installgo').hidden,
    marche: !document.querySelector('#installsteps').hidden,
    sous: !document.querySelector('#installsub').hidden,
    texte: (b.textContent || '').replace(/\\s+/g, ' ').trim(),
  };
}"""


async def ouvrir(p, **kwargs):
    """Opens the prototype in a fresh context, past the startup screen."""
    ctx = await p.new_context(viewport={"width": 390, "height": 844},
                              device_scale_factor=2, is_mobile=True, has_touch=True,
                              **kwargs)
    pg = await ctx.new_page()
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    return ctx, pg


async def main():
    global _journal
    _journal = Journal(f"R51 — l'invitation à installer")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # ── Android / desktop: the event is captured, kept, and replayed ────
        ctx, pg = await ouvrir(b)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        avant = await pg.evaluate(BANDEAU)
        verifier("rien n'est proposé sans que le navigateur l'annonce",
                 not avant["visible"], str(avant["visible"]))

        await pg.evaluate(POSER)
        await pg.wait_for_timeout(200)
        apres = await pg.evaluate(BANDEAU)
        verifier("l'annonce du navigateur fait apparaître le bandeau", apres["visible"])
        verifier("son défaut est empêché, sinon le navigateur garde la main",
                 await pg.evaluate("()=>window.__prevenu"))
        verifier("il offre un BOUTON, pas une marche à suivre",
                 apres["bouton"] and not apres["marche"], str(apres))

        await pg.click("#installgo")
        await pg.wait_for_timeout(250)
        verifier("le bouton rejoue l'événement capturé",
                 await pg.evaluate("()=>window.__prompt") == 1,
                 str(await pg.evaluate("()=>window.__prompt")))
        verifier("et le bandeau se retire", not (await pg.evaluate(BANDEAU))["visible"])

        # Refused once, not asked again in the same session.
        await pg.evaluate(POSER)
        await pg.wait_for_timeout(150)
        await pg.click("#installclose")
        await pg.evaluate(POSER)
        await pg.wait_for_timeout(200)
        verifier("un refus n'est pas redemandé dans la même session",
                 not (await pg.evaluate(BANDEAU))["visible"])
        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await ctx.close()

        # ── iOS Safari: no event exists, so the banner IS the guide ─────────
        ctx, pg = await ouvrir(b, user_agent=IPHONE)
        await pg.wait_for_timeout(1600)
        ios = await pg.evaluate(BANDEAU)
        verifier("sur iOS le bandeau apparaît de lui-même", ios["visible"], str(ios))
        verifier("il donne la MARCHE À SUIVRE, sans bouton d'installation",
                 ios["marche"] and not ios["bouton"], str(ios))
        verifier("et il nomme les trois gestes réels",
                 all(mot in ios["texte"] for mot in ("Partager", "écran d'accueil", "Ajouter")),
                 ios["texte"][:110])
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
        installee = await pg.evaluate(BANDEAU)
        verifier("rien n'est proposé à qui l'a déjà installée",
                 not installee["visible"], str(installee["visible"]))
        await ctx.close()

        # ── Over the entry screen: never ────────────────────────────────────
        ctx, pg = await ouvrir(b)
        await pg.evaluate("()=>window.__go('connexion')")
        await pg.wait_for_timeout(200)
        await pg.evaluate(POSER)
        await pg.wait_for_timeout(200)
        portail = await pg.evaluate(BANDEAU)
        verifier("rien n'est proposé par-dessus l'écran d'entrée",
                 not portail["visible"], str(portail["visible"]))
        await ctx.close()
        await b.close()

    _journal.bilan()

asyncio.run(main())
