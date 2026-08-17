# Maquette SP2 — Vite Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Re-pointed 2026-08-17 (clean-code / i18n wave).** The harness moved to
> English: its scripts were renamed, its hold labels translated, and its printed
> verdict is now `  PASS` / `  FAIL` and `N rules EXECUTED — no violation`. Every
> quoted expectation and every file name below was re-pointed at what the current
> sources actually say — a quotation that silently misses its target is how a
> recipe stops working without anyone noticing. Two things were deliberately NOT
> rewritten: the fenced source LISTINGS, which are the code as authored on the
> day, and the hold COUNTS, which are what was expected then. R72 has since been rescoped (see the SP3 router plan): `shell.py` runs 4 holds today, not 18, and the DOM-comparison mutation at Task 4 can no longer fell anything — the label it names no longer exists.

**Goal:** Wrap the untouched prototype in a Vite project (`frontend/maquette/design/`) whose build output is proved DOM-identical to the source by a new harness rule (R72).

**Architecture:** `design/` becomes the Vite root; a tiny local plugin injects `refonte.html` verbatim into `index.html` after Vite's own HTML processing (`transformIndexHtml`, `order: "post"`) and symlinks `dist/assets` to the real assets at `closeBundle`. R72 builds, serves `dist/` on a scratch port, drives source and build to the same named states, and compares rendered DOM serialization + harness-region geometry.

**Tech Stack:** Vite ^8.1.3 (sole devDependency), node v22.13.1 / npm 11 (present at `/Users/izno/.nvm/versions/node/v22.13.1/bin`). Harness rule in Python (Playwright works under the project's Python 3.12.4, `channel="chrome"` required).

**Spec:** `docs/superpowers/specs/2026-08-14-maquette-sp2-coquille-vite-design.md`

## Global Constraints

- Branch `refactor/maquette-sp2` (from `main` `aa88fc73`); spec committed (`962739d0`).
- **`refonte.html` does not change by one byte.** `serve.py`, the live host, the 42 existing rules, the CSS extraction contract: untouched.
- Conventional Commits, scope `(shell-mobile)`, French messages, no AI attribution.
- Comments in shell sources and harness: English, no session/date references.
- Never `rg` without `-g`/`--type` filters; `curl` always with `--connect-timeout 10 --max-time 30`; `command python3` for plain python.
- Scratch ports only — never 8710/8711/8899/8712. R72 uses **8917** and must kill its server on every exit path.
- One measuring process at a time; re-sync `/tmp/tm-refonte/wrapped.html` before harness runs:
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
- After every push: verify the remote SHA (`git ls-remote origin refactor/maquette-sp2`).
- Version bump (patch → `0.97.2`) lives in `personalscraper/__init__.py` (pyproject is dynamic-version).

---

### Task 1: The Vite project — dev serves, build emits, nothing transformed

**Files:**

- Create: `frontend/maquette/design/package.json`
- Create: `frontend/maquette/design/index.html`
- Create: `frontend/maquette/design/vite.config.mjs`
- Create: `frontend/maquette/design/package-lock.json` (by `npm install`)

**Interfaces:**

- Consumes: `frontend/maquette/design/refonte.html` (read at build/serve time, never modified).
- Produces: `npm run build` in `design/` emits `dist/index.html` (envelope + verbatim fragment) and `dist/assets` (symlink to `../assets`). Task 2's rule runs exactly that command and serves that output.

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "torrentmate-maquette",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "vite": "^8.1.3"
  }
}
```

- [ ] **Step 2: Write `index.html`** (the real envelope; the placeholder is where the prototype lands)

```html
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <meta
      name="viewport"
      content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"
    />
    <title>TorrentMate Design</title>
  </head>
  <body>
    <!-- maquette -->
  </body>
