# Item 12 — Analyse critique design + architecture

**Date** : 2026-05-21
**Méthode** : meta-analyse de l'architecture personalscraper telle qu'elle existe à 0.15.0,
critique des choix structurels présents, identification des décisions à figer pour 1.0 vs
celles qui peuvent dériver. Distinct des audits précédents qui regardaient "ce qui est cassé" :
ici on regarde "ce qui est juste mal pensé".
**Output** : critique architecturale + items DESIGN-ready focalisés architecture.

---

## 0. Constat global de l'architecture 0.15.x

### Organisation des modules (vue de surface)

```
personalscraper/
  api/                  # Adapters HTTP (TMDB, TVDB, qBit, Transmission, LaCale, C411, Telegram, Healthchecks)
    metadata/
    torrent/
    tracker/
    notify/
  core/                 # AppContext, event_bus
  commands/             # CLI entry points (Typer)
    library/
    pipeline.py
    config.py
    info.py
  ingest/               # Stage A : torrents → 097-TEMP
  sorter/               # Stage B : 097-TEMP → categories
  scraper/              # Stage C : NFO + artwork + structure
  verify/               # Stage D : qualification pre-dispatch
  enforce/              # (between scrape and verify) sanitization
  dispatch/             # Stage E : staging → disks
  trailers/             # Acquisition trailers (orthogonal to pipeline steps)
  library/              # Scanner (high-level), analyzer, rescraper, validator
  indexer/              # BDD layer (schema, scanner low-level, repos, migrations, drift, reconcile)
  conf/                 # Configuration loading
  logger.py
  config.py             # Pydantic models
```

### Ce qui est bien

- **Couches techniques claires** : api/ (HTTP), core/ (process-wide), commands/ (CLI), modules
  métier (ingest/sort/scrape/verify/enforce/dispatch/library/indexer/trailers). 9 couches
  bien séparées.
- **Configuration overlays** (split config 0.14+) : composition explicite, validation Pydantic
  stricte.
