# Clean-code / i18n wave — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the operator's binding rule (2026-08-16): the code in scope contains NO
French — identifiers, file names, tool messages — and NO UI string lives in code: French
interface texts move to react-i18next translation files. The rule is then CONTROLLED by
an automated gate in `make check` and CI. Rendered output stays byte-identical — the 48
harness rules assert French text and MUST stay green at unchanged rule ASSERTIONS.

**Architecture:** Strings first, then names. (1) react-i18next lands in the design shell
with `src/i18n/fr.json` (namespaces `common` / `settings` / `screens`); every UI string
is EXTRACTED (copy, never retype) so the rendered text is byte-identical. (2) The `src/`
identifiers and files rename to English around a FROZEN seam surface (~65 member names
the legacy fragment calls, all `data-*` names/values, `__go` state ids, route paths, CSS
classes — the DOM/address contract is deferred to SP5/SP4-fin by operator ruling).
(3) The harness renames in batches (files, identifiers, messages → English), with the
README rule table and every reference updated. (4) `serve.py`/`resynchro.py` follow;
serve.py's served French pages read their strings from the shared `fr.json`. (5) A
two-armed gate (`scripts/check-no-french.py`: French-lexicon scan over identifiers +
accent/stopword scan over string literals outside i18n files, with the frozen allowlist)
enters `make check` and CI.

**Tech Stack:** react-i18next + i18next (new deps), Vite 8/TS 6 (`resolveJsonModule`),
Playwright harness (`command python3` 3.12.4).

**Spec:** the operator directive + arbitrations recorded in memory
(`feedback_no_french_in_code_i18n`): scope = `design/src` + harness + `serve.py` +
`resynchro.py` + all new code; EXCLUDED: the legacy fragment (`refonte.html`), the DOM
contract, the window seams, route paths/addresses. Commits stay French (lane convention).
**Inventory:** measured 2026-08-16 on `main` = `a50c1fae` (this plan's numbers come from
it; re-grep before editing).

## Global Constraints

- Rendered-output invariant: UI text byte-identical after extraction — the proof is the
  SP4b-style full-text oracle (rendered innerText compared across driven states,
  before/after) PLUS the full suite green. Extraction copies strings; a retyped string
  is a defect.
- FROZEN surface (never rename): `Magasin` members `lire/ecrire/adopterEtat/adopterMonde/
  toucher/store`; `Pont` members `noter/remplacer/coucher/retour/reculer/surRetour`;
  `Ecrans` members `profil/fiche/releases/resolution/ajout`; `Panneau` members
  `ouvrir/fermer/ouverte`; ALL `window.__referentiel` member keys (~45); the window
  seam names (`__pont`, `__panneau`, `__ecrans`, `__magasin`, `__referentiel`,
  `__derouler`, `__annoncerPops`, `__demarrerMoteur`, `__navEchec`, `__panneauInconnu`,
  `__sujetsSansNom`, `__fermerCouches`, `__go`, `__states`, `__close`, `__reset`,
  `__chargementTermine`); `__demarrerMoteur`'s deps keys `{ magasin, base }`; all
  `data-*` attribute names AND values (incl. `data-cle` prefixes `fiche:`/`ajout:`/
  `profil:`/`releases:`/`resolution:`); `__go` state ids; CSS class names; ROUTE PATHS
  (`/fiche`, `/ajout`, `/profil`, `/releases`, `/resolution`) — addresses are product
  surface, deferred with the DOM contract. TYPE names and factory/implementation
  identifiers around these ARE renameable.
- Data literals that mirror the legacy data model (e.g. `k: "Film" | "Série"`) are the
  DATA contract, not UI — they stay.
- Gate of every task that changes what is served: full suite green (48 scripts);
  R59/R69/R71 at unchanged rule code except where a task explicitly amends (recorded in
  regions.json — expected: R72 for the entry-file rename; message-wording changes in
  harness output are NOT rule-assertion changes).
- Measurement ritual after every design/ source edit:
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
  (Node: `/Users/izno/.nvm/versions/node/v22.13.1/bin`). `command python3`, server 8899,
  one measuring process, FOREGROUND everything. `rg` ALWAYS with `-g` filters.
