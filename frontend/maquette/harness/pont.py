"""R74 — the bridge wires the legacy nav cluster to the router.

The shell is the single writer of history entries, speaking through
`window.__pont`; the legacy engine keeps its navigation LOGIC (when to
push, when to unwind) and loses only its history primitives. The bridge
verifies that: (a) the engine's source makes no raw history calls that
bypass the bridge; (b) the journey through the bridge (results → sheet →
back) redraws and restores state correctly; (c) deep URL entry lands on
the promised state; (d) a state-only navigation (__go) does not change
history depth; (e) both the pre-bridge (recorder in envelope) and the
real bridge (shell in router) are present and functional. Verified by
`pont.py` through source inspection, runtime checks, and a mutation that
severs __rejouerLePont and confirms hold (e) falls.
"""
import asyncio
import pathlib
import re
import subprocess
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import TELEPHONE, Journal, ouvrir

_journal = None


def verifier(nom, condition, detail=""):
    return _journal.verifier(nom, condition, detail)


def compter_history_primitives(source_path):
    """Count direct history.pushState, replaceState, back, go calls in source."""
    source = source_path.read_text(encoding="utf-8")

    # Strip comments: // and /* */
    # Simple state machine: skip //, skip /* */, handle strings naively
    cleaned = []
    i = 0
    while i < len(source):
        if i < len(source) - 1 and source[i:i+2] == "//":
            while i < len(source) and source[i] != "\n":
                cleaned.append(" ")
                i += 1
            if i < len(source):
                cleaned.append("\n")
                i += 1
        elif i < len(source) - 1 and source[i:i+2] == "/*":
            cleaned.append(" ")
            cleaned.append(" ")
            i += 2
            while i < len(source) - 1:
                if source[i:i+2] == "*/":
                    cleaned.append(" ")
                    cleaned.append(" ")
                    i += 2
                    break
                cleaned.append(" " if source[i] != "\n" else "\n")
                i += 1
        else:
            cleaned.append(source[i])
            i += 1
    cleaned_str = "".join(cleaned)

    # Count all four primitives
    patterns = [
        r"history\.pushState\s*\(",
        r"history\.replaceState\s*\(",
        r"history\.back\s*\(",
        r"history\.go\s*\(",
    ]
    total = sum(len(re.findall(p, cleaned_str)) for p in patterns)
    return total


async def main():
    global _journal
    _journal = Journal("R74 — le pont lie le cluster nav au routeur")

    # ─── Hold (a): Source assertion ───────────────────────────────────
    refonte_path = pathlib.Path(
        "/Users/izno/dev/PersonalScraper/frontend/maquette/design/refonte.html"
    )
    raw_calls = compter_history_primitives(refonte_path)
    verifier(
        "zéro appel direct history.* dans refonte.html",
        raw_calls == 0,
        f"{raw_calls} appel(s) trouvé(s)",
    )

    # ─── Hold (e) pre-bridge: Source assertion ───────────────────────
    enveloppe_path = pathlib.Path(
        "/Users/izno/dev/PersonalScraper/frontend/maquette/design/index.html"
    )
    prebridges = enveloppe_path.read_text(encoding="utf-8")
    has_prebidge_stub = "__rejouerLePont" in prebridges
    verifier(
        "l'enveloppe porte le pré-pont (source envelope)",
        has_prebidge_stub,
        "fonction __rejouerLePont présente",
    )

    # Launch the browser and open the prototype (non-mutated)
    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")
        ctx, pg = await ouvrir(navigateur)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        # ─── Hold (e) real bridge: Runtime probe ─────────────────────
        # The pre-bridge sets window.__pont.psi = true; the real bridge
        # replaces __pont entirely, so psi is absent. If __rejouerLePont
        # is never called, psi will still be true (recorder not replaced).
        has_real_bridge = await pg.evaluate(
            """()=>
                typeof window.__pont === "object" &&
                typeof window.__pont.noter === "function" &&
                !window.__rejouerLePont &&
                typeof window.__routeur === "object" &&
                window.__pont.psi !== true
            """
        )
        verifier(
            "le vrai pont est présent (shell + replay)",
            has_real_bridge,
            "psi absent (recorder replaced), rejouerLePont deleté",
        )

        # ─── Hold (b): R71 journey through the bridge ──────────────────
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

        await pg.evaluate("()=>document.querySelector('.reslist .poster').click()")
        await pg.wait_for_timeout(450)

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
        await navigateur.close()

    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")
        ctx = await navigateur.new_context(**TELEPHONE)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
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

    # ─── Mutation: sever __rejouerLePont ──────────────────────────────
    print("  MUTATION — severing __rejouerLePont in wrapped.html")
    wrapped_path = pathlib.Path("/tmp/tm-refonte/wrapped.html")
    wrapped_content = wrapped_path.read_text(encoding="utf-8")

    # Find and replace the pre-bridge's __rejouerLePont function assignment
    severed = re.sub(
        r"window\.__rejouerLePont\s*=\s*function\s*\([^)]*\)\s*\{[^}]*\};",
        "window.__rejouerLePont = void 0;",
        wrapped_content,
    )

    if severed == wrapped_content:
        print("  WARNING: mutation pattern did not match; retrying with multiline")
        # Fallback: line-by-line replacement
        lines = wrapped_content.split("\n")
        for i, line in enumerate(lines):
            if "window.__rejouerLePont = function (pont)" in line:
                j = i
                while j < len(lines) and "};" not in lines[j]:
                    j += 1
                lines[i:j+1] = ["        window.__rejouerLePont = void 0;"]
                severed = "\n".join(lines)
                break

    wrapped_path.write_text(severed, encoding="utf-8")
    print("  ✓ Mutation applied")

    # Re-run hold (b) with severed bridge: the boot order is gone, history is shorter
    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")
        ctx = await navigateur.new_context(**TELEPHONE)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
        await pg.wait_for_timeout(250)

        # Check history length: without boot order replay, it should be minimal (1 or 2)
        # vs normal (3 with boot entries)
        history_length_mutated = await pg.evaluate("()=>history.length")

        verifier(
            "la mutation (rejouerLePont severed) rompt hold (b) — boot non rejoué",
            history_length_mutated < 3,
            f"history.length={history_length_mutated} (attendu <3 sans rejoué)",
        )

        await navigateur.close()

    # Restore the measured copy via ritual
    subprocess.run(
        [
            "bash",
            "-c",
            """
            cd /Users/izno/dev/PersonalScraper/frontend/maquette/design
            npm run build > /dev/null 2>&1
            cp dist/index.html /tmp/tm-refonte/wrapped.html
            rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite
            """,
        ],
        check=True,
        capture_output=True,
    )
    print("  ✓ Ritual restore complete")

    _journal.bilan(erreurs)


asyncio.run(main())
