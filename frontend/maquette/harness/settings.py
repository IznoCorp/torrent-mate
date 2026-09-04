"""R60 — the settings, and the one decision that shapes them.

ONE NAVIGATES BY WHAT ONE WANTS TO CHANGE, NEVER BY FILE.

The engine keeps nineteen JSON5 files and the shipped editor put them in a
dropdown. That asks the operator to know that « thresholds.json5 » holds how
much free space is needed before an ingest — knowledge about the code, not
about the media library. The files are not hidden: every setting says which one
it lives in, in the mono face, because that is what one needs when reading a
log or a diff. They are simply not the map.

What this script holds to:

  · the rubrics are named by what one changes, and every one of the 153 real
    settings belongs to exactly one of them — a setting reachable from nowhere
    is a setting nobody will ever find;
  · a setting says WHERE it comes from, and the explanation it carries is the
    comment its own file holds, never invented prose;
  · nothing is written until the save bar is used, the bar exists only when
    there is something to save, and it NAMES the files it will write;
  · a pending change is marked on its own row, not only counted at the bottom;
  · a secret's value is never shown — only whether it is set;
  · a read-only instance says so and offers nothing.
"""
import asyncio
import pathlib
import re

from common import Journal, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = pathlib.Path.home() / ".torrentmate" / "config"
# Where a setting can live WITHOUT being a JSON5 overlay: the schedules belong
# to PM2, and its ecosystem file is checked out with the deployment rather than
# kept beside the engine's own configuration.
OUTSIDE = (pathlib.Path.home() / "deploy" / "torrentmate",
          pathlib.Path.home() / "dev")
# Typed into one setting's field, and looked for everywhere else afterwards.
# Nothing a real setting could hold, so finding it under another id names the
# defect rather than a coincidence.
PROBE = "cross-panel-probe"

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


