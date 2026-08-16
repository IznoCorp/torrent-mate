# Phase 7 — Filtre par nom sur les suivis (demande opérateur, 2026-08-05)

**Origine** : extension de périmètre demandée en cours d'implémentation, capture d'écran à
l'appui. Hors DESIGN initial — tracée ici plutôt que glissée dans une autre phase.
**Constitution servie** : §12 (mobile first), §8 (rien en silence).

## Gate

```bash
cd frontend && npm run lint && npx tsc -b --noEmit && npm run test -- --run
```

Attendu : portes frontend vertes.

## Le besoin

La liste des séries suivies ne fait que grandir (15 au moment de la demande). Retrouver un
titre impose de faire défiler l'ensemble. L'opérateur demande un champ de filtre par nom,
appliqué **au fil de la frappe**, placé entre la ligne de cadence (« Recherche automatique :
… ») et la première carte.

## Sous-phases

### 7.1 — Champ de filtre

`frontend/src/components/acquisition/FollowedPanel.tsx` : `Input type="search"` étiqueté
« Filtrer par nom », entre la légende de cadence et la liste. Pas de bouton de validation —
la liste est déjà en mémoire, un aller-retour serait de la latence pour rien.

### 7.2 — Normalisation

Insensible à la casse **et aux accents** (décomposition NFD + retrait des diacritiques) :
« evades » doit trouver « Les Évadés ». Un filtre qui exige les accents exacts est un filtre
contre lequel l'opérateur travaille.

### 7.3 — Ce que le filtre ne touche pas

Les compteurs des onglets `Séries (n)` / `Films (n)` restent **non filtrés** : ils répondent
à « combien j'en suis », pas à « combien correspondent à ma frappe ». Les filtrer ferait
muter l'onglet sous les doigts de l'opérateur.

### 7.4 — L'état vide dit la vérité

Une liste vidée **par le filtre** affiche « Aucun résultat pour « … » », jamais « Aucune série
suivie » — qui serait un mensonge sur l'état (§8).

### 7.5 — Tests

Cinq cas : filtrage au fil de la frappe, insensibilité casse/accents, filtre vide neutre,
message d'état vide correct, compteurs non filtrés.

## Fichiers

| Fichier | Nature |
| --- | --- |
| `frontend/src/components/acquisition/FollowedPanel.tsx` | champ + normalisation + états |
| `frontend/src/components/acquisition/FollowedPanel.test.tsx` | 5 tests |
