# Phase 4 — Fallback Disque + Auto-create Catégorie

## Objectif

Permettre au dispatch de placer de nouveaux médias sur un disque qui n'a pas encore le dossier de catégorie, en le créant automatiquement sur le disque le moins plein. Pour les médias existants (replace/merge), skip si le disque est plein — pas de déplacement inter-disque.

## Sous-phases

### 8.4.1 — Modifier choose_disk avec allow_create_category

- [ ] Ajouter paramètre `allow_create_category: bool = False` à `choose_disk()`
- [ ] Stratégie en 2 passes :
  - Pass 1 (inchangée) : disques avec la catégorie ET assez d'espace
  - Pass 2 (si pass 1 vide ET `allow_create_category=True`) : tous les disques montés avec assez d'espace, triés par espace libre
- [ ] Le dossier catégorie n'est PAS créé dans choose_disk — juste le choix du disque
- [ ] Écrire tests dans `test_disk_scanner.py` :
  - `allow_create_category=False` (défaut) → même comportement qu'avant
  - `allow_create_category=True` + catégorie existe → choisit normalement
  - `allow_create_category=True` + catégorie n'existe nulle part → choisit disque le plus libre
  - `allow_create_category=True` + catégorie existe mais disque plein → choisit autre disque
  - Aucun disque avec assez d'espace → None
- [ ] Vérifier que les 7 tests existants passent sans modification

**Commit** : `v8.4.1: Add allow_create_category to choose_disk()`

### 8.4.2 — Intégrer dans le dispatcher

- [ ] Modifier `dispatch_movie()` :
  - Existant (replace) : si disque plein → skip avec `reason="Disk {name} full, cannot replace"`
  - Nouveau : `choose_disk(..., allow_create_category=True)`
  - Si target trouvé : `dest.parent.mkdir(parents=True, exist_ok=True)` (crée la catégorie)
- [ ] Modifier `dispatch_tvshow()` : même logique
  - Existant (merge) : si disque plein → skip
  - Nouveau : allow_create_category=True
- [ ] Ajouter détection "disk full" pour existants :
  - Calculer item_size_gb, vérifier espace libre sur le disque existant
  - Si `free_space_gb < max(min_free_gb, item_size_gb * 1.5)` → skip
- [ ] Écrire tests dans `test_dispatcher.py` :
  - Movie replace + disk full → skip
  - Movie new + no category → category created + moved
  - TVShow merge + disk full → skip
  - TVShow new + no category → category created + moved
- [ ] Lancer tous les tests pour vérifier rétrocompatibilité

**Commit** : `v8.4.2: Integrate disk fallback and full-disk handling in dispatcher`