async def main():
    global _journal
    _journal = Journal("R60 — the settings")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        # ── the map is what one wants to change ────────────────────────────
        await pg.evaluate("()=>window.__go('settings')")
        await pg.wait_for_timeout(320)
        map_ = await pg.evaluate("""()=>({
          topics: [...document.querySelectorAll('[data-part="topic"]')].map(r => ({
            title: (r.querySelector('[data-part="topic/title"]')||{}).textContent||'',
            sub: (r.querySelector('[data-part="topic/subtitle"]')||{}).textContent||'',
            count: (r.querySelector('[data-part="topic/count"]')||{}).textContent||''})),
          search: !!document.querySelector('#qsettings'),
          text: (document.querySelector('#view')||{}).textContent||''})""")
        check("the topics are named by what one changes",
              len(map_["topics"]) >= 6
              and all(r["sub"].strip() for r in map_["topics"]),
              str([r["title"] for r in map_["topics"]]))
        # A rubric named after a file would be the defect this exists to avoid.
        files = [f.stem for f in CONFIG.glob("*.json5")]
        named = [r["title"].lower() for r in map_["topics"]]
        check("no topic is named after a file",
              not [f for f in files if f in named],
              str([f for f in files if f in named]))
        check("a setting can be searched for", map_["search"])

        # ── every real setting belongs to exactly one rubric ───────────────
        coverage = await pg.evaluate("""()=>{
          const all = SETTINGS.flatMap(r => r.r.map(x => r.f + ':' + x.f + ':' + x.c));
          const keys = SETTINGS.flatMap(r => r.r.map(x => x.f + ':' + x.c));
          return {total: keys.length, distinct: new Set(keys).size,
                  files: [...new Set(SETTINGS.flatMap(r => r.fileNames))].sort()};}""")
        check("a setting belongs to one topic and no other",
              coverage["total"] == coverage["distinct"],
              f"{coverage['total']} settings, {coverage['distinct']} distinct")
        # Nineteen of these are JSON5 overlays named by their concern; one is
        # not. The schedules belong to PM2 and live in `ecosystem.config.js`,
        # so a name carrying its own extension is looked for where PM2 keeps
        # it. What the check holds to is unchanged and is the point: a setting
        # names a file that EXISTS, never one the drawing invented.
        missing = [
            f for f in coverage["files"]
            if not (CONFIG / f"{f}.json5").is_file()
            and not any((base / f).is_file() for base in OUTSIDE)
        ]
        check("and they come from the real configuration files",
              not missing,
              f"{len(coverage['files'])} files"
              + (f" — not found: {', '.join(missing)}" if missing else ""))

        # ── a setting says where it comes from, and explains itself ────────
        await pg.evaluate("()=>window.__go('settings-topic')")
        await pg.wait_for_timeout(320)
        # The origin is read as it is SEEN: the row carries the path, its group
        # header carries the file. Reading only the row would pass a screen where
        # nothing on it names a file.
        rows = await pg.evaluate("""()=>[...document.querySelectorAll('[data-part="setting/row"]')].map(r => ({
          label: (r.querySelector('[data-part="setting/label"]')||{}).firstChild?.textContent?.trim()||'',
          path: (r.querySelector('[data-part="setting/origin"]')||{}).textContent||'',
          header: (r.closest('[data-part="panel"]')?.previousElementSibling||{}).textContent||'',
          value: (r.querySelector('[data-part="setting/value"]')||{}).textContent||''}))""")
        check("a topic lists its settings", len(rows) > 10, str(len(rows)))
        mute = [l for l in rows
                if not l["path"].strip() or ".json5" not in l["header"]]
        check("each says where it comes from — its key, under its file's name",
              not mute, str([(m["path"], m["header"]) for m in mute][:2]))
        check("and the key does not repeat the file",
              not [l for l in rows if ".json5" in l["path"]],
              str([l["path"] for l in rows if ".json5" in l["path"]][:2]))
        check("and it shows its value",
              all(l["value"].strip() for l in rows),
              str([l["label"] for l in rows if not l["value"].strip()][:3]))

        # The explanation is the comment the file itself carries. Compared
        # against the file on disk, so invented prose cannot creep in.
        await pg.evaluate("()=>window.__go('settings-one')")
        await pg.wait_for_timeout(350)
        panel = await pg.evaluate("""()=>{
          const s = document.querySelector('#sheetin');
          return {text: (s.textContent||'').replace(/\\s+/g,' '),
                  mono: !!s.querySelector('code'),
                  field: !!s.querySelector('[data-part="field"]'),
                  actions: [...s.querySelectorAll('[data-part="sheet/action"]')].map(x=>x.textContent.trim())};}""")
        source = (CONFIG / "thresholds.json5").read_text()
        comment = re.search(r"//\s*(.+?)\n\s*min_free_space_staging_gb", source)
        check("the panel carries the explanation WRITTEN IN THE FILE",
              comment is not None
              and comment.group(1).strip().rstrip(".") in panel["text"],
              (comment.group(1) if comment else "comment not found"))
        check("it names the file in the mono face", panel["mono"])
        check("and it carries the field that edits",
              panel["field"], str(panel["actions"]))

        # ── nothing is written until the bar is used ───────────────────────
        at_rest = await pg.evaluate("()=>!!document.querySelector('#savebar')")
        check("no save bar at rest", not at_rest)

        await pg.evaluate("()=>window.__go('settings-edited')")
        await pg.wait_for_timeout(350)
        pending = await pg.evaluate("""()=>{
          const bar = document.querySelector('#savebar');
          return {bar: !!bar, text: bar ? bar.textContent.replace(/\\s+/g,' ') : '',
                  marked: document.querySelectorAll('[data-part="setting/row"][data-edited]').length,
                  insideFrame: bar ? bar.getBoundingClientRect().bottom <=
                    document.querySelector('#device').getBoundingClientRect().bottom + 1 : false};}""")
        check("a change raises the bar", pending["bar"])
        check("and the bar NAMES the files it will write",
              ".json5" in pending["text"], pending["text"][:90])
        check("the changed row is marked where one reads it",
              pending["marked"] >= 1, f"{pending['marked']} row(s)")
        check("the bar stays inside the frame", pending["insideFrame"])

        # ── AND THE PANEL SAYS THE EDIT, not the file ─────────────────────
        # The panel of an EDITED setting must show what the operator typed as
        # « Valeur actuelle » and the file's own value as « Valeur écrite ». It
        # is one derivation — `valueShown` — and NOTHING read it: a mutation
        # making it answer `setting.v` unconditionally fell no hold in this file
        # and none in R120, and what it produces is a panel telling the operator
        # their edit did not take. The two rows are read TOGETHER, because
        # either alone passes over a panel showing the same value twice.
        edited = await pg.evaluate("""()=>{
          const row = document.querySelector('[data-part="setting/row"][data-edited]');
          if (!row) return null;
          row.click();
          return true;}""")
        await pg.wait_for_timeout(400)
        shown = await pg.evaluate(r"""()=>{
          const rows = [...document.querySelectorAll('#sheetin [data-part="key-value"]')]
            .map(r => r.textContent.replace(/\s+/g, ' ').trim());
          return {rows, pending: [...(window.__referentiel.SETTINGS_STATE.modifs || new Map())
            .values()].map(String)};}""")
        current = next((r for r in shown["rows"] if r.startswith("Valeur actuelle")), "")
        written = next((r for r in shown["rows"] if r.startswith("Valeur écrite")), "")
        check("an edited setting's panel says the EDIT as its current value",
              bool(edited) and bool(shown["pending"])
              and any(value in current for value in shown["pending"]),
              f"{current!r} · pending {shown['pending']}")
        check("and the file's own value beside it, as the written one",
              bool(written) and current != written,
              f"current {current!r} · written {written!r}")

        # ── « Annuler la modification » DROPS THAT EDIT, and only that one ──
        #
        # NO RULE READ THIS VERB. `grep -ln 'cancelsetting'
        # frontend/maquette/harness/*.py` returned nothing on 2026-09-04, and it
        # is emitted by a producer and read by a delegation branch — a contract
        # with two ends and no reader. It is written HERE, against the engine's
        # own branch, and seen red under a mutation of it BEFORE the reader
        # moves into this feature: a rule written after a move proves only that
        # it agrees with the move.
        #
        # TWO EDITS ARE MADE, and that is the whole shape. Cancelling one must
        # leave the other standing; a hold that cancels the only pending edit
        # passes over a branch that clears the map.
        await pg.evaluate("()=>window.__go('settings-edited')")
        await pg.wait_for_timeout(350)
        before_cancel = await pg.evaluate(
            "()=>[...window.__referentiel.SETTINGS_STATE.modifs.keys()]")
        check("the walk really starts with more than one pending edit, so "
              "« only that one » is a question",
              len(before_cancel) > 1, str(before_cancel))
        opened = await pg.evaluate("""(id)=>{
          window.__panel.produce("setting", id); return true;}""", before_cancel[0])
        await pg.wait_for_timeout(400)
        cancel_present = await pg.evaluate(
            """()=>{const b = document.querySelector('#sheetin [data-cancelsetting]');
                    return b ? {id: b.dataset.cancelsetting, text: b.textContent.trim()} : null;}""")
        check("an edited setting's panel offers to cancel THAT edit",
              bool(opened) and cancel_present is not None
              and cancel_present["id"] == before_cancel[0],
              f"{cancel_present} · expected {before_cancel[0]}")
        await pg.click("#sheetin [data-cancelsetting]")
        await pg.wait_for_timeout(500)
        after_cancel = await pg.evaluate(
            "()=>[...window.__referentiel.SETTINGS_STATE.modifs.keys()]")
        check("cancelling drops that edit",
              before_cancel[0] not in after_cancel,
              f"{before_cancel} → {after_cancel}")
        check("and leaves every other edit standing",
              sorted(after_cancel) == sorted(before_cancel[1:]),
              f"{before_cancel} → {after_cancel}")
        check("and the panel is gone",
              not await pg.evaluate("()=>window.__panel.isOpen()"))

        # ── a secret is never shown ────────────────────────────────────────
        await pg.evaluate("()=>window.__go('settings-secrets')")
        await pg.wait_for_timeout(320)
        secrets = await pg.evaluate("""()=>({
          rows: [...document.querySelectorAll('[data-part="setting/row"]')].map(r =>
            (r.querySelector('[data-part="setting/value"]')||{}).textContent.trim()),
          fields: document.querySelectorAll('#view input').length})""")
        check("a secret says whether it is set, never what it holds",
              all(v in ("définie", "absente") for v in secrets["rows"]),
              str(sorted(set(secrets["rows"]))))
        check("and no value is pre-filled into a field",
              secrets["fields"] == 0, f"{secrets['fields']} field(s)")

        # ── read-only says so, and offers nothing ─────────────────────────
        await pg.evaluate("()=>window.__go('settings-read-only')")
        await pg.wait_for_timeout(320)
        read_only = await pg.evaluate("""()=>((document.querySelector('#view')||{}).textContent||'')
          .replace(/\\s+/g,' ')""")
        check("a read-only instance says so",
              "lecture seule" in read_only.lower(), read_only[:80])

        # ── restart required names what is waiting ────────────────────────
        await pg.evaluate("()=>window.__go('settings-restart')")
        await pg.wait_for_timeout(320)
        restart = await pg.evaluate("""()=>{
          const v = document.querySelector('#view');
          return {text: (v.textContent||'').replace(/\\s+/g,' '),
                  button: !!v.querySelector('[data-restart]')};}""")
        check("a required restart says so and offers it",
              "edémarrage" in restart["text"] and restart["button"], restart["text"][:70])

        # ── search looks through every setting ─────────────────────────────
        await pg.evaluate("()=>window.__go('settings-search')")
        await pg.wait_for_timeout(320)
        searched = await pg.evaluate("""()=>({
          results: document.querySelectorAll('[data-part="setting/row"]').length,
          empty: !!document.querySelector('[data-part="empty-state"]'),
          text: (document.querySelector('#view')||{}).textContent||''})""")
        # A FRENCH word must find something: the labels used to be the files'
        # English comments, so « espace » matched no row at all — the search
        # existed and answered nothing.
        check("a French word finds settings",
              searched["results"] > 0, f"{searched['results']} result(s) for « espace »")

        # A result stands alone under no header, so THERE the row names its file.
        unnamed = await pg.evaluate("""()=>[...document.querySelectorAll('[data-part="setting/row"] [data-part="setting/origin"]')]
          .map(e => e.textContent).filter(t => !t.includes('.json5'))""")
        check("a search result names its own file",
              not unnamed, str(unnamed[:2]))

        # And no label is an English sentence — over EVERY setting, not the one
        # rubric that happens to be on screen. The comment is not lost: it is
        # the explanation in the panel, where a sentence has room.
        english = await pg.evaluate("""()=>{
          const words = /\\b(the|of|for|before|when|with|and|from|number|seconds|days|file|path|used|which|that)\\b/i;
          return SETTINGS.flatMap(r => r.r)
            .map((x) => window.__settingLabels.label(x)).filter(t => words.test(t));}""")
        check("no setting is labelled in English",
              not english, f"{len(english)}: {english[:3]}")

        # And no two rows in the same list read the same. The leaf key alone drew
        # « Activé » seven times under « Ce qu'on va chercher »: every tracker and
        # every client owns one, and the only thing telling them apart was the
        # machine path — which is there to be read AFTER one has found the row,
        # not to find it.
        collisions = await pg.evaluate("""()=>SETTINGS.flatMap(r => {
          const by = {};
          for (const x of r.r) (by[window.__settingLabels.label(x)] ||= []).push(x.c);
          return Object.entries(by).filter(([, v]) => v.length > 1)
                       .map(([l, v]) => `${r.t} : « ${l} » ×${v.length}`);})""")
        check("two settings in one topic never wear the same label",
              not collisions, f"{len(collisions)}: {collisions[:3]}")

        # And every subject is NAMED — a tracker added tomorrow lands under a raw
        # machine word otherwise. This catches an ABSENT name; a wrong one is
        # caught only by reading the file the segment comes from, which is how
        # « economy » stopped being « Économie d'appels » under a tracker whose
        # `economy` block is its seeding obligation.
        # A POSITIVE CONTROL first, because this hold's shape is the one that
        # passes on nothing: it asserts an EMPTY set, and an empty set is also
        # what a dead detector produces. The set is filled as a SIDE EFFECT of
        # naming a subject, and that side effect had already been dropped once,
        # deliberately, when the naming was first reimplemented on the React
        # side as "an unrelated diagnostic" — so the day the page's renderer
        # stops going through the function that fills it, this hold goes green
        # while measuring nothing. It is what this control caught when the two
        # implementations were unified: the naming moved to `settings-labels.ts`
        # and the recording had to move with it, or the hold below would have
        # gone quiet in the same commit. The probe is a segment no table can
        # name: if it is NOT caught, the detector is dead, and nothing this hold
        # says afterwards means anything.
        probe = await pg.evaluate("""()=>{
          const seam = window.__settingLabels;
          const before = [...seam.unnamedSubjects];
          // french-ok: a DATA value shaped like a setting, whose path segment
          // is deliberately one no table can name — the probe itself.
          seam.label({f: "sonde", c: "segment_que_rien_ne_nomme.x", n: "x"});
          const caught = seam.unnamedSubjects.has("segment_que_rien_ne_nomme");
          seam.unnamedSubjects.delete("segment_que_rien_ne_nomme");
          return {caught, before};}""")
        check("the unnamed-subject detector actually detects",
              probe["caught"] and "segment_que_rien_ne_nomme" not in probe["before"],
              "a probe segment no table names was absent, then caught"
              if probe["caught"] else "the detector is dead — the hold below "
              "would pass on nothing")
        unnamed_subjects = await pg.evaluate("""()=>{
          SETTINGS.flatMap(r => r.r).forEach((x) => window.__settingLabels.label(x));
          return [...window.__settingLabels.unnamedSubjects];}""")
        check("every setting subject carries a written name", not unnamed_subjects,
              str(unnamed_subjects))

        # ── THE FIELD A VALUE ASKS FOR ─────────────────────────────────────
        # « Modifier » used to be a button that flipped « oui »/« non » and
        # otherwise appended « (modifié) » to the string — a placeholder that
        # could express neither a number, nor a list, nor an empty value. The
        # 153 real settings hold ten JSON shapes, and those ask for five fields,
        # one refusal, and one state that crosses them.
        #
        # The field is derived from the VALUE, never from a list of keys, so a
        # setting added tomorrow is editable without touching the rendering.
        # Driven by TYPE for the same reason: naming a key here would pass the
        # day that key moves and open something else.
        expected = {
            "boolean": '[data-part="field/toggle"]',
            "number": '[data-part="field/input"][type=number]',
            "text": '[data-part="field/input"][type=text]',
            "path": '[data-part="field/input"][data-mono]',
            "list": '[data-part="field/list-add"]',
            "duration": '[data-part="field/input"]',
            "structure": '[data-part="field"][data-read-only]',
            "empty": '[data-part="field/input"]',
            # A CRON EXPRESSION, and it is a NINTH kind since L09. It draws the
            # same text field as `text` — the difference is in how the value is
            # READ, not in the control — and the kind had to exist because it
            # lived nowhere: the interface guessed it from the shape of the
            # value, and the six cron settings rendered as raw cron on screen.
            "schedule": '[data-part="field/input"][type=text]',
        }
        seen = await pg.evaluate(
            """()=>[...new Set(SETTINGS.flatMap(r => r.r).map(x => x.type))].sort()""")
        check("every setting carries the type of its value",
              set(seen) == set(expected), str(sorted(seen)))

        for kind, selector in expected.items():
            await pg.evaluate("(g)=>window.__go(`settings-field-${g}`)", kind)
            await pg.wait_for_timeout(320)
            check(f"a « {kind} » value opens the field it asks for",
                  await pg.evaluate("(s)=>!!document.querySelector('#sheetin ' + s)",
                                    selector), selector)

        # A structure is REFUSED rather than half-drawn: a form for a list of
        # objects cannot be validated here, and drawing one would promise an
        # edit that breaks the file.
        await pg.evaluate("()=>window.__go('settings-field-structure')")
        await pg.wait_for_timeout(320)
        refusal = await pg.evaluate("""()=>{
          const s = document.querySelector('#sheetin');
          return {input: !!s.querySelector('[data-part="field/input"], [data-part="field/toggle"], [data-part="field/list-add"]'),
                  names: !!s.querySelector('[data-part="field"][data-read-only] code')};}""")
        check("a structure offers no field", not refusal["input"], str(refusal))
        check("and it names the file to open", refusal["names"])

        # The value a field files keeps its TYPE. Filed as a string, a number
        # compares unequal to the file's for ever, and the change could never be
        # undone by typing the original back — which is the check after.
        await pg.evaluate("()=>window.__go('settings-field-number')")
        await pg.wait_for_timeout(320)
        await pg.fill('#sheetin [data-part="field/input"]', "42")
        await pg.evaluate("""()=>document.querySelector('#sheetin [data-part="field/input"]')"""
                          ".dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(320)
        filed = await pg.evaluate(
            "()=>[...SETTINGS_STATE.modifs.values()].map(v => [v, typeof v])")
        check("a number is filed as a number",
              filed == [[42, "number"]], str(filed))

        original = await pg.evaluate(
            """()=>String(SETTINGS.flatMap(r => r.r).find(x => x.type === 'number').brut)""")
        await pg.fill('#sheetin [data-part="field/input"]', original)
        await pg.evaluate("""()=>document.querySelector('#sheetin [data-part="field/input"]')"""
                          ".dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(320)
        check("and typing the file's value back cancels the change",
              await pg.evaluate("()=>SETTINGS_STATE.modifs.size") == 0,
              f"original value {original}")

        await pg.evaluate("()=>window.__go('settings-field-boolean')")
        await pg.wait_for_timeout(320)
        await pg.click('#sheetin [data-part="field/toggle"]')
        await pg.wait_for_timeout(320)
        toggled = await pg.evaluate(
            "()=>[...SETTINGS_STATE.modifs.values()].map(v => [v, typeof v])")
        check("a switch files a boolean",
              len(toggled) == 1 and toggled[0][1] == "boolean", str(toggled))

        await pg.evaluate("""()=>{
          const x = SETTINGS.flatMap(r => r.r)
            .find(y => y.type === 'list' && (y.brut || []).length > 1);
          SETTINGS_STATE.topic = SETTINGS.find(r => r.r.includes(x)).id;
          render(); window.__panel.produce("setting", settingId(x));}""")
        await pg.wait_for_timeout(330)
        before = await pg.evaluate("""()=>document.querySelectorAll('#sheetin [data-part="field/list-item"]').length""")
        await pg.click('#sheetin [data-part="field/list-remove"]')
        await pg.wait_for_timeout(330)
        after = await pg.evaluate("""()=>document.querySelectorAll('#sheetin [data-part="field/list-item"]').length""")
        check("a list really loses an item", after == before - 1,
              f"{before} → {after}")

        # A field belongs to the setting it edits, and to no other. The panel
        # is ONE layer, reused from one setting to the next — the checks above
        # only ever open a single one, so a field handed on to the setting
        # after it would pass every one of them. Two settings of the same type
        # are opened in a row, with something typed into the first, because
        # that is the whole defect: a text field carries a value the operator
        # typed, and carrying it into the NEXT panel both shows a value that is
        # not the setting's and files it under the setting's id on the next
        # commit — a setting silently overwritten with another's value.
        open_text = """(n) => {
          const texts = SETTINGS.flatMap(r => r.r).filter(x => x.type === 'text');
          const x = texts[n];
          SETTINGS_STATE.topic = SETTINGS.find(r => r.r.includes(x)).id;
          render(); window.__panel.produce("setting", settingId(x));
          return {id: settingId(x), own: String(x.brut ?? '')};}"""
        read_field = """() => {const e = document.querySelector('#sheetin [data-part="field/input"]');
          return e ? {value: e.value, field: e.dataset.field} : null;}"""

        first = await pg.evaluate(open_text, 0)
        await pg.wait_for_timeout(330)
        await pg.fill('#sheetin [data-part="field/input"]', PROBE)
        await pg.evaluate("""()=>document.querySelector('#sheetin [data-part="field/input"]')"""
                          ".dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(330)
        await pg.evaluate("()=>closeSheet()")
        await pg.wait_for_timeout(330)

        second = await pg.evaluate(open_text, 1)
        await pg.wait_for_timeout(330)
        read = await pg.evaluate(read_field)
        check("the next setting opens on ITS OWN value",
              bool(read) and read["value"] == second["own"]
              and read["field"] == second["id"],
              f"expected {second['own']!r} under {second['id']}, read {read}")

        # And what a commit on the second one FILES, which is the half that
        # corrupts the configuration rather than merely misinforming.
        await pg.evaluate("""()=>document.querySelector('#sheetin [data-part="field/input"]')"""
                          ".dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(330)
        filed = await pg.evaluate(
            "()=>[...SETTINGS_STATE.modifs.entries()].map(([k, v]) => [k, String(v)])")
        leak = [k for k, v in filed if v == PROBE and k != first["id"]]
        check("and nothing typed into the other is filed under it",
              not leak, f"{PROBE!r} filed under {leak}" if leak else str(filed))

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
