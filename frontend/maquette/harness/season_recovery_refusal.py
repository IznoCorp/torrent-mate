"""R-season-recovery-d and -f — the release picker says which releases the season's recovery covers.

The operator, 2026-09-29 17:36: « on doit s'assuré qu'aucun téléchargement d'épisode de la saison se
lance en parallèle » — and DOIT-2 (« chaque rien a sa raison affichée »), DOIT-12 (« visible et
expliqué plutôt que silencieusement absent »). His principle of 09-29: « on crée pas de nouveau
composant on adapte ».

WHAT IT HOLDS:

  R-season-recovery-d  during Silo's S03 recovery every `S03E07` release keeps its row but has no pick
                       act: it carries the chip « Couvert par la saison 3 » and « Voir la carte de la
                       saison », the landing naming the season's card; the season pack keeps its act;
                       when every candidate is covered the count says so and the empty note stays;
                       before the ask and after the library `S03E07` takes again; a FILM's release
                       list draws no refusal (a recovery is a series'). A finger on the pointer lands
                       on the season's card, highlighted; Retour returns to the release screen.
  R-season-recovery-f  the design system is reused: the release's refusal and the season row's
                       « Demandée » are the SAME `ui` chip (one class set); the journey's pointer is a
                       panel note and a panel action; no `features/*` variant is named for the
                       recovery.
"""
import asyncio
import re

from common import ROOT, PANEL_IN, SETTLED, Journal, open_page, chrome_launch_args
from playwright.async_api import async_playwright

COVERED = "Couvert par la saison 3"  # french-ok: the refusal's chip, asserted as drawn
SEE_CARD = "Voir la carte de la saison"  # french-ok: the pointer's words, asserted as drawn
ALL_COVERED = "tous couverts par la saison 3"  # french-ok: the count's words, asserted as drawn
PACK = "Silo.S03.MULTi"
EPISODE = "S03E07"
FILM = "Wicker"

ROWS = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="releases:"]');
  if (!screen) return {open: false};
  return {
    open: true,
    count: (screen.querySelector('[data-part="result/count"]') || {}).textContent || '',
    empty: !!screen.querySelector('[data-part="empty-state"]'),
    rows: [...screen.querySelectorAll('[data-part="release"]')].map((row) => {
      const covered = row.querySelector('[data-part="release/covered"]');
      const pointer = [...row.querySelectorAll('[data-go="acq"]')][0];
      return {
        name: row.firstElementChild ? row.firstElementChild.textContent.trim() : '',
        pick: !!row.querySelector('[data-pick-release]'),
        chip: covered ? covered.textContent.trim() : '',
        chipClass: covered ? [...covered.classList].sort().join(' ') : '',
        pointer: pointer ? {text: pointer.textContent.trim(), dial: pointer.dataset.dial} : null,
      };
    }),
  };
}"""


async def releases_at(page, state, title="Silo"):
    """Drives a state, opens a title's release picker over it, and reads the rows."""
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(SETTLED * 2)
    await page.evaluate("(title)=>window.__screens.releases(title)", title)
    await page.wait_for_timeout(SETTLED * 2)
    return await page.evaluate(ROWS)


def episodes(read):
    """The rows naming Silo's S03E07."""
    return [row for row in read.get("rows", []) if EPISODE in row["name"]]


