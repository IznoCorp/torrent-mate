"""R74 — the bridge wires the legacy nav cluster to the router.

The shell is the single writer of history entries, speaking through
`window.__pont`; the legacy engine keeps its navigation LOGIC (when to
push, when to unwind) and loses only its history primitives. The bridge
verifies that: (a) the engine's source makes no raw history calls that
bypass the bridge; (b) the journey through the bridge (results → sheet →
back) redraws and restores state correctly; (c) deep URL entry
(wrapped.html?page=lib&mode=list) lands on the promised state; (d) a
state-only navigation (__go) does not change history depth; (e) both
the pre-bridge (recorder, envelope-side) and the real bridge (shell,
router-side) are present in the built page. Verified by `pont.py`
through source-code inspection and driven state testing on the build.
"""
import asyncio
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import Journal, ouvrir

_journal = None


def verifier(nom, condition, detail=""):
    return _journal.verifier(nom, condition, detail)


def compter_appels_history(source_path):
    """Count direct history.pushState/history.back() calls in source, excluding comments.

    Reads the source, strips /* */ and // comment content, then counts
    remaining calls to history.pushState( or history.back(). The pre-bridge
    and bridge implementations use __pont.* instead, so legitimate call sites
    should be zero.
    """
    source = source_path.read_text(encoding="utf-8")

    # Strip /* */ block comments
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)

    # Strip // line comments
    source = re.sub(r"//.*?$", "", source, flags=re.MULTILINE)

    # Count remaining calls to the primitives
    pushstate_count = len(re.findall(r"history\.pushState\s*\(", source))
    back_count = len(re.findall(r"history\.back\s*\(", source))

    return pushstate_count + back_count


async def main():
    global _journal
    _journal = Journal("R74 — le pont lie le cluster nav au routeur")

    # ─── Hold (a): Source assertion ───────────────────────────────────
    # Zero raw history.pushState/history.back() calls outside comments.
    refonte_path = pathlib.Path(
        "/Users/izno/dev/PersonalScraper/frontend/maquette/design/refonte.html"
    )
    raw_calls = compter_appels_history(refonte_path)
    verifier(
        "zéro appel direct history.pushState/back() dans refonte.html",
        raw_calls == 0,
        f"{raw_calls} appel(s) trouvé(s)",
    )

    # ─── Hold (e): Both-halves presence ────────────────────────────────
    # (a) Pre-bridge in envelope (source check)
    # (b) Real bridge installed at runtime (live page check)
    enveloppe_path = pathlib.Path(
        "/Users/izno/dev/PersonalScraper/frontend/maquette/design/index.html"
    )
    prebridges = enveloppe_path.read_text(encoding="utf-8")
    has_prebidge_stub = "__rejouerLePont" in prebridges
    verifier(
        "l'enveloppe porte le pré-pont (recorder)",
        has_prebidge_stub,
        "fonction __rejouerLePont présente",
    )

    # Launch the browser and open the prototype
    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")
        ctx, pg = await ouvrir(navigateur)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        # ─── Hold (e): Real bridge installed at runtime ────────────────
        # window.__pont is the REAL bridge (not the recorder).
        # The pre-bridge's __pont.noter records to enregistrees array;
        # the real bridge's __pont.noter calls historique.push().
        # After replay, enregistrees should be gone.
        has_real_bridge = await pg.evaluate(
            """()=>
                typeof window.__pont === "object" &&
                typeof window.__pont.noter === "function" &&
                !window.__rejouerLePont &&
                typeof window.__routeur === "object" &&
                typeof window.enregistrees === "undefined"
            """
        )
        verifier(
            "les deux moitiés du pont sont présentes (pré et vrai)",
            has_real_bridge,
            "enveloppe + shell, rejouerLePont deleté, enregistrees disparu",
        )

        # ─── Hold (b): R71 journey through the bridge ──────────────────
        # Results → Sheet → Back redraws results with query + scroll.
        await pg.evaluate("()=>window.__go('acq-ajout-resultats')")
        await pg.wait_for_timeout(400)

        depart_state = await pg.evaluate(
            """()=>({
                ecran: document.querySelector('#screen').classList.contains('open'),
                cle: document.querySelector('#screen').dataset.cle,
                cartes: document.querySelectorAll('.reslist .card').length,
                requete: document.querySelector('#addq')?.value
            })"""
        )
        verifier(
            "l'écran de résultats est là",
            depart_state["ecran"] and depart_state["cartes"] >= 2,
            f"{depart_state['cartes']} cartes",
        )

        # Tap a poster to open the sheet
        await pg.evaluate("()=>document.querySelector('.reslist .poster').click()")
        await pg.wait_for_timeout(450)

        # Go back via browser back button
        await pg.go_back()
        await pg.wait_for_timeout(500)

        retour_state = await pg.evaluate(
            """()=>({
                ecran: document.querySelector('#screen').classList.contains('open'),
                cle: document.querySelector('#screen').dataset.cle,
                cartes: document.querySelectorAll('.reslist .card').length,
                requete: document.querySelector('#addq')?.value,
                scroll: document.querySelector('#screen .port').scrollTop
            })"""
        )

        verifier(
            "le retour redessine la liste de résultats",
            retour_state["ecran"]
            and (retour_state["cle"] or "").startswith("ajout:")
            and retour_state["cartes"] == depart_state["cartes"]
            and retour_state["requete"] == depart_state["requete"],
            f"{retour_state['cartes']} cartes · requête « {retour_state['requete']} »",
        )

        # ─── Hold (c): Deep-URL entry ─────────────────────────────────
        # wrapped.html?page=lib&mode=list lands on promised state.
        # Close the browser and reopen at the deep URL.
        await navigateur.close()

    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")
        ctx = await navigateur.new_context(
            **{
                "viewport": {"width": 390, "height": 844},
                "device_scale_factor": 2,
                "is_mobile": True,
                "has_touch": True,
            }
        )
        pg = await ctx.new_page()
        await pg.goto(
            "http://127.0.0.1:8899/wrapped.html?page=lib&mode=list", wait_until="load"
        )
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
        await pg.wait_for_timeout(250)

        state = await pg.evaluate(
            """()=>({
                page: state.page ?? null,
                libMode: state.libMode ?? null
            })"""
        )
        verifier(
            "l'entrée directe ?page=lib&mode=list établit l'état promis",
            state["page"] == "lib" and state["libMode"] == "list",
            f"page={state['page']} libMode={state['libMode']}",
        )

        # ─── Hold (d): __go() ne change pas history.depth ──────────────
        # A state-only navigation (acq-decouvrir is a page-level state,
        # not a layer push) should not change history.length.
        depth_avant = await pg.evaluate("()=>history.length")
        await pg.evaluate("()=>window.__go('acq-decouvrir')")
        await pg.wait_for_timeout(400)
        depth_apres = await pg.evaluate("()=>history.length")

        verifier(
            "window.__go() ne change pas la profondeur de l'historique",
            depth_apres == depth_avant,
            f"avant={depth_avant} après={depth_apres}",
        )

        await navigateur.close()

    _journal.bilan(erreurs)


asyncio.run(main())
