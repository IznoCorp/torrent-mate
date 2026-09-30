"""R403 — « Corriger » arrives with candidates (L24 S5, DOIT-7, § 3).

The act of a settled decision's block (OPEN 7 = A: one act for both authors).
On an identification the engine made alone it CREATES the decision —
`enqueueForResolution`; on the operator's own choice it RE-OPENS it by its id —
`reopenDecision`, on a shelved medium's Médiathèque sheet too (OPEN 8 = A).
The call comes BEFORE the candidates screen, and the screen opens on the
candidates the call filed — or on the pre-filled manual search when there are
none (§ 3: never a dead end). A refused call says its reason and opens nothing.

WHAT IS READ, each walked by a tap on « Corriger »:

  1. the engine's identification (journey sheet): `enqueueForResolution`
     answered 200, then the screen of that folder draws its candidates;
  2. the operator's choice (journey sheet): `reopenDecision` answered 200, the
     screen draws its candidates;
  3. a shelved medium (Médiathèque sheet): `reopenDecision`, the screen draws
     its candidates;
  4. a decision whose search finds nothing (« The Alabama Solution »): the screen
     opens on « no candidate » and the manual search, pre-filled from its folder;
  5. the creation refused (`acq-resolution-enqueue-failed`): no candidates screen,
     the refusal said with its reason;
  6. the named states `acq-resolution-enqueued` and
     `media-sheet-decision-corrected` land on the screen their name says.
"""
import asyncio
import json
import pathlib

from common import ACTED, PANEL_IN, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
REFUSED = WORDS["verbs"]["decision"]["correctRefused"].split("{{")[0].strip()
NO_CANDIDATES = WORDS["screens"]["resolution"]["noCandidates"]

TAP = """(scope) => {
  const root = scope === 'sheet' ? document.querySelector('#sheet[data-open]') : document;
  const act = root?.querySelector('[data-part="decision/correct"]');
  window.__mocks.clearAnswered?.();
  const before = window.__mocks.answered().length;
  const folder = act ? window.__queries.getQueryData(['/api/decisions/'])
    ?.settled.find((one) => one.id === act.dataset.decisionCorrect)?.folder ?? null : null;
  act?.click();
  return {tapped: !!act, before, folder};
}"""

LANDED = """(before) => {
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="resolution:"]');
  const calls = window.__mocks.answered().slice(before).map((call) => call.operationId + ' ' + call.status);
  return {screen: screen?.dataset.key ?? null,
          candidates: screen ? screen.querySelectorAll('[data-part="card/pick"]').length : 0,
          manual: screen?.querySelector('[data-manual]')?.dataset.manual ?? null,
          text: screen?.textContent.replace(/\\s+/g, ' ') ?? '',
          toast: document.querySelector('#toastmsg')?.textContent.trim() ?? '',
          calls};
}"""

CASES = (
    ("the engine's identification", "sheet-journey-decision-engine", "sheet", "enqueueForResolution", True),
    ("the operator's choice", "sheet-journey-decision-operator", "sheet", "reopenDecision", True),
    ("a shelved medium", "media-sheet-decision", "screen", "reopenDecision", True),
    ("a search that finds nothing", "sheet-journey-decision-dismissed", "sheet", "reopenDecision", False),
)


async def main():
    journal = Journal("R403 — « Corriger » arrives with candidates")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for what, state, scope, operation, with_candidates in CASES:
            tapped = await read_at(page, state, TAP, scope, wait=PANEL_IN + SETTLED)
            journal.check(f"{what}: the block offers « Corriger »", tapped["tapped"], str(tapped))
            await page.wait_for_timeout(ACTED + PANEL_IN)
            landed = await page.evaluate(LANDED, tapped["before"])
            journal.check(f"{what}: « Corriger » calls {operation}, answered 200",
                          f"{operation} 200" in landed["calls"], str(landed["calls"]))
            journal.check(f"{what}: the candidates screen of that folder opens",
                          landed["screen"] == f"resolution:{tapped['folder']}", str(landed["screen"]))
            if with_candidates:
                journal.check(f"{what}: the screen draws the candidates the call filed",
                              landed["candidates"] > 0, str(landed["candidates"]))
            else:
                journal.check(f"{what}: no candidate, said, and the manual search pre-filled from its folder",
                              landed["candidates"] == 0 and NO_CANDIDATES in landed["text"]
                              and landed["manual"] == tapped["folder"],
                              str({k: landed[k] for k in ("candidates", "manual")}))

        refused = await read_at(page, "acq-resolution-enqueue-failed", LANDED, 0, wait=PANEL_IN + ACTED + SETTLED)
        journal.check("refused: no candidates screen opens on nothing", refused["screen"] is None,
                      str(refused["screen"]))
        journal.check("refused: the refusal is said with its reason",
                      refused["toast"].startswith(REFUSED) and len(refused["toast"]) > len(REFUSED) + 3,
                      repr(refused["toast"]))

        for state, folder in (("acq-resolution-enqueued", "Furious.S01E01.MULTi.1080p.WEB-DL"),
                              ("media-sheet-decision-corrected", "The Bombing of Pan Am 103")):
            seen = await read_at(page, state, LANDED, 0, wait=PANEL_IN + ACTED + SETTLED + SETTLED)
            journal.check(f"{state}: lands on the screen of « {folder} », with candidates",
                          seen["screen"] == f"resolution:{folder}" and seen["candidates"] > 0,
                          str({k: seen[k] for k in ("screen", "candidates")}))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
