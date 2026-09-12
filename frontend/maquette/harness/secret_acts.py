"""R167 — the two acts a secret offers DO what they say (B-334, B-335).

Reported of both: « ne fait rien », and of the second « il devrait proposer une
confirmation ».

Both actions carried `target: { toast: … }` — a panel action's `target` IS its
`data-*` map, and `data-toast` says a sentence and moves nothing. No layer was
written, no cache, no state: the interface would have said « remplacée » with
nothing replaced, which is NE-DOIT-PAS-1 read from the closest possible range.

WHAT THIS RULE READS IS THE LAYER, NEVER THE MESSAGE. A message is what the
defect already produced; counting it would certify the defect. The layer's own
record — `window.__mocks.answered()` — says the call happened, and the secrets
read back afterwards says what it did.

AND REMOVING A KEY IS DESTRUCTIVE, so the walk goes through the CANCEL first.
Cutting a provider cuts it for every account of the household (§17), which is
the case NE-DOIT-PAS-6 covers; a confirmation one can only tap THROUGH is a
delay, not a confirmation. Cancelling must leave the key exactly where it was
and say nothing about a removal. The sentence itself is dictated, and the hold
reads its substance rather than its punctuation.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

from playwright.async_api import async_playwright

# Typed into the secret's field. A secret's value is never read back by the
# interface, so this is only ever seen by the layer — which is the point.
TYPED = "rule-secret-probe"

# WHAT THE LAYER HOLDS about the secrets, read through the query cache: the
# same answer the panel was built from, rather than a second opinion about it.
SECRETS = """()=>(window.__queries?.getQueryData(['/api/config/secrets']) || [])
  .map((one) => ({k: one.k, def: !!one.def}))"""

DIALOG = """()=>{const dialog = document.querySelector('#dlg');
  if (!dialog || !dialog.hasAttribute('data-open')) return null;
  return {text: dialog.textContent.replace(/\\s+/g, ' ').trim(),
          actions: [...dialog.querySelectorAll('button')]
            .map((one) => one.textContent.trim())};}"""


async def open_at(browser, address):
    """Opens the prototype AT an address, past the startup screen."""
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(PROTOTYPE + address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(320)
    return context, page, errors


async def main():
    journal = Journal("R167 — a secret's two acts")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page, errors = await open_at(browser, "settings")
        await page.click('[data-topic="secrets"]')
        await page.wait_for_timeout(450)

        held = await page.evaluate(SECRETS)
        posed = next((one for one in held if one["def"]), None)
        journal.check("the secrets rubric holds a key that is SET",
                      posed is not None, str(held))

        # ── B-334: REPLACING A VALUE WRITES THE LAYER ──────────────────────
        if posed is not None:
            await page.click(f'[data-secret="{posed["k"]}"]')
            await page.wait_for_timeout(450)
            entry = await page.query_selector('#sheetin [data-part="secret/field"]')
            journal.check(
                "the secret's panel offers somewhere to PUT a new key (B-334)",
                entry is not None,
                (await page.evaluate(
                    "()=>(document.querySelector('#sheetin')||{}).textContent||''"))[:200])
            act = await page.query_selector('#sheetin [data-replacesecret]')
            journal.check("and « Remplacer la valeur » is an act, not a sentence "
                          "(B-334)", act is not None, str(act is not None))
            calls_before = await page.evaluate(
                "()=>window.__mocks.answered().length")
            if entry is not None and act is not None:
                await entry.click()
                await page.keyboard.type(TYPED)
                await act.click()
                await page.wait_for_timeout(800)
            wrote = await page.evaluate(
                """(n)=>window.__mocks.answered().slice(n)
                     .filter((one) => one.operationId === 'updateSecrets')""",
                calls_before)
            journal.check(
                "and tapping it WRITES the key through the layer — not a toast "
                "over nothing (B-334)",
                bool(wrote), str(wrote))
            after = await page.evaluate(SECRETS)
            journal.check(
                "the key stays posed afterwards, and its value is still never "
                "read back",
                any(one["k"] == posed["k"] and one["def"] for one in after),
                str(after))

        # ── B-335: REMOVING A KEY ASKS FIRST, AND THE CANCEL IS REAL ───────
        await page.evaluate("()=>window.__panel?.close()")
        await page.wait_for_timeout(400)
        held = await page.evaluate(SECRETS)
        posed = next((one for one in held if one["def"]), None)
        if journal.check("a set key is still there to be removed",
                         posed is not None, str(held)):
            await page.click(f'[data-secret="{posed["k"]}"]')
            await page.wait_for_timeout(450)
            remove = await page.query_selector('#sheetin [data-removesecret]')
            journal.check("« Retirer la clé » is an act, not a sentence (B-335)",
                          remove is not None, str(remove is not None))
            calls_before = await page.evaluate(
                "()=>window.__mocks.answered().length")
            if remove is not None:
                await remove.click()
                await page.wait_for_timeout(500)
            asked = await page.evaluate(DIALOG)
            journal.check("and it ASKS before it cuts (B-335, §17, NE-DOIT-PAS-6)",
                          asked is not None, str(asked))
            journal.check(
                "the question says the key goes for every account of the "
                "household",
                asked is not None and "foyer" in asked["text"].lower(),
                (asked or {}).get("text", "")[:160])
            journal.check("and it offers a way out as well as a way through",
                          asked is not None and len(asked["actions"]) >= 2,
                          str((asked or {}).get("actions")))

            # CANCELLING LEAVES THE KEY WHERE IT WAS, and calls nothing.
            await page.evaluate(
                """()=>{const out = [...document.querySelectorAll('#dlg button')]
                  .find((one) => !('confirmRemoveSecret' in one.dataset));
                  if (out) out.click();}""")
            await page.wait_for_timeout(450)
            cancelled = await page.evaluate(SECRETS)
            calls_after_cancel = await page.evaluate(
                """(n)=>window.__mocks.answered().slice(n)
                     .filter((one) => one.operationId === 'updateSecrets')""",
                calls_before)
            journal.check("cancelling leaves the key posed (B-335)",
                          any(one["k"] == posed["k"] and one["def"]
                              for one in cancelled), str(cancelled))
            journal.check("and writes nothing at all",
                          not calls_after_cancel, str(calls_after_cancel))

            # CONFIRMING REMOVES IT, and only then.
            await page.evaluate("()=>window.__panel?.close()")
            await page.wait_for_timeout(400)
            await page.click(f'[data-secret="{posed["k"]}"]')
            await page.wait_for_timeout(450)
            await page.evaluate(
                """()=>{const act = document.querySelector('#sheetin [data-removesecret]');
                  if (act) act.click();}""")
            await page.wait_for_timeout(500)
            await page.evaluate(
                """()=>{const go = document.querySelector('#dlg [data-confirm-remove-secret]');
                  if (go) go.click();}""")
            await page.wait_for_timeout(800)
            removed = await page.evaluate(SECRETS)
            journal.check("confirming CLEARS the key through the layer (B-335)",
                          any(one["k"] == posed["k"] and not one["def"]
                              for one in removed), str(removed))

        journal.check("no JS error over the whole walk", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
