"""R166 — an edit is FILED when one says so, WRITTEN when one saves, and the save is told the truth (B-341, B-342, B-343).

Three defects met in one sitting, walking the settings by hand, and they
compound: each one hides the next.

  · B-341 — « Pas de bouton de validation d'un changement faut sortir du champ ».
    The field bound the native `change` event, which fires once on BLUR. On a
    phone, the keyboard's « ✓ » does not always blur, so the edit the operator
    had typed was simply never filed. The panel offered no control that would
    file it.
  · B-342 — « quand on a enregistré sur la liste la valeur est reset à la valeur
    d'origine ». The mock recorded the file's NAME and never read the request's
    BODY, so the next read answered the seed: the interface said the file was
    written and showed that it was not (NE-DOIT-PAS-1, and D7 — a layer that
    answers without moving certifies nothing).
  · B-343 — « Aucun redémarrer maintenant apparaît ». The restart flag was
    raised on an ENGINE object that nothing re-renders, so the banner appeared at
    the next render caused by something else, or never. That is why B-300's
    confirmation could not be reached through a save at all.

THE WALK IS THE OPERATOR'S, not a named state: a load of `/settings` at its
address, a real click into a rubric, a real click on a row, a real keyboard, a
real tap on « Valider », a real tap on « Enregistrer ». A hold that drove
`settings-edited` would arrive with the edit already filed and measure none of
this — which is exactly how all three lived under sixty-five green holds.

THE NATIVE `change` PATH IS CUT WHILE THE BUTTON IS MEASURED, and this is the
one part of the walk that is not a finger's. The button sits in the same panel
as the field, so tapping it blurs the field, so the native listener commits —
and a hold that simply typed and tapped would be GREEN over a « Valider » that
does nothing at all, which is the defect. The rule therefore stops `change`
from reaching the input (one capturing listener on the document, added by the
rule and removed after it) so that the only thing left that can file the edit is
the button. That is also the real case B-341 reports: a keyboard that commits
without blurring.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

from playwright.async_api import async_playwright

# Typed into the field by a real keyboard. Nothing a real setting could hold, so
# reading it back anywhere names the path it travelled rather than a coincidence.
TYPED = "127.0.0.77"

# THE NATIVE COMMIT, CUT AND RESTORED. A capturing listener on the document
# never lets `change` reach the input, so the element's own listener — the blur
# path — cannot run. Capture on an ancestor precedes the target's own handlers
# whatever order they were registered in, which is what makes this reliable.
CUT_THE_BLUR_PATH = """()=>{
  window.__ruleBlockChange = (event) => event.stopPropagation();
  document.addEventListener('change', window.__ruleBlockChange, true);}"""
RESTORE_THE_BLUR_PATH = """()=>{
  document.removeEventListener('change', window.__ruleBlockChange, true);}"""

# What the bottom bar and the panel say, read the way they are SEEN. Written
# with SINGLE quotes inside the triple-quoted string: the guard that pairs a
# selection with the markup emitting it reads these files as raw text, so an
# escaped quote makes the selection invisible to it and the pair goes unheld.
STANDING = r"""()=>({
  path: location.pathname + location.search,
  depth: history.length,
  inRubric: !!document.querySelector('[data-part="screen/back"]'),
  rows: document.querySelectorAll('[data-part="setting/row"]').length,
  pending: (document.querySelector('[data-part="save-bar/pending"]')
    || {}).textContent || '',
  bar: !!document.querySelector('#savebar [data-save]'),
  panel: (document.querySelector('#sheetin') || {}).textContent || '',
  field: (document.querySelector('#sheetin [data-part="field/input"]') || {}).value || '',
  banners: [...document.querySelectorAll('[data-part="load-error"]')]
    .map((one) => one.textContent.replace(/\s+/g, ' ').trim())})"""

# Every row of the open rubric, with the value it prints.
ROWS = """()=>[...document.querySelectorAll('[data-part="setting/row"]')].map((row) => ({
  id: row.dataset.setting || '',
  value: (row.querySelector('[data-part="setting/value"]') || {}).textContent || ''}))"""


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
    journal = Journal("R166 — filing an edit, writing it, and being told")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page, errors = await open_at(browser, "settings")

        # ── into a rubric, and onto a row that carries a TEXT field ────────
        rubrics = await page.evaluate(
            """()=>[...document.querySelectorAll('[data-topic]')]
                 .map((one) => one.dataset.topic).filter((one) => one !== 'secrets')""")
        editable = None
        if journal.check("the settings offer a rubric to enter", bool(rubrics),
                         str(rubrics)):
            # The row is chosen by the TYPE the layer answers, never by a
            # literal id: a fixture reword would otherwise fell this rule for a
            # reason that is not a defect.
            for rubric in rubrics:
                await page.click(f'[data-topic="{rubric}"]')
                await page.wait_for_timeout(420)
                found = await page.evaluate(
                    """()=>{const topics = window.__queries
                        ?.getQueryData(['/api/config/schema']) || [];
                      const text = topics.flatMap((t) => t.r)
                        .find((s) => s.type === 'path' || s.type === 'text');
                      return text ? (text.f + ':' + text.c) : null;}""")
                if found and await page.query_selector(f'[data-setting="{found}"]'):
                    editable = found
                    break
                await page.evaluate("()=>history.back()")
                await page.wait_for_timeout(420)

        if journal.check("and a rubric holding a setting one can type into",
                         editable is not None, str(editable)):
            before_rows = await page.evaluate(ROWS)
            stored = next((row["value"] for row in before_rows
                           if row["id"] == editable), "")
            await page.click(f'[data-setting="{editable}"]')
            await page.wait_for_timeout(450)

            # ── B-341: THE TAP FILES THE EDIT, WITHOUT A BLUR ──────────────
            await page.evaluate(CUT_THE_BLUR_PATH)
            await page.click('#sheetin [data-part="field/input"]')
            # Selected and replaced, the way a thumb does it — and `Meta+A` is
            # the platform's own « select all », which `Control+A` is not here:
            # typed after it, the probe was APPENDED to the stored path and the
            # read-back compared two strings that were both wrong.
            await page.keyboard.press("Meta+A")
            await page.keyboard.type(TYPED)
            before_commit = await page.evaluate(STANDING)
            journal.check(
                "nothing is filed by typing alone — the two-step writing of "
                "DOIT-8 is untouched",
                "attente" not in before_commit["pending"],
                before_commit["pending"][:80])
            commit = await page.query_selector('#sheetin [data-commitsetting]')
            journal.check("the field's panel offers « Valider » (B-341)",
                          commit is not None,
                          before_commit["panel"][:160])
            if commit is not None:
                await commit.click()
                await page.wait_for_timeout(450)
            await page.evaluate(RESTORE_THE_BLUR_PATH)
            filed = await page.evaluate(STANDING)
            journal.check(
                "and a tap on it files the edit WITHOUT the field losing focus "
                "(B-341)",
                "attente" in filed["pending"],
                filed["pending"][:80])
            journal.check(
                "the panel names the typed value « nouvelle », not « actuelle » "
                "(B-341)",
                "Nouvelle valeur" in filed["panel"] and TYPED in filed["panel"],
                filed["panel"][:200])
            journal.check(
                "and it names the file's own value « enregistrée » (B-341)",
                "Valeur enregistrée" in filed["panel"],
                filed["panel"][:200])

            # ── B-342: SAVING MOVES THE LAYER, AND THE ROW SAYS SO ─────────
            calls_before = await page.evaluate(
                "()=>window.__mocks.answered().length")
            # THE PANEL IS SHUT BY THE SYSTEM GESTURE, which is how a thumb
            # shuts it: its scrim covers the save bar, exactly as it covers it
            # for a finger, so « Enregistrer » is not reachable until it is
            # gone. `history.back()` rather than `__panel.close()` — the panel
            # is addressable and pushed its own entry, so the gesture that
            # closes it is the one that pops that entry, and driving the seam
            # instead would leave the stack describing a panel nobody is
            # looking at.
            # BACK UNTIL THE PANEL IS GONE, and the loop is not politeness: a
            # panel RE-PRODUCED after an edit pushes a second entry of its own,
            # so shutting it takes as many steps as it was opened in. That is
            # the field's long-standing behaviour — the native blur path
            # re-produces exactly the same way — and this rule measures the
            # edit, not the ladder, so it walks the steps rather than driving
            # the seam that would hide them.
            for _ in range(4):
                if "panel=" not in await page.evaluate("()=>location.search"):
                    break
                await page.evaluate("()=>history.back()")
                await page.wait_for_timeout(450)
            standing = await page.evaluate(STANDING)
            # READ ON THE RUBRIC ITSELF, never on the save bar: the bar is
            # PORTALLED beside the page and drawn on every branch of it, so a
            # hold that read the bar would be green with the rubric shut — the
            # exact vacuous reading this rule found in its own first draft.
            journal.check(
                "shutting the panel leaves the reader IN the rubric, not back "
                "on the list of rubrics",
                standing["inRubric"] and standing["rows"] > 0
                and "attente" in standing["pending"],
                f"back={standing['inRubric']} rows={standing['rows']} at "
                f"{standing['path']} pending={standing['pending']!r}")
            save = await page.query_selector('#savebar [data-save]')
            if save is not None:
                await save.click()
                await page.wait_for_timeout(900)
            written = await page.evaluate(
                """(n)=>window.__mocks.answered().slice(n)
                     .filter((one) => one.operationId === 'updateConfigurationFile')""",
                calls_before)
            journal.check("« Enregistrer » really writes the file through the layer",
                          bool(written), str(written))
            # READ BACK THROUGH THE LAYER, never through the message: a toast
            # is what B-342 IS — the interface saying a thing it had not done.
            answered = await page.evaluate(
                """(id)=>{const topics = window.__queries
                    ?.getQueryData(['/api/config/schema']) || [];
                  const one = topics.flatMap((t) => t.r)
                    .find((s) => (s.f + ':' + s.c) === id);
                  return one ? String(one.brut) : null;}""", editable)
            journal.check(
                "and the layer ANSWERS the written value on the next read "
                "(B-342)",
                answered == TYPED, f"{stored!r} → {answered!r}, typed {TYPED!r}")
            after_save = await page.evaluate(STANDING)
            after_rows = await page.evaluate(ROWS)
            shown = next((row["value"] for row in after_rows
                          if row["id"] == editable), None)
            journal.check("so the row shows what was written, not the seed (B-342)",
                          shown is not None and TYPED in shown,
                          f"{stored!r} → {shown!r} at {after_save['path']}, "
                          f"in rubric={after_save['inRubric']}, "
                          f"{len(after_rows)} row(s)")

            # ── B-343: THE RESTART BANNER FOLLOWS THE SAVE ─────────────────
            restart_banner = next(
                (one for one in after_save["banners"]
                 if "redémarr" in one.lower()), None)
            journal.check(
                "the restart banner comes up BECAUSE the save happened (B-343)",
                restart_banner is not None, str(after_save["banners"]))
            offer = await page.query_selector('[data-restart]')
            journal.check("and it offers the restart the operator has to confirm",
                          offer is not None, str(restart_banner))
            # AND B-300 IS REACHABLE FROM HERE, which is the whole reason this
            # hold exists: the confirmation was fixed and could not be walked to.
            if offer is not None:
                await offer.click()
                await page.wait_for_timeout(500)
                asked = await page.evaluate(
                    """()=>{const dialog = document.querySelector('#dlg');
                      return dialog && dialog.hasAttribute('data-open')
                        ? dialog.textContent.replace(/\\s+/g, ' ').trim() : null;}""")
                journal.check(
                    "so B-300's confirmation is reachable by the path a hand "
                    "walks, and not only from a named state",
                    asked is not None, str(asked))
                await page.evaluate(
                    """()=>{const out = [...document.querySelectorAll('#dlg button')]
                      .find((one) => !('confirmrestart' in one.dataset));
                      if (out) out.click();}""")
                await page.wait_for_timeout(350)

        journal.check("no JS error over the whole walk", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