- Comments English timeless; commits French Conventional `(shell-mobile)` scope for
  maquette-side, `(clean-code)` acceptable for the gate script; tree buildable at every
  commit; verify remote SHA after push.

---

### Task 1: i18n infrastructure + pilot extraction (releases screen)

**Files:**
- Modify: `frontend/maquette/design/package.json` (add `i18next`, `react-i18next`)
- Modify: `frontend/maquette/design/tsconfig.json` (`resolveJsonModule: true`)
- Create: `frontend/maquette/design/src/i18n/fr.json` (namespaces `common`, `settings`, `screens`)
- Create: `frontend/maquette/design/src/i18n/index.ts` (i18next init, static import — `publicDir: false` forbids fetch)
- Modify: `frontend/maquette/design/src/coquille.tsx` (import the i18n init once, before mount)
- Modify: `frontend/maquette/design/src/ecrans/releases.tsx` (pilot: its 10 UI strings → `t("screens.releases.…")`)

**Interfaces:**
- Produces: `useTranslation()` pattern the other screens copy; `fr.json`'s key
  convention: `screens.<screen>.<slug>` for prose, `settings.labels.*` /
  `settings.subjects.*` / `settings.units.*` reserved for Task 2's dictionaries,
  `common.*` for shared bits. Interpolations use i18next `{{var}}` where the legacy
  string had template holes — the RENDERED text stays byte-identical.

- [ ] **Step 1:** Install deps; init module (`fallbackLng: "fr"`, `resources: { fr }`,
      `interpolation.escapeValue: false` — React escapes); import in the shell entry.
- [ ] **Step 2:** Extract the pilot's strings by COPY (cut from JSX, paste into fr.json;
      no retyping). Typecheck + build green.
- [ ] **Step 3:** Byte-identity proof: drive `ecran-releases` before/after (git stash the
      change to capture BEFORE if needed) and diff the rendered innerText — 0 divergence.
      Paste. Run `command python3 frontend/maquette/harness/cartes.py` + full smoke of any
      rule reading this screen; then FULL suite. Zero FAILED.
- [ ] **Step 4:** Commit: `feat(shell-mobile): i18n s'installe — les textes de l'écran releases quittent le code`

### Task 2: Full extraction — the remaining screens + the panneau dictionaries

