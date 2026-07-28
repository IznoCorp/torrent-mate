# DESIGN — episode-states : statut « Annoncé » + légende + date au clic

**Codename**: `episode-states` · **Ticket**: #332 · **Type**: `feat` · **Bump**: 0.59.1 → 0.60.0
**Constitution**: §5 (états visibles épisode par épisode), NE-DOIT-PAS-8, NE-DOIT-PAS-4 (pas de
jargon), source unique de vocabulaire.

## Décisions opérateur (2026-07-28)

- Statut « Annoncé » = **tous** les épisodes futurs connus du provider (pas seulement la saison
  courante), avec date de diffusion.
- Légende à code couleurs sous la matrice : 1 couleur par statut.
- Date de diffusion (passée ou future) affichée **au clic** sur chaque puce.

## État actuel

Le cache `aired_episode` stocke `air_date` par épisode, mais `poll_aired` filtre
`air_date <= today` (`airing.py:_is_aired`) → les futurs ne sont jamais cachés. `EpisodeState`
a 5 valeurs, pas d'« annoncé ». `EpisodeCompleteness.air_date` est **déjà** exposé au contrat
(la date au clic a déjà sa donnée). Le vocabulaire vit en source unique dans `meta.ts`
(`EPISODE_STATE_LABEL` / `EPISODE_STATE_TONE` / `EPISODE_STATE_HINT`).

## D1 — Le cache stocke les épisodes connus, la file ne prend que les diffusés

Séparation stricte, invariant central :

- **`poll_known(series, registry)`** (ou `poll_aired` élargi par un flag `include_future`)
  retourne TOUS les épisodes à date connue — diffusés **et** annoncés — chacun avec son
  `air_date`. **Un seul poll par série** (NE-DOIT-PAS-8 : le provider est déjà interrogé une
  fois, on ne filtre plus le résultat, on ne double pas les appels).
- Le cache `aired_episode` reçoit **tous** les épisodes connus (sémantique élargie ;
  `air_date` porte la distinction — pas de colonne ajoutée, pas de migration).
- **L'enfilage `wanted` garde le filtre `air_date <= today`** — un épisode futur n'est jamais
  enfilé (non cherchable sur les trackers). C'est l'invariant à tester en dur.

Le nom `aired_episode` devient légèrement impropre (il contient des futurs) mais renommer =
churn de migration sans bénéfice ; docstring mise à jour (« épisodes à date connue »).

## D2 — L'état `annonce`, dérivé

`states.py` : `EpisodeState` gagne `"annonce"`. `derive_episode_state` reçoit `air_date` +
`today` et retourne `"annonce"` **en tête** quand `air_date > today` (un épisode non diffusé
ne peut être ni possédé, ni cherché, ni en attente — c'est un futur, point). Les 5 règles
existantes s'appliquent inchangées aux diffusés.

L'agrégation de carte **ignore** les annoncés (un épisode futur ne rend pas une série « en
retard ») : `annonce` ne remonte pas au `FollowStatus` de la carte — une série dont tous les
diffusés sont en médiathèque reste « À jour » même si des épisodes futurs sont annoncés.

`SeasonCompleteness` : les compteurs (owned/queued/total) comptent les **diffusés** ; un
compteur `announced` séparé expose le nombre d'annoncés de la saison (pour l'affichage).

## D3 — UI : statut, légende, date au clic

- `meta.ts` : `annonce` ajouté aux 3 maps — label « Annoncé », un ton distinct (DS), hint
  « Sortie prévue » ; ordre de comptage inchangé (annonce hors des compteurs d'action).
- **Légende** (#9) : un composant sous la matrice d'épisodes listant chaque statut × sa
  couleur × son libellé, dérivé des maps `meta.ts` (source unique — la légende ne réécrit
  aucun label/ton). Une couleur par statut, distinctes et lisibles (light + dark).
- **Date au clic** (#10) : au clic/tap sur une puce, un popover/tooltip DS affiche la date —
  « Diffusé le {date} » (passé) / « Sortie prévue le {date} » (futur) — jamais le jeton brut.
  Portalisé (pas clippé par le shell). Accessible clavier.
- **MINOR #331 replié** : `ATraiterList` titre tronqué gagne un `title`/tooltip (même geste
  d'ergonomie clic/hover).

## ACC

| ID     | Critère                                                                                                                                                                              |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ACC-01 | Un épisode `air_date > today` va au cache mais **PAS** à la file `wanted` (test store+detect).                                                                                       |
| ACC-02 | `derive_episode_state(air_date>today, …)` ⇒ `annonce`, quelles que soient possession/verdict (rouge-avant).                                                                          |
| ACC-03 | Un futur annoncé ne dégrade PAS le `FollowStatus` de la carte (série à jour reste « À jour »).                                                                                       |
| ACC-04 | `poll_known` fait **un seul** appel provider par série (pas de doublement — spy).                                                                                                    |
| ACC-05 | UI : légende présente, 1 couleur/statut, dérivée de meta.ts ; date au clic sur diffusé ET annoncé, libellé français, jamais le jeton. Preuve 390 px (les popovers ne débordent pas). |
| ACC-06 | `make check` + `make openapi` (schema.d.ts régénéré, `annonce` + compteur `announced`).                                                                                              |

## Hors périmètre

Notifications de sortie ; calendrier ; les films (pas d'épisodes futurs).
