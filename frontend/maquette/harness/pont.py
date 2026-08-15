"""R74 — the bridge wires the legacy nav cluster to the router.

The shell is the single writer of history entries, speaking through
`window.__pont`; the legacy engine keeps its navigation LOGIC (when to
push, when to unwind) and loses only its history primitives. The bridge
verifies that: (a) the engine's source makes no raw history calls that
bypass the bridge; (b) the journey through the bridge (results → sheet →
back) redraws and restores state correctly; (c) deep URL entry lands on
the promised state; (d) a state-only navigation (__go) does not change
history depth; (f′) the boot handshake is real — `window.__demarrerMoteur`
exists AND the startup screen comes off on its own, before this harness
ever calls `window.__chargementTermine`.

The boot order used to run the other way: the engine booted itself, ahead
of the bridge, through a pre-bridge that queued the engine's writes and
replayed them once the real bridge existed (hold (e), now retired along
with that pre-bridge). The shell now creates the store and the bridge
FIRST and only then calls `window.__demarrerMoteur({ magasin })`, so
nothing is queued and nothing is replayed — a module that never evaluates
simply never makes that call, and the startup screen stays up: a visible,
truthful failure rather than an app with mute verbs.

Nothing here mutates anything. The measured copy is shared by every rule
of the harness, so a rule that severed it would, on any interruption,
fail the next rule for a reason having nothing to do with what that rule
holds. Hold (e′) — that severing the copy's module entry leaves the
startup screen up, because the fail-silent path is dead — is proven by a
mutation applied by hand to the copy, outside any rule, and its outcome
is recorded in regions.json.
"""
import asyncio
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import RACINE, TELEPHONE, Journal

# The engine may hold no history primitive of its own — the bridge is the
# only way to the single writer.
PRIMITIVES = (
    r"history\s*\.\s*pushState\s*\(",
    r"history\s*\.\s*replaceState\s*\(",
    r"history\s*\.\s*back\s*\(",
    r"history\s*\.\s*go\s*\(",
    r"history\s*\.\s*forward\s*\(",
)

# A slash opens a regular expression rather than a division when the last
# significant character before it cannot end an expression.
AVANT_REGEX = set("(,=:[!&|?{};+-*%^~<>")
MOTS_AVANT_REGEX = ("return", "typeof", "case", "in", "of", "new", "delete",
                    "do", "else", "void", "instanceof", "yield", "await")

_journal = None


def verifier(nom, condition, detail=""):
    return _journal.verifier(nom, condition, detail)


def sans_commentaires(source):
    """Blanks out the JavaScript comments of a document, and only those.

    A stripper that knows about `//` and `/* */` alone is fail-open on this
    document, and measurably so: the engine carries URLs inside string
    literals (`"https://…"`, whose `//` would blank the rest of the line) and
    quotes inside regular-expression literals (`/[&<>"]/g`, whose `"` would
    open a string state that runs on until the file's next quote). Either
    mistake swallows the real calls that follow, so a rule counting them
    would pass by having lost its evidence rather than by finding none.

    The source is therefore walked as JavaScript: code, line comment, block
    comment, the three string kinds with their escapes, template
    substitutions (`${…}`, whose contents are code again) and regular
    expressions, told apart from division by the last significant character.

    Args:
        source: JavaScript, or a document containing it, as text.

    Returns:
        The same text with every comment character replaced by a space,
        newlines preserved so lines still line up with the original.
    """
    sortie = []
    i, n = 0, len(source)
    # `precedent` is the last significant character of the CODE regions; it is
    # what tells a regular expression from a division.
    precedent = ""
    # Brace depth inside the current code region, and the stack of depths
    # suspended by the enclosing `${` substitutions.
    profondeur, gabarits = 0, []

    def mot_avant(position):
        """True when a keyword ends right before `position` (regex context)."""
        prefixe = source[:position].rstrip()
        return any(prefixe.endswith(mot)
                   and (len(prefixe) == len(mot)
                        or not (prefixe[-len(mot) - 1].isalnum()
                                or prefixe[-len(mot) - 1] in "_$"))
                   for mot in MOTS_AVANT_REGEX)

    while i < n:
        c = source[i]
        paire = source[i:i + 2]

        if paire == "//":
            while i < n and source[i] != "\n":
                sortie.append(" ")
                i += 1
            continue

        if paire == "/*":
            while i < n and source[i:i + 2] != "*/":
                sortie.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                sortie.append("  ")
                i += 2
            continue

        if c in "\"'":
            # A single- or double-quoted string: escapes only, no nesting.
            sortie.append(c)
            i += 1
            while i < n and source[i] != c:
                if source[i] == "\\" and i + 1 < n:
                    sortie.append(source[i:i + 2])
                    i += 2
                    continue
                if source[i] == "\n":  # unterminated: do not eat the file
                    break
                sortie.append(source[i])
                i += 1
            if i < n and source[i] == c:
                sortie.append(c)
                i += 1
            precedent = c
            continue

        if c == "`":
            # A template literal: runs to its closing backtick, except that
            # every `${…}` inside it is code, and is lexed as such.
            sortie.append(c)
            i += 1
            while i < n:
                if source[i] == "\\" and i + 1 < n:
                    sortie.append(source[i:i + 2])
                    i += 2
                    continue
                if source[i] == "`":
                    sortie.append("`")
                    i += 1
                    precedent = "`"
                    break
                if source[i:i + 2] == "${":
                    sortie.append("${")
                    i += 2
                    gabarits.append(profondeur)
                    profondeur = 0
                    precedent = "{"
                    break
                sortie.append(source[i])
                i += 1
            continue

        if c == "}" and profondeur == 0 and gabarits:
            # Closes a `${…}`: back inside the template literal that opened it.
            sortie.append("}")
            i += 1
            profondeur = gabarits.pop()
            while i < n:
                if source[i] == "\\" and i + 1 < n:
                    sortie.append(source[i:i + 2])
                    i += 2
                    continue
                if source[i] == "`":
                    sortie.append("`")
                    i += 1
                    precedent = "`"
                    break
                if source[i:i + 2] == "${":
                    sortie.append("${")
                    i += 2
                    gabarits.append(profondeur)
                    profondeur = 0
                    precedent = "{"
                    break
                sortie.append(source[i])
                i += 1
            continue

        if c == "/" and (precedent == "" or precedent in AVANT_REGEX
                         or mot_avant(i)):
            # A regular expression literal: its `/` delimiters, its character
            # classes (where a `/` is literal) and its escapes.
            sortie.append(c)
            i += 1
            classe = False
            while i < n and source[i] != "\n":
                if source[i] == "\\" and i + 1 < n:
                    sortie.append(source[i:i + 2])
                    i += 2
                    continue
                if source[i] == "[":
                    classe = True
                elif source[i] == "]":
                    classe = False
                elif source[i] == "/" and not classe:
                    sortie.append("/")
                    i += 1
                    break
                sortie.append(source[i])
                i += 1
            precedent = "/"
            continue

        if c == "{":
            profondeur += 1
        elif c == "}":
            profondeur = max(0, profondeur - 1)
        sortie.append(c)
        if not c.isspace():
            precedent = c
        i += 1

    return "".join(sortie)


