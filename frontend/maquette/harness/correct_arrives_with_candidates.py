"""R403 — « Corriger » arrives with candidates (L24 S5, DOIT-7, § 3).

The act of a settled decision's block (OPEN 7 = A: one act for both authors).
On an identification the engine made alone it CREATES the decision —
`enqueueForResolution`; on the operator's own choice it RE-OPENS it by its id —
`reopenDecision`, on a shelved medium's Médiathèque sheet too (OPEN 8 = A).
The call comes BEFORE the candidates screen, and the screen opens on the
candidates the call filed. A refused call says why in the interface's own words
and opens nothing.

WHAT IS READ, each walked by a tap on « Corriger »:

  1. the engine's identification (journey sheet): `enqueueForResolution`
     answered 200, then the screen of that folder;
  2. the operator's choice (journey sheet): `reopenDecision` answered 200, the
     screen;
  3. a shelved medium (Médiathèque sheet): `reopenDecision`, the screen;
  4. a decision left as it was (« The Alabama Solution »): `reopenDecision`,
     the screen;
     and on each screen, THE DECISION'S OWN CANDIDATES — as many as the block
     said it was settled among, never a search's — the one it picked marked,
     and none marked when it kept none of them (left as it was, or an identity
     found by a manual search); the manual search pre-filled from its
     folder beside them (§ 3: never a dead end). RE-AIMED (reader, 2026-10-01):
     the screen offered what a search on the title found — « Parmi 3
     candidats », then one card, the one already kept;
  5. the creation refused (`acq-resolution-enqueue-failed`, a 409) and the
     re-opening refused (a 404): no candidates screen, and the refusal said in
     the interface's own sentence for that kind (`fr.json`) — never the
     server's text. RE-AIMED (reader, 2026-10-01): the toast read « reopenDecision
     is set to answer 404 »;
  6. the named states `acq-resolution-enqueued` and
     `media-sheet-decision-corrected` land on the screen their name says.
"""
import asyncio
import json
import pathlib

from common import ACTED, PANEL_IN, SETTLED, Journal, open_page, read_at, screen_arrives, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
REFUSALS = WORDS["verbs"]["decision"]["correctRefused"]
REFUSALS = REFUSALS if isinstance(REFUSALS, dict) else {}

TAP = """(scope) => {
  const root = scope === 'sheet' ? document.querySelector('#sheet[data-open]') : document;
  const act = root?.querySelector('[data-part="decision/correct"]');
  window.__mocks.clearAnswered?.();
  const before = window.__mocks.answered().length;
  const decision = act ? window.__queries.getQueryData(['/api/decisions/'])
    ?.settled.find((one) => one.id === act.dataset.decisionCorrect) ?? null : null;
  act?.click();
  return {tapped: !!act, before, folder: decision?.folder ?? null,
          count: decision ? decision.candidates?.length ?? decision.candidatesCount : null,
          // Kept AMONG the candidates only when picked from them: an identity
          // found by a manual search was never one of them.
          kept: decision?.choice?.via === 'pick' ? String(decision.choice.id) : null};
}"""

LANDED = """(before) => {
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="resolution:"]');
  const calls = window.__mocks.answered().slice(before).map((call) => call.operationId + ' ' + call.status);
  return {screen: screen?.dataset.key ?? null,
          candidates: screen ? screen.querySelectorAll('[data-part="card/pick"]').length : 0,
          kept: screen ? [...screen.querySelectorAll('[data-kept]')].map((card) =>
            card.querySelector('[data-provider-id]')?.dataset.providerId ?? '') : [],
          manual: screen?.querySelector('[data-manual]')?.dataset.manual ?? null,
          text: screen?.textContent.replace(/\\s+/g, ' ') ?? '',
          toast: document.querySelector('#toastmsg')?.textContent.trim() ?? '',
          calls};
}"""

CASES = (
    ("the engine's identification", "sheet-journey-decision-engine", "sheet", "enqueueForResolution"),
    ("the operator's choice", "sheet-journey-decision-operator", "sheet", "reopenDecision"),
    ("a shelved medium", "media-sheet-decision", "screen", "reopenDecision"),
    ("a decision left as it was", "sheet-journey-decision-dismissed", "sheet", "reopenDecision"),
)

# A settled decision's « Corriger », refused: the state, the operation, the
# status, and the kind of refusal the interface words it as.
REFUSED = (
    ("acq-resolution-enqueue-failed", None, None, "conflict"),
    ("sheet-journey-decision-operator", "reopenDecision", 404, "gone"),
)


async def main():
    journal = Journal("R403 — « Corriger » arrives with candidates")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for what, state, scope, operation in CASES:
            tapped = await read_at(page, state, TAP, scope, wait=PANEL_IN + SETTLED)
            journal.check(f"{what}: the block offers « Corriger »", tapped["tapped"], str(tapped))
            # The screen of THIS folder, not a fixed wait: the one before it stays open
            # until it arrives, and a reading then names the last case's.
            await screen_arrives(page, f"resolution:{tapped['folder']}")
            landed = await page.evaluate(LANDED, tapped["before"])
            journal.check(f"{what}: « Corriger » calls {operation}, answered 200",
                          f"{operation} 200" in landed["calls"], str(landed["calls"]))
            journal.check(f"{what}: the candidates screen of that folder opens",
                          landed["screen"] == f"resolution:{tapped['folder']}", str(landed["screen"]))
            journal.check(f"{what}: the screen offers the decision's own {tapped['count']} candidates",
                          landed["candidates"] == tapped["count"],
                          f"drawn {landed['candidates']}, the decision's {tapped['count']}")
            journal.check(f"{what}: the one it kept is marked, and only it",
                          landed["kept"] == ([tapped["kept"]] if tapped["kept"] else []),
                          f"marked {landed['kept']}, kept {tapped['kept']}")
            journal.check(f"{what}: the manual search beside them, pre-filled from its folder",
                          landed["manual"] == tapped["folder"], str(landed["manual"]))

        for state, operation, status, kind in REFUSED:
            if operation is None:
                refused = await read_at(page, state, LANDED, 0, wait=PANEL_IN + ACTED + SETTLED)
            else:
                await read_at(page, state, "() => null", wait=PANEL_IN + SETTLED)
                await page.evaluate("([operation, status]) => window.__mocks.setOperationOutcome(operation, {status})",
                                    [operation, status])
                tapped = await page.evaluate(TAP, "sheet")
                await page.wait_for_timeout(ACTED + PANEL_IN)
                refused = await page.evaluate(LANDED, tapped["before"])
            journal.check(f"refused ({kind}): no candidates screen opens on nothing", refused["screen"] is None,
                          str(refused["screen"]))
            journal.check(f"refused ({kind}): said in the interface's own sentence, never the server's",
                          kind in REFUSALS and refused["toast"] == REFUSALS[kind]
                          and "answer" not in refused["toast"],
                          repr(refused["toast"]))

        for state, folder in (("acq-resolution-enqueued", "Furious.S01E01.MULTi.1080p.WEB-DL"),
                              ("media-sheet-decision-corrected", "The Bombing of Pan Am 103")):
            await page.evaluate("(id)=>window.__go(id)", state)
            await screen_arrives(page, f"resolution:{folder}")
            seen = await page.evaluate(LANDED, 0)
            journal.check(f"{state}: lands on the screen of « {folder} », with candidates",
                          seen["screen"] == f"resolution:{folder}" and seen["candidates"] > 0,
                          str({k: seen[k] for k in ("screen", "candidates")}))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
