"""R67 — Système says whether the MACHINE is unwell, Maintenance is what one does to it.

The cut is the operator's: a medium in trouble is Arrivées, a machine in
trouble is Système, and a command run against the library is Maintenance. Two
surfaces, one rule, because the boundary between them is what the rule is
about — a panel on the wrong page is the defect, not a missing panel.

What this holds to:

1. **No blocked medium on Système.** Its business is processes, schedules,
   space, and code that raised. A medium the pipeline refused is a DECISION
   and belongs to Arrivées; drawn here it would be reported twice and answered
   nowhere.
2. **A scheduler between two runs is not stopped.** PM2 reports `stopped` and
   that is the literal truth about the process and a lie about the system: six
   red rows on a machine in perfect health. A service is judged on whether it
   is UP, a scheduler on whether it RAN, and the two lists never share a
   vocabulary.
3. **Every service and scheduler shown really exists**, checked against
   `pm2 jlist` rather than against a list written beside it.
4. **Maintenance is navigated by what one wants to DO**, and every command it
   draws is one the engine really registers — checked against the registry,
   count included, so a command cannot silently disappear from the drawing.
5. **A command that DELETES cannot be run for real before it has been run
   blank.** The second control is inert and says why. This is the one decision
   of the page: a dialog asks « are you sure », which is answered without
   reading; a blank run produces a list, which has to be looked at. A real
   deletion cannot be rehearsed on this machine — staging writes to the real
   disks — so what the interface owes is the look BEFORE, not a net after.
6. Nothing overflows a 390px frame on either surface.
"""
import asyncio
import json
import os
import pathlib
import subprocess
import sys

from common import Journal, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(os.path.expanduser("~/dev/PersonalScraper"))

# THE VOCABULARY BELONGS TO THE RULE, not to the data.
#
# Comparing the rendered tone against the declared one proves the renderer
# follows the data and nothing else: mutate the data and both move together,
# so a nearly-full disk coloured as a critical alert changed nothing. That is a
# derivation reading back its own output. The mapping from a WORD to the tone
# it deserves is stated here instead, once, and a disagreement is a defect —
# whichever side wandered.
VOCABULARY = {
    "success": {"en ligne", "à l'heure", "réussi", "connecté", "joignable",
                "disponibles", "de la place", "aucune"},
    "alert": {"hors ligne", "en retard", "échoué", "des erreurs"},
    "warning": {"bientôt plein", "à nettoyer"},
}

# WCAG AA for body text. A badge that cannot be read is a badge that is not
# there, and the chip is a TINT of its own colour — exactly the shape that put
# a label on its own background once already (B-014).
CONTRAST_FLOOR = 4.5

# THE FIVE LISTS, NAMED ONCE — heading, reading key, the word the verdicts are
# phrased in, and the declared source they are compared against.
#
# A list is located by the FRENCH text of its `<h2>`, and that text is now the
# component's, read from `fr.json`. One character of drift and the lookup finds
# nothing; every hold below phrased as « no row is wrong » then judges an EMPTY
# list and passes. Naming the heading here, and generating the reading from the
# same tuples, is what makes the lookup and the verdict share one spelling —
# and the rung that follows is what makes a list that was not found say so.
BLOCKS = (
    ("Services", "services", "service", "SERVICES"),
    ("Planificateurs", "schedulers", "scheduler", "SCHEDULERS"),
    ("Disques", "disks", "disk", "DISKS"),
    ("Index de la médiathèque", "index", "index row", "INDEX"),
    ("Dépendances", "dependencies", "dependency", "DEPENDENCIES"),
)

# TWO MORE LISTS CARRY A TONE, and no comparison against a declared field can
# judge them: their tone is DERIVED where they are drawn (`ok ? success :
# alert`, and a fixed `alert` for the errors), so a rendered-versus-declared
# check would be a derivation reading back its own output — the very thing the
# note above says makes such a check worthless. What can still be held is the
# half that needs no data: a badge says what its WORD means. Badge PRESENCE is
# not held here either, and deliberately: the errors block draws a second row
# that carries no state at all, exactly as the legacy did.
DERIVED = (
    ("Exécutions du pipeline", "runs", "run", None),
    ("Erreurs de code", "codeErrors", "code-error row", None),
)

