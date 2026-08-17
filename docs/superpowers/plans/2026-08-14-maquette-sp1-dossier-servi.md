# Maquette SP1 — Served Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Re-pointed 2026-08-17 (clean-code / i18n wave).** The harness moved to
> English: its scripts were renamed, its hold labels translated, and its printed
> verdict is now `  PASS` / `  FAIL` and `N rules EXECUTED — no violation`. Every
> quoted expectation and every file name below was re-pointed at what the current
> sources actually say — a quotation that silently misses its target is how a
> recipe stops working without anyone noticing. Two things were deliberately NOT
> rewritten: the fenced source LISTINGS, which are the code as authored on the
> day, and the hold COUNTS, which are what was expected then. The counts quoted here still match.

**Goal:** Move the prototype into a dedicated served directory (`frontend/maquette/design/`) and turn its 930 embedded base64 images into real files under `design/assets/`, without changing a line of prototype logic or harness rule logic.

**Architecture:** `design/` becomes the served root (everything a browser reaches, nothing else); the four image tables keep their keys and lookup semantics but their values become relative `assets/...` URLs; `serve.py` gains one session-gated `/assets/` route; the harness reaches assets through a symlink next to `wrapped.html`.

**Tech Stack:** Python 3.11 (Playwright harness, `serve.py`), no framework, no build. The conversion script is one-shot and never committed.

**Spec:** `docs/superpowers/specs/2026-08-14-maquette-sp1-served-directory-design.md`

## Global Constraints

- Branch `refactor/maquette-sp1`, already created from `main` (`c49e7ada`). The spec is committed on it (`1982e828`).
- Conventional Commits, scope `(shell-mobile)`, messages in French, no AI attribution.
- Comments in prototype/harness sources: English, no session or date references.
- Correction to carry: the spec says "931 images" in two places; the measured total is **930** (402 POSTERS + 319 HEROS + 38 AFFICHES_HD + 170 ACTEURS + 1 `COMPTE.avatar`). 925 distinct contents. Fix the spec in Task 6.
- Harness Python is **`/Users/izno/.pyenv/versions/3.11.9/bin/python3`** and Playwright needs `channel="chrome"`.
- Static server for the harness already runs: `python3 -m http.server 8899` with cwd `/private/tmp/tm-refonte`. Never touch ports 8710/8711 (prod/staging) or start a second measuring process while a suite runs.
- The design host (pm2 `torrentmate-design`, port 8712) serves **this working tree live**. `pm2 restart torrentmate-design` after `serve.py` changes.
- `rg` always with `-g`/`--type` filters (14 GB fixture dir). `curl` always with `--connect-timeout 10 --max-time 30`.
- After every `git push`: verify the remote SHA (`git ls-remote origin refactor/maquette-sp1`) — the pre-push hook can kill the transport with SIGPIPE while printing success.
- The verification suite is the harness itself: rules are "tests" here, and the new rule is mutation-verified (break on purpose, watch it fall naming the right defect, restore).

---

### Task 1: The move — `design/` exists and every reader points at it

**Files:**

- Create: `frontend/maquette/design/` (via `git mv`)
- Modify: `frontend/maquette/serve.py:50`
- Modify: `frontend/maquette/harness/panel.py:71`, `harness/export.py:33,53`, `harness/startup.py:48,78`, `harness/palette.py:30`, `harness/rename.mjs:25`
- Modify: `scripts/extract-maquette-css.py:41`
- Modify: `frontend/maquette/regions.json:4`

**Interfaces:**

- Consumes: nothing (first task).
- Produces: the path `frontend/maquette/design/refonte.html` — every later task reads the prototype there. `serve.py`'s `DOSSIER_ASSETS` now resolves to `design/assets/`.

- [ ] **Step 1: Move the files**

```bash
cd /Users/izno/dev/PersonalScraper
mkdir frontend/maquette/design
git mv frontend/maquette/refonte.html frontend/maquette/design/refonte.html
git mv frontend/maquette/assets frontend/maquette/design/assets
```

- [ ] **Step 2: Update the path constants** (exact edits, one line each)