</html>
```

- [ ] **Step 3: Write `vite.config.mjs`**

```js
// The shell's whole job is to change NOTHING: the prototype is injected
// verbatim, after Vite's own HTML processing, so no minifier and no script
// extraction ever touches it. The real conversion happens module by module
// in later sub-projects; this file is the chassis they will move into.
import { readFileSync, rmSync, symlinkSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

const RACINE = resolve(import.meta.dirname);

function injecteMaquette() {
  return {
    name: "injecte-maquette",
    transformIndexHtml: {
      // "post" runs after Vite's internal transforms: the fragment below is
      // emitted untransformed — byte-for-byte the source file.
      order: "post",
      handler(html) {
        const fragment = readFileSync(resolve(RACINE, "refonte.html"), "utf8");
        return html.replace("<!-- maquette -->", () => fragment);
      },
    },
    closeBundle() {
      // The fragment's image URLs are relative `assets/...`; the build links
      // the real files in rather than copying 10 MB per build. `dist/` is
      // gitignored, so the symlink never reaches the repository.
      rmSync(resolve(RACINE, "dist/assets"), { force: true, recursive: true });
      symlinkSync("../assets", resolve(RACINE, "dist/assets"));
    },
  };
}

export default defineConfig({
  root: RACINE,
  // The prototype references `assets/...` itself; nothing else is public.
  publicDir: false,
  build: { outDir: "dist", emptyOutDir: true },
  plugins: [injecteMaquette()],
});
```

Note the second argument of `html.replace(marker, () => fragment)`: a function, so the
1.9 MB fragment's `$`-sequences are never interpreted as replacement patterns.

- [ ] **Step 4: Install and build**

```bash
cd /Users/izno/dev/PersonalScraper/frontend/maquette/design
npm install
npm run build
```

Expected: build succeeds; `dist/index.html` exists; `dist/assets` is a symlink.

- [ ] **Step 5: Prove the fragment is emitted verbatim**

```bash
command python3 - <<'PY'
from pathlib import Path
frag = Path("refonte.html").read_text(encoding="utf-8")
out = Path("dist/index.html").read_text(encoding="utf-8")
assert frag in out, "the emitted html does not contain the source fragment verbatim"
print("fragment verbatim dans dist/index.html —", len(frag), "chars")
PY
```

Expected: the verbatim line. If this fails, Vite transformed the fragment — stop and report (the `order: "post"` contract is broken).

- [ ] **Step 6: Prove git hygiene**

```bash
cd /Users/izno/dev/PersonalScraper
git check-ignore frontend/maquette/design/node_modules/vite frontend/maquette/design/dist/index.html && echo "ignorés"
git status --short -- frontend/maquette/design | head
```

Expected: `ignorés`; status shows ONLY the four new files (package.json, package-lock.json, index.html, vite.config.mjs).

- [ ] **Step 7: Quick serve sanity** (scratch port, killed after)

```bash
cd frontend/maquette/design/dist && command python3 -m http.server 8917 --bind 127.0.0.1 &
SRV=$!
sleep 1
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8917/index.html
UN=$(ls ../assets/posters | head -1)
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8917/assets/posters/$UN"
kill $SRV
```

Expected: `200` twice (the second proves the symlink serves).

- [ ] **Step 8: Commit**

```bash
cd /Users/izno/dev/PersonalScraper
git add frontend/maquette/design/package.json frontend/maquette/design/package-lock.json \
        frontend/maquette/design/index.html frontend/maquette/design/vite.config.mjs
git commit -m "feat(shell-mobile): la coquille Vite — le prototype injecté verbatim, rien de transformé

design/ devient un projet Vite : index.html porte l'enveloppe réelle, un
plugin local injecte refonte.html tel quel APRÈS les transformations de
Vite (order post), et le build lie dist/assets aux vrais fichiers. Aucun
octet du prototype ne change ; la conversion réelle viendra module par
module (SP3/SP4)."
```

---

### Task 2: R72 — `harness/shell.py`, the DOM-identity proof

**Files:**

- Create: `frontend/maquette/harness/shell.py`
- Modify: `frontend/maquette/regions.json` (add the `R72` entry in `$adversarialReview`)
- Modify: `frontend/maquette/README.md` (script-table row after `screens.py`)

**Interfaces:**

- Consumes: Task 1's `npm run build` contract (`dist/index.html` + `dist/assets` symlink); `common.Journal`, `common.ROOT`, `common.PHONE`; the source page on `http://127.0.0.1:8899/wrapped.html`; named states via `window.__go`.
- Produces: the 43rd rule, picked up by the suite's `*.py` glob.

- [ ] **Step 1: Write the rule** — `frontend/maquette/harness/shell.py`:

```python
"""R72 — the Vite shell changes nothing the prototype renders.

`design/` carries a Vite project whose one job is to emit the prototype
verbatim inside a real envelope. A shell that transformed anything — a
minified inline script, a re-written attribute, an asset URL that stopped
resolving — would make every later conversion step start from a lie. So the
rule builds the shell, serves the output, drives the SOURCE and the BUILD to
the same named states in the same browser, and requires the rendered DOM and
the geometry of the exported regions to be identical. Rendered truth, never
screenshots: two captures of one file diverge, measured twice on this
project.
"""
import asyncio
import json
import pathlib
import subprocess
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import Journal, RACINE, TELEPHONE

DESIGN = RACINE / "design"
PORT = 8917
SOURCE = "http://127.0.0.1:8899/wrapped.html"
BATI = f"http://127.0.0.1:{PORT}/index.html"
ETATS = ["acq-ajout-resultats", "lib-grille", "fiche-film", "systeme"]

# The serialization compares what layout READS: tag, id, classes and the
# hidden attribute, in document order, for the three surfaces a state draws.
SERIALISER = """(sel) => {
  const racine = document.querySelector(sel);
  if (!racine) return null;
  const sortie = [];
  const marche = (n) => {
    if (n.nodeType !== 1) return;
    sortie.push(n.tagName + (n.id ? "#" + n.id : "")
      + (n.className && typeof n.className === "string"
         ? "." + n.className.trim().split(/\\s+/).sort().join(".") : "")
      + (n.hidden ? "[hidden]" : ""));
    for (const e of n.children) marche(e);
  };
  marche(racine);
  return sortie.join("\\n");
}"""

RECTS = """(sels) => {
  const sortie = {};
  for (const sel of sels) {
    const e = document.querySelector(sel);
    if (!e) continue;
    const r = e.getBoundingClientRect();
    sortie[sel] = [r.x, r.y, r.width, r.height].map((v) => Math.round(v));
  }
  return sortie;
}"""


def construire(journal):
    """Runs the build, installing first only when node_modules is absent."""
    if not (DESIGN / "node_modules").exists():
        print("  npm ci (première fois — long)")
        subprocess.run(["npm", "ci"], cwd=DESIGN, check=True,
                       capture_output=True, text=True)
    fait = subprocess.run(["npm", "run", "build"], cwd=DESIGN,
                          capture_output=True, text=True)
    journal.verifier("le build de la coquille aboutit", fait.returncode == 0,
                     (fait.stderr or fait.stdout).strip().splitlines()[-1]
                     if fait.returncode else "vite build")
    return fait.returncode == 0


async def ouvrir_page(navigateur, url, erreurs):
    ctx = await navigateur.new_context(**TELEPHONE)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: erreurs.append(f"{url}: {e}"))
    pg.on("console", lambda m: erreurs.append(f"{url}: {m.text}")
          if m.type == "error" else None)
    await pg.goto(url, wait_until="load")
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(250)
    return pg


async def main():
    journal = Journal("R72 — la coquille ne change rien au rendu")
    if not construire(journal):
        journal.bilan()

    serveur = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=DESIGN / "dist",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    erreurs = []
    try:
        async with async_playwright() as p:
            navigateur = await p.chromium.launch(channel="chrome")
            src = await ouvrir_page(navigateur, SOURCE, erreurs)
            bat = await ouvrir_page(navigateur, BATI, erreurs)

            connus = await src.evaluate("()=>window.__states()")
            journal.verifier("les états conduits existent",
                             all(e in connus for e in ETATS), " · ".join(ETATS))

            regions = json.loads((RACINE / "regions.json").read_text())
            selecteurs = regions["harnessSelectors"]

            for etat in ETATS:
                for pg in (src, bat):
                    await pg.evaluate("(e)=>window.__go(e)", etat)
                    await pg.wait_for_timeout(450)
                for surface in ("#view", "#screen", "#sheet"):
                    a = await src.evaluate(SERIALISER, surface)
                    b = await bat.evaluate(SERIALISER, surface)
                    detail = ""
                    if a != b and a and b:
                        la, lb = a.split("\n"), b.split("\n")
                        i = next((k for k in range(min(len(la), len(lb)))
                                  if la[k] != lb[k]), min(len(la), len(lb)))
                        detail = f"premier écart au nœud {i}: {la[i:i+1]} ≠ {lb[i:i+1]}"
                    journal.verifier(f"{etat} · {surface} identique", a == b,
                                     detail or f"{(a or '').count(chr(10))+1} nœuds")
                ra = await src.evaluate(RECTS, selecteurs)
                rb = await bat.evaluate(RECTS, selecteurs)
                ecarts = [s for s in ra
                          if s in rb and any(abs(x - y) > 1
                                             for x, y in zip(ra[s], rb[s]))]
                journal.verifier(f"{etat} · géométrie des régions identique",
                                 set(ra) == set(rb) and not ecarts,
                                 f"{len(ra)} régions"
                                 + (f" · écarts: {ecarts[:2]}" if ecarts else ""))
            await navigateur.close()
    finally:
        serveur.terminate()
        serveur.wait(timeout=5)
    journal.bilan(erreurs)


asyncio.run(main())
```

- [ ] **Step 2: Re-sync `wrapped.html`** (Global Constraints recipe), then run the rule green

```bash
cd /Users/izno/dev/PersonalScraper/frontend/maquette/harness
command python3 shell.py
```

Expected: `the shell build succeeds`, the states check, then per state 3 surface checks + 1 geometry check, all PASS — `18 rules EXECUTED — no violation`, exit 0.

- [ ] **Step 3: Mutation one — corrupt one class in the EMITTED html; the DOM comparison must fall**

```bash
command python3 - <<'PY'
from pathlib import Path
p = Path("../design/dist/index.html")
s = p.read_text(encoding="utf-8")
assert 'class="topbar"' in s
p.write_text(s.replace('class="topbar"', 'class="topbarr"', 1), encoding="utf-8")
print("mutation posée: topbar → topbarr dans dist")
PY
command python3 shell.py; echo "exit=$?"
```

Expected: exit 1 — at least one `FAIL … identique` naming the diverging node — CAUTION: the rule REBUILDS at start, which would erase a pre-run mutation. The mutation must therefore be applied differently: run the rule once so `dist/` is fresh, then apply the mutation, then re-run **with the build skipped**. To keep the rule honest AND mutable, `construire()` skips the build when the environment variable `R72_SANS_BUILD=1` is set — add this line at the top of `construire`:

```python
    if os.environ.get("R72_SANS_BUILD") == "1":
        journal.verifier("le build de la coquille aboutit", True,
                         "sauté (R72_SANS_BUILD=1 — mutation en cours)")
        return True
```

(and `import os` at the top). Then the mutation run is:

```bash
R72_SANS_BUILD=1 command python3 shell.py; echo "exit=$?"
```

Expected: exit 1, `FAIL` on DOM identity naming the node. Restore with a plain re-run (no env var — the rebuild restores dist): `command python3 shell.py` → green.

- [ ] **Step 4: Mutation two — break the assets; the console-error guard must fall**

```bash
rm ../design/dist/assets
R72_SANS_BUILD=1 command python3 shell.py; echo "exit=$?"
```

Expected: exit 1 with `JS errors:` listing failed image loads on the 8917 side (the DOM checks may stay green — the markup is intact; it is the error guard that bites). Restore: `command python3 shell.py` (rebuild recreates the symlink) → green.

- [ ] **Step 5: Register R72 in `regions.json`** — read one existing `$adversarialReview` entry for shape, then add key `"R72"`: what it holds (the shell's build renders identically to the source — DOM serialization and region geometry per driven state, zero console errors either side), how it was verified (both mutations, each felling its own guard: a corrupted class fells the DOM comparison naming the node; removed assets fell the error guard).

- [ ] **Step 6: Add the README row** after the `screens.py` row, matching the table's voice:

```
| `shell.py`        | R72: the Vite shell's build renders identically to the source — DOM serialization and region geometry compared per driven state on both pages, zero console errors on either side |
```

- [ ] **Step 7: Commit**

```bash
cd /Users/izno/dev/PersonalScraper
git add frontend/maquette/harness/shell.py frontend/maquette/regions.json frontend/maquette/README.md
git commit -m "test(shell-mobile): R72 — la coquille ne change rien au rendu, prouvé par mutation

Le build est comparé à la source dans le même navigateur, sur les mêmes
états conduits : sérialisation du DOM des trois surfaces et géométrie des
régions exportées, zéro erreur console des deux côtés. Une classe corrompue
dans le dist fait tomber la comparaison DOM en nommant le nœud ; les assets
retirés font tomber la garde d'erreurs, seule."
```

---

### Task 3: Full suite, docs, version bump, delivery

**Files:**

- Modify: `personalscraper/__init__.py:17` (`0.97.1` → `0.97.2`)
- Modify: `frontend/maquette/README.md` (a short "The shell" paragraph)
- Modify: `IMPLEMENTATION.md` (SP2 entry in the current-state section)

**Interfaces:**

- Consumes: everything above, green.

- [ ] **Step 1: Full suite in the background** (43 scripts, sequential, one process; re-sync `wrapped.html` first — Global Constraints recipe):

```bash
cd /Users/izno/dev/PersonalScraper/frontend/maquette/harness
rm -f /tmp/tm-refonte/suite-sp2.log
nohup bash -c 'for s in *.py; do
    [ "$s" = common.py ] && continue
    command python3 "$s" > /dev/null 2>&1 || echo "FAILED: $s" >> /tmp/tm-refonte/suite-sp2.log
  done; echo "SUITE TERMINEE" >> /tmp/tm-refonte/suite-sp2.log' > /dev/null 2>&1 &
```

Poll the log until `SUITE TERMINEE`. Expected: zero `FAILED:` lines. A failure is classified before any fix (mechanism, not symptom), and fixed inside the failing rule or reported.

- [ ] **Step 2: README paragraph** — in `frontend/maquette/README.md`, after the layout description, a short English paragraph: `design/` is also a Vite project; `npm run build` emits `dist/` (gitignored) whose output R72 proves identical to the source; the prototype itself is injected verbatim and never transformed; the live host still serves the source — the switch to the built output is a later, explicit step.

- [ ] **Step 3: IMPLEMENTATION.md** — add an SP2 entry to the current-state section (style-matched): branch, the shell, R72, host unchanged, next = SP3 (routing) and the host-switch step.

- [ ] **Step 4: Version bump** — `personalscraper/__init__.py`: `0.97.1` → `0.97.2`.

- [ ] **Step 5: `make check`**

```bash
cd /Users/izno/dev/PersonalScraper && make check 2>&1 | tail -3; echo "exit=$?"
```

Expected: exit 0.

- [ ] **Step 6: Commit docs + bump**

```bash
git add frontend/maquette/README.md IMPLEMENTATION.md personalscraper/__init__.py
git commit -m "docs(shell-mobile): la coquille entre dans la méthode, v0.97.2"
```

- [ ] **Step 7: Push, verify, PR, CI**

```bash
git push -u origin refactor/maquette-sp2
git ls-remote origin refactor/maquette-sp2 && git rev-parse HEAD
```

Expected: SHAs identical (SIGPIPE 141 → `--no-verify` retry, then re-verify). PR title `refactor(shell-mobile): SP2 — la coquille Vite et sa preuve d'identité DOM`; body in French: the arbitration (host stays on source), what the shell does and does not do, the R72 proof lines, both mutations, suite green, next steps (host switch, SP3). Watch CI (10 checks; 3-4s failures without logs = billing-blocked pattern, not test failures).

- [ ] **Step 8: Merge** — squash (standing operator instruction for this lane), then `git checkout main && git pull --ff-only`, verify `main`'s SHA matches the merge. No pm2 restart needed (`serve.py` untouched) — but re-sync `/tmp/tm-refonte/wrapped.html` from the merged main.
