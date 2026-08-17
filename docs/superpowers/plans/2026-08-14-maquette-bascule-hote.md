# Maquette Host Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Re-pointed 2026-08-17 (clean-code / i18n wave).** The harness moved to
> English: its scripts were renamed, its hold labels translated, and its printed
> verdict is now `  PASS` / `  FAIL` and `N rules EXECUTED — no violation`. Every
> quoted expectation and every file name below was re-pointed at what the current
> sources actually say — a quotation that silently misses its target is how a
> recipe stops working without anyone noticing. Two things were deliberately NOT
> rewritten: the fenced source LISTINGS, which are the code as authored on the
> day, and the hold COUNTS, which are what was expected then. `shell.py` runs 4 holds today, not 23, and `switchover.py` runs 11, not 5 — the six extra ones are R73's later SPA-fallback, dotted-path, favicon and gated-`/assets/` amendments. Both labels quoted in Task 3's mutations still exist verbatim.

**Goal:** The design host serves the Vite build (byte-exact `dist/index.html`), auto-rebuilding on stale sources, with a build failure shown as a 503 that says so — held by a new rule R73.

**Architecture:** The PWA head moves from `serve.py`'s synthesis into the Vite envelope (`index.html`) between extraction markers; `serve.py`'s login page EXTRACTS that head (one source of truth, the file's own pattern); `_document()` becomes stale-check → locked rebuild → serve `dist` bytes. A `TM_DESIGN_ROOT` env lets R73 point `serve.py` at a scratch copy so no rule ever mutates the real source.

**Tech Stack:** Python 3.12 stdlib (serve.py), npm at `/Users/izno/.nvm/versions/node/v22.13.1/bin/npm` (build measured at 0.4 s), Playwright harness (`command python3`, `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-14-maquette-bascule-hote-design.md`

## Global Constraints

- Branch `refactor/maquette-bascule` (from `main` `61fe2b7b`); spec committed (`458013cf`).
- `refonte.html`: zero bytes changed. The harness's measuring URL and `wrapped.html` ritual: unchanged.
- Conventional Commits, scope `(shell-mobile)`, French messages, no AI attribution. Comments English, no session/date refs.
- Never `rg` unfiltered; `curl` with `--connect-timeout 10 --max-time 30`; `command python3`; scratch ports only (8913/8917/8918 — never 8710/8711/8899/8712 for scratch).
- The pm2 host `torrentmate-design` serves THIS tree — restart it when `serve.py` or the envelope change, and note that `pwa.py`/`entry.py` measure it live.
- One measuring process at a time. Re-sync recipe (unchanged):
  ```bash
  command python3 - <<'EOF'
  from pathlib import Path
  src = Path("frontend/maquette/design/refonte.html").read_text()
  head = ('<!doctype html><html><head><meta charset="utf-8">'
          '<meta name="viewport" content="width=device-width,initial-scale=1,'
          'maximum-scale=1,user-scalable=no"></head><body>\n')
  Path("/tmp/tm-refonte/wrapped.html").write_text(head + src)
  EOF
  ```
- Version bump at the end: `personalscraper/__init__.py` `0.97.2` → `0.97.3`.
- After every push: verify the remote SHA.

---

### Task 1: The envelope carries the PWA head; the login page extracts it

**Files:**

- Modify: `frontend/maquette/design/index.html` (head gains the PWA block between markers)
- Modify: `frontend/maquette/serve.py` (TETE_PWA constant → extraction from the envelope)

**Interfaces:**

- Consumes: the SP2 envelope and `extraire()`-style marker extraction already in serve.py.
- Produces: `index.html` contains `<!-- pwa:start -->…<!-- pwa:end -->`; serve.py exposes `tete_pwa()` returning that block's text; Task 2 serves the whole envelope so the main document gets the head from the FILE, and `page_connexion` keeps getting it from `tete_pwa()`.

- [ ] **Step 1: Add the PWA head to `frontend/maquette/design/index.html`** — inside `<head>`, after the `<title>` line:

```html
<!-- pwa:start — the document half of installability. The server half
         (manifest body, sw.js, brand assets, the offline page) stays in
         serve.py: those are routes, not markup. The login gate EXTRACTS this
         block rather than restating it, so there is exactly one copy. -->
<link rel="manifest" href="/manifest.webmanifest" />
<meta name="theme-color" content="#0b0b0d" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<!-- iOS reads neither the manifest's display nor its short_name:
         standalone mode and the home-screen label are declared here, or the
         icon opens a Safari tab instead of an app. -->
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="mobile-web-app-capable" content="yes" />
<meta
  name="apple-mobile-web-app-status-bar-style"
  content="black-translucent"
/>
<meta name="apple-mobile-web-app-title" content="TorrentMate Design" />
<script>
  if ("serviceWorker" in navigator)
    addEventListener("load", () => navigator.serviceWorker.register("/sw.js"));
</script>
<!-- pwa:end -->
```

- [ ] **Step 2: Replace serve.py's TETE_PWA constant with an extraction.** Delete the whole
      `TETE_PWA = (...)` assignment (serve.py:180-197) AND its lead comment block right above
      (the « Everything that makes a document installable… » paragraph, :172-179), and put in
      their place:

```python
ENVELOPPE = Path(__file__).resolve().parent / "design" / "index.html"


def tete_pwa() -> str:
    """Returns the PWA head block, extracted from the envelope.

    The envelope (`design/index.html`) is the document's single source of
    truth since the host began serving the build; the login gate sits in
    front of that document and must be installable too, so it borrows the
    same block rather than restating it — a restated copy is where drift
    hides (measured twice on the login screen's styles).

    Raises:
        ValueError: When the markers are missing — the gate must fail loudly
            rather than serve a page that silently lost its installability.
    """
    source = ENVELOPPE.read_text()
    debut = source.find("pwa:start")
    fin = source.find("<!-- pwa:end -->")
    if debut < 0 or fin < 0 or fin < debut:
        raise ValueError("marqueurs pwa introuvables dans design/index.html")
    return source[source.index("-->", debut) + 3 : fin]
```

Then update the TWO consumers:

- In `HEAD` (serve.py:199-206): replace `f"{TETE_PWA}"` with `f"{tete_pwa()}"` — Task 2
  deletes `HEAD` entirely; this keeps the tree working between commits.
- In `page_connexion` (serve.py:305-313): replace `f"{TETE_PWA}"` with `f"{tete_pwa()}"`.

- [ ] **Step 3: Prove it on a scratch port** (8913, killed after; env-hash password pattern):

```bash
cd /Users/izno/dev/PersonalScraper/frontend/maquette
HASH=$(command python3 -c "import hashlib,os,base64; s=os.urandom(16); \
print(base64.b64encode(s).decode()+':'+base64.b64encode( \
hashlib.scrypt(b'epreuve', salt=s, n=16384, r=8, p=1, dklen=32)).decode())")
TM_DESIGN_PASSWORD_HASH="$HASH" command python3 serve.py 8913 & SRV=$!
sleep 1
curl --connect-timeout 10 --max-time 30 -s http://127.0.0.1:8913/ | rg -g '*' -c "manifest.webmanifest" && echo "login page carries the manifest link"
kill $SRV
```

Expected: count ≥ 1 and the message.

- [ ] **Step 4: R72 still green** (the envelope changed; the byte-exact assertion recomputes
      from the CURRENT envelope). Re-sync `wrapped.html` (Global Constraints), then:

```bash
cd /Users/izno/dev/PersonalScraper/frontend/maquette/harness && command python3 shell.py | tail -3
```

Expected: `23 rules EXECUTED — no violation`.

- [ ] **Step 5: Commit**

```bash
cd /Users/izno/dev/PersonalScraper
git add frontend/maquette/design/index.html frontend/maquette/serve.py
git commit -m "refactor(shell-mobile): la tête PWA vit dans l'enveloppe; le portail l'extrait au lieu de la redire"
```

---

### Task 2: serve.py serves the build, rebuilt à la volée

**Files:**

- Modify: `frontend/maquette/serve.py` (`HEAD`/`TAIL` die; `_document()` rewritten; `MANQUANT` joined by `panne_build()`; `TM_DESIGN_ROOT` env; a build lock)

**Interfaces:**

- Consumes: Task 1's envelope; `npm run build` (0.4 s) emitting `design/dist/index.html`.
- Produces: authenticated `GET /` ≡ `dist/index.html` bytes; stale sources rebuild before serving; build failure → 503 naming it. `TM_DESIGN_ROOT` (absolute path env) points serve.py at another design root — Task 3's rule depends on exactly that.

- [ ] **Step 1: Root and constants.** At serve.py's constant section (top, where `PROTOTYPE` is defined), replace

```python
PROTOTYPE = Path(__file__).resolve().parent / "design" / "refonte.html"
```

with:

```python
# The design root is overridable so a harness rule can point the server at a
# SCRATCH copy and mutate it freely: no measurement may ever write into the
# operator's real source.
RACINE_DESIGN = Path(
    os.environ.get("TM_DESIGN_RACINE")
    or Path(__file__).resolve().parent / "design"
).resolve()
PROTOTYPE = RACINE_DESIGN / "refonte.html"
DIST = RACINE_DESIGN / "dist" / "index.html"
# What staleness is measured against: every input the build reads.
SOURCES_BUILD = (
    PROTOTYPE,
    RACINE_DESIGN / "index.html",
    RACINE_DESIGN / "vite.config.mjs",
)
NPM = "/Users/izno/.nvm/versions/node/v22.13.1/bin/npm"
```

(`import os` and `import subprocess` and `import threading` join the imports;
`ENVELOPPE` from Task 1 becomes `RACINE_DESIGN / "index.html"` — replace its assignment.)

- [ ] **Step 2: Delete `HEAD` and `TAIL`** (the whole `HEAD = (...)` and `TAIL = b"..."`
      assignments) — the build IS the document now.

- [ ] **Step 3: The build-failure page.** After `MANQUANT`, add:

```python
def panne_build(erreur: str) -> bytes:
    """Builds the 503 shown when the build fails.

    Serving the PREVIOUS build instead would be a stale reference wearing
    today's date — the exact failure a design host exists to avoid. The page
    says what broke, with the build's own last words.
    """
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Build en échec</title></head><body "
        'style="font:16px system-ui;max-width:44em;margin:12vh auto;padding:0 1.5em">'
        "<h1>Le build de la maquette a échoué</h1><p>Le serveur reconstruit le "
        "document à chaque source modifiée ; cette reconstruction vient "
        "d'échouer, et servir l'ancienne version serait mentir sur la date de "
        "ce que vous jugez.</p><pre style=\"white-space:pre-wrap;background:#f6f6f6;"
        'padding:12px;border-radius:8px">'
        f"{erreur}"
        "</pre></body></html>"
    ).encode()
```

- [ ] **Step 4: Rewrite `_document()`** (and the class attributes around it). Replace the
      `_cache` attribute comment + `_document` method (serve.py:343-365) with:

```python
    # The document is the BUILD, reconstructed on demand: comparing the
    # newest source mtime against dist's answers « is what I would serve
    # what the sources say? », and 0.4 s of vite build is cheaper than one
    # stale judgement. mtime_ns, not mtime: a second-resolution stamp
    # misses two edits within the same second — the cadence of an editing
    # session. One lock, or two stale requests race the same build.
    _cache: tuple[int, bytes] | None = None
    _verrou_build = threading.Lock()

    def _document(self) -> bytes:
        """Returns the built document, rebuilding it when sources changed.

        Returns:
            The bytes of `dist/index.html`, freshly rebuilt if any build
            input was newer.

        Raises:
            FileNotFoundError: When `refonte.html` is absent (branch without
                the prototype) — the caller answers with MANQUANT.
            RuntimeError: When the build fails — the caller answers with the
                build's own words, never with a stale document.
        """
        sources = max(chemin.stat().st_mtime_ns for chemin in SOURCES_BUILD)
        with Handler._verrou_build:
            try:
                bati = DIST.stat().st_mtime_ns
            except FileNotFoundError:
                bati = -1
            if bati < sources:
                fait = subprocess.run(
                    [NPM, "run", "build"], cwd=RACINE_DESIGN,
                    capture_output=True, text=True, timeout=120)
                if fait.returncode != 0:
                    queue = (fait.stderr or fait.stdout).strip().splitlines()[-12:]
                    raise RuntimeError("\n".join(queue))
            stamp = DIST.stat().st_mtime_ns
            cached = Handler._cache
            if cached is None or cached[0] != stamp:
                Handler._cache = (stamp, DIST.read_bytes())
            return Handler._cache[1]  # type: ignore[index]
```

- [ ] **Step 5: The caller.** In `do_GET` (the tail, serve.py:446-450), replace

```python
        body = self._document()
        if body is None:
            self._send(503, MANQUANT)
            return
        self._send(200, body)
```

with:

```python
        try:
            body = self._document()
        except FileNotFoundError:
            self._send(503, MANQUANT)
            return
        except RuntimeError as erreur:
            self._send(503, panne_build(str(erreur)))
            return
        self._send(200, body)
```

- [ ] **Step 6: Prove the three behaviours on a scratch design root** (this is R73's dry
      run, by hand; port 8918):

```bash
cd /Users/izno/dev/PersonalScraper/frontend/maquette
R=/tmp/tm-refonte/_bascule
rm -rf "$R" && mkdir -p "$R"
cp design/refonte.html design/index.html design/vite.config.mjs design/package.json "$R/"
ln -s "$(pwd)/design/node_modules" "$R/node_modules"
ln -s "$(pwd)/design/assets" "$R/assets"
HASH=$(command python3 -c "import hashlib,os,base64; s=os.urandom(16); \
print(base64.b64encode(s).decode()+':'+base64.b64encode( \
hashlib.scrypt(b'epreuve', salt=s, n=16384, r=8, p=1, dklen=32)).decode())")
TM_DESIGN_ROOT="$R" TM_DESIGN_PASSWORD_HASH="$HASH" command python3 serve.py 8918 & SRV=$!
sleep 1
COOKIE=$(curl --connect-timeout 10 --max-time 30 -s -D - -o /dev/null \
  -d "identifiant=izno&motdepasse=epreuve" "http://127.0.0.1:8918/connexion" \
  | grep -i '^set-cookie:' | cut -d' ' -f2 | cut -d';' -f1)
# (a) byte identity
curl --connect-timeout 10 --max-time 30 -s -H "Cookie: $COOKIE" http://127.0.0.1:8918/ -o /tmp/tm-refonte/_servi.html
cmp /tmp/tm-refonte/_servi.html "$R/dist/index.html" && echo "IDENTIQUE à l'octet"
# (b) auto-rebuild
printf '\n<!-- bascule-probe -->\n' >> "$R/refonte.html"
curl --connect-timeout 10 --max-time 30 -s -H "Cookie: $COOKIE" http://127.0.0.1:8918/ | rg -g '*' -c "bascule-probe" && echo "REBUILD à la volée"
# (c) build failure shown
printf 'ceci n est pas du javascript {' > "$R/vite.config.mjs"
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" -H "Cookie: $COOKIE" http://127.0.0.1:8918/
curl --connect-timeout 10 --max-time 30 -s -H "Cookie: $COOKIE" http://127.0.0.1:8918/ | rg -g '*' -c "build de la maquette a échoué" && echo "PANNE DITE"
kill $SRV
```

Expected: `IDENTIQUE à l'octet`, `1` + `REBUILD à la volée`, `503`, `1` + `PANNE DITE`.

- [ ] **Step 7: Restart the live host and check it serves the build**

```bash
cd /Users/izno/dev/PersonalScraper && pm2 restart torrentmate-design && sleep 2
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8712/
```

Expected: `401` (gate up; the authenticated byte-identity is R73's and Task 4's live check).

- [ ] **Step 8: Commit**

```bash
git add frontend/maquette/serve.py
git commit -m "feat(shell-mobile): l'hôte sert le build, reconstruit à la volée — une panne se montre, jamais l'ancien document

_document() compare le mtime le plus récent des sources du build à celui de
dist/index.html, reconstruit sous verrou quand c'est périmé (0,4 s mesuré),
et sert les octets du build. Un build en échec répond 503 avec ses propres
derniers mots — servir l'ancienne version daterait faussement ce qui est
jugé. TM_DESIGN_ROOT pointe le serveur sur une copie de brouillon pour
que la règle R73 mute sans toucher la source réelle."
```

---

### Task 3: R73 — `harness/switchover.py`

**Files:**

- Create: `frontend/maquette/harness/switchover.py`
- Modify: `frontend/maquette/regions.json` (R73 entry), `frontend/maquette/README.md` (row)

**Interfaces:**

- Consumes: `TM_DESIGN_ROOT` + `TM_DESIGN_PASSWORD_HASH` envs of serve.py; `common.Journal`.
- Produces: the 44th rule.

- [ ] **Step 1: Write the rule** — `frontend/maquette/harness/switchover.py` (no Playwright —
      this rule measures HTTP, not rendering):

```python
"""R73 — the host serves the build, and a failed build says so.

Since the switch, the document the operator judges is the Vite build. Three
things must therefore hold, and each has its own way of rotting silently:
the served bytes could drift from `dist/index.html` (a re-grown synthesis),
an edit could serve yesterday's build (a stale reference wearing today's
date), and a broken build could hide behind the previous output. The rule
boots the real `serve.py` on a scratch COPY of the design root — a
measurement must never write into the operator's source — and holds all
three over plain HTTP.
"""
import base64
import hashlib
import http.client
import os
import pathlib
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import Journal, RACINE

PORT = 8918
SCRATCH = pathlib.Path("/tmp/tm-refonte/_r73")
MOT_DE_PASSE = "epreuve"


def empreinte() -> str:
    sel = os.urandom(16)
    calcule = hashlib.scrypt(MOT_DE_PASSE.encode(), salt=sel,
                             n=16384, r=8, p=1, dklen=32)
    return (base64.b64encode(sel).decode() + ":"
            + base64.b64encode(calcule).decode())


def preparer_scratch() -> None:
    """Builds the scratch design root: copies for what mutates, links for
    what must stay shared and read-only (node_modules, the artwork)."""
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    design = RACINE / "design"
    for nom in ("refonte.html", "index.html", "vite.config.mjs", "package.json"):
        shutil.copy(design / nom, SCRATCH / nom)
    (SCRATCH / "node_modules").symlink_to(design / "node_modules")
    (SCRATCH / "assets").symlink_to(design / "assets")


def requete(chemin, cookie=None, methode="GET", corps=None):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=150)
    entetes = {}
    if cookie:
        entetes["Cookie"] = cookie
    if corps is not None:
        entetes["Content-Type"] = "application/x-www-form-urlencoded"
    conn.request(methode, chemin, body=corps, headers=entetes)
    reponse = conn.getresponse()
    donnees = reponse.read()
    conn.close()
    return reponse, donnees


def main():
    journal = Journal("R73 — l'hôte sert le build")
    preparer_scratch()
    serveur = subprocess.Popen(
        [sys.executable, str(RACINE / "serve.py"), str(PORT)],
        env={**os.environ, "TM_DESIGN_RACINE": str(SCRATCH),
             "TM_DESIGN_PASSWORD_HASH": empreinte()},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1)
        reponse, _ = requete(
            "/connexion", methode="POST",
            corps=f"identifiant=izno&motdepasse={MOT_DE_PASSE}")
        cookie = (reponse.getheader("Set-Cookie") or "").split(";")[0]
        journal.verifier("la session s'ouvre", reponse.status == 303 and cookie,
                         f"{reponse.status}")

        # (a) The served document IS the build, to the byte.
        reponse, servi = requete("/", cookie)
        bati = (SCRATCH / "dist" / "index.html").read_bytes()
        journal.verifier("le document servi est le build, à l'octet",
                         reponse.status == 200 and servi == bati,
                         f"{len(servi)} octets servis, {len(bati)} au build")

        # (b) An edited source is served rebuilt — never yesterday's build.
        with open(SCRATCH / "refonte.html", "a") as fichier:
            fichier.write("\n<!-- r73-probe -->\n")
        reponse, servi = requete("/", cookie)
        journal.verifier("une source modifiée est reconstruite à la volée",
                         reponse.status == 200 and b"r73-probe" in servi,
                         f"{reponse.status}")

        # (c) A broken build answers 503 and SAYS it broke.
        (SCRATCH / "vite.config.mjs").write_text("ceci n'est pas du javascript {\n")
        # The config is a build input: its mtime alone must trigger the try.
        reponse, corps = requete("/", cookie)
        journal.verifier("un build cassé répond 503 en le disant",
                         reponse.status == 503
                         and "build de la maquette a" in corps.decode("utf-8", "replace"),
                         f"{reponse.status}")

        # And the way back: restoring the config heals the host on its own.
        shutil.copy(RACINE / "design" / "vite.config.mjs",
                    SCRATCH / "vite.config.mjs")
        reponse, servi = requete("/", cookie)
        journal.verifier("le rétablissement de la source guérit l'hôte",
                         reponse.status == 200 and b"r73-probe" in servi,
                         f"{reponse.status}")
    finally:
        serveur.terminate()
        serveur.wait(timeout=5)
        shutil.rmtree(SCRATCH, ignore_errors=True)
    journal.bilan()


main()
```

- [ ] **Step 2: Run it green**

```bash
cd /Users/izno/dev/PersonalScraper/frontend/maquette/harness && command python3 switchover.py; echo "exit=$?"
```

Expected: `5 rules EXECUTED — no violation`, exit 0.

- [ ] **Step 3: Mutation one — the staleness comparison inverted; hold (b) must fall.** In
      `frontend/maquette/serve.py`, temporarily change `if bati < sources:` to
      `if bati > sources:` (Edit tool, one token), run `command python3 switchover.py; echo "exit=$?"`.
      Expected: exit 1, `FAIL an edited source is rebuilt on the fly` (the byte-identity
      check may also fall — dist never gets built on the fresh scratch — name whatever falls, the
      rebuild check MUST be among them). Restore with `git checkout -- ../serve.py`, re-run green.

- [ ] **Step 4: Mutation two — the failure path masked; hold (c) must fall.** Temporarily
      change `raise RuntimeError("\n".join(queue))` to `pass  # muted` (keeping indentation
      valid), run the rule. Expected: exit 1, `FAIL a broken build answers 503 and says so` —
      the host served the stale document instead. Restore with `git checkout -- ../serve.py`,
      re-run green.

- [ ] **Step 5: Register** — `regions.json` `$adversarialReview` gains `"R73"` (same shape as
      siblings): what it holds (served bytes ≡ build; stale sources rebuilt before serving;
      broken build answers 503 naming itself, heals on restore), how verified (two serve.py
      mutations, each felling its own hold: inverted staleness starves the rebuild; muted
      failure serves the stale document). README table row after `shell.py`:

```
| `switchover.py`   | R73: the host serves the build to the byte, rebuilds stale sources before serving, and a broken build answers 503 that says so — proven against a scratch design root, never the real source |
```

- [ ] **Step 6: Commit**

```bash
cd /Users/izno/dev/PersonalScraper
git add frontend/maquette/harness/switchover.py frontend/maquette/regions.json frontend/maquette/README.md
git commit -m "test(shell-mobile): R73 — l'hôte sert le build, prouvé sur une racine de brouillon

Trois tenues sur HTTP nu : octets servis ≡ dist/index.html, source modifiée
reconstruite avant d'être servie, build cassé répondu 503 qui le dit puis
guéri par la source rétablie. Deux mutations de serve.py, chacune ne
faisant tomber que sa tenue : la comparaison de fraîcheur inversée affame
la reconstruction ; l'échec muselé sert le document périmé."
```

---

### Task 4: Suite, live host, docs, delivery

**Files:**

- Modify (only if the suite says so): `harness/startup.py`, `harness/logout.py`, `harness/pwa.py`, `harness/entry.py`
- Modify: `frontend/maquette/README.md` (serving-path paragraph), `IMPLEMENTATION.md` (bascule entry), `personalscraper/__init__.py` (`0.97.3`)

**Interfaces:**

- Consumes: everything above green, pm2 restarted on this tree.

- [ ] **Step 1: Full suite** (44 scripts, sequential, detached; re-sync `wrapped.html` first):

```bash
cd /Users/izno/dev/PersonalScraper/frontend/maquette/harness
rm -f /tmp/tm-refonte/suite-bascule.log
nohup bash -c 'for s in *.py; do
    [ "$s" = common.py ] && continue
    command python3 "$s" > /dev/null 2>&1 || echo "FAILED: $s" >> /tmp/tm-refonte/suite-bascule.log
  done; echo "SUITE TERMINEE" >> /tmp/tm-refonte/suite-bascule.log' > /dev/null 2>&1 &
```

Poll until `SUITE TERMINEE`. Expected: zero `FAILED:`. A failure in `startup.py`/
`logout.py`/`pwa.py`/`entry.py` is diagnosed by mechanism (what did the serving
change actually alter?) and fixed inside the rule ONLY where its expectation described the
old synthesis; anything else stops and reports.

- [ ] **Step 2: The live gate check** (the host serves this tree; its UNAUTHENTICATED
      surface only — the authenticated byte-identity is proven by R73 against the same code
      path, and no rule may carry the operator's real password):

```bash
curl --connect-timeout 10 --max-time 30 -s http://127.0.0.1:8712/ -o /tmp/tm-refonte/_gate.html
rg -g '*' -c "manifest.webmanifest" /tmp/tm-refonte/_gate.html && echo "portail installable, tête extraite de l'enveloppe"
```

Expected: count ≥ 1. (The authenticated live byte-identity was proven by R73 against the
same code path; the live gate cannot be session-probed without the operator's real
password, which no rule may carry — state this plainly in the report.)

- [ ] **Step 3: Docs.** README: in the shell paragraph (added in SP2), update the last
      sentence — the live host now serves the BUILD, rebuilt on stale sources, R73 holds it, and
      the harness still measures the source through `wrapped.html` (mutation isolation).
      IMPLEMENTATION.md: add the bascule to the SP2 entry (host switched, R73, serve.py
      auto-rebuild). Version `0.97.3` in `personalscraper/__init__.py`.

- [ ] **Step 4: `make check`** — expected exit 0.

- [ ] **Step 5: Commit docs + bump**

```bash
git add frontend/maquette/README.md IMPLEMENTATION.md personalscraper/__init__.py
git commit -m "docs(shell-mobile): la bascule entre dans la méthode, v0.97.3"
```

- [ ] **Step 6: Push (verify SHA), PR, CI, merge** — PR title
      `refactor(shell-mobile): la bascule — l'hôte sert le build, reconstruit à la volée`; body:
      the arbitration chain (source→build only now that R72 holds), the three R73 holds with
      their mutations, what stayed (harness ritual, R72, session gate), suite green, next = SP3.
      CI 10 checks; squash merge (standing instruction), `git checkout main && git pull --ff-only`,
      `pm2 restart torrentmate-design` on merged main, then re-run the live gate check
      (Step 2's curl) once more and re-sync `wrapped.html`.
