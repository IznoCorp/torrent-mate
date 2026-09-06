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
   that is the literal truth about the process and a lie about the system:
   seven red rows on a machine in perfect health. A service is judged on
   whether it is UP, a scheduler on whether it RAN, and the two lists never
   share a vocabulary.
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
import pathlib
import subprocess
import sys

from common import Journal, open_page
from playwright.async_api import async_playwright

# THE TREE THIS FILE LIVES IN, never a path typed out. It read
# `expanduser("~/dev/PersonalScraper")` and was the only harness file that did:
# every neighbour resolves from `__file__`. The consequence was not stylistic.
# This office reviews on a WORKTREE pinned at a pull request's head, so a rule
# reading an absolute path measures the main checkout while the reader believes
# it is measuring the branch — a hold below went green over a label deleted in
# the tree under test, and only passed honestly because the main checkout
# happened to sit on the same commit. Off that path the module raised at import
# and printed no verdict at all.
ROOT = pathlib.Path(__file__).resolve().parents[3]

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
#
# THE DECLARED SOURCE IS AN EXPRESSION, not a fixture name, and the schedulers
# are why. Four of these lists are still declared by the dying engine and
# republished on `window`; the schedulers are the layer's answer, held in the
# query cache. Comparing the drawn tone against `window.SCHEDULERS` after the
# family left the engine would not read a stale list — it would raise, which is
# the honest failure. Naming the CACHE keeps the comparison against what the
# page was actually given, which is the whole point of a declared source.
SCHEDULERS_SOURCE = "window.__queries.getQueryData(['/api/maintenance/schedulers'])"