- **Event bus en place** (0.14.0) : observability + extensibilité via subscribers.
- **Indexer + dispatch découplés** : la BDD reflète l'état des disques mais n'est pas le
  source-of-truth (le FS l'est).
- **NO DEFERRAL discipline** (event-bus posture) : limite la dette tacite.
- **Migrations versionnées** : schéma évolution propre (modulo DEV #15 cosmétique).
- **Provider-IDs flow** : capabilities atomiques (post-fix CF-B), multi-source ratings, soft
  fallback.

### Ce qui est mal pensé

#### A — La duplication "library scanner" vs "indexer scanner"

Deux scanners coexistent :

- `personalscraper/library/scanner.py` — crée les `media_item` (lit NFOs sur disque)
- `personalscraper/indexer/scanner/` — crée les `media_file` (walk FS, fingerprints)

Le library scanner appelle l'indexer en interne. Le mapping métier (item ↔ file) est dispersé.
Conséquence directe : **DEV #16** — la library scanner n'est pas exposée en CLI, donc media_item
ne se peuple jamais sur prod.

**Critique** : Pourquoi deux scanners ? Le périmètre est lié (un media_item est une "vue
sémantique" de N media_files). Un seul scanner avec deux passes serait plus clair :

```
personalscraper library-scan
  ├── Pass 1 : walk FS, upsert media_item + season + episode (depuis NFOs)
  └── Pass 2 : walk FS, upsert media_file + media_release + media_stream (depuis ffprobe + linker)
```

Ou plus radical : un unique `library-index` qui fait tout, avec des modes (`--mode items-only`,
`--mode files-only`, `--mode full`).

**Décision DESIGN tech-debt** : ne PAS refactor en 0.16.0 (breaking). Mais formaliser la
relation library ↔ indexer dans `docs/reference/architecture.md` et décider en 0.17+ si on
unifie.

#### B — Pipeline composite `process` vs steps individuels

`process` regroupe `clean + scrape + cleanup`. C'est cohérent fonctionnellement (3 ops sur
le staging) mais opaque pour le pipeline-monitor :

- Le matrix v2.0 traite chaque sous-step comme un StepReport distinct
- Le CLI expose `process` (composite) ET `scrape` (sous-step) mais pas `clean` / `cleanup`
  individuellement

**Critique** : asymétrie. Pourquoi `scrape` accessible mais pas `clean` / `cleanup` ? Soit on
expose tout, soit on n'expose que le composite.

**Décision DESIGN** : exposer les 3 sous-commandes individuellement (`personalscraper clean`,
`personalscraper cleanup`) en plus du composite. Permet debugging + composition. Coût faible
(des wrappers Typer).

#### C — `enforce` step "couteau suisse"

`enforce` combine : sanitize_filename + structure_validator (move orphan episodes) +
coherence_checker (.DS_Store cleanup). Trois responsabilités très différentes pour un seul step.

**Critique** : viole le single-responsibility. Le DEV #4 (scope-limited .DS_Store cleanup) en
est un symptôme : enforce a plein de responsabilités donc chaque sous-responsabilité a son
scope mal défini.

**Décision DESIGN** : décomposer `enforce` en 3 modes ou 3 sous-commandes :

- `enforce sanitize` — renommage NTFS-safe
- `enforce structure` — organize orphan episodes (handoff PROCESS:scrape → ENFORCE documenté)
- `enforce coherence` — coherence checks (NFO conformance, dispatch readiness)

Pas pour 0.16.0 (re-design). Mais identifier comme tech debt structurelle.

#### D — `trailers` orthogonal au pipeline

`trailers` est un group CLI séparé (`scan`/`download`/`verify`/`purge`) avec son propre scanner.
Il vit hors du pipeline mais utilise la library DB.

**Critique** : OK pour le découplage, mais pourquoi `trailers verify` existe alors qu'il y a
`verify` global ? Naming collision. P19 (item 9).

Aussi : trailers a son propre concept de "scan library" (different from `library.scanner.scan_library()`)
qui crée parfois de la confusion. Différents periodes/contexts.

**Décision DESIGN** : OK pour 0.16.0. Renommer `trailers verify` en `trailers audit` ou
`trailers check` pour disambiguer. Non-breaking (deprecation alias).

#### E — `indexer` vs `library` namespace flou

- `library/scanner.py` (high-level) vs `indexer/scanner/` (low-level)
- `library/analyzer.py` vs `indexer/reconcile.py`
- `library/rescraper.py` vs `scraper/` (top-level)

Le mot "library" désigne tantôt la BDD (`library.db`), tantôt un module Python, tantôt le set
de médias sur disques. **Polysémique → ambigu**.

**Critique** : pas critique fonctionnellement, mais c'est de la dette de naming. Audit le
naming pour 1.0 : `library` = la BDD, `media` = les fichiers sur disque, `indexer` = la couche
SQL repos, `scanner` = le composant qui populate.

Renommings possibles (breaking, 1.0+) :

- `library.scanner` → `mediascanner` (high-level)
- `indexer.scanner` → `fileindexer` (low-level)
- `library.rescraper` → fusionner avec `scraper.rescrape`

#### F — `scraper` top-level vs sub-modules

`personalscraper/scraper/` contient le scrape mécanisme. Mais c'est aussi le name de la
commande pipeline (`personalscraper scrape`). C'est aussi le mot dans `personalscraper` (le
projet entier !).

**Critique** : surcharge sémantique. Pas grave, à décliner en sub-namespaces clairs si refactor
1.0.

#### G — `core/` ne contient que `app_context` + `event_bus`

Le module `core/` est très minimal. Tout le reste (config, logger, etc.) est au niveau
package top. Convention "ce qui est process-wide va dans core" → OK mais peu peuplé.

Logger pourrait y aller. Config aussi (currently à `personalscraper/config.py`).

**Décision DESIGN** : low priority. Cosmétique.

---

## 1. Décisions structurelles à figer pour 1.0

### 1.1 Boundaries claires

Décrire formellement en `docs/reference/architecture.md` :

1. **L'application est process-bound** : un CLI invocation = un AppContext. Pas de mode serveur
   pour 1.0 (peut venir en 1.x via JSON-API CL-AN).
2. **BDD = projection des FS** : le filesystem est la vérité, la BDD est un cache/index.
   Reconcile par drift detection + soft-delete lifecycle.
3. **Pipeline a 9 StepReports** (matrix v2.0) : ingest, sort, clean, scrape, cleanup, enforce,
   verify, trailers, dispatch. Trailers est optionnel (config flag).
4. **EventBus est in-process** : pas de transport réseau. Un host externe peut subscribe via
   import direct (`personalscraper.Pipeline` host mode).
5. **CLI surface est l'API publique** : tout ce qui est dans `personalscraper --help` est
   stable, le reste est interne (refactorable sans breaking).

### 1.2 Anti-décisions (NE PAS faire en 1.0)

- **Pas de microservices** : monolithique CLI.
- **Pas d'auth/users multi-tenant** : single-user (l'opérateur).
- **Pas de réseau** : pas de socket, pas d'HTTP server (sauf si JSON-API 1.x).
- **Pas de cloud** : self-hosted only.
- **Pas de plugins runtime** : extensions via subclassing/import, pas de plugin loader dynamique.

