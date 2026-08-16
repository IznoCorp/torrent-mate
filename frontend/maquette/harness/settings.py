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
DEHORS = (pathlib.Path.home() / "deploy" / "torrentmate",
          pathlib.Path.home() / "dev")
# Typed into one setting's field, and looked for everywhere else afterwards.
# Nothing a real setting could hold, so finding it under another id names the
# defect rather than a coincidence.
SONDE = "sonde-inter-panneaux"

_journal = None


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(nom, condition, detail)


async def main():
    global _journal
    _journal = Journal("R60 — les réglages")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        # ── the map is what one wants to change ────────────────────────────
        await pg.evaluate("()=>window.__go('reglages')")
        await pg.wait_for_timeout(320)
        carte = await pg.evaluate("""()=>({
          rubriques: [...document.querySelectorAll('.topic')].map(r => ({
            titre: (r.querySelector('.rt')||{}).textContent||'',
            sous: (r.querySelector('.rs')||{}).textContent||'',
            nombre: (r.querySelector('.rn')||{}).textContent||''})),
          recherche: !!document.querySelector('#qreg'),
          texte: (document.querySelector('#view')||{}).textContent||''})""")
        verifier("les rubriques sont nommées par ce qu'on change",
                 len(carte["rubriques"]) >= 6
                 and all(r["sous"].strip() for r in carte["rubriques"]),
                 str([r["titre"] for r in carte["rubriques"]]))
        # A rubric named after a file would be the defect this exists to avoid.
        fichiers = [f.stem for f in CONFIG.glob("*.json5")]
        nommees = [r["titre"].lower() for r in carte["rubriques"]]
        verifier("aucune rubrique ne porte le nom d'un fichier",
                 not [f for f in fichiers if f in nommees],
                 str([f for f in fichiers if f in nommees]))
        verifier("on peut chercher un réglage", carte["recherche"])

        # ── every real setting belongs to exactly one rubric ───────────────
        couverture = await pg.evaluate("""()=>{
          const tous = REGLAGES.flatMap(r => r.r.map(x => r.f + ':' + x.f + ':' + x.c));
          const cles = REGLAGES.flatMap(r => r.r.map(x => x.f + ':' + x.c));
          return {total: cles.length, distincts: new Set(cles).size,
                  fichiers: [...new Set(REGLAGES.flatMap(r => r.fichiers))].sort()};}""")
        verifier("chaque réglage n'appartient qu'à une rubrique",
                 couverture["total"] == couverture["distincts"],
                 f"{couverture['total']} réglages, {couverture['distincts']} distincts")
        # Nineteen of these are JSON5 overlays named by their concern; one is
        # not. The schedules belong to PM2 and live in `ecosystem.config.js`,
        # so a name carrying its own extension is looked for where PM2 keeps
        # it. What the check holds to is unchanged and is the point: a setting
        # names a file that EXISTS, never one the drawing invented.
        introuvables = [
            f for f in couverture["fichiers"]
            if not (CONFIG / f"{f}.json5").is_file()
            and not any((base / f).is_file() for base in DEHORS)
        ]
        verifier("et ils viennent des vrais fichiers de configuration",
                 not introuvables,
                 f"{len(couverture['fichiers'])} fichiers"
                 + (f" — introuvables : {', '.join(introuvables)}" if introuvables else ""))

        # ── a setting says where it comes from, and explains itself ────────
        await pg.evaluate("()=>window.__go('reglages-rubrique')")
        await pg.wait_for_timeout(320)
        # The origin is read as it is SEEN: the row carries the path, its group
        # header carries the file. Reading only the row would pass a screen where
        # nothing on it names a file.
        lignes = await pg.evaluate("""()=>[...document.querySelectorAll('.settingrow')].map(r => ({
          libelle: (r.querySelector('.rl')||{}).firstChild?.textContent?.trim()||'',
          chemin: (r.querySelector('.rf')||{}).textContent||'',
          entete: (r.closest('.panel')?.previousElementSibling||{}).textContent||'',
          valeur: (r.querySelector('.rv')||{}).textContent||''}))""")
        verifier("une rubrique liste ses réglages", len(lignes) > 10, str(len(lignes)))
        muets = [l for l in lignes
                 if not l["chemin"].strip() or ".json5" not in l["entete"]]
        verifier("chacun dit d'où il vient — sa clé, sous le nom de son fichier",
                 not muets, str([(m["chemin"], m["entete"]) for m in muets][:2]))
        verifier("et la clé n'y répète pas le fichier",
                 not [l for l in lignes if ".json5" in l["chemin"]],
                 str([l["chemin"] for l in lignes if ".json5" in l["chemin"]][:2]))
        verifier("et montre sa valeur",
                 all(l["valeur"].strip() for l in lignes),
                 str([l["libelle"] for l in lignes if not l["valeur"].strip()][:3]))

        # The explanation is the comment the file itself carries. Compared
        # against the file on disk, so invented prose cannot creep in.
        await pg.evaluate("()=>window.__go('reglages-un')")
        await pg.wait_for_timeout(350)
        panneau = await pg.evaluate("""()=>{
          const s = document.querySelector('#sheetin');
          return {texte: (s.textContent||'').replace(/\\s+/g,' '),
                  mono: !!s.querySelector('code'),
                  champ: !!s.querySelector('.field'),
                  actions: [...s.querySelectorAll('.sact')].map(x=>x.textContent.trim())};}""")
        source = (CONFIG / "thresholds.json5").read_text()
        commentaire = re.search(r"//\s*(.+?)\n\s*min_free_space_staging_gb", source)
        verifier("le panneau porte l'explication ÉCRITE DANS LE FICHIER",
                 commentaire is not None
                 and commentaire.group(1).strip().rstrip(".") in panneau["texte"],
                 (commentaire.group(1) if commentaire else "commentaire introuvable"))
        verifier("il nomme le fichier en chasse fixe", panneau["mono"])
        verifier("et il porte le champ qui modifie",
                 panneau["champ"], str(panneau["actions"]))

        # ── nothing is written until the bar is used ───────────────────────
        repos = await pg.evaluate("()=>!!document.querySelector('#savebar')")
        verifier("aucune barre d'enregistrement au repos", not repos)

        await pg.evaluate("()=>window.__go('reglages-modifie')")
        await pg.wait_for_timeout(350)
        attente = await pg.evaluate("""()=>{
          const bar = document.querySelector('#savebar');
          return {barre: !!bar, texte: bar ? bar.textContent.replace(/\\s+/g,' ') : '',
                  marquees: document.querySelectorAll('.settingrow.modified').length,
                  sousLaBarre: bar ? bar.getBoundingClientRect().bottom <=
                    document.querySelector('#device').getBoundingClientRect().bottom + 1 : false};}""")
        verifier("une modification fait apparaître la barre", attente["barre"])
        verifier("et la barre NOMME les fichiers qu'elle écrira",
                 ".json5" in attente["texte"], attente["texte"][:90])
        verifier("la ligne modifiée est marquée là où on la lit",
                 attente["marquees"] >= 1, f"{attente['marquees']} ligne(s)")
        verifier("la barre reste dans le cadre", attente["sousLaBarre"])

        # ── a secret is never shown ────────────────────────────────────────
        await pg.evaluate("()=>window.__go('reglages-secrets')")
        await pg.wait_for_timeout(320)
        secrets = await pg.evaluate("""()=>({
          lignes: [...document.querySelectorAll('.settingrow')].map(r =>
            (r.querySelector('.rv')||{}).textContent.trim()),
          champs: document.querySelectorAll('#view input').length})""")
        verifier("un secret dit s'il est posé, jamais ce qu'il vaut",
                 all(v in ("définie", "absente") for v in secrets["lignes"]),
                 str(sorted(set(secrets["lignes"]))))
        verifier("et aucune valeur n'est pré-remplie dans un champ",
                 secrets["champs"] == 0, f"{secrets['champs']} champ(s)")

        # ── read-only says so, and offers nothing ─────────────────────────
        await pg.evaluate("()=>window.__go('reglages-lecture-seule')")
        await pg.wait_for_timeout(320)
        lecture = await pg.evaluate("""()=>((document.querySelector('#view')||{}).textContent||'')
          .replace(/\\s+/g,' ')""")
        verifier("une instance en lecture seule le dit",
                 "lecture seule" in lecture.lower(), lecture[:80])

        # ── restart required names what is waiting ────────────────────────
        await pg.evaluate("()=>window.__go('reglages-redemarrage')")
        await pg.wait_for_timeout(320)
        redem = await pg.evaluate("""()=>{
          const v = document.querySelector('#view');
          return {texte: (v.textContent||'').replace(/\\s+/g,' '),
                  bouton: !!v.querySelector('[data-redemarrer]')};}""")
        verifier("un redémarrage nécessaire le dit et l'offre",
                 "edémarrage" in redem["texte"] and redem["bouton"], redem["texte"][:70])

        # ── search looks through every setting ─────────────────────────────
        await pg.evaluate("()=>window.__go('reglages-recherche')")
        await pg.wait_for_timeout(320)
        cherche = await pg.evaluate("""()=>({
          resultats: document.querySelectorAll('.settingrow').length,
          vide: !!document.querySelector('.empty'),
          texte: (document.querySelector('#view')||{}).textContent||''})""")
        # A FRENCH word must find something: the labels used to be the files'
        # English comments, so « espace » matched no row at all — the search
        # existed and answered nothing.
        verifier("un mot français trouve des réglages",
                 cherche["resultats"] > 0, f"{cherche['resultats']} résultat(s) pour « espace »")

        # A result stands alone under no header, so THERE the row names its file.
        sans = await pg.evaluate("""()=>[...document.querySelectorAll('.settingrow .rf')]
          .map(e => e.textContent).filter(t => !t.includes('.json5'))""")
        verifier("un résultat de recherche nomme son fichier lui-même",
                 not sans, str(sans[:2]))

        # And no label is an English sentence — over EVERY setting, not the one
        # rubric that happens to be on screen. The comment is not lost: it is
        # the explanation in the panel, where a sentence has room.
        anglais = await pg.evaluate("""()=>{
          const mots = /\\b(the|of|for|before|when|with|and|from|number|seconds|days|file|path|used|which|that)\\b/i;
          return REGLAGES.flatMap(r => r.r).map(libelleReglage).filter(t => mots.test(t));}""")
        verifier("aucun réglage n'est libellé en anglais",
                 not anglais, f"{len(anglais)} : {anglais[:3]}")

        # And no two rows in the same list read the same. The leaf key alone drew
        # « Activé » seven times under « Ce qu'on va chercher »: every tracker and
        # every client owns one, and the only thing telling them apart was the
        # machine path — which is there to be read AFTER one has found the row,
        # not to find it.
        collisions = await pg.evaluate("""()=>REGLAGES.flatMap(r => {
          const par = {};
          for (const x of r.r) (par[libelleReglage(x)] ||= []).push(x.c);
          return Object.entries(par).filter(([, v]) => v.length > 1)
                       .map(([l, v]) => `${r.t} : « ${l} » ×${v.length}`);})""")
        verifier("deux réglages d'une même rubrique ne portent pas le même libellé",
                 not collisions, f"{len(collisions)} : {collisions[:3]}")

        # And every subject is NAMED — a tracker added tomorrow lands under a raw
        # machine word otherwise. This catches an ABSENT name; a wrong one is
        # caught only by reading the file the segment comes from, which is how
        # « economy » stopped being « Économie d'appels » under a tracker whose
        # `economy` block is its seeding obligation.
        sansNom = await pg.evaluate("""()=>{
          REGLAGES.flatMap(r => r.r).forEach(libelleReglage);
          return [...window.__sujetsSansNom];}""")
        verifier("chaque sujet de réglage porte un nom écrit", not sansNom, str(sansNom))

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
        attendus = {
            "booleen": ".fieldtoggle",
            "nombre": ".fieldinput[type=number]",
            "texte": ".fieldinput[type=text]",
            "chemin": ".fieldinput.mono",
            "liste": ".ladd",
            "duree": ".fieldinput",
            "structure": ".field.readonly",
            "nul": ".fieldinput",
        }
        vus = await pg.evaluate(
            """()=>[...new Set(REGLAGES.flatMap(r => r.r).map(x => x.type))].sort()""")
        verifier("chaque réglage porte le type de sa valeur",
                 set(vus) == set(attendus), str(sorted(vus)))

        for genre, selecteur in attendus.items():
            await pg.evaluate("(g)=>window.__go(`reglages-champ-${g}`)", genre)
            await pg.wait_for_timeout(320)
            verifier(f"une valeur « {genre} » ouvre le champ qu'elle demande",
                     await pg.evaluate("(s)=>!!document.querySelector('#sheetin ' + s)",
                                       selecteur), selecteur)

        # A structure is REFUSED rather than half-drawn: a form for a list of
        # objects cannot be validated here, and drawing one would promise an
        # edit that breaks the file.
        await pg.evaluate("()=>window.__go('reglages-champ-structure')")
        await pg.wait_for_timeout(320)
        refus = await pg.evaluate("""()=>{
          const s = document.querySelector('#sheetin');
          return {saisie: !!s.querySelector('.fieldinput, .fieldtoggle, .ladd'),
                  nomme: !!s.querySelector('.field.readonly code')};}""")
        verifier("une structure n'offre aucun champ", not refus["saisie"], str(refus))
        verifier("et elle nomme le fichier à ouvrir", refus["nomme"])

        # The value a field files keeps its TYPE. Filed as a string, a number
        # compares unequal to the file's for ever, and the change could never be
        # undone by typing the original back — which is the check after.
        await pg.evaluate("()=>window.__go('reglages-champ-nombre')")
        await pg.wait_for_timeout(320)
        await pg.fill("#sheetin .fieldinput", "42")
        await pg.evaluate("()=>document.querySelector('#sheetin .fieldinput')"
                          ".dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(320)
        depose = await pg.evaluate(
            "()=>[...REG_ETAT.modifs.values()].map(v => [v, typeof v])")
        verifier("un nombre est déposé comme un nombre",
                 depose == [[42, "number"]], str(depose))

        origine = await pg.evaluate(
            """()=>String(REGLAGES.flatMap(r => r.r).find(x => x.type === 'nombre').brut)""")
        await pg.fill("#sheetin .fieldinput", origine)
        await pg.evaluate("()=>document.querySelector('#sheetin .fieldinput')"
                          ".dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(320)
        verifier("et retaper la valeur du fichier annule la modification",
                 await pg.evaluate("()=>REG_ETAT.modifs.size") == 0,
                 f"valeur d'origine {origine}")

        await pg.evaluate("()=>window.__go('reglages-champ-booleen')")
        await pg.wait_for_timeout(320)
        await pg.click("#sheetin .fieldtoggle")
        await pg.wait_for_timeout(320)
        bascule = await pg.evaluate(
            "()=>[...REG_ETAT.modifs.values()].map(v => [v, typeof v])")
        verifier("un interrupteur dépose un booléen",
                 len(bascule) == 1 and bascule[0][1] == "boolean", str(bascule))

        await pg.evaluate("""()=>{
          const x = REGLAGES.flatMap(r => r.r)
            .find(y => y.type === 'liste' && (y.brut || []).length > 1);
          REG_ETAT.rubrique = REGLAGES.find(r => r.r.includes(x)).id;
          render(); ouvrirReglage(reglageId(x));}""")
        await pg.wait_for_timeout(330)
        avant = await pg.evaluate("()=>document.querySelectorAll('#sheetin .litem').length")
        await pg.click("#sheetin .lremove")
        await pg.wait_for_timeout(330)
        apres = await pg.evaluate("()=>document.querySelectorAll('#sheetin .litem').length")
        verifier("une liste perd vraiment un élément", apres == avant - 1,
                 f"{avant} → {apres}")

        # A field belongs to the setting it edits, and to no other. The panel
        # is ONE layer, reused from one setting to the next — the checks above
        # only ever open a single one, so a field handed on to the setting
        # after it would pass every one of them. Two settings of the same type
        # are opened in a row, with something typed into the first, because
        # that is the whole defect: a text field carries a value the operator
        # typed, and carrying it into the NEXT panel both shows a value that is
        # not the setting's and files it under the setting's id on the next
        # commit — a setting silently overwritten with another's value.
        ouvrir_texte = """(n) => {
          const textes = REGLAGES.flatMap(r => r.r).filter(x => x.type === 'texte');
          const x = textes[n];
          REG_ETAT.rubrique = REGLAGES.find(r => r.r.includes(x)).id;
          render(); ouvrirReglage(reglageId(x));
          return {id: reglageId(x), sienne: String(x.brut ?? '')};}"""
        lire_champ = """() => {const e = document.querySelector('#sheetin .fieldinput');
          return e ? {valeur: e.value, champ: e.dataset.champ} : null;}"""

        premier = await pg.evaluate(ouvrir_texte, 0)
        await pg.wait_for_timeout(330)
        await pg.fill("#sheetin .fieldinput", SONDE)
        await pg.evaluate("()=>document.querySelector('#sheetin .fieldinput')"
                          ".dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(330)
        await pg.evaluate("()=>closeSheet()")
        await pg.wait_for_timeout(330)

        second = await pg.evaluate(ouvrir_texte, 1)
        await pg.wait_for_timeout(330)
        lu = await pg.evaluate(lire_champ)
        verifier("le réglage suivant ouvre sur SA valeur",
                 bool(lu) and lu["valeur"] == second["sienne"]
                 and lu["champ"] == second["id"],
                 f"attendu {second['sienne']!r} sous {second['id']}, lu {lu}")

        # And what a commit on the second one FILES, which is the half that
        # corrupts the configuration rather than merely misinforming.
        await pg.evaluate("()=>document.querySelector('#sheetin .fieldinput')"
                          ".dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(330)
        depose = await pg.evaluate(
            "()=>[...REG_ETAT.modifs.entries()].map(([k, v]) => [k, String(v)])")
        fuite = [k for k, v in depose if v == SONDE and k != premier["id"]]
        verifier("et rien de ce qui a été tapé dans l'autre n'est déposé sous lui",
                 not fuite, f"{SONDE!r} déposé sous {fuite}" if fuite else str(depose))

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    _journal.summary()

asyncio.run(main())