`frontend/maquette/serve.py:50`:

```python
# old
PROTOTYPE = Path(__file__).resolve().parent / "refonte.html"
# new
PROTOTYPE = Path(__file__).resolve().parent / "design" / "refonte.html"
```

(`DOSSIER_ASSETS = PROTOTYPE.parent / "assets"` at line 66 follows automatically — do not touch it.)

`harness/panel.py:71`, `harness/export.py:33`, `harness/export.py:53`, `harness/startup.py:48`, `harness/startup.py:78` — same one-token change at each site:

```python
# old
(RACINE / "refonte.html").read_text()
# new
(RACINE / "design" / "refonte.html").read_text()
```

`harness/palette.py:30`:

```python
# old
PROTOTYPE = pathlib.Path(__file__).resolve().parent.parent / "refonte.html"
# new
PROTOTYPE = pathlib.Path(__file__).resolve().parent.parent / "design" / "refonte.html"
```

`harness/rename.mjs:25`:

```js
// old
const CHEMIN = `${RACINE}/maquette/refonte.html`;
// new
const CHEMIN = `${RACINE}/maquette/design/refonte.html`;
```

`scripts/extract-maquette-css.py:41`:

```python
# old
PROTOTYPE = RACINE / "frontend" / "maquette" / "refonte.html"
# new
PROTOTYPE = RACINE / "frontend" / "maquette" / "design" / "refonte.html"
```

`frontend/maquette/regions.json:4`:

```json
"source": "frontend/maquette/design/refonte.html",
```

- [ ] **Step 3: Verify no reader is left behind**

```bash
rg -n "maquette/refonte|RACINE / \"refonte" -g '*.py' -g '*.mjs' -g '*.json' -g '*.cjs' frontend/ scripts/
```