**Files:**
- Modify: `frontend/maquette/design/src/ecrans/{fiche,profil,ajout,resolution}.tsx`,
  `src/composants/panneau.tsx`, `src/coquille.tsx` (EcranEnErreur's message),
  `src/i18n/fr.json`

**Interfaces:**
- Produces: zero French string literals in components (≈197 UI lines, ~220-250 keys;
  `panneau.tsx`'s three dictionaries — `LIBELLES_REGLAGES` 94, `NOMS_SUJETS` 54,
  `UNITES` 8 — become `settings.labels/subjects/units` namespaces; the lookup helpers
  keep their SEMANTICS (fallback chains identical) but read via `t()`/the imported
  resource object).
- CAUTION: `data-toast="…"` attributes carry French UI text consumed by the LEGACY toast
  mechanism — the VALUE is UI; extract via `t()` into the attribute (the rendered
  attribute value stays byte-identical). `aria-label`/`placeholder`/`title` same.
- The `bloc de panneau inconnu` throw message: tool/dev message → English (not UI).
  `console.error` messages → English.

- [ ] **Step 1:** Extract file by file (COPY discipline), typecheck after each.
- [ ] **Step 2:** Byte-identity oracle over the FULL driven state set (the SP4b
      fidelity-oracle pattern: all `__states()` ids, rendered innerText before/after,
      0 divergence — accepting only the known JSX-whitespace-neutral differences ALREADY
      established; paste counts). Full suite. Zero FAILED.
- [ ] **Step 3:** `rg -n -g '*.tsx' -g '*.ts' "[àâéèêëîïôùûüç]" frontend/maquette/design/src --glob '!**/i18n/**'`
      → only comments and the `"Série"` data literal remain (paste; each residual justified).
- [ ] **Step 4:** Commit: `feat(shell-mobile): tous les textes d'interface en fr.json — le code ne parle plus français à l'écran`

### Task 3: `design/src` renames — identifiers, files, directories

**Files:**
- Rename: `magasin.ts`→`store.ts`, `donnees.ts`→`data.ts`, `coquille.tsx`→`shell.tsx`,
  `composants/`→`components/` (`feuille.tsx`→`sheet.tsx`, `panneau.tsx`→`panel.tsx`),
  `ecrans/`→`screens/` (`ajout.tsx`→`add.tsx`, `fiche.tsx`→`media.tsx`,
  `profil.tsx`→`profile.tsx`, `releases.tsx` stays, `resolution.tsx` stays)
- Modify: every internal import (18 edges), `index.html` (the module entry
  `/src/coquille.tsx` → `/src/shell.tsx`)
- Modify: `frontend/maquette/harness/coquille.py` (R72 — asserts the named module entry;
  amend the expectation ONLY as far as the entry name, record in regions.json) and
  `frontend/maquette/harness/coquille.py`→ file itself renames in Task 4, not here
- Modify: `frontend/maquette/regions.json` (R72 record)

**Interfaces:**
- Produces: English identifiers throughout `src/` (~140 declarations, 250-350 sites):
  `creerMagasin`→`createStore`, `Magasin`→`Store` (type; members FROZEN),
  `EtatUI`→`UiState`, `Contenu`→`StoreContent`, `aller`→`go`,
  `ouvrirPanneau`/`fermerPanneau`→`openPanel`/`closePanel`, `historique`→`history`,
  `EcranEnErreur`→`ScreenError`, hooks `useEtat`→`useUiState`, `useMonde`→`useWorld`,
  `useContenu`→`useStoreContent`, `useReferentiel`→`useReference` (type
  `Referentiel`→`Reference`; MEMBER KEYS FROZEN), components `FicheEcran`→`MediaScreen`,
  `AjoutEcran`→`AddScreen`, `ProfilEcran`→`ProfileScreen`, `ReleasesEcran`→`ReleasesScreen`,
  `ResolutionEcran`→`ResolutionScreen`, `PanneauContenu`→`PanelContent`,
  `Feuille`→`Sheet`, `Descripteur`→`PanelDescriptor`, `Bloc`→`PanelBlock`,
  `CarteRelease`→`ReleaseCard`, `CarteDecision`→`DecisionCard`, `Icone`→`Icon`, etc. —
  the implementer completes the map file-by-file, FROZEN list in hand; every window
  seam ASSIGNMENT keeps its name (`window.__ecrans = { profil: … }` — the KEYS stay).

- [ ] **Step 1:** Renames + import updates + identifier sweep, file by file; typecheck
      after each file; build at the end.
- [ ] **Step 2:** R72 amendment (entry name) recorded; run `command python3 frontend/maquette/harness/coquille.py` green.
- [ ] **Step 3:** Frozen-surface audit, pasted: `rg -n -g '*.tsx' -g '*.ts' "ecrire|toucher|adopter" frontend/maquette/design/src` shows only frozen-member USES (no renamed member); `rg -g '*.html' ` for 3 spot-checked seam calls unchanged.
- [ ] **Step 4:** FULL suite (the bundle name changed — everything reruns). Zero FAILED.
- [ ] **Step 5:** Commit: `refactor(shell-mobile): le code de la coquille parle anglais — fichiers, identifiants, la couture gelée intacte`

### Task 4: Harness renames — files + references (mechanical, zero behavior)

**Files:**
- Rename ~36 French-named harness files (map fixed here): `actions`→`behaviors`? NO —
  `actions.py` is EN; the FRENCH ones: `adresse`→`address`, `adresse_url`→`url-address`
  (keep underscore style: `url_address`), `adresses_ecrans`→`screen_addresses`,
  `arrivees`→`arrivals`, `bascule`→`failover`, `cartes`→`cards`, `commun`→`common`,
  `contenu`→`content`, `coquille`→`shell`, `decision`→`decision` (EN already? keep),
  `deconnexion`→`logout`, `demarrage`→`startup`, `doigt`→`touch`, `ecrans`→`screens`,
  `entree`→`entry`, `filtres`→`filters`, `galerie`→`gallery`, `glisse`→`drag`,
  `images`→`images` (keep), `installation`→`install`, `machine`→`machine` (keep),
  `navigation`→`navigation` (keep), `palette`→`palette` (keep), `panneau`→`panel`,
  `pont`→`bridge`, `reglages`→`settings`, `retour`→`back`, `scroll`→`scroll` (keep),
  `sel`→`selection`, `souris`→`mouse`, `suivis`→`follows`, `surfaces`→`surfaces` (keep),
  `tiroir`→`drawer`, `serveur`→`server`, `renommer.mjs`→`rename.mjs`; the implementer
  verifies each name against the file's actual subject before renaming (a wrong
  translation is a finding, not a convention).