# WHAT THE WORD-AGREEMENT HALF CANNOT REACH TODAY, named rather than assumed:
# the runs list is all-success in the embedded data and has no fault twin —
# `SERVICES_PANNE` and `SCHEDULERS_DOWN` exist, `EXECUTIONS_PANNE` does
# not — so forcing every run's tone to `success` renders nothing different and
# no hold can see it. The hold below still bites the reverse (a succeeded run
# wearing an alert). Closing it properly is a change to the prototype's own
# named fault state, not to this rule: the state that replays a fault would
# have to replay a FAILED RUN as well.

ALL_BLOCKS = BLOCKS + DERIVED

# Colours are converted through a canvas, never parsed: `getComputedStyle`
# returns the space the author wrote — `oklch()` here — and three numbers pulled
# out of that string with a regex built for `rgb()` mean nothing. Drawing over
# white and again over black also recovers a tint's alpha, which compositing a
# translucent chip needs.
CONTRAST = """() => {
  const cnv = document.createElement('canvas');
  cnv.width = cnv.height = 1;
  const ctx = cnv.getContext('2d', { willReadFrequently: true });
  const over = (color, background) => {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, 1, 1);
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, 1, 1);
    return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
  };
  const rgba = (color) => {
    const white = over(color, '#fff');
    const black = over(color, '#000');
    const a = 1 - (white[0] - black[0]) / 255;
    return { rgb: black.map((v) => (a > 0 ? v / a : 0)), a };
  };
  const channel = (v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  const lum = (c) =>
    0.2126 * channel(c[0] / 255) + 0.7152 * channel(c[1] / 255) + 0.0722 * channel(c[2] / 255);
  const behind = (el) => {
    const stack = [];
    let node = el.parentElement;
    while (node) {
      const { rgb, a } = rgba(getComputedStyle(node).backgroundColor);
      if (a > 0.001) stack.push([rgb, a]);
      if (a > 0.999) break;
      node = node.parentElement;
    }
    let out = [255, 255, 255];
    for (let i = stack.length - 1; i >= 0; i--) {
      const [c, a] = stack[i];
      out = out.map((v, k) => c[k] * a + v * (1 - a));
    }
    return out;
  };
  return [...document.querySelectorAll('#view .flux .fr .chip')].map((el) => {
    const s = getComputedStyle(el);
    const own = rgba(s.backgroundColor);
    let background = behind(el);
    if (own.a > 0.001) {
      background = background.map((v, k) => own.rgb[k] * own.a + v * (1 - own.a));
    }
    const text = rgba(s.color).rgb;
    const [l1, l2] = [lum(text), lum(background)].sort((x, y) => y - x);
    return {
      word: el.textContent.trim(),
      contrast: Math.round(((l1 + 0.05) / (l2 + 0.05)) * 100) / 100,
    };
  });
}"""

READ = """() => {
  const port = document.querySelector('#port');
  const block = (heading) => {
    const headings = [...document.querySelectorAll('#view .h2')];
    const t = headings.find((x) => x.textContent.trim() === heading);
    // NO HEADING and NO LIST UNDER ONE are different defects — the first sends
    // a reader to the strings, the second to the component — so the miss says
    // which of the two it was rather than one word for both.
    if (!t) return {heading: false, rows: null};
    let n = t.nextElementSibling;
    while (n && !n.classList.contains('flux')) {
      if (n.classList.contains('h2')) return {heading: true, rows: null};
      n = n.nextElementSibling;
    }
    return {heading: true, rows: n
      ? [...n.querySelectorAll('.fx')].map((x) => {
          // The badge IS the value: a row whose value is a state wears it as
          // a chip. Reading a dot beside the label would measure a shape the
          // interface no longer draws.
          const badge = x.querySelector('.fr .chip');
          const TONS = { success: 'success', danger: 'alert',
                         warning: 'warning', info: 'info' };
          return {
            l: x.querySelector('.fn').textContent.trim(),
            v: x.querySelector('.fr').textContent.trim(),
            s: x.querySelector('.fs').textContent.trim(),
            // Reported in the operator's vocabulary, which is what the data is
            // written in: the stylesheet's `danger` is their `alert`.
            tone: badge
              ? TONS[[...badge.classList].find((c) => TONS[c])] || 'unknown'
              : null,
          };
        })
      : null};
  };
  return {
    overflow: port.scrollWidth - port.clientWidth,
    text: document.querySelector('#view').textContent,
    simulated: document.querySelector('#view').textContent.includes('SIMULÉE'),
    headings: [...document.querySelectorAll('#view .h2')].map((x) => x.textContent.trim()),
    __BLOCKS__
    topics: [...document.querySelectorAll('#view .topic .rt')].map((x) => x.textContent.trim()),
    commands: [...document.querySelectorAll('#view .flux .fx .fk')].map((x) => x.textContent.trim()),
  };
}"""

