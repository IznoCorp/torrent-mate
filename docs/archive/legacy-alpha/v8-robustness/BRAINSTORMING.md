# V8 — ROBUSTNESS : Brainstorming

> Durcissement du pipeline existant : circuit breaker, anti-faux-positifs, rollback dispatch, fallback disque, timeout E2E.

## Contexte

V0-V7 sont implémentées et stables (710 tests passants, 79% couverture). L'audit a révélé 5 points de fragilité dans le pipeline qui ne provoquent pas de crashs immédiats mais peuvent causer des comportements incorrects ou des blocages silencieux.

V8 ne crée pas de nouvelles fonctionnalités — elle renforce les modules existants. Tous les tests V0-V7 doivent continuer à passer après chaque modification.

## Décisions prises

### D1 — Circuit breaker TMDB/TVDB

**Comportement en 2 temps :**

1. **Cooldown d'abord** — Après 5 erreurs consécutives sur un provider, attendre 5 minutes puis réessayer
2. **Fallback ensuite** — Si le cooldown échoue, switcher vers le provider alternatif (TMDB↔TVDB). Si les deux providers sont down, skip les items restants avec log warning

**Erreurs comptées :** 5xx, timeout, ConnectionError. Les 429 (rate limit) sont déjà gérés par tenacity avec Retry-After — ne pas les compter dans le circuit breaker.

**Raison :** Le retry tenacity gère les erreurs transitoires (1-2 échecs). Le circuit breaker gère les pannes durables (provider down). Le cooldown évite de spammer un provider en difficulté.

### D2 — Anti-faux-positifs fuzzy matching

**Stratégie combinée (approche D) :**

- Contrainte d'année : ±1 an maximum entre le titre cherché et le candidat
- Contrainte de longueur : ratio longueur titre ≤ 1.5x (empêche "Matrix" de matcher "The Matrix Reloaded")
- Seuil adaptatif : titres courts (≤ 10 chars) → seuil 95%, titres longs (> 10 chars) → seuil 90%
- Le scorer WRatio + media_processor reste inchangé

**Raison :** Un seuil fixe ne suffit pas — les titres courts sont plus sensibles aux faux positifs (ex: "Matrix" vs "Matrix Reloaded" score ~88%). La contrainte multi-critères est plus robuste qu'un simple seuil élevé.

### D3 — Rollback dispatch

**Pattern staging → commit :**

1. rsync vers un dossier temporaire `_tmp_dispatch_{name}` sur le disque cible
2. Si rsync réussit → atomic rename (os.replace) du tmp vers la destination finale
3. Si rsync échoue → supprimer le dossier tmp, log l'erreur, remettre la source en staging (skip cet item)

**Raison :** L'atomic swap garantit qu'à tout moment le disque cible contient soit l'ancien dossier complet, soit le nouveau complet — jamais un état partiel. Le pattern est standard pour les bases de données (WAL).

### D4 — Fallback disque + auto-create catégorie

**Pour les nouveaux médias (action = "moved") :**

- Ordre de préférence : disques ayant déjà la catégorie, triés par espace libre
- Si aucun disque n'a la catégorie : créer le dossier catégorie sur le disque le moins plein
- Si un disque a la catégorie mais est plein : créer sur un autre disque avec de l'espace (spread automatique)

**Pour les médias existants (action = "replace" / "merge") :**

- Si le disque contenant l'existant est plein : skip avec log warning
- Pas de déplacement automatique d'existants entre disques (trop risqué, impact Kodi)

**Raison :** Les nouveaux médias n'ont pas d'historique, le spread est sans risque. Les existants sont référencés par Kodi/Plex — les déplacer casserait les liens.

### D5 — Timeout dynamique E2E

**Formule :** `timeout_minutes = ceil(size_gb) * 3`

**Exemple :** fichier 12.6 Go → ceil(12.6) = 13 → 13 × 3 = 39 minutes

**Scope :** Uniquement `tests/e2e/setup_torrents.py:wait_for_completion()`. Le pipeline production (V1 ingest) ne fait jamais de wait — il traite les torrents déjà complétés.

**Comportement au timeout :** `TimeoutError` avec message explicite (taille, temps attendu, temps écoulé). Le test est marqué FAILED (pas skip).

**Raison :** Les tests E2E utilisent des torrents de trackers privés dont le débit est imprévisible. 3 min/Go est un seuil raisonnable (≈5.7 MB/s minimum requis). Sans timeout, un test peut bloquer indéfiniment.

## Contraintes techniques

1. **Rétrocompatibilité** — Les 710 tests existants doivent passer sans modification (sauf les tests E2E qui testent le timeout)
2. **Pas de nouvelle dépendance** — Le circuit breaker est implémenté en interne (pas de lib externe type pybreaker)
3. **Tenacity reste en place** — Le circuit breaker s'ajoute PAR-DESSUS le retry tenacity, pas en remplacement
4. **media_processor partagé** — Les changements de fuzzy matching doivent être cohérents entre V2 (matcher), V3 (confidence), V5 (media_index)
5. **rsync reste le transport** — Le rollback s'adapte à rsync, pas de changement de mécanisme de transfert
6. **Disk categories** — La table DISK_CATEGORIES dans dispatcher.py reste la source de vérité pour les catégories par disque

## Flux proposé

```
                    ┌──────────────────────────────┐
                    │     Circuit Breaker Layer     │
                    │  (wraps TMDB/TVDB clients)    │
                    │                               │
                    │  5 errors → cooldown 5min     │
                    │  still failing → switch to    │
                    │  fallback provider             │
                    │  both down → skip remaining   │
                    └──────────────────────────────┘
                                 │
                    ┌──────────────────────────────┐
                    │     Fuzzy Match Guards        │
                    │  (media_index + matcher)      │
                    │                               │
                    │  year: ±1 an                  │
                    │  length: ratio ≤ 1.5x         │
                    │  score: ≤10ch→95%, >10→90%    │
                    └──────────────────────────────┘
                                 │
                    ┌──────────────────────────────┐
                    │   Dispatch Transaction        │
                    │  (dispatcher.py)              │
                    │                               │
                    │  1. rsync → _tmp_dispatch_X   │
                    │  2. success → atomic rename   │
                    │  3. failure → delete tmp      │
                    └──────────────────────────────┘
                                 │
                    ┌──────────────────────────────┐
                    │   Disk Fallback               │
                    │  (disk_scanner.py)            │
                    │                               │
                    │  new: prefer existing cat     │
                    │       → spread if none fits   │
                    │  existing: skip if disk full  │
                    └──────────────────────────────┘
                                 │
                    ┌──────────────────────────────┐
                    │   E2E Timeout                 │
                    │  (setup_torrents.py)          │
                    │                               │
                    │  ceil(GB) × 3 min             │
                    │  TimeoutError on expiry       │
                    └──────────────────────────────┘
```

## Points de design à trancher

Aucun — toutes les questions ont été tranchées lors du brainstorming.