Expected: zero matches (doc files are Task 6's job; this glob set does not include `*.md`).

- [ ] **Step 4: Re-sync the wrapper and prove the harness still measures**

```bash
/Users/izno/.pyenv/versions/3.11.9/bin/python3 - <<'EOF'
from pathlib import Path
src = Path("frontend/maquette/design/refonte.html").read_text()
head = ('<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,'
        'maximum-scale=1,user-scalable=no"></head><body>\n')
Path("/tmp/tm-refonte/wrapped.html").write_text(head + src)
EOF
cd frontend/maquette/harness
for s in export.py panel.py startup.py cards.py; do
  /Users/izno/.pyenv/versions/3.11.9/bin/python3 "$s" > /dev/null && echo "OK $s" || echo "FAILED: $s"
done
```

Expected: four `OK`. These four cover both source-readers and a DOM-measuring rule.

- [ ] **Step 5: `make check` still green (CSS extraction guard follows the move)**

```bash
cd /Users/izno/dev/PersonalScraper && make check 2>&1 | tail -5
```

Expected: exit 0. If the extraction fails, the `PROTOTYPE` constant in `scripts/extract-maquette-css.py` was missed.

- [ ] **Step 6: Restart the design host and check it serves**

```bash
pm2 restart torrentmate-design
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8712/
```

Expected: `401` (the login gate — proof the server found the moved prototype; a lost file answers 503).

- [ ] **Step 7: Commit**

```bash
git add -A frontend/maquette scripts/extract-maquette-css.py
git commit -m "refactor(shell-mobile): le prototype emménage dans design/, la racine servie dédiée"
```

---

### Task 2: Image extraction — 930 data URIs become files, values become URLs

**Files:**

- Create: `frontend/maquette/design/assets/{posters,heros,affiches,acteurs}/<hash8>.webp` (~925 files) + `design/assets/avatar.webp`
- Modify: `frontend/maquette/design/refonte.html` (930 value strings only)
- Create (scratchpad only, never committed): `extract_images.py`

**Interfaces:**

- Consumes: `design/refonte.html` from Task 1.
- Produces: image values shaped `"assets/<dir>/<hash8>.webp"` (or `"assets/avatar.webp"`); Task 3's route and Task 5's rule rely on exactly that shape.

- [ ] **Step 1: Write the one-shot script** in the session scratchpad (NOT in the repo):

```python
"""One-shot: extract every base64 image from the prototype into design/assets/.

Forward pass: decode, hash, write, replace the value with a relative URL.
Reverse proof: re-substitute each written file's re-encoded content back into
the new text and require byte-identity with the original document.
"""
import base64, hashlib, pathlib, re, sys

DESIGN = pathlib.Path("frontend/maquette/design")
SRC = DESIGN / "refonte.html"
src = SRC.read_text(encoding="utf-8")

def span(name):
    m = re.search(r'^\s*const %s = \{' % name, src, re.M)
    i = src.index("{", m.start()); depth = 0
    for j in range(i, len(src)):
        if src[j] == "{": depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0: return (m.start(), j)
    raise SystemExit(f"unbalanced braces in {name}")

TABLES = {"POSTERS": "posters", "HEROS": "heros",
          "AFFICHES_HD": "affiches", "ACTEURS": "acteurs"}
spans = {TABLES[n]: span(n) for n in TABLES}

pieces, replacements, last = [], [], 0
for m in re.finditer(r'"data:image/webp;base64,([A-Za-z0-9+/=]+)"', src):
    b64 = m.group(1)
    raw = base64.b64decode(b64)
    dossier = next((d for d, (a, b) in spans.items() if a <= m.start() <= b), None)
    if dossier is None:
        rel = "assets/avatar.webp"          # the single stray: COMPTE.avatar
    else:
        rel = f"assets/{dossier}/{hashlib.sha1(raw).hexdigest()[:8]}.webp"
    dest = DESIGN / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        assert dest.read_bytes() == raw, f"hash collision at {rel}"
    else:
        dest.write_bytes(raw)
    assert dest.read_bytes() == raw, f"write/readback mismatch at {rel}"
    pieces.append(src[last:m.start()]); pieces.append(f'"{rel}"')
    replacements.append((rel, b64)); last = m.end()
pieces.append(src[last:])
nouveau = "".join(pieces)

# Counts, then the reverse proof.
strays = sum(1 for rel, _ in replacements if rel == "assets/avatar.webp")
assert len(replacements) == 930, f"expected 930 URIs, got {len(replacements)}"
assert strays == 1, f"expected exactly one stray (avatar), got {strays}"
assert "data:image" not in nouveau, "a data URI survived"

reconstruit, pos = [], 0
for rel, b64 in replacements:
    i = nouveau.index(f'"{rel}"', pos)
    reconstruit.append(nouveau[pos:i])
    reconstruit.append('"data:image/webp;base64,' + base64.b64encode(
        (DESIGN / rel).read_bytes()).decode() + '"')
    pos = i + len(rel) + 2
reconstruit.append(nouveau[pos:])
assert "".join(reconstruit) == src, "reverse proof failed: reconstruction differs"

SRC.write_text(nouveau, encoding="utf-8")
fichiers = sum(1 for _ in DESIGN.glob("assets/*/*.webp")) + 1  # + avatar
print(f"930 references rewritten over {fichiers} files; byte-identity proved")
```

- [ ] **Step 2: Run it and read the proof line**

```bash
cd /Users/izno/dev/PersonalScraper
command python3 <scratchpad>/extract_images.py
```

Expected: `930 references rewritten over 926 files; byte-identity proved` (925 distinct table images + avatar; if the file count differs slightly because duplicates straddle two tables, the assertions above are the authority — they must all pass).

- [ ] **Step 3: Measure the result**

```bash
ls -la frontend/maquette/design/refonte.html
du -sh frontend/maquette/design/assets/
rg -c "data:image" -g '*.html' frontend/maquette/design/refonte.html || echo "0 data URIs"
```

Expected: `refonte.html` ≈ 1.9 MB; assets ≈ 9.9 MB; `0 data URIs`.

- [ ] **Step 4: Give the harness its assets and prove the symlink is followed**

```bash
ln -sfn /Users/izno/dev/PersonalScraper/frontend/maquette/design/assets /tmp/tm-refonte/assets
UN=$(ls frontend/maquette/design/assets/posters | head -1)
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" \
  "http://127.0.0.1:8899/assets/posters/$UN"
```

Expected: `200`. (`http.server` follows symlinks — this is the measurement, not the assumption.)

- [ ] **Step 5: Re-sync `wrapped.html` (Task 1 Step 4 recipe) and run image-heavy rules**

```bash
cd frontend/maquette/harness
for s in cards.py content.py gallery.py deck.py; do
  /Users/izno/.pyenv/versions/3.11.9/bin/python3 "$s" > /dev/null && echo "OK $s" || echo "FAILED: $s"
done
```

Expected: four `OK`. A 404'd asset shows up as a console error and `Journal.summary(errors)` fails on those — so green here proves the URLs resolve.

- [ ] **Step 6: Commit** (the extraction script stays in the scratchpad; the message records the method)

```bash
git add -A frontend/maquette/design
git commit -m "refactor(shell-mobile): les 930 images sortent en fichiers réels sous design/assets/

Un script one-shot (non versionné) a décodé chaque data:URI, écrit
assets/<table>/<sha1-8>.webp, remplacé la valeur par l'URL relative, puis
reconstruit le document original depuis les fichiers écrits — identité
byte-à-byte prouvée. 925 contenus distincts + l'avatar du compte."
```

---

### Task 3: `serve.py` serves `/assets/` behind the session

**Files:**

- Modify: `frontend/maquette/serve.py` (`_send` at :380-405, `do_GET` at :407-450)

**Interfaces:**

- Consumes: `design/assets/` layout from Task 2.
- Produces: `GET /assets/<sub>` → 200 (session) / 401 (none); brand assets by exact name stay session-free. `entry.py`/`pwa.py` (live host) and the Task 4 suite depend on this behaviour.

- [ ] **Step 1: Let a route override the default `Cache-Control`** — in `_send`, replace the unconditional header:

```python
# old (serve.py:398-400)
        # The design is read to be judged, and a judgement passed on a stale
        # copy is worse than no judgement. Revalidate every time.
        self.send_header("Cache-Control", "no-store")
# new
        # The design is read to be judged, and a judgement passed on a stale
        # copy is worse than no judgement. Revalidate every time — except where
        # a route says otherwise: hash-named assets change URL when they change
        # content, so they alone may claim immutability.
        if not any(n.lower() == "cache-control" for n, _ in entetes or []):
            self.send_header("Cache-Control", "no-store")
```

- [ ] **Step 2: Add the route** in `do_GET`, immediately after the `if chemin in ASSETS:` block (after serve.py:427):

```python
        if chemin.startswith("/assets/"):
            # The library's real artwork: session-gated, unlike the brand set.
            if not self._authentifie():
                self._send(401, b"")
                return
            fichier = (DOSSIER_ASSETS / chemin[len("/assets/"):]).resolve()
            types = {".webp": "image/webp", ".png": "image/png",
                     ".svg": "image/svg+xml"}
            type_mime = types.get(fichier.suffix)
            if (type_mime is None or not fichier.is_file()
                    or not fichier.is_relative_to(DOSSIER_ASSETS.resolve())):
                self._send(404, b"")
                return
            self._send(200, fichier.read_bytes(),
                       [("Cache-Control", "public, max-age=31536000, immutable")],
                       type_mime=type_mime)
            return
```

- [ ] **Step 3: Measure the gate on a scratch port** (never 8710/8711/8899/8712) with a known password:

```bash
HASH=$(command python3 -c "import hashlib,os,base64; s=os.urandom(16); \
print(base64.b64encode(s).decode()+':'+base64.b64encode( \
hashlib.scrypt(b'epreuve', salt=s, n=16384, r=8, p=1, dklen=32)).decode())")
cd frontend/maquette
TM_DESIGN_PASSWORD_HASH="$HASH" /Users/izno/.pyenv/versions/3.11.9/bin/python3 serve.py 8913 &
SERVEUR=$!
sleep 1
UN=$(ls design/assets/posters | head -1)
echo "-- no session:"
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8913/assets/posters/$UN"
echo "-- brand asset, no session:"
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8913/pwa-192.png"
echo "-- sign in, then asset:"
COOKIE=$(curl --connect-timeout 10 --max-time 30 -s -D - -o /dev/null \
  -d "identifiant=izno&motdepasse=epreuve" "http://127.0.0.1:8913/connexion" \
  | grep -i '^set-cookie:' | cut -d' ' -f2 | cut -d';' -f1)
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" -H "Cookie: $COOKIE" "http://127.0.0.1:8913/assets/posters/$UN"
echo "-- traversal refused:"
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" -H "Cookie: $COOKIE" "http://127.0.0.1:8913/assets/../serve.py"
kill $SERVEUR
```

Expected, in order: `401`, `200`, `200`, then `404` **or** `303` for the traversal (the URL normalizes `..` client-side; both refusals are refusals — what must never appear is `200`).

- [ ] **Step 4: Restart the live host and check the served page carries images**

```bash
pm2 restart torrentmate-design
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8712/
```

Expected: `401` (gate up). The full live proof (`pwa.py`, `entry.py`) runs with the suite in Task 4.

- [ ] **Step 5: Commit**

```bash
git add frontend/maquette/serve.py
git commit -m "feat(shell-mobile): serve.py sert design/assets/ derrière la session, cache immutable"
```

---

### Task 4: The full suite — 41 scripts green against the new layout

**Files:**

- Modify (only if a rule flakes on async decode): the affected `harness/*.py`, per the spec's response plan — explicit `width`/`height` or `await img.decode()` inside the rule, never a sleep.

**Interfaces:**

- Consumes: everything from Tasks 1–3, wrapped.html re-synced, `/tmp/tm-refonte/assets` symlink, live host restarted.
- Produces: the green baseline Task 5's new rule joins.

- [ ] **Step 1: Re-sync `wrapped.html`** (Task 1 Step 4 recipe — the extraction changed the source).

- [ ] **Step 2: Run the whole suite sequentially in the background** (one process — two concurrent halves would fight over `wrapped.html`):

```bash
cd frontend/maquette/harness
( for s in *.py; do
    [ "$s" = common.py ] && continue
    /Users/izno/.pyenv/versions/3.11.9/bin/python3 "$s" > /dev/null 2>&1 \
      || echo "FAILED: $s"
  done; echo "SUITE TERMINEE" ) > /tmp/tm-refonte/suite-sp1.log 2>&1 &
```

Poll `/tmp/tm-refonte/suite-sp1.log` until `SUITE TERMINEE` (>20 min). Expected: zero `FAILED:` lines.

- [ ] **Step 3: If a rule fails** — read its output by re-running it alone, in the foreground. Classify:
  - **404 console error** → a URL shape the extraction missed; fix the data, not the rule.
  - **geometry off with images pending** → the known async-decode risk; fix inside the affected rule (`await pg.evaluate("() => Promise.all([...document.images].map(i => i.decode().catch(() => null)))")` after `open_page()`, or explicit dimensions in the prototype if the box should never have been image-sized). One commit per fixed rule, message naming the mechanism.
  - Anything else → stop and report; it is not on this task's causal path.

- [ ] **Step 4: Commit** (only if Step 3 touched files)

```bash
git add frontend/maquette/harness
git commit -m "fix(shell-mobile): <règle> attend le décodage des images désormais asynchrones"
```

---

### Task 5: The new rule — the prototype embeds no image, and every reference resolves

**Files:**

- Create: `frontend/maquette/harness/images.py`
- Modify: `frontend/maquette/regions.json` (register the rule in `$adversarialReview`)

**Interfaces:**

- Consumes: `Journal` and `ROOT` from `harness/common.py`; the `"assets/<dir>/<hash8>.webp"` value shape from Task 2.
- Produces: the 42nd script; the suite loop picks it up by globbing `*.py`.

- [ ] **Step 1: Find the next free rule number**

```bash
rg -o '"R[0-9]+' -g '*.json' frontend/maquette/regions.json | sort -Vu | tail -3
```

Use the highest + 1 below (written as R70 here; adjust if the measurement says otherwise).

- [ ] **Step 2: Write the rule** — `frontend/maquette/harness/images.py`:

```python
"""R70 — no image is embedded in the prototype source.

Every image lives in `design/assets/` as a real file the server can cache and
git can store once. A data URI that slips back in silently regrows the
single-file weight this rule exists to keep off; a reference to a file that
does not exist renders as a broken image only at runtime. Both are source
properties, so this rule reads the SOURCE — the DOM only shows what loaded.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import Journal, RACINE


def main():
    journal = Journal("R70 — aucune image embarquée")
    source = (RACINE / "design" / "refonte.html").read_text()

    incrustees = re.findall(r"data:image/", source)
    journal.verifier("aucun data:image dans la source", not incrustees,
                     f"{len(incrustees)} incrustée(s)")

    references = sorted(set(re.findall(r'"assets/([\w./-]+\.webp)"', source)))
    absentes = [r for r in references
                if not (RACINE / "design" / "assets" / r).is_file()]
    journal.verifier("chaque référence assets/ existe sur disque", not absentes,
                     f"{len(references)} références"
                     + (f" · absentes : {absentes[:3]}" if absentes else ""))
    journal.bilan()


main()
```

- [ ] **Step 3: Run it green**

```bash
cd frontend/maquette/harness
/Users/izno/.pyenv/versions/3.11.9/bin/python3 images.py
```

Expected: `2 rules EXECUTED — no violation`, exit 0.

- [ ] **Step 4: Mutation one — reinsert a data URI, the FIRST check must fall naming it**

```bash
command python3 - <<'EOF'
from pathlib import Path
p = Path("frontend/maquette/design/refonte.html")
p.write_text(p.read_text().replace("</title>", "</title><!-- data:image/webp;base64,AAAA -->", 1))
EOF
/Users/izno/.pyenv/versions/3.11.9/bin/python3 images.py; echo "exit=$?"
git checkout -- ../design/refonte.html
```

Expected: `FAIL no data:image in the source` and `exit=1`. The second check stays PASS — the mutation names exactly its own defect.

- [ ] **Step 5: Mutation two — hide one asset file, the SECOND check must fall naming it**

```bash
UN=$(ls ../design/assets/posters | head -1)
mv "../design/assets/posters/$UN" /tmp/tm-refonte/_hidden.webp
/Users/izno/.pyenv/versions/3.11.9/bin/python3 images.py; echo "exit=$?"
mv /tmp/tm-refonte/_hidden.webp "../design/assets/posters/$UN"
/Users/izno/.pyenv/versions/3.11.9/bin/python3 images.py > /dev/null && echo "restored green"
```

Expected: `FAIL every assets/ reference exists on disk` with the missing name printed, `exit=1`, then `restored green`.

- [ ] **Step 6: Register the rule in `regions.json`** — read one existing `$adversarialReview` entry first and append a new entry of the **same shape** for R70, stating: what it holds (no embedded image, no dangling reference), how it was mutation-verified (both mutations, each felling its own check).

- [ ] **Step 7: Commit**

```bash
git add frontend/maquette/harness/images.py frontend/maquette/regions.json
git commit -m "test(shell-mobile): R70 — aucune image embarquée, chaque référence assets/ résolue

Vérifiée par mutation dans les deux sens : une data:URI réinsérée fait
tomber le premier contrôle, un fichier retiré fait tomber le second,
chacun en nommant son propre défaut."
```

---

### Task 6: Docs, spec correction, version bump

**Files:**

- Modify: `frontend/maquette/README.md` (sync recipe + symlink step + script table row + layout description)
- Modify: `CLAUDE.md` (§Design Reference path)
- Modify: `docs/reference/product-intent.md:296` (§15 path citation)
- Modify: `IMPLEMENTATION.md` (sync recipe at :73-84; current-state section gains SP1)
- Modify: `docs/superpowers/specs/2026-08-14-maquette-sp1-served-directory-design.md` (931 → 930, twice)
- Modify: `pyproject.toml` (patch bump)

**Interfaces:**

- Consumes: final layout and recipe from Tasks 1–5.
- Produces: nothing downstream; this is the record.

- [ ] **Step 1: README** — update every `refonte.html` path to `design/refonte.html`; in the run recipe add the symlink line right after the wrapped.html sync:

```bash
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets
```

Add the `images.py` row to the script table (same voice as the others): "R70: the source embeds no image and every `assets/` reference resolves to a file". Describe the `design/` root where the layout is described.

- [ ] **Step 2: CLAUDE.md + product-intent.md** — replace `frontend/maquette/refonte.html` with `frontend/maquette/design/refonte.html` at the two citation sites (`CLAUDE.md:46`, `product-intent.md:296`). No other wording changes.

- [ ] **Step 3: IMPLEMENTATION.md** — update the sync recipe path (line ~76) and add the symlink line; add an SP1 entry to the current-state section (branch, what moved, the new rule, the 5-sub-project decomposition with SP2 next).

- [ ] **Step 4: Spec correction** — in the SP1 spec, change both "931" occurrences to "930" and "~925" file count to "925 distinct + avatar".

- [ ] **Step 5: Version bump (patch)**

```bash
rg -n '^version' -g '*.toml' pyproject.toml
```

Bump Z+1 (e.g. `0.97.0` → `0.97.1`) in `pyproject.toml`.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md IMPLEMENTATION.md pyproject.toml frontend/maquette/README.md
git add -f docs/reference/product-intent.md docs/superpowers/specs/2026-08-14-maquette-sp1-served-directory-design.md
git commit -m "docs(shell-mobile): le dossier servi design/ entre dans la méthode, v0.97.1"
```

(`git add -f` on `docs/` is the project's documented convention for tracked docs — root CLAUDE.md §Gotchas.)

---

### Task 7: Delivery — push, PR, CI

**Interfaces:**

- Consumes: all commits from Tasks 1–6, suite green, `make check` green.

- [ ] **Step 1: Final gates, all three, freshly run**

```bash
make check 2>&1 | tail -3
cd frontend/maquette/harness && /Users/izno/.pyenv/versions/3.11.9/bin/python3 images.py > /dev/null && echo "R70 green"
```

Expected: `make check` exit 0; `R70 green`. The 41-script suite was Task 4's gate; re-run it only if anything touched the prototype since.

- [ ] **Step 1b: The CSS drift guard still bites in BOTH directions**

```bash
cd /Users/izno/dev/PersonalScraper
echo "/* drift */" >> frontend/src/styles/ps/app-surface.css
python3 scripts/extract-maquette-css.py --check; echo "exit=$?"
git checkout -- frontend/src/styles/ps/app-surface.css
python3 scripts/extract-maquette-css.py --check && echo "guard green again"
```

Expected: `exit=1` on the mutated sheet (the guard names the drift), then `guard green again`.

- [ ] **Step 2: Push and verify the remote actually moved**

```bash
git push -u origin refactor/maquette-sp1
git ls-remote origin refactor/maquette-sp1
git rev-parse HEAD
```

Expected: the two SHAs identical. On SIGPIPE (exit 141) with checks already validated: `git push --no-verify`, then re-verify.

- [ ] **Step 3: Open the PR** — title `refactor(shell-mobile): SP1 — le dossier servi design/ et les images en fichiers réels`; body in French: the operator arbitrations (A/A, session-gated, committed assets), the measured before/after (15.0 MB → 1.9 MB + 9.9 MB of files), the proof lines (byte-identity, both mutations, suite green), and the SP2–SP5 table. Use the `github-curl` skill if `gh` fails in the sandbox.

- [ ] **Step 4: Watch CI** — 10 checks. A job failing in 3–4 s without logs is the billing-blocked GHA pattern, not a test failure; a "runner shutdown signal" is usually external. Re-trigger with an empty commit only if the trigger itself was missed (0 check-suites).

- [ ] **Step 5: Report to the operator** — merge is their call, as is `pm2 restart torrentmate-design` timing on the merged tree.