READ = READ.replace("__BLOCKS__", "".join(
    f"{key}: block({heading!r}),\n    " for heading, key, _, _ in ALL_BLOCKS).strip())

PANEL = """() => ({
  open: document.querySelector('#sheet').classList.contains('open'),
  title: (document.querySelector('.sheettitle') || {}).textContent || '',
  actions: [...document.querySelectorAll('.sheetacts .sact')].map((b) => ({
    text: b.textContent.trim(),
    inert: b.disabled,
    why: b.getAttribute('title') || '',
  })),
})"""


def real_processes():
    """The process names PM2 really runs, or None when pm2 cannot be read."""
    try:
        out = subprocess.run(["pm2", "jlist"], capture_output=True, text=True,
                                timeout=25)
    except Exception:  # noqa: BLE001 — pm2 absent is a skip, not a verdict
        return None
    try:
        items = json.loads(out.stdout)
    except Exception:  # noqa: BLE001
        return None
    return {p["name"]: p.get("pm2_env", {}) for p in items}


def real_commands():
    """The `library-*` commands the engine really registers, or None."""
    try:
        sys.path.insert(0, str(ROOT))
        from personalscraper.web.maintenance.registry import REGISTRY
    except Exception:  # noqa: BLE001 — the engine not importable is a skip
        return None
    return {a.id: a for a in REGISTRY}


async def on_page(pg, page, **patch):
    """Drives a named state and reads it, blocks flattened to their rows.

    Every hold below reads a list, so the reading is flattened here — and what
    a MISS was (no heading, or a heading with no list under it) is kept beside
    it under `blocks`, which is what the rung reports.
    """
    fields = ", ".join(f"{k}: {json.dumps(v)}" for k, v in patch.items())
    await pg.evaluate(
        f"()=>{{applyState({{page: '{page}', phase: 'ready'{', ' + fields if fields else ''}}});}}")
    await pg.wait_for_timeout(320)
    seen = await pg.evaluate(READ)
    seen["blocks"] = {key: seen[key] for _, key, _, _ in ALL_BLOCKS}
    for _, key, _, _ in ALL_BLOCKS:
        seen[key] = seen["blocks"][key]["rows"]
    return seen