- Modify: the 12 `from commun import …` lines → `from common import …`
- Modify: `frontend/maquette/README.md` (the 49-row rule table + ~15 prose mentions),
  `IMPLEMENTATION.md` (~18 refs), `frontend/maquette/regions.json` ($comment prose refs),
  `frontend/maquette/resynchro.py` (its `harness/contenu.py` ref), `scripts/extract-maquette-css.py` (comment)

- [ ] **Step 1:** `git mv` each (macOS case-insensitivity: no case-only renames here, all
      are word changes — safe), imports, then ALL references (rg each old name -g '*.md'
      -g '*.py' -g '*.json' across the repo, fix, paste the zero-hit sweep at the end).
- [ ] **Step 2:** FULL suite from the NEW file names — this IS the behavior proof (48
      scripts, zero FAILED). R59/R69/R71: renamed files, UNCHANGED assertions — record
      one summary amendment note in regions.json ($comment: the rule↔file map moved with
      the English names; per-rule entries stay keyed by R-number so only prose mentions
      change).
- [ ] **Step 3:** Commit: `refactor(shell-mobile): le harnais renommé en anglais — 36 fichiers, la table des règles suit`

### Task 5: Harness content — identifiers and messages to English (batched)

**Files:** all 49 harness scripts (in 4 batches of ~12, one commit per batch)

**Interfaces:**
- `common.py` first: `Journal` (keep), `verifier`→`check`, `bilan`→`summary`,
  `ouvrir`→`open_page`, `RACINE`→`ROOT`, `PROTOTYPE`→`PROTOTYPE` (EN), `TELEPHONE`→`PHONE`,
  output formats → English (`"  OK  "/"  FAIL"`, `"{n} rules EXECUTED"`,
  `"no violation"`, `"violation(s):"`, `"JS errors:"`). Then every script: module-local
  `verifier` wrappers → `check`, French locals/params → English, `Journal("R59 — …")`
  titles → English translations of the rule's NAME (translate meaning, not word-by-word),
  the 342 French `verifier` labels → English (the label is a tool message, not UI).
- DO NOT touch: JS-eval string BODIES' DOM/state tokens (`state.acqTab`, `data-cle`,
  selectors, `__go` ids, asserted RENDERED FRENCH TEXT — a hold asserting
  `« En cours »` keeps asserting `« En cours »`: the app renders French).
- The suite's own pass/fail semantics unchanged: exit codes, counts.

- [ ] **Per batch:** sweep ~12 files; run each renamed script foreground (paste tails);
      after batches 2 and 4, FULL suite. Zero FAILED.
- [ ] **Batch commits:** `refactor(shell-mobile): le harnais parle anglais — lot N/4`

### Task 6: `serve.py` + `resynchro.py` — English code, served French via fr.json

**Files:**
- Modify: `frontend/maquette/serve.py` (16 defs → English: `tete_pwa`→`pwa_head`,
  `panne_build`→`build_failure`, `page_connexion`→`login_page`, `jeton`→`token`,
  `mot_de_passe_correct`→`password_ok`, etc.; the login page + build-failure page are
  UI: their French strings move to `frontend/maquette/design/src/i18n/fr.json` under a
  `server.*` namespace, read by serve.py at startup (json.load of the SAME file — one
  source of truth; served bytes identical))
