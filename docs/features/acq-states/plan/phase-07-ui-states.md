# Phase 07 — UI : les 5 états en français

**Goal**: afficher les 5 états, en français clair, sur la carte et épisode par épisode groupé par
saison. L'UI **mappe** un état serveur vers un libellé et un ton — elle n'en dérive aucun.

**Constitution servie**: §5 (états visibles, épisode par épisode groupé par saison), DOIT-1
(compréhensible sans être ingénieur), NE-DOIT-PAS-4 (message obscur).

**Design**: `DESIGN.md` §3.1.

## Surface

| Fichier                                                         | Action                                    |
| --------------------------------------------------------------- | ----------------------------------------- |
| `frontend/src/components/acquisition/meta.ts`                   | 5 états dans `FOLLOW_STATUS_LABEL` + tons |
| `frontend/src/components/acquisition/FollowedPanel.tsx`         | rendu de la carte                         |
| `frontend/src/components/acquisition/CompletenessAccordion.tsx` | états par épisode                         |
| `frontend/src/api/schema.d.ts`                                  | régénéré par `make openapi`               |
| tests `*.test.tsx` associés                                     | un test par état                          |

## Vocabulaire (contraignant)

| État serveur            | Libellé série          | Libellé film           | Ton     |
| ----------------------- | ---------------------- | ---------------------- | ------- |
| `en_mediatheque`        | À jour                 | Acquis                 | success |
| `a_recuperer`           | À récupérer            | À récupérer            | warning |
| `en_acquisition`        | En cours d'acquisition | En cours d'acquisition | info    |
| `en_attente`            | En attente             | En attente             | neutral |
| `non_verifie`           | Non vérifié            | Non vérifié            | neutral |
| `verification_en_cours` | Vérification en cours  | Vérification en cours  | info    |
| `disabled`              | En pause               | En pause               | muted   |

`En attente` et `Non vérifié` partagent un ton neutre mais **ne doivent pas** se ressembler au
point d'être confondus : l'un dit « j'ai cherché, rien de prenable », l'autre « je ne sais pas
encore ». Le libellé porte la distinction ; une infobulle l'explicite.

Le vocabulaire existant (`FOLLOW_STATUS_LABEL`, `FOLLOW_STATUS_LABEL_MOVIE` dans `meta.ts`) est
**étendu**, pas dupliqué — la feature `systeme-hub` a déjà unifié ces maps, ne pas rouvrir la
divergence.

## Décisions d'implémentation

**Zéro dérivation en JSX.** Aucun `if (wanted_pending > 0)` côté client. Le composant lit
`item.status` et le mappe. Toute logique métier en TSX est un échec de phase.

**Motif d'attente lisible.** Quand un épisode est « En attente », l'interface dit pourquoi en
français à partir de `last_search_outcome` — « aucun résultat », « rien de conforme au profil »,
« pas d'épisode exact » — jamais le jeton machine brut (NE-DOIT-PAS-4).

**Mobile.** Vérification obligatoire à **390 px de large réel** via le harnais iframe : la
largeur du viewport Chrome est épinglée à 1440 px et `resize_window` ne déclenche pas le CSS
mobile. Auditer `scrollWidth - innerWidth == 0` sur les routes touchées.

## Sous-phases

### 7.1 — Vocabulaire + tons

**Commit**: `feat(acq-states): extend the follow-status vocabulary to five states`

### 7.2 — Carte

**Commit**: `feat(acq-states): render the five states on the follow card`

### 7.3 — Épisode par épisode

**Commit**: `feat(acq-states): per-episode states grouped by season`

### 7.4 — Motif d'attente

**Commit**: `feat(acq-states): explain in French why an episode is waiting`

## Gate

1. `npm run lint` **et** `npm run typecheck` **et** `npm run test` côté frontend — les trois,
   la lint est une gate CI distincte du typecheck.
2. `make lint` + `make test` côté backend.
3. `make openapi` ⇒ `openapi.json` + `schema.d.ts` régénérés **et commités**.
4. `rg -n "wanted_pending|wanted_grabbed|aired_count" -g '*.tsx' frontend/src/components/acquisition/` — aucune dérivation d'état en JSX.
5. Preuve mobile 390 px : capture par route touchée, `scrollWidth - innerWidth == 0`.
6. Les 7 états ont chacun un test de rendu.