### 1.3 Décisions à figer pour 0.16.0 tech-debt

| Décision                                     | Choix                                                              |
| -------------------------------------------- | ------------------------------------------------------------------ |
| Library scanner vs indexer scanner unifiés ? | NON (breaking) — formaliser la relation en doc                     |
| Process sous-commandes exposées ?            | OUI — `clean`, `cleanup` ajoutés (low cost)                        |
| Enforce décomposé ?                          | NON (re-design 0.17+) — mais documenter les 3 sous-responsabilités |
| Trailers verify renommé ?                    | OUI — alias `trailers audit` (non-breaking, deprecation message)   |
| Namespace library/indexer/scraper refactor ? | NON (breaking 1.0+) — audit + plan only                            |
| Core/ étoffé avec logger/config ?            | NON — cosmétique seulement                                         |
| JSON-API mode ?                              | NON — 1.x roadmap                                                  |

---

## 2. Patterns architecturaux à enforce dans DESIGN tech-debt

### P26 — Single-responsibility per CLI command (extends P19)

Une commande CLI = une responsabilité atomique. `enforce` actuel viole (3 résponsabilités).

→ Item DESIGN : audit des "couteaux suisses" + refactor 0.17+.

### P27 — FS = vérité, BDD = projection

Tout module qui modifie state doit clarifier : muter FS, muter BDD, ou les deux. Si les deux,
ordre canonique (FS first, BDD reconcile second).

→ Item DESIGN : `docs/reference/architecture.md` section "State ownership matrix".

### P28 — Composition over inheritance pour les Protocols

Le DESIGN provider-ids avait déjà cette posture (capabilities atomiques). Maintenir + étendre :
les Protocols futurs DOIVENT être atomiques. CF-B (drop monolithic Protocols) instancie.

→ Item DESIGN : règle dans CLAUDE.md / norms.md.

### P29 — CLI = API publique stable

Toute commande exposée a un contrat. Changer un flag → breaking (semver Y bump). Ajouter
une commande → non-breaking. Renommer → alias deprecation + 1 release.

→ Item DESIGN : doc-as-contract dans `docs/reference/commands.md`.

---

## 3. Items DESIGN-ready (AR-A..AR-G)

**AR-A. `docs/reference/architecture.md` section "State ownership"**

Documenter qui owns quoi : FS owns media files + NFOs + sidecars. BDD owns dispatch_path,
fingerprints, drift state. Pipeline owns lock files. EventBus owns transient observability.

**AR-B. Section "Module relationships"**

Diagramme + texte expliquant library/scanner ↔ indexer/scanner ↔ scraper ↔ commands ↔ trailers.
Évite la confusion polysémique constatée en §1.E.

**AR-C. Expose `clean` + `cleanup` CLI sous-commandes**

Composition possible : `personalscraper clean --dry-run` ; `personalscraper cleanup --dry-run`.
Le composite `process` reste inchangé. Coût ~2h, doc + tests pin.