BLOCKS = (
    ("Services", "services", "service", "SERVICES"),
    ("Planificateurs", "schedulers", "scheduler", SCHEDULERS_SOURCE),
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
  return [...document.querySelectorAll('#view [data-part="flux"] [data-part="flux/value"] [data-part="chip"]')].map((el) => {
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
    const headings = [...document.querySelectorAll('#view [data-part="heading"]')];
    const t = headings.find((x) => x.textContent.trim() === heading);
    // NO HEADING and NO LIST UNDER ONE are different defects — the first sends
    // a reader to the strings, the second to the component — so the miss says
    // which of the two it was rather than one word for both.
    if (!t) return {heading: false, rows: null};
    // WHICH SIBLING IS THE LIST, and did we run into the next heading first
    // — both are questions about STRUCTURE, and both parts are emitted and
    // selected by this same file three lines up and two hundred down. They
    // read the class until 6.6, under a genre exemption whose written reason
    // — « the subject is the applied style » — described a geometry rule two
    // files over and was simply false here.
    let n = t.nextElementSibling;
    while (n && !n.matches('[data-part="flux"]')) {
      if (n.matches('[data-part="heading"]')) return {heading: true, rows: null};
      n = n.nextElementSibling;
    }
    return {heading: true, rows: n
      ? [...n.querySelectorAll('[data-part="flux/row"]')].map((x) => {
          // The badge IS the value: a row whose value is a state wears it as
          // a chip. Reading a dot beside the label would measure a shape the
          // interface no longer draws.
          const badge = x.querySelector('[data-part="flux/value"] [data-part="chip"]');
          const TONS = { success: 'success', danger: 'alert',
                         warning: 'warning', info: 'info' };
          return {
            l: x.querySelector('[data-part="flux/name"]').textContent.trim(),
            v: x.querySelector('[data-part="flux/value"]').textContent.trim(),
            s: x.querySelector('[data-part="flux/detail"]').textContent.trim(),
            // Reported in the operator's vocabulary, which is what the data is
            // written in: the emitted `danger` is their `alert`. The tone is
            // read from `data-tone`, which every chip emitter writes from the
            // SAME expression as its class — matching the class list against
            // the table's keys named those keys as class names, and no
            // instrument could see a class name that is never quoted.
            tone: badge ? TONS[badge.dataset.tone] || 'unknown' : null,
          };
        })
      : null};
  };
  return {
    overflow: port.scrollWidth - port.clientWidth,
    text: document.querySelector('#view').textContent,
    simulated: document.querySelector('#view').textContent.includes('SIMULÉE'),
    headings: [...document.querySelectorAll('#view [data-part="heading"]')].map((x) => x.textContent.trim()),
    __BLOCKS__
    topics: [...document.querySelectorAll('#view [data-part="topic"] [data-part="topic/title"]')].map((x) => x.textContent.trim()),
    commands: [...document.querySelectorAll('#view [data-part="flux"] [data-part="flux/row"] [data-part="flux/key"]')].map((x) => x.textContent.trim()),
  };
}"""

READ = READ.replace("__BLOCKS__", "".join(
    f"{key}: block({heading!r}),\n    " for heading, key, _, _ in ALL_BLOCKS).strip())

PANEL = """() => ({
  open: document.querySelector('#sheet').hasAttribute('data-open'),
  title: (document.querySelector('[data-part="sheet/title"]') || {}).textContent || '',
  actions: [...document.querySelectorAll('[data-part="sheet/actions"] [data-part="sheet/action"]')].map((b) => ({
    text: b.textContent.trim(),
    inert: b.disabled,
    why: b.getAttribute('title') || '',
  })),
})"""


# HOW LONG A DECLARED SOURCE IS GIVEN TO ANSWER. Four of the five are synchronous
# `window` globals that exist before any rule can look; the schedulers' is a
# query cache entry, so it is the one read that has to arrive. The page itself
# is settled with a fixed wait above, and this is the same discipline applied to
# the one source that is not the document.
DECLARED_SOURCE_TIMEOUT_MILLISECONDS = 4000


async def declared_tones(page, source):
    """Reads a declared source's tones, waiting for it and never raising.

    A rule must always print its verdict. `getQueryData` answers `undefined`
    until its query settles, and `undefined.map` raises a TypeError out of
    `main()` — so `Journal.summary()` never runs and the run prints no « N
    rules » line at all, handing its reader a traceback naming `.map` instead
    of the schedulers. A source that never answers is a FAILED hold, with the
    expression named; it is not an exception.

    Args:
        page: The page.
        source: The JavaScript expression naming the declared list.

    Returns:
        `(tones, None)` when it answered, and `(None, why)` when it did not —
        the two failures being different facts: a source that never arrived and
        a source that arrived carrying something else are not one defect, and
        reporting both as « never answered » would say the false one half the
        time.
    """
    try:
        await page.wait_for_function(f"()=>{source} != null",
                                     timeout=DECLARED_SOURCE_TIMEOUT_MILLISECONDS)
    except Exception:  # noqa: BLE001 — a source that never arrives is a verdict
        return None, "never answered"
    try:
        return await page.evaluate(f"()=>{source}.map((x) => x.ton)"), None
    except Exception:  # noqa: BLE001 — it answered, and with the wrong thing
        return None, "answered with something that is not a list of facts"


# THE TWO VOCABULARIES, AND WHAT IS ACCEPTED BETWEEN THEM (B-327). The
# prototype names these jobs twice — « Système » draws one label, the schedule's
# own table carries another — and five of the six pre-existing pairs disagree.
# Those five are ACCEPTED here BY NAME, not tolerated by a count: a sixth
# disagreement is a new one and is refused. The two that agree are named too,
# so a name that stops agreeing is a fall rather than a silence.
SCHEDULERS_NAMED_ALIKE = (
    "personalscraper-index-enrich",
    "personalscraper-index-full",
)
SCHEDULERS_NAMED_TWICE = (
    "personalscraper-health-check",
    "personalscraper-grab",
    "personalscraper-search",
    "personalscraper-follow-detect",
    "personalscraper-backfill-ids",
)


def setting_labels():
    """The schedule's own label table, read from the tree this file lives in.

    READ WHEN THE HOLD RUNS, never at import. A module-level read makes a
    missing file raise before any hold, and this rule runs on import — so an
    absent resource printed no verdict at all instead of one failing hold,
    which is the silence B-273 is about.

    Returns:
        The table, or None when it cannot be read.
    """
    try:
        return json.loads(
            (ROOT / "frontend" / "maquette" / "design" / "src" / "i18n" / "fr.json")
            .read_text(encoding="utf-8"))["settings"]["labels"]
    except Exception:  # noqa: BLE001 — an unreadable resource is a verdict
        return None


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


async def on_page(pg, page, settle=None, **patch):
    """Drives a named state and reads it, blocks flattened to their rows.

    Every hold below reads a list, so the reading is flattened here — and what
    a MISS was (no heading, or a heading with no list under it) is kept beside
    it under `blocks`, which is what the rung reports.
    """
    fields = ", ".join(f"{k}: {json.dumps(v)}" for k, v in patch.items())
    await pg.evaluate(
        f"()=>{{applyState({{page: '{page}', phase: 'ready'{', ' + fields if fields else ''}}});}}")
    await pg.wait_for_timeout(320)
    # AND THEN WAIT FOR WHAT THE FIXED PAUSE CANNOT PROMISE. The pause above is
    # a guess about the DOCUMENT; a list the layer answers arrives when the
    # query settles, which is a different clock. Reading the page before it and
    # the declared source after it made the two halves of every tone comparison
    # come from two different instants: at half a second of latency the hold
    # read « rendered [] vs declared [success x7] » and accused the page of a
    # hand-written colour, when what happened is that the rows were not there
    # yet. Both halves are read after this wait, so they describe one moment.
    if settle:
        try:
            await pg.wait_for_function(f"()=>{settle} != null",
                                       timeout=DECLARED_SOURCE_TIMEOUT_MILLISECONDS)
        except Exception:  # noqa: BLE001 — the holds below report it, by name
            pass
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
        sys_view = await on_page(pg, "sys", settle=SCHEDULERS_SOURCE, fault=False)

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
            # IT COMPARES COUNTS, AND SAYS BOTH SIDES WHEN IT FALLS. A
            # drawn label and a PM2 process name are two vocabularies, and the
            # rows this hold reads carry no key — so it can say that one row is
            # unaccounted for and not WHICH. Printing both lists is what lets a
            # reader do that join by eye; « 6 vs 7 » alone sent its reader back
            # to `pm2 jlist`.
            #
            # « NOTHING IN THE TREE JOINS THEM » IS WHAT THIS NOTE USED TO SAY,
            # AND IT WAS FALSE. `settings.labels` is keyed by the exact process
            # names, six of the seven, in the resource file the interface reads
            # — the join exists and is one table away. What is true is smaller
            # and worse: the prototype names these jobs TWICE, in two French
            # vocabularies that disagree on five of the six (« Contrôle de
            # santé » against « Contrôle de santé du système »), so joining
            # this list to the machine needs the prototype to name a job ONCE
            # first. That is a debt with an owner, written in B-327, and it is
            # why the row below reads a count while section 6 reads the table.
            journal.check("as many schedulers drawn as PM2 schedules",
                             schedulers_drawn == len(real_schedulers),
                             f"{schedulers_drawn} drawn vs {len(real_schedulers)} real: "
                             + ", ".join(sorted(real_schedulers))
                             + " — drawn: "
                             + ", ".join(sorted(x["l"] for x in (sys_view["schedulers"] or []))))

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
            declared, why = await declared_tones(pg, source)
            rendered = [x["tone"] for x in (rows or [])]
            journal.check(f"a {name}'s badge follows the declared state, never a hand-written colour",
                          declared is not None and rendered == declared,
                          f"rendered {rendered} vs declared {declared}"
                          if declared is not None else
                          f"rendered {rendered} vs a declared source that {why}: {source}")
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
        quantities = await pg.evaluate("""() => [...document.querySelectorAll('#view [data-part="flux"] [data-part="flux/row"]')]
          .map((x) => ({
            l: x.querySelector('[data-part="flux/name"]').textContent.trim(),
            v: x.querySelector('[data-part="flux/value"]').textContent.trim(),
            badge: !!x.querySelector('[data-part="flux/value"] [data-part="chip"]'),
            tone: (() => {
              const c = x.querySelector('[data-part="flux/value"] [data-part="chip"]');
              const T = { success: 'success', danger: 'alert',
                          warning: 'warning', info: 'info' };
              return c ? T[c.dataset.tone] || 'unknown' : null;
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
                await on_page(pg, "sys", settle=SCHEDULERS_SOURCE, fault=state_)
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
        # `fault` is NAMED on the way back: a state driven without naming every
        # dial inherits whatever the previous one left, which is the defect R10
        # found in the interface and which this probe had just repeated.
        sys_view = await on_page(pg, "sys", settle=SCHEDULERS_SOURCE, fault=False)

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
        fault = await on_page(pg, "sys", settle=SCHEDULERS_SOURCE, fault=True)
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
            await pg.evaluate(
                f'()=>window.__panel.produce("action", {json.dumps(action.id)})')
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

        # 6. THE SAME MACHINE IS DESCRIBED BY TWO SURFACES, AND ONLY ONE OF
        # THEM WAS EVER JOINED TO IT. « Système » says WHICH schedulers exist;
        # « Réglages », under « Les passages programmés », says WHEN each of
        # them runs. They are drawn from different fixtures, and `pm2 jlist`
        # was read against the first alone — which is how a repair that made
        # « Système » agree with the machine left « Réglages » a job behind
        # with every tier green. A rule that holds one drawing of a list and
        # not the other holds the drawing, not the list.
        #
        # THE ROW ITSELF IS NOT HELD HERE, AND B-327 CARRIES THE RULE THAT
        # WOULD. That surface is one job behind on the branch point too — its
        # seed is byte-identical there and the machine already ran seven — so
        # it is not a defect this change introduced; what this change did was
        # make the disagreement visible. Adding the row needs either the engine
        # to grow, which the size ledger refuses with an exit code, or a
        # 1 461-line family to leave it, and that family is read by the
        # engine's own `allSettings` and by eleven places in `settings.py`.
        # The hold that reads the drawn set against PM2 is written out in
        # B-327 with the two lines it printed, so the wave that converts the
        # family inherits a rule rather than a description.
        #
        # WHAT IS HELD IS THE JOIN — the thing this rule's own note used to say
        # did not exist. `settings.labels` is keyed by the PM2 process name, so
        # a scheduler the machine runs either has a name written for it there
        # or it does not, and that is readable today. It is read from the
        # resource file rather than from the drawing because an absent key
        # falls back to the humanised key, which LOOKS like a label on screen.
        if pm2 is not None:
            labels = setting_labels()
            drawn_names = {x["l"] for x in (sys_view["schedulers"] or [])}
            if labels is None:
                journal.check(
                    "every scheduler the machine runs is named in the schedule's LABEL TABLE",
                    False, "the label table could not be read from " + str(ROOT))
            else:
                unnamed = [name for name in sorted(real_schedulers)
                           if name not in labels]
                journal.check(
                    "every scheduler the machine runs is named in the schedule's LABEL TABLE",
                    not unnamed, str(unnamed) if unnamed else "all of them")
                # AND THE TWO VOCABULARIES DO NOT GAIN A THIRD. Presence is not
                # agreement: the label may be present and say something « Système »
                # never says, which is what the repair this hold serves promised
                # not to do. The five that already disagree are accepted by name;
                # a scheduler that is named ALIKE stays that way, and a new one
                # has to be placed in one list or the other before it can pass.
                drifted = [name for name in SCHEDULERS_NAMED_ALIKE
                           if name in real_schedulers
                           and labels.get(name) not in drawn_names]
                unplaced = [name for name in sorted(real_schedulers)
                            if name not in SCHEDULERS_NAMED_ALIKE
                            and name not in SCHEDULERS_NAMED_TWICE]
                journal.check(
                    "a scheduler named alike on both surfaces stays that way, and a new one is placed",
                    not drifted and not unplaced,
                    f"drifted: {drifted} · unplaced: {unplaced}" if (drifted or unplaced)
                    else f"{len(SCHEDULERS_NAMED_ALIKE)} alike, "
                         f"{len(SCHEDULERS_NAMED_TWICE)} accepted as disagreeing (B-327)")

        journal.check("no JS error", not errors, str(errors))
        await ctx.close()
        await b.close()

    journal.summary()


asyncio.run(main())
