# Phase 04 — Gates, PR, CI, merge, preuve sur données réelles

**Ce que cette phase refuse** : déclarer « conforme » sur une relecture. La §13 exige un
contrôle croisé données ↔ affichage, exécuté et daté.

## 04.1 — Gate locale

- `make check` vert (lint + typecheck + tests + coverage).
- `make test` vert (il rapporte ~161 tests de plus que `make check` — la coverage en
  désélectionne ; le critère est **zéro échec**, pas l'égalité des comptes).
- Front : `npm run lint`, `tsc -b --noEmit`, `vitest` — les trois séparément.
- `git status --short` **propre** avant de pousser : un worktree sale masque un lint CI
  (un reformatage non commité rend le local vert et la CI rouge).
- Vérifier la version : `personalscraper/__init__.py` = `0.84.1`, et `/api/version` la sert.

## 04.2 — PR

- Pousser `fix/file-absorbee`, ouvrir la PR.
- Corps de PR : le défaut, la cause racine (le pointeur rapporté au lieu d'être suivi), les
  31 lignes, le trou de garde, et **l'écart assumé §3.4** (le filtre serveur `status=`
  continue de porter sur le statut stocké).
- Vérifier `mergeable` avant d'attendre la CI : une base périmée produit une PR
  `CONFLICTING` avec zéro check-suite, qui ressemble à une CI qui ne démarre pas.

## 04.3 — CI

- Attendre le vert. Points de vigilance connus du dépôt :
  - dérive OpenAPI (le schéma régénéré doit être commité) ;
  - version de ruff non pinnée en CI → un lint vert en local peut être rouge en CI ;
  - un job qui échoue en 3-4 s sans log = blocage de facturation GHA, pas le code.

## 04.4 — Review puis merge

- `/implement:pr-review`, corriger les findings confirmés.
- Merge : **auto** (squash via API), conformément à la stratégie retenue.

## 04.5 — La preuve, après déploiement

Rien de ce qui suit n'est remplaçable par une relecture.

1. **Déploiement** : le déploiement prod est automatique (`torrentmate-autodeploy`) ;
   confirmer que le service tourne bien la version `0.84.1` avant toute vérification.
   Attention au cache du service worker : comparer le hash du bundle servi avec
   `/index.html` en `no-store` avant de conclure que le front est à jour.
2. **Données ↔ écran, sur les 4 lignes rapportées** : `GET /api/acquisition/wanted` sert
   `done` pour les wanted #5, #6, #7, #8.
3. **Les 31, pas seulement les 4** : vérifier que **toutes** les lignes `absorbed` de la base
   sont servies avec le statut de leur saison. Une preuve sur les 4 lignes du rapport serait
   une preuve partielle — donc pas une preuve.
4. **Écran, à 390 px** (largeur mobile réelle, harnais iframe) : la file affiche « Terminé »
   sur ces lignes ; aucun débordement horizontal.
5. **Filtre** : « Terminé » ramène les lignes absorbées résolues ; le compte suit.
6. **`scripts/check-acquisition-coherence.py` → 0 anomalie** sur les données réelles.
7. **État existant** : re-vérifier qu'aucune ligne n'était à réparer (les 31 pointeurs
   résolvent). Si une seule ne résout pas, elle est instruite — pas passée sous silence.

## 04.6 — Clôture

- Consigner le déroulé daté (commandes + sorties) dans le corps de PR ou un ACCEPTANCE.md.
- Carte kanban #411 → Done (ferme l'issue GitHub).
