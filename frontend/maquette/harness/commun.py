"""What every rule script needs, in one place.

Twelve scripts carried a byte-identical `verifier()`, fourteen their own `BAR`,
and thirty-two the same four lines to open the prototype. That is not a style
question: when the startup screen started covering the frame for as long as the
load it stands for, twenty-eight scripts had to be edited by hand to close that
wait, and a script that had been forgotten would have failed for a reason that
has nothing to do with the rule it carries.

A script still owns its own rules, its own state driving and its own probes.
What it borrows here is the plumbing: how a verdict is printed, how a run ends,
and how the document is opened.
"""
import pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent
PROTOTYPE = "http://127.0.0.1:8899/wrapped.html"
BAR = "─" * 62

# The phone the design targets. Every measurement is taken here, because a
# geometry read at another width answers a question nobody asked.
# The appearance is PINNED: the document's « systeme » mode follows the
# browser's colour-scheme preference, and a headless browser's preference is
# an accident of its defaults. The rules measure the reference appearance —
# dark — deterministically; a rule that wants to measure the light theme
# passes color_scheme="light" itself.
TELEPHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2,
             "is_mobile": True, "has_touch": True, "color_scheme": "dark"}


class Journal:
    """Collects the verdicts of one script and decides its exit code.

    A rule that only prints cannot fail, and a script that cannot fail is a
    report nobody is obliged to read — so the count and the failures live
    together, and `bilan()` is what ends the process.
    """

    def __init__(self, titre):
        self.titre = titre
        self.faits = 0
        self.echecs = []
        print(f"{BAR}\n{titre}\n{BAR}")

    def verifier(self, nom, condition, detail=""):
        """Records one executed check and its verdict.

        Args:
            nom: What is being held to, phrased as the interface's promise.
            condition: The measurement's verdict.
            detail: What was measured, printed either way — a green line that
                shows its number is what makes a rule readable a year later.
        """
        self.faits += 1
        print(("  OK   " if condition else "  ECHEC") + f" {nom}"
              + (f" — {detail}" if detail else ""))
        if not condition:
            self.echecs.append(nom)
        return bool(condition)

    def bilan(self, erreurs=()):
        """Prints the run's summary and exits non-zero on any failure.

        Args:
            erreurs: JS errors collected from the page, which are failures even
                when every rule passed.
        """
        print()
        print(f"{BAR}\n{self.faits} règles EXÉCUTÉES — "
              + ("aucune violation" if not self.echecs
                 else f"{len(self.echecs)} violation(s) : {', '.join(self.echecs)}"))
        if erreurs:
            print("erreurs JS :", list(erreurs))
        if self.echecs or erreurs:
            raise SystemExit(1)


async def ouvrir(navigateur, **kwargs):
    """Opens the prototype in a fresh context, past the startup screen.

    The startup screen covers the frame for as long as the load it stands for
    lasts. Nothing is fetched here, so the wait is closed through the same seam
    the app uses rather than slept out — a sleep would be slower and would still
    be a race.

    Args:
        navigateur: A launched Playwright browser.
        **kwargs: Context overrides — a user agent, an init script, anything a
            script needs that the phone defaults do not carry.

    Returns:
        The (context, page) pair, on a page that has dismissed the design note.
    """
    ctx = await navigateur.new_context(**{**TELEPHONE, **kwargs})
    pg = await ctx.new_page()
    await pg.goto(PROTOTYPE, wait_until="load")
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(250)
    return ctx, pg