async def main():
    """Runs the rule."""
    journal = Journal("R-season-recovery-d, -f — the release picker says what the season's recovery covers")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── R-d during the recovery ─────────────────────────────────────────────
        await page.evaluate("()=>window.__go('releases-season-recovering')")
        await page.wait_for_timeout(SETTLED * 2)
        during = await page.evaluate(ROWS)
        covered = episodes(during)
        journal.check("R-d: during the recovery the four S03E07 releases keep their rows",
                      len(covered) == 4, str([row["name"] for row in during.get("rows", [])]))
        journal.check("R-d: none of them offers a pick act; each carries « Couvert par la saison 3 »",
                      all(not row["pick"] and row["chip"] == COVERED for row in covered), str(covered))
        journal.check("R-d: each carries « Voir la carte de la saison », landing on the season's card",
                      all(row["pointer"] == {"text": SEE_CARD, "dial": "now:Silo|S03"} for row in covered),
                      str([row["pointer"] for row in covered]))
        pack = [row for row in during.get("rows", []) if row["name"].startswith(PACK)]
        journal.check("R-d: the season pack keeps its pick act and no refusal",
                      len(pack) == 1 and pack[0]["pick"] and not pack[0]["chip"], str(pack))

        await page.evaluate("()=>window.__go('releases-season-recovering-all-covered')")
        await page.wait_for_timeout(SETTLED * 2)
        every = await page.evaluate(ROWS)
        journal.check("R-d: every candidate covered — the count says so, and the empty note stays",
                      ALL_COVERED in every.get("count", "") and every.get("empty")
                      and len(every.get("rows", [])) == 4, f"{every.get('count')!r}, empty={every.get('empty')}")

        for state, when in (("season-recovery-before-ask", "before the ask"),
                            ("season-recovery-shelved-sheet", "after the library")):
            read = await releases_at(page, state)
            rows = episodes(read)
            journal.check(f"R-d: {when}, S03E07 takes again — its pick act, no refusal",
                          len(rows) == 4 and all(row["pick"] and not row["chip"] for row in rows), str(rows))
        film = await releases_at(page, "acq-now-loaded", FILM)
        journal.check("R-d: a film's release list draws no refusal and keeps its acts",
                      film.get("rows") and all(row["pick"] and not row["chip"] for row in film["rows"]),
                      str(film.get("rows")))

        # ── the pointer, by finger ────────────────────────────────────────────
        await page.evaluate("()=>window.__go('releases-season-recovering')")
        await page.wait_for_timeout(SETTLED * 2)
        pointer = page.locator('[data-part="release"] [data-go="acq"]').first
        await pointer.scroll_into_view_if_needed()
        await pointer.tap()
        await page.wait_for_timeout(SETTLED * 3)
        landed = await page.evaluate("""() => {
          const card = document.querySelector('#view [data-part="card"][data-acquisition="Silo|S03"]');
          const state = window.__store.read().state;
          return {page: state.page, tab: state.acqTab, landed: !!card && card.hasAttribute('data-landed'),
                  screen: !!document.querySelector('[data-part="screen"][data-open][data-key^="releases:"]')};
        }""")
        journal.check("R-d: a finger on the pointer lands on « En cours », the season's card highlighted",
                      landed["page"] == "acq" and landed["tab"] == "now" and landed["landed"] and not landed["screen"],
                      str(landed))
        await page.go_back()
        await page.wait_for_timeout(SETTLED * 2)
        back = await page.evaluate(ROWS)
        journal.check("R-d: Retour returns to the release screen", back.get("open"), str(back.get("open")))

        # ── R-f: the design system reused ─────────────────────────────────────
        await page.evaluate("()=>window.__go('season-row-requested-sheet')")
        await page.wait_for_timeout(SETTLED * 3)
        mark = await page.evaluate("""() => {
          const one = document.querySelector('[data-part="season/asked"]');
          return one ? [...one.classList].sort().join(' ') : '';
        }""")
        journal.check("R-f: the release's refusal and the row's « Demandée » are the SAME ui chip",
                      bool(mark) and covered and all(row["chipClass"] == mark for row in covered),
                      f"row {mark!r} / release {covered[0]['chipClass'] if covered else ''!r}")
        await page.evaluate("()=>window.__go('absorbed-journey-pointer')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        blocks = await page.evaluate("""() => {
          const sheet = document.querySelector('#sheet');
          const notes = [...sheet.querySelectorAll('p')].filter((one) => /couvert par/.test(one.textContent));
          const provenance = [...sheet.querySelectorAll('p')].find((one) => /spine de provenance/.test(one.textContent));
          const action = [...sheet.querySelectorAll('[data-part="sheet/action"]')]
            .find((one) => one.dataset.go === 'acq');
          return {note: notes.length === 1 && !!provenance && notes[0].className === provenance.className,
                  action: !!action};
        }""")
        journal.check("R-f: the journey's pointer is a panel note and a panel action", blocks["note"] and blocks["action"],
                      str(blocks))
        named = []
        for variants in (ROOT / "design" / "src" / "features").glob("*/variants.ts"):
            named += [f"{variants.parent.name}:{name}" for name in re.findall(
                r"export const (\w+)", variants.read_text(encoding="utf-8"))
                      if re.search(r"(?i)recover|absorb|covered|requested", name)]
        journal.check("R-f: no features/* variant is named for the recovery", not named, str(named))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
