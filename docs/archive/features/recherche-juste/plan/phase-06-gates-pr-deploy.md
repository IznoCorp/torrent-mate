# Phase 6 — Portes, PR, CI, merge, déploiement, vérification réelle

**DESIGN** : §11 (les 8 critères ACCEPTANCE).

## Gate

```bash
make check                                   # ACC-06 — lint + test + module-size + typed-api
command python -c "import personalscraper"   # smoke
make openapi && git diff --exit-code openapi.json frontend/src/api/schema.d.ts   # ACC-07
python3 scripts/audit_design_coverage.py --strict
python3 scripts/update_feature_map.py --check
```

Attendu : tout vert. Les deux derniers scripts ne sont **pas** dans `make check` (CI seulement) —
les lancer localement évite une CI rouge sur un point qu'on aurait pu voir en 10 secondes.

Note sur les compteurs : `make test` rapporte ~161 tests de plus que `make check` (la couverture
en désélectionne) — la porte est **zéro échec**, pas l'égalité des compteurs.

## Sous-phases

### 6.1 — Les huit critères ACCEPTANCE, exécutés

Écrire `docs/archive/features/recherche-juste/ACCEPTANCE.md` en **exécutant** chaque critère du DESIGN
§11 et en collant la sortie réelle, datée. Aucun critère n'est « conforme » sans son déroulé.

ACC-01 (diff scrape vide), ACC-02 (golden), ACC-06 (`make check`), ACC-07 (dérive OpenAPI) et
ACC-08 (les deux surfaces) sont exécutables **avant** merge.

ACC-03 (les deux cas sur données live), ACC-04 (pagination) et ACC-05 (390 px) exigent le
déploiement : ils sont exécutés **après** merge, sur staging puis prod, et l'ACCEPTANCE est
complétée à ce moment-là. Un critère différé se déclare comme tel — il ne se coche pas d'avance.

### 6.2 — PR

Corps de PR : le défaut, les preuves live (les deux requêtes, rangs avant/après), les six causes
racines et où chacune est traitée, le tableau de calibrage des pondérations (phase 2.4), les
invariants tenus, et les items laissés ouverts.

À mentionner explicitement dans le corps : les **7 codenames non archivés** de `docs/features/`
(`decisions-spine`, `parcours`, `provenance`, `run-linkage`, `spine-actions`, `tech-debt-2`,
`webui-ux`) — signalés à l'opérateur, hors périmètre de cette PR, à arbitrer.

Vérifier `mergeable` **avant** de guetter les Actions : un `main` local périmé produit une PR
`CONFLICTING` avec zéro check-suite, ce qui ressemble à une CI en panne alors que ce n'en est
pas une.

### 6.3 — CI

Poller jusqu'au vert. Pièges connus à ne pas confondre avec un vrai échec :

- Un job qui échoue en 3-4 s **sans log** = limite de dépense GitHub Actions, pas le code.
- « Pending, jamais démarré » avec 0 check-suite = trigger manqué ; ré-armer par un commit vide.
- La CI installe le **dernier** ruff : un lint vert en local peut être rouge en CI. Aligner la
  version si l'écart se manifeste.
- Vérifier `git status --short` après toute reformulation automatique : un worktree sale masque
  une CI rouge.

### 6.4 — Merge

Mode `auto` (choisi à la création) : squash via l'API une fois la review clean et la CI verte.
Ne jamais lancer `gh pr merge --delete-branch` depuis ce worktree — la bascule de checkout qu'il
provoque casse le remote HTTPS.

### 6.5 — Déploiement et vérification réelle

Prod autodéploie depuis `~/deploy/torrentmate`. Vérifier que `GET /api/version` sert bien
`0.85.0` **et** le SHA déployé — pas la version du code local.

Puis exécuter ACC-03, ACC-04 et ACC-05 sur les données réelles et compléter `ACCEPTANCE.md`.
Buster le cache PWA avant de conclure sur le front : le service worker sert volontiers un bundle
périmé, et on croit alors avoir déployé un correctif qui n'est pas là.

### 6.6 — Carte kanban

Avancer #409 jusqu'à Done une fois la vérification réelle faite — pas à la fusion de la PR. Une
carte en Done sur un correctif non vérifié en prod est un mensonge d'état.

## Ce que cette phase ne fait pas

Elle ne clôt rien sur la foi d'une CI verte. « Mergé » n'est pas « vérifié » : les trois critères
qui exigent des données réelles sont la condition de clôture.
