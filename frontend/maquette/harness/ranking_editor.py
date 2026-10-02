"""R266 — the ranking editor lists what `ranking.json5` holds, never a constant.

§ 18: the ranking follows the ratio, and the operator edits it where it is
written. The editor opens on the file's own content, read through the file's
own operation: every criterion the file holds, in its order, with its weight
and its scoring — a score per value, or its thresholds. Read here against the
very seed the layer answers from, so a list drawn from anywhere else falls.

1. `ranking-editor` draws one row per criterion of the file, in the file's order;
2. each row's weight is the file's;
3. each row's scoring names every value the file scores, or every threshold;
4. from Réglages, a finger on « Classement des releases » opens the GLOBAL
   quality profile, and there a finger on « Poids du classement » lands on the
   editor, as an arrival;
5. from a quality screen, a finger on « Poids du classement » lands on the
   editor, and says no promise in a toast (B-298);
6. `ranking-editor-loading` draws no criterion while the file is read, and
   `ranking-editor-error` says the read failed rather than an empty list;
7. a weight typed and « Enregistrer » tapped writes `ranking.json5` through
   `updateConfigurationFile`, once, and says so;
8. the NEXT read of the file — the screen entered again on a fresh read —
   answers the saved weight, and every other weight as it was;
9. `ranking-editor-saving` keeps the typed weight and says the save is under
   way, its button closed to a second tap;
10. `ranking-editor-save-conflict` says the file moved, in the settings' own
   words, and the next read answers the file's weight: nothing was written;
11. a second editor still holding the digest read BEFORE a save is refused —
   the write answers a conflict and the next read keeps the saved weight;
12. a save the layer REFUSES (a 500) leaves « Enregistrement… », reopens the
   button and SAYS the refusal — never a save left spinning;
13. every control the editor adds is a finger's target: each weight field and
   « Relire le classement » at least 44 px high.

The layer's CONFLICT is the maquette contract's `200 {conflict: true}`; the
backend answers a conflict with HTTP 412 instead — a divergence recorded in the
lot's ledger, not repaired here, and a real 412 reaches hold 12's path.

RE-AIMED OUT LOUD: hold 4 first read « the rubric lands on the editor ». The
rubric opens the global quality profile — a route of its own, held by
`page_host.py` — and the promise B-298 names was that profile's weights button,
a toast. The rubric keeps its route; the path to the editor runs through it.

RE-AIMED OUT LOUD: hold 2 first read the weight as the row's text. The weight
became the field the operator types it into, so it is read as that field's
value — the same number, the file's.

Holds 12–13 came with correction round C16, red while `send`'s rethrow skipped
`setSaving(false)` and the fields stood at 39 and 35 px.

Red before the move: no screen answers `/settings/ranking`; holds 7–10: no
weight can be typed and nothing saves.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, browser_channel, chrome_launch_args, open_page, ready
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
FILES = json.loads((SOURCE / "mocks/seeds/configuration-files.json").read_text(encoding="utf-8"))
SEEDED = next(file for file in FILES if file["name"] == "ranking.json5")
RANKING = SEEDED["values"]["ranking"]

SETTINGS_WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]
RUBRIC = SETTINGS_WORDS["settings"]["rankingTitle"]
SAVE = SETTINGS_WORDS["ranking"]["save"]
SAVING = SETTINGS_WORDS["ranking"]["saving"]
CONFLICT = SETTINGS_WORDS["settings"]["conflictLead"]
REFUSED = SETTINGS_WORDS["ranking"].get("saveRefused", "<no copy>")
FINGER = 44
HEIGHTS = """(selector) => [...document.querySelectorAll(selector)].map(one => Math.round(one.getBoundingClientRect().height))"""
# EVERY toast shown, kept as it is shown: a later one replacing it must not hide it.
WATCH_TOASTS = """() => { window.__seenToasts = [];
  const toast = document.getElementById('toast');
  if (toast) new MutationObserver(() => window.__seenToasts.push(toast.textContent.trim()))
    .observe(toast, {childList: true, subtree: true, characterData: true}); }"""
REREAD = """()=>{window.__queries?.removeQueries({queryKey: ['/api/config/files/ranking.json5']});
  window.__screens.ranking()}"""
STALE_WRITE = """async ({values, digest}) => (await (await fetch('/api/config/files/ranking.json5',
  {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({values, digest})})).json())"""
STORED = """async (field) => (await (await fetch('/api/config/files/ranking.json5')).json())
  .values.ranking.criteria.find((one) => one.field === field)?.weight ?? null"""
WEIGHTS = SETTINGS_WORDS["profile"]["rankingWeights"]
ROWS = """() => [...document.querySelectorAll('[data-part="ranking/criterion"]')].map(row => ({
  field: row.dataset.field,
  weight: row.querySelector('[data-part="ranking/weight"]')?.value ?? '',
  scoring: row.querySelector('[data-part="ranking/scoring"]')?.textContent.trim() ?? '',
}))"""


def number(value):
    """A weight or a threshold as the interface writes it: a decimal comma, no trailing zero.

    A threshold the file writes as words (« 1GB ») is written as the file wrote it.
    """
    return value if isinstance(value, str) else f"{value:g}".replace(".", ",")


async def main():
    journal = Journal("R266 — the ranking editor lists what ranking.json5 holds")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('ranking-editor');return null}catch(error){return String(error)}}")
        await ready(page)
        journal.check("the named state ranking-editor exists", answer is None, answer or "")
        where = await page.evaluate("()=>location.pathname")
        journal.check("it stands at /settings/ranking", where.endswith("/settings/ranking"), where)
        drawn = await page.evaluate(ROWS)
        criteria = RANKING["criteria"]
        journal.check("one row per criterion of the file, in the file's order",
                      [row["field"] for row in drawn] == [criterion["field"] for criterion in criteria],
                      f"{[row['field'] for row in drawn]} against {[criterion['field'] for criterion in criteria]}")
        by_field = {row["field"]: row for row in drawn}
        for criterion in criteria:
            row = by_field.get(criterion["field"], {"weight": "", "scoring": ""})
            journal.check(f"{criterion['field']}: its weight is the file's, {number(criterion['weight'])}",
                          number(criterion["weight"]) in row["weight"], repr(row["weight"]))
            wanted = ([f"{value} {score}" for value, score in (criterion.get("values") or {}).items()]
                      or [f"{number(threshold['at'])}" for threshold in criterion.get("thresholds") or []])
            journal.check(f"{criterion['field']}: its scoring names every one of the file's {len(wanted)}",
                          bool(wanted) and all(one in row["scoring"] for one in wanted), repr(row["scoring"][:120]))

        # ── the two ways in, by a finger (B-298) ─────────────────────────
        async def lands(start, locator, label):
            await page.evaluate(f"()=>window.__go('{start}')")
            await page.wait_for_timeout(SETTLED)
            before = await page.evaluate("()=>history.length")
            target = page.locator(locator, has_text=label)
            if await target.count():
                await target.first.tap()
                await page.wait_for_timeout(SETTLED)
            return await page.evaluate("""()=>({path: location.pathname, length: history.length,
                rows: document.querySelectorAll('[data-part="ranking/criterion"]').length,
                toast: document.querySelector('#toast[data-shown]')?.textContent.trim() || null})"""), before
        # THE RUBRIC BY WHAT IT IS, not by its words: another topic's subtitle
        # quotes « Classement des releases ».
        where, before = await lands("settings", '#view [data-part="topic"][data-profile]', RUBRIC)
        journal.check(f"from Réglages, « {RUBRIC} » opens the global quality profile",
                      where["path"].endswith("/quality/global"), str(where))
        weights = page.locator('[data-part="card/foot"]', has_text=WEIGHTS)
        if await weights.count():
            await weights.first.tap()
            await page.wait_for_timeout(SETTLED)
        where = await page.evaluate("""()=>({path: location.pathname, length: history.length,
            rows: document.querySelectorAll('[data-part="ranking/criterion"]').length})""")
        journal.check(f"and there « {WEIGHTS} » lands on the editor, as an arrival",
                      where["path"].endswith("/settings/ranking") and where["rows"] == len(criteria)
                      and where["length"] == before + 2, f"{where} · history.length {before}")
        where, before = await lands("screen-profile", '[data-part="card/foot"]', WEIGHTS)
        journal.check(f"from a quality screen, « {WEIGHTS} » lands on the editor, with no promise in a toast",
                      where["path"].endswith("/settings/ranking") and where["rows"] == len(criteria)
                      and not where["toast"], str(where))

        # ── while the file is read, and when the read fails ─────────────
        for state, wanted in (("ranking-editor-loading", "loading"), ("ranking-editor-error", "error")):
            answer = await page.evaluate(
                f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
            await page.wait_for_timeout(SETTLED)
            seen = await page.evaluate("""()=>({rows: document.querySelectorAll('[data-part="ranking/criterion"]').length,
                skeleton: document.querySelector('[data-part="screen"] [data-skeleton]') !== null,
                error: document.querySelector('[data-part="screen"] [data-part="surface-error"]') !== null})""")
            journal.check(f"{state}: no criterion, and {'the read is shown under way' if wanted == 'loading' else 'the failure is said'}",
                          answer is None and seen["rows"] == 0 and (seen["skeleton"] if wanted == "loading" else seen["error"]),
                          f"{answer or ''} {seen}")

        # ── the save, and the read that follows it (F16) ─────────────────
        async def enter(state):
            answer = await page.evaluate(
                f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
            await page.wait_for_timeout(SETTLED)
            return answer

        target = criteria[0]
        typed = target["weight"] + 2
        weight = f'[data-part="ranking/criterion"][data-field="{target["field"]}"] [data-part="ranking/weight"]'
        await enter("ranking-editor")
        calls = await page.evaluate("()=>window.__mocks.answered().length")
        walked = {"field": await page.locator(weight).count(), "save": await page.locator('[data-part="ranking/save"]').count()}
        if walked["field"]:
            await page.locator(weight).first.tap()
            await page.keyboard.press("ControlOrMeta+A")
            await page.keyboard.type(str(typed))
        if walked["save"]:
            await page.locator('[data-part="ranking/save"]').first.tap()
            await page.wait_for_timeout(SETTLED)
        written = await page.evaluate(
            """(n)=>window.__mocks.answered().slice(n).filter((one) => one.operationId === 'updateConfigurationFile')
                 .map((one) => one.path)""", calls)
        toast = await page.evaluate("()=>document.querySelector('#toast[data-shown]')?.textContent.trim() || null")
        journal.check("« Enregistrer » writes ranking.json5 through updateConfigurationFile, once, and says so",
                      len(written) == 1 and written[0].endswith("/ranking.json5") and toast is not None
                      and "ranking.json5" in toast, f"walked {walked}: {written} · toast {toast!r}")
        await page.evaluate(REREAD)
        await page.wait_for_timeout(SETTLED)
        readAgain = {row["field"]: row["weight"] for row in await page.evaluate(ROWS)}
        wanted = {criterion["field"]: number(criterion["weight"]) for criterion in criteria}
        wanted[target["field"]] = number(typed)
        journal.check(f"the NEXT read answers the saved weight {typed} for {target['field']}, the others as they were",
                      {field: number(float(value)) if value else "" for field, value in readAgain.items()} == wanted,
                      f"{readAgain} against {wanted}")

        stale = await page.evaluate(STALE_WRITE, {"values": SEEDED["values"], "digest": SEEDED["digest"]})
        kept = await page.evaluate(STORED, target["field"])
        journal.check("a second editor holding the digest read before the save is refused: a conflict, "
                      f"and the next read keeps the saved {typed}",
                      stale.get("conflict") is True and kept == typed, f"answered {stale} · read {kept!r}")

        answer = await enter("ranking-editor-saving")
        seen = await page.evaluate(f"""()=>({{field: document.querySelector('{weight}')?.value ?? null,
            save: document.querySelector('[data-part="ranking/save"]')?.textContent.trim() ?? null,
            closed: document.querySelector('[data-part="ranking/save"]')?.disabled ?? null}})""")
        journal.check(f"ranking-editor-saving keeps the typed weight and says « {SAVING} », the button closed",
                      answer is None and seen["field"] == str(typed) and seen["save"] == SAVING and seen["closed"] is True,
                      f"{answer or ''} {seen}")

        answer = await enter("ranking-editor-save-conflict")
        banner = await page.evaluate("""()=>document.querySelector('[data-part="screen"] [data-part="load-error"]')
            ?.textContent.trim() ?? null""")
        # THE LAYER, not the screen: after a conflict the screen keeps the typed
        # weight on purpose — the operator's work is not thrown away.
        stored = await page.evaluate(STORED, target["field"])
        journal.check(f"ranking-editor-save-conflict says « {CONFLICT} », and the next read answers the file's "
                      f"{number(target['weight'])}: nothing was written",
                      answer is None and banner is not None and CONFLICT in banner
                      and stored == target["weight"], f"{answer or ''} banner {banner!r} · read {stored!r}")
        again = await page.evaluate(HEIGHTS, '[data-part="ranking/read-again"]')

        # ── a refused save is said, and lets go ──────────────────────────
        await enter("ranking-editor")
        fields = await page.evaluate(HEIGHTS, '[data-part="ranking/weight"]')
        journal.check(f"each weight field and « Relire le classement » is at least {FINGER} px high",
                      bool(fields) and bool(again) and min(fields + again) >= FINGER,
                      f"fields {sorted(set(fields))} · read again {again}")
        await page.evaluate("()=>window.__mocks.setOperationOutcome('updateConfigurationFile', {status: 500})")
        await page.evaluate(WATCH_TOASTS)
        if await page.locator(weight).count():
            await page.locator(weight).first.tap()
            await page.keyboard.press("ControlOrMeta+A")
            await page.keyboard.type(str(typed))
        if await page.locator('[data-part="ranking/save"]').count():
            await page.locator('[data-part="ranking/save"]').first.tap()
        await page.wait_for_timeout(SETTLED)
        seen = await page.evaluate(f"""()=>({{save: document.querySelector('[data-part="ranking/save"]')?.textContent.trim() ?? null,
            closed: document.querySelector('[data-part="ranking/save"]')?.disabled ?? null,
            field: document.querySelector('{weight}')?.value ?? null,
            toasts: (window.__seenToasts || []).join(' | ')}})""")
        journal.check(f"a refused save leaves « {SAVING} », reopens the button, keeps the weight and says « {REFUSED} »",
                      seen["save"] == SAVE and seen["closed"] is False and seen["field"] == str(typed)
                      and REFUSED in seen["toasts"], str(seen))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