- Modify: `frontend/maquette/resynchro.py` (5 defs + messages → English)
- Modify: `frontend/maquette/harness/` (whichever renamed script holds R73 — its holds
  read the login page's semantics, not its wording, verify)

- [ ] **Step 1:** serve.py refactor; byte-identity of the served login page proven
      (curl the scratch instance before/after, diff — paste). R73 script green.
- [ ] **Step 2:** resynchro.py; run it (should report no drift / loud behavior intact —
      re-run its Task-7-era scratch proofs quickly).
- [ ] **Step 3:** `pm2 restart torrentmate-design` NOT needed until merge (serve.py is
      imported at process start — note for the wave gate's post-merge step).
- [ ] **Step 4:** Commit: `refactor(shell-mobile): serve et resynchro parlent anglais — la page de connexion lit fr.json`

### Task 7: The gate — `scripts/check-no-french.py` in make check + CI

**Files:**
- Create: `scripts/check-no-french.py` (pattern of `check-typed-api.py`: violations list,
  stderr, exit 1)
- Modify: `Makefile` (one line in `check:`), `.github/workflows/ci.yml` (a step in the
  `frontend` job under the maquette condition — the scoped files are maquette-side; plus
  the `changes` filter already routes it)

**Interfaces:**
- Two arms over the SCOPE (design/src minus i18n/, harness, serve.py, resynchro.py):
  (1) STRING arm: accented chars or French stopwords (` le `, ` la `, ` les `, ` une `,
  ` des `, ` est `, ` pour `…) inside string literals → violation (i18n files excluded;
  per-line pragma `# french-ok: <reason>` / `// french-ok: <reason>` for the few data
  literals like `"Série"` and harness holds that ASSERT rendered French — each pragma
  carries its reason);
  (2) IDENTIFIER arm: declared names (def/class/const/let/var/function/type) matched
  against a French lexicon (the inventory's top tokens: verifier, erreurs, etat, fiche,
  titre, ouvrir, lire, ecrire… ~60 words + accent detection) → violation, with the
  FROZEN allowlist (the ~65 seam member names + window seam tokens) embedded and
  commented.
- [ ] **Step 1:** Write it; run on the CURRENT (post-Task-6) tree → zero violations
      (paste). MUTATION: seed a French identifier and a French string in a scratch copy →
      both arms fall naming them (paste); remove.
- [ ] **Step 2:** Wire Makefile + ci.yml. `make check` green end-to-end.
- [ ] **Step 3:** Commit: `ci(shell-mobile): la garde anti-français — deux bras, liste gelée, contrôlée dans make check et la CI`

### Task 8: Wave gate

- [ ] `resynchro` (renamed) run; FULL suite 48/48 zero FAILED pasted; `make check` green
      (INCLUDING the new gate); `make check-frontend` green; residual sweep:
      the old French file names → zero references repo-wide (paste).
- [ ] Docs: IMPLEMENTATION.md (wave record), `frontend/maquette/README.md` (i18n section:
      where strings live, the key convention, the gate; CLAUDE.md maquette section notes
      the standing rule). Bump 0.97.13. ONE commit:
      `docs(shell-mobile): registre clean-code/i18n — le code en anglais, les textes en fr.json, bump 0.97.13`
- [ ] Push/PR/merge = controller after the final adversarial review. Post-merge:
      `pm2 restart torrentmate-design` (serve.py changed) + live check (login page
      byte-identical, deep routes fold).

---

## Self-review notes (executed)

- Directive coverage: no-French code ✔ (T3 src, T4/T5 harness, T6 servers); UI via i18n
  ✔ (T1/T2, serve.py pages T6); enforced/controlled ✔ (T7 gate in make check + CI);
  corrected ✔ (the whole wave); scope per arbitration ✔ (fragment excluded; DOM
  contract + seams frozen; route paths frozen as addresses).
- Rendered byte-identity is a Global Constraint with an oracle per extraction task, and
  the harness keeps asserting FRENCH rendered text (T5's do-not-touch list).
- Type consistency: the T3 rename map is used by T4's `coquille.py`→`shell.py`? NO —
  T4 renames harness FILES (coquille.py→shell.py per its map); R72's amendment happens
  in T3 (entry expectation) while the FILE renames in T4 — sequential, no conflict.
- Known risk, named: T5's 1900-token sweep inside JS-eval strings — the do-not-touch
  list (DOM/state tokens, asserted French) is the reviewers' first check per batch.