def compter_history_primitives(source):
    """Counts the direct history primitives left in a document's code.

    Args:
        source: JavaScript, or a document containing it, as text.

    Returns:
        How many `history.pushState|replaceState|back|go|forward(` calls the
        code holds, comments excluded and string/regex contents left alone.
    """
    nettoye = sans_commentaires(source)
    return sum(len(re.findall(motif, nettoye)) for motif in PRIMITIVES)


async def main():
    global _journal
    _journal = Journal("R74 — le pont lie le cluster nav au routeur")

    # ─── Hold (a): the engine holds no primitive of its own ───────────
    refonte = (RACINE / "design" / "refonte.html").read_text(encoding="utf-8")
    appels = compter_history_primitives(refonte)
    verifier(
        "zéro appel direct history.* dans refonte.html",
        appels == 0,
        f"{appels} appel(s) trouvé(s)",
    )

    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")
        ctx = await navigateur.new_context(**TELEPHONE)
        pg = await ctx.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        # ─── Hold (f′): the boot handshake exists and fired on its own ─
        # Navigated WITHOUT going through commun.ouvrir(): that helper calls
        # window.__chargementTermine itself to get past the startup screen,
        # which would force the very effect this hold exists to observe.
        # What is measured here is whether the screen came off BEFORE this
        # harness ever touched that seam — proof the real handshake ran.
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        sonde = await pg.evaluate(
            """()=>({
                demarreur: typeof window.__demarrerMoteur,
                splashMasque: document.querySelector('#splash')?.hidden === true
            })"""
        )
        verifier(
            "window.__demarrerMoteur existe",
            sonde["demarreur"] == "function",
            f"typeof window.__demarrerMoteur = {sonde['demarreur']}",
        )
        verifier(
            "l'écran de démarrage s'efface tout seul, avant tout appel du harnais",
            sonde["splashMasque"],
            f"#splash.hidden = {sonde['splashMasque']}",
        )

        # Same plumbing commun.ouvrir() would run, on the same page, now
        # that the hold above has taken its measurement: idempotent (it only
        # re-sets #splash.hidden), so calling it again here is harmless.
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
        await pg.wait_for_timeout(250)

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

        # Scrolled away from the top before leaving, so the return has a
        # position to restore and not merely a list to redraw.
        await pg.evaluate(
            "()=>{document.querySelector('#screen .port').scrollTop = 300;}"
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
        # The restored position is asserted, not merely collected: the record
        # says the journey holds the scroll, and a collected number nobody
        # judges is the one thing this harness exists to prevent. Same
        # tolerance as R71, which holds the same journey off the bridge.
        verifier(
            "avec sa position de défilement",
            abs(retour_state["scroll"] - 300) <= 40,
            f"{retour_state['scroll']}px",
        )

        await navigateur.close()

    # ─── Hold (c): deep-URL entry ─────────────────────────────────────
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

        # ─── Hold (d): __go() does not change history depth ────────────
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
