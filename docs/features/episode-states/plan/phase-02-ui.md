# Phase 02 — UI : statut, légende, date au clic

**Goal**: la puce « Annoncé », la légende couleurs, la date au clic. Vocabulaire source-unique.

## Surface

| Fichier                                                                                      | Action                                                                                                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/components/acquisition/meta.ts`                                                | `annonce` dans `EPISODE_STATE_LABEL` (« Annoncé »), `EPISODE_STATE_TONE` (ton DS distinct des 5 autres), `EPISODE_STATE_HINT` (« Sortie prévue »). `COUNT_ORDER`/compteurs d'action **inchangés** (annonce n'est pas une action).                                                                             |
| `frontend/src/components/acquisition/CompletenessAccordion.tsx` (ou le composant de matrice) | rendre la puce `annonce` ; afficher les épisodes annoncés (le read-model les remonte désormais) ; **date au clic** : popover/tooltip DS portalisé (non clippé par le shell), « Diffusé le {date} » / « Sortie prévue le {date} », accessible clavier                                                          |
| `frontend/src/components/acquisition/…Legende.tsx`                                           | **NEW** — légende sous la matrice : une entrée par `EpisodeState`, couleur (du `EPISODE_STATE_TONE`) + libellé (`EPISODE_STATE_LABEL`) — **dérivée des maps, aucune réécriture** ; lisible light + dark                                                                                                       |
| `frontend/src/components/controle/ATraiterList.tsx`                                          | MINOR #331 : `title={…}` sur le titre tronqué (fallback hover)                                                                                                                                                                                                                                                |
| `frontend/src/components/layout/AppShell.tsx`                                                | **Tâche #11 repliée** : le bloc version+commit (`<VersionCard/>`, déjà source-unique) est invisible en mobile (il vit dans `Sidebar.tsx` `hidden md:flex`). L'ajouter au `SheetContent` du menu latéral mobile (après `NavSections`, même wrapper `border-t px-3 py-3`) — même composant, aucune duplication. |
| tests                                                                                        | légende dérive de meta.ts (pas de map en dur) ; puce annonce rendue ; date au clic (les 2 libellés) ; **VersionCard rendu dans le Sheet mobile** ; contrat de classe                                                                                                                                          |

## Règles

- La légende **consomme** meta.ts — un test vérifie qu'elle liste exactement les clés de
  `EPISODE_STATE_LABEL` (drift = échec).
- Popover portalisé (Radix/shadcn to body) : la garde mobile-shell clampe le shell, un
  popover inline serait coupé.
- Formats de date : locale FR lisible (« 3 août 2026 »), jamais l'ISO brut à l'écran.

## Gate

`cd frontend && npm run lint && npm run typecheck && npm run test` verts ; la légende dérive
de meta.ts (test) ; aucune régression des tests d'acquisition existants.
