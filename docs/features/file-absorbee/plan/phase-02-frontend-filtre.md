# Phase 02 — Frontend : filtre JS sur statut résolu, vocabulaire corrigé

**Défaut visé** : le filtre serveur et la pastille liraient deux valeurs différentes, et
trois commentaires + un test épinglent le raisonnement « un épisode absorbé EST en cours
d'acquisition », faux dès que sa saison est terminée.

## 02.1 — Le panneau filtre en JS

Fichier : `frontend/src/components/acquisition/FileDAcquisitionPanel.tsx`.

État actuel (l.117-143) : la requête envoie `status` à l'API et la clé TanStack dépend du
filtre, donc chaque changement de filtre re-fetch toutes les pages.

Après :

1. La requête ne passe **plus** `status` — elle charge toujours « tous » (elle boucle déjà
   sur les pages jusqu'à `HARD_CAP`). Clé de requête : `["acquisition", "wanted", "all"]`,
   sans le filtre → changer de filtre ne déclenche plus de fetch.
2. Le filtrage se fait en JS sur `item.status` (déjà résolu par la phase 01), en amont de
   `groupByTitleSeason`, dans un `useMemo` dépendant de `(items, status)`.
3. Le compte affiché (« N résultats », l.191-193) devient le compte **filtré**. Le bandeau
   de troncature (`capped`, l.198-206) doit continuer de dire la vérité : il parle du total
   **non filtré** rapporté par l'API — vérifier qu'il ne se met pas à mentir une fois le
   compte devenu local.
4. Le message « vide » (l.229+) distingue déjà `status === "all"` du cas filtré : il reste
   correct, mais relire son libellé à la lumière du filtre local.

## 02.2 — Le vocabulaire cesse d'affirmer le faux

Fichier : `frontend/src/components/acquisition/meta.ts`.

`STATUS_LABEL.absorbed` (l.145) et `STATUS_TONE.absorbed` (l.135) **restent inchangés** :
après la phase 01, l'API ne sert plus `absorbed` que pour le pointeur pendant, et « En cours
d'acquisition » reste la lecture retenue pour ce cas (D3 : on ne troque pas une ignorance
contre un autre mensonge). Ce sont les **justifications** qui sont fausses :

| Emplacement | Ce qu'il affirme aujourd'hui | Ce qui est vrai |
| ----------- | ---------------------------- | --------------- |
| `meta.ts:117-119` | « `absorbed` … il lit déjà "En cours d'acquisition" dans la file » — présenté comme une propriété permanente | La file lit désormais le statut de la saison ; `absorbed` n'y apparaît plus que pour un pointeur pendant |
| `meta.ts:504-506` | « Un épisode absorbé EST un épisode en cours d'acquisition » | Seulement tant que sa saison l'est |
| `meta.ts:525` | même alias, même raisonnement | idem |

Réécrire les trois commentaires. Ne pas se contenter d'ajouter : **retirer** l'affirmation
fausse, sinon le prochain lecteur la croit.

## 02.3 — Le test qui épingle l'alias

Fichier : `frontend/src/components/acquisition/meta.test.ts` (l.145-153).

Le test « aliases absorbed onto en_acquisition — same label AND same tone » **reste** — l'alias
est toujours vrai pour le cas pendant. Sa justification en commentaire (« the backend already
reads it that way: states.py maps absorbed -> en_acquisition ») est périmée et devient
trompeuse : le mapping `_EPISODE_TO_FOLLOW_STATUS["absorbed"]` est un filet défensif de la
carte, jamais le contrat de la file. Corriger le commentaire pour dire ce que le test protège
réellement : **le rendu du pointeur pendant**.

Vérifier également `FileDAcquisitionPanel.test.tsx:776` (« renders an absorbed episode row as
« En cours d'acquisition » ») : ce test doit désormais construire explicitement un cas de
**pointeur pendant**, sinon il fige le bug.

## 02.4 — Tests du panneau

Ajouter à `FileDAcquisitionPanel.test.tsx` :

1. Une ligne servie `done` (absorbée résolue par le backend) rend « Terminé ».
2. Le filtre « Terminé » ramène cette ligne, et le compte affiché suit.
3. Changer de filtre ne déclenche **pas** de nouvel appel réseau (le fetch est unique).

## Critères de sortie

- `npm run lint`, `tsc -b --noEmit` et `vitest` verts — les trois, la gate eslint du CI est
  séparée du typecheck.
- Aucun commentaire du dépôt n'affirme plus qu'un épisode absorbé est en cours d'acquisition.