async def main():
    journal = Journal("R67 — Système is the machine, Maintenance is what one does to it")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # ── SYSTÈME ────────────────────────────────────────────────────────
        # NAMED, both dials: a state driven without naming every dial inherits
        # whatever the previous one left. The reading below is the one the rung
        # and every badge hold rest on, so it is pinned exactly like the one on
        # the way back from the fault.
        sys_view = await on_page(pg, "sys", panne=False)

        # 0. THE RUNG EVERYTHING BELOW STANDS ON: a list that was not FOUND is
        # not a list that is fine. The five blocks are located by their French
        # heading, `rows or []` turns a miss into an empty list, and « no row
        # is wrong » is true of no rows at all — so a heading the component
        # spells differently would leave the badge holds green while the page
        # showed nothing. Held first, and by count, because a found-but-empty
        # list passes exactly the same holds a missing one does.
        for heading, key, word, _ in ALL_BLOCKS:
            rows = sys_view[key]
            found = sys_view["blocks"][key]["heading"]
            journal.check(
                f"the « {heading} » list is found, and has rows to judge",
                rows is not None and len(rows) > 0,
                f"{len(rows)} row(s)" if rows else
                (f"NO HEADING carries that text — every {word} hold below would "
                 "judge an empty list" if not found else
                 f"the heading is there and NO LIST follows it — every {word} "
                 "hold below would judge an empty list"))

        # 1. No blocked medium here. The two stuck folders are named on
        # Arrivées; finding either name on Système means a medium is being
        # reported twice and answered nowhere.
        blocked = await pg.evaluate("()=>window.__blocked ? window.__blocked() : null")
        journal.check("the list of blocked media is reachable",
                         bool(blocked),
                         f"{len(blocked or [])} : {', '.join(blocked or [])}")
        leaks = [t for t in (blocked or []) if t.split(" (")[0] in sys_view["text"]]
        journal.check("no blocked medium is drawn on Système",
                         bool(blocked) and not leaks,
                         str(leaks) if leaks else "none")

        # 2. A scheduler is never said to be stopped.
        forbidden_words = ["stopped", "arrêté", "arrêtée", "hors ligne"]
        found = [m for m in forbidden_words
                   if m in " ".join(f"{x['l']} {x['v']} {x['s']}"
                                    for x in (sys_view["schedulers"] or [])).lower()]
        journal.check("no scheduler is called « arrêté » between two runs",
                         not found, str(found) if found else "none")
        # The badge carries the STATE; when it last ran is a detail and lives
        # in the sub-line. A badge reading « ce matin à 03 h 20 » would be a
        # date wearing a colour, which says nothing about whether that date is
        # late.
        journal.check("a scheduler is judged on « à l'heure » or « en retard »",
                         all(x["v"] in ("à l'heure", "en retard")
                             for x in (sys_view["schedulers"] or [])),
                         str([x["v"] for x in (sys_view["schedulers"] or [])]))
        journal.check("and SAYS when it ran, under the badge",
                         all("dernier passage" in x["s"]
                             for x in (sys_view["schedulers"] or [])),
                         str([x["s"][:40] for x in (sys_view["schedulers"] or [])]))
        journal.check("a service is judged on whether it RUNS",
                         all("ligne" in x["v"] for x in (sys_view["services"] or [])),
                         str([x["v"] for x in (sys_view["services"] or [])]))

        # 3. Everything shown really runs.
        pm2 = real_processes()
        if pm2 is None:
            journal.check("the processes drawn really exist", False,
                          "pm2 unreadable — the comparison could not be made")
        else:
            services = len(sys_view["services"] or [])
            schedulers_drawn = len(sys_view["schedulers"] or [])
            real_services = [n for n, e in pm2.items()
                              if n.startswith(("torrentmate", "personalscraper"))
                              and not e.get("cron_restart")]
            real_schedulers = [n for n, e in pm2.items()
                             if n.startswith(("torrentmate", "personalscraper"))
                             and e.get("cron_restart")]
            journal.check("as many services drawn as PM2 really runs",
                             services == len(real_services),
                             f"{services} drawn vs {len(real_services)} real: "
                             + ", ".join(sorted(real_services)))
            journal.check("as many schedulers drawn as PM2 schedules",
                             schedulers_drawn == len(real_schedulers),
                             f"{schedulers_drawn} drawn vs {len(real_schedulers)} real: "
                             + ", ".join(sorted(real_schedulers)))

        # 3bis. Every service and scheduler carries a pastille, and the
        # pastille AGREES with the sentence beside it. Deriving the colour from
        # one field is what makes that true by construction; checking it is
        # what proves the derivation was not bypassed by a hand-written colour.
        # The colour is compared against the DECLARED state, never against the
        # wording. A first version of this matched the sentence with a pattern
        # and failed on « le 9 août », which says nothing wrong — it was
        # measuring the pattern rather than the interface. Reading `ok` off the
        # page's own data proves the derivation was not bypassed by a colour
        # written in by hand, which is the only way the two could disagree.
        # EVERY list whose tone can be compared against a DECLARED field, not
        # only the two the page opens with: a mutation that coloured a
        # nearly-full disk as an alert changed nothing, because nothing looked
        # at the disks. A guard that covers two lists out of five is a guard for
        # two lists. The two whose tone is derived where they are drawn are held
        # just below, by the half that needs no data.
        for _, key, name, source in BLOCKS:
            rows = sys_view[key]
            without_badge = [x["l"] for x in (rows or []) if x["tone"] is None]
            journal.check(f"every {name} carries a badge", not without_badge, str(without_badge) or "all of them")
            declared = await pg.evaluate(f"()=>{source}.map((x) => x.ton)")
            rendered = [x["tone"] for x in (rows or [])]
            journal.check(f"a {name}'s badge follows the declared state, never a hand-written colour",
                          rendered == declared, f"rendered {rendered} vs declared {declared}")
            # And the tone matches what the WORD means. This is the half that
            # a comparison against the data cannot do.
            misworded = [
                f"« {x['v']} » en {x['tone']}"
                for x in (rows or [])
                for expected, words in VOCABULARY.items()
                if x["v"] in words and x["tone"] != expected
            ]
            journal.check(f"a {name}'s tone says what its WORD means",
                          not misworded, "; ".join(misworded) or "all agree")

        for _, key, name, _ in DERIVED:
            misworded = [
                f"« {x['v']} » en {x['tone']}"
                for x in (sys_view[key] or [])
                for expected, words in VOCABULARY.items()
                if x["v"] in words and x["tone"] != expected
            ]
            journal.check(f"a {name}'s tone says what its WORD means",
                          not misworded, "; ".join(misworded) or "all agree")

        # A QUANTITY is not a state, and badging one is how a badge stops
        # meaning anything: « 1 863 titres » is neither good nor bad, it is how
        # big the library is. Read from the whole page rather than from the two
        # lists, because the temptation to badge a number lives everywhere.
        quantities = await pg.evaluate("""() => [...document.querySelectorAll('#view .flux .fx')]
          .map((x) => ({
            l: x.querySelector('.fn').textContent.trim(),
            v: x.querySelector('.fr').textContent.trim(),
            badge: !!x.querySelector('.fr .chip'),
            tone: (() => {
              const c = x.querySelector('.fr .chip');
              const T = { success: 'success', danger: 'alert',
                          warning: 'warning', info: 'info' };
              return c ? T[[...c.classList].find((k) => T[k])] || 'unknown' : null;
            })(),
          }))
          .filter((r) => r.badge && /^[\\d\\s  ]+$/.test(r.v.replace(/titres|éléments/g, '')))""")
        journal.check("the page draws a badged quantity at all",
                      len(quantities) > 0,
                      f"{len(quantities)} — the hold below asserts an EMPTINESS, "
                      "and an empty list satisfies it whatever the tones are")
        wrongly_toned = [q for q in quantities if q["tone"] != "info"]
        journal.check("a quantity carries only the « info » tone, never a success or an alert",
                      not wrongly_toned, str(wrongly_toned) or f"{len(quantities)} quantity(ies), all in info")

        # And a badge that cannot be read is a badge that is not there. This is
        # B-014's lesson applied before the defect: the chip is a TINT of its
        # own colour, and a tint is exactly where a label lands on its own
        # background.
        # BOTH themes, and the second is the one that was broken: on a white
        # card the same fills that read on near-black sat at 2.91 (success) and
        # 2.02 (warning), under AA — true of every chip in the interface long
        # before this page existed. A rule that measures one theme certifies
        # half a design.
        for theme, apply in (("dark", "()=>document.documentElement.removeAttribute('data-theme')"),
                            ("light", "()=>document.documentElement.setAttribute('data-theme','light')")):
            await pg.evaluate(apply)
            await pg.wait_for_timeout(220)
            for state_ in (False, True):
                await on_page(pg, "sys", panne=state_)
                contrasts = await pg.evaluate(CONTRAST)
                journal.check(
                    f"there are badges to read — {theme} theme"
                    + (", with a fault" if state_ else ""),
                    len(contrasts) > 0,
                    f"{len(contrasts)} badge(s)")
                unreadable = [f"{c['word']} ({c['contrast']})"
                              for c in contrasts if c["contrast"] < CONTRAST_FLOOR]
                journal.check(
                    f"every badge reads against its background — {theme} theme"
                    + (", with a fault" if state_ else ""),
                    not unreadable,
                    f"{len(contrasts)} badges, floor {CONTRAST_FLOOR}, the lowest "
                    f"{min((c['contrast'] for c in contrasts), default='—')}"
                    + (f" — unreadable: {', '.join(unreadable)}" if unreadable else ""))
        await pg.evaluate("()=>document.documentElement.removeAttribute('data-theme')")
        await pg.wait_for_timeout(200)
        # `panne` is NAMED on the way back: a state driven without naming every
        # dial inherits whatever the previous one left, which is the defect R10
        # found in the interface and which this probe had just repeated.
        sys_view = await on_page(pg, "sys", panne=False)

        # The rung again, on the reading « at rest » is judged from: that hold
        # says « nothing alerts », which is true of an empty list too.
        resting = {key: ("no heading" if not sys_view["blocks"][key]["heading"]
                         else "no list under the heading"
                         if sys_view[key] is None else "empty")
                   for _, key, _, _ in ALL_BLOCKS if not sys_view[key]}
        journal.check("the resting reading still finds every toned list",
                      not resting, str(resting) if resting
                      else ", ".join(f"{key}={len(sys_view[key])}"
                                     for _, key, _, _ in ALL_BLOCKS))

        alerting = [x["l"] for x in (sys_view["services"] or [])
                    + (sys_view["schedulers"] or []) if x["tone"] != "success"]
        journal.check("at rest, no service and no scheduler alerts",
                      not alerting,
                      str(alerting) if alerting else
                      f"{len(sys_view['services']) + len(sys_view['schedulers'])} "
                      "rows, success everywhere")
        journal.check("and the resting state does not present itself as a simulation",
                         not sys_view["simulated"])

        # 3ter. A screen that can only be green cannot be judged, so a named
        # state replays a fault — and SAYS it is simulated, or the operator
        # would read an invented outage as a real one (§13).
        fault = await on_page(pg, "sys", panne=True)
        red_services = [x for x in (fault["services"] or []) if x["tone"] == "alert"]
        red_schedulers = [x for x in (fault["schedulers"] or []) if x["tone"] == "alert"]
        journal.check("a named state shows what an alert looks like, on the services side",
                         len(red_services) == 1, str([x["l"] for x in red_services]))
        journal.check("and on the schedulers side",
                         len(red_schedulers) == 1, str([x["l"] for x in red_schedulers]))
        journal.check("a faulty service is called HORS LIGNE, not late",
                         red_services and red_services[0]["v"] == "hors ligne",
                         str([x["v"] for x in red_services]))
        # The property has not changed, its PLACE has: the badge carries the
        # state and the sub-line carries how long. « il y a trois jours » on an
        # hourly job is still the whole of what one needs — a badge reading a
        # date would be a date wearing a colour, saying nothing about whether
        # that date is late.
        journal.check("a late scheduler says so with a word in its badge",
                         red_schedulers and red_schedulers[0]["v"] == "en retard",
                         str([x["v"] for x in red_schedulers]))
        journal.check("and SAYS by how much, under the badge",
                         red_schedulers and "il y a" in red_schedulers[0]["s"],
                         str([x["s"][:60] for x in red_schedulers]))
        journal.check("and the screen says this fault is SIMULÉE", fault["simulated"])

        journal.check("nothing spills past the frame on Système",
                         sys_view["overflow"] <= 0, f"{sys_view['overflow']}px")
        journal.check("nothing spills past the frame with a fault",
                         fault["overflow"] <= 0, f"{fault['overflow']}px")

        # ── MAINTENANCE ────────────────────────────────────────────────────
        maint = await on_page(pg, "maint", maintTopic=None)
        journal.check("Maintenance is navigated by what one wants to DO",
                         len(maint["topics"]) >= 5, str(maint["topics"]))
        journal.check("the deletion journal is on Maintenance",
                         "Journal des suppressions" in maint["headings"],
                         str(maint["headings"]))

        registry = real_commands()
        seen = set()
        for topic in ("query", "scan", "repair", "clean", "fix", "analyze"):
            page = await on_page(pg, "maint", maintTopic=topic)
            seen.update(page["commands"])
            journal.check(f"the « {topic} » topic draws commands",
                             len(page["commands"]) > 0, str(page["commands"]))
            journal.check(f"nothing spills past the frame in « {topic} »",
                             page["overflow"] <= 0, f"{page['overflow']}px")

        if registry is None:
            journal.check("the commands drawn exist in the engine", False,
                          "engine not importable — the comparison could not be made")
        else:
            invented = sorted(seen - set(registry))
            forgotten = sorted(set(registry) - seen)
            journal.check("no command drawn is invented",
                          not invented, str(invented) if invented else "none")
            journal.check("no engine command is forgotten",
                          not forgotten, str(forgotten) if forgotten else "none")

        # 5. The one decision: a command that deletes is blank-first.
        destructive = ([a for a in registry.values() if a.risk == "destructive"]
                         if registry else [])
        journal.check("the engine does have commands that delete",
                         len(destructive) > 0, f"{len(destructive)}")
        for action in destructive:
            await on_page(pg, "maint", maintTopic=action.category)
            await pg.evaluate(f"()=>openActionMaintenance({json.dumps(action.id)})")
            await pg.wait_for_timeout(320)
            panel = await pg.evaluate(PANEL)
            real_run = [a for a in panel["actions"] if "vrai" in a["text"]]
            journal.check(
                f"« {action.title} » offers to run it blank FIRST",
                any("blanc" in a["text"] for a in panel["actions"]),
                str([a["text"] for a in panel["actions"]]))
            journal.check(
                f"« {action.title} » cannot be run for real straight away",
                real_run and all(a["inert"] for a in real_run),
                str([(a["text"], a["inert"]) for a in real_run]))
            journal.check(
                f"« {action.title} » SAYS why it is held back",
                real_run and all(a["why"] for a in real_run),
                str([a["why"] for a in real_run]))
            await pg.evaluate("()=>closeSheet()")
            await pg.wait_for_timeout(180)

        journal.check("no JS error", not errors, str(errors))
        await ctx.close()
        await b.close()

    journal.summary()


asyncio.run(main())