**AR-D. Renommer `trailers verify` → `trailers audit` (alias deprecation)**

Disambiguate vs `verify` global. Le old name reste 1 release avec warning.

**AR-E. Anti-décisions inscrites dans le DESIGN**

Section "Out of scope for 1.0" dans `docs/reference/architecture.md` listant les anti-decisions
§1.2 ci-dessus. Évite scope creep dans les features futures.

**AR-F. Audit "couteau suisse" pour 0.17+**

Identifier les commandes/modules qui font trop. `enforce`, peut-être `library-validate`,
`library-clean`. Liste pour roadmap 0.17+.

**AR-G. Convention "CLI = API publique" inscrite**

Règle dans CLAUDE.md : ajouter une commande = non-breaking ; modifier flag = breaking. Tous
les changements CLI sont visible dans les release notes.

---

## 4. Catégorisation must/should/nice

### Must-have

Aucun item architecture critique pour 0.16.0. Les fixes durs (DEV #18, #19, etc.) sont dans
items 6-11.

### Should-have

- **AR-A** State ownership doc
- **AR-B** Module relationships doc
- **AR-C** Expose clean + cleanup CLI
- **AR-D** Trailers verify rename alias
- **AR-E** Anti-décisions doc

### Nice-to-have (0.17+ — gros refactors)

- **AR-F** Couteau-suisse audit + decomposition `enforce`
- **AR-G** Convention CLI = API formalisée
- Library scanner + indexer scanner unification
- Namespace refactor library/indexer/scraper

---

## 5. Plan architecture (intégré au plan global)

| Phase            | Items                                             | Effort  |
| ---------------- | ------------------------------------------------- | ------- |
| ARCH-1           | AR-A + AR-B + AR-E (docs reference)               | 1 j     |
| ARCH-2           | AR-C (clean+cleanup CLI) + AR-D (trailers rename) | 0.5-1 j |
| ARCH-3 (différé) | AR-F + AR-G + namespace refactor + enforce decomp | 0.17+   |

Total architecture 0.16.0 : **1-2 jours** (uniquement docs + ajouts CLI mineurs).

---

## 6. Mise à jour cumulative

| Dimension                         | Items                                         | Jours 0.16.0 (nets)                              |
| --------------------------------- | --------------------------------------------- | ------------------------------------------------ |
| Pipeline app + indexer            | item 6 A-G + DEV #15-#19 + item 8 BD-A..BD-AK | 9-14 j                                           |
| Skill matrix v2.1 + agents        | item 6 M-T                                    | 1-2 j                                            |
| Tests E2E + validation            | items 6/8/9/10 transverses                    | 2-3 j                                            |
| CLI + observability + doc         | item 9/10 CL-A..CL-AN                         | 8-13 j                                           |
| Conformité / ACCEPTANCE_FAIL      | item 11 CF-A..CF-K                            | 1-2 j                                            |
| **Architecture / docs reference** | **item 12 AR-A..AR-E**                        | **1-2 j**                                        |
| **TOTAL 0.16.0**                  |                                               | **~14-23 j** (parallélisable, planning ~13-22 j) |

Croissance minimale par rapport à l'estimation item 11. Item 12 confirme le périmètre.

---

## 7. Suite

L'item 13 (brainstorm global) consolide :

- Items 6 (A-G + M-T + AB-AE + autres)
- Items 8 (BD-A..BD-AK)
- Items 9/10 (CL-A..CL-AN)
- Item 11 (CF-A..CF-K)
- Item 12 (AR-A..AR-E)

En un master backlog ordonné par dépendances + priorité, prêt pour l'item 14 challenge final.

L'item 14 (challenge final DESIGN + plan tech-debt) :

1. Re-read DESIGN.draft.md actuel + plan.draft/INDEX.md
2. Réécrire DESIGN.md depuis zéro avec 11 sections (1-8 du draft + §9 BDD + §10 CLI + §11 archi)
3. Generate plan/INDEX.md + phases-01..phases-N.md
4. Validate avec items 6-12 via cross-table patterns/leviers
5. Output non-draft prêt à `/implement:phase`
