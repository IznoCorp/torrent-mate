# La file d'acquisition suit le pointeur d'absorption

- **Codename** : `file-absorbee`
- **Type** : `fix`
- **Bump** : bugfix — 0.84.0 → 0.84.1
- **Ticket** : #411
- **Date** : 2026-08-05

---

## 1. Le défaut

Onglet **Acquisition → File d'acquisition**. `American Dad!` affiche S15E21, S15E22,
S17E23 et S17E24 en **« En cours d'acquisition »** alors que plus rien n'est en cours.

### Vérité des données (`.data/acquire.db`, lecture seule, 2026-08-05)

| ligne wanted | statut BDD | `absorbed_by` | saison pointée      |
| ------------ | ---------- | ------------- | ------------------- |
| #5 S15E21    | `absorbed` | 88            | #88 `done`/`grabbed` |
| #6 S15E22    | `absorbed` | 88            | #88 `done`/`grabbed` |
| #7 S17E23    | `absorbed` | 89            | #89 `done`/`grabbed` |
| #8 S17E24    | `absorbed` | 89            | #89 `done`/`grabbed` |

Dernière recherche épisode : 2026-07-28. Saisons grabbées : 2026-08-05 03:20. Les quatre
fichiers sont présents et non supprimés dans `library.db` (`S15E21 - Fleabiscuit.mkv`,
`S15E22 - The Future is Borax.mkv`, `S17E23 - 300.mkv`, `S17E24 - Yule. Tide. Repeat..mkv`).

### Cause racine

La file **rapporte le pointeur d'absorption au lieu de le suivre** :

1. `GET /api/acquisition/wanted` sert le statut brut —
   `personalscraper/web/routes/acquisition.py:516` : `status=row["status"]`.
2. Le frontend rend `absorbed` par une **constante** —
   `frontend/src/components/acquisition/meta.ts:145` : `absorbed: "En cours d'acquisition"`.

§13, littéralement : « Aucun état affiché n'est une constante. Un état qui *pointe* vers
autre chose (un épisode "absorbé" par une saison) doit **suivre le pointeur**, jamais le
rapporter tel quel. » Et : « Une seule dérivation par question. »

Le seam de vérité existe déjà — `substitute_absorbed_facts` / `governing_facts_by_episode`
(`personalscraper/web/acquisition/states.py`), posé par #398 le 2026-08-04. Il a converti
la carte et la matrice de complétude. **La file n'a jamais été convertie.**

### Ampleur

**31 lignes sur 94**, pas 4 : toutes les lignes `absorbed` de la base pointent vers une
saison `done`. Un tiers de la file ment.

### La garde a le même trou

`scripts/check-acquisition-coherence.py` rend **« 0 anomalie »** à l'instant où l'écran
affiche 31 faux « En cours d'acquisition ». Sa règle `UI_ACQUIRING_NO_TORRENT` calcule ce
que lit l'opérateur via `governing_facts_by_episode` + `derive_episode_state` — la
dérivation *corrigée*, celle de l'onglet Suivis. Elle ne modélise nulle part ce que la
**file** affiche.

---

## 2. Décisions arbitrées par l'opérateur

| # | Décision | Portée |
| - | -------- | ------ |
| D1 | Une ligne absorbée affiche **le statut de sa saison, tel quel**. S15E21 lit « Terminé », comme la ligne « Saison 15 » au-dessus. | Affichage |
| D2 | La résolution passe par le **seam partagé** `substitute_absorbed_facts`, jamais par une seconde implémentation de la règle. | Architecture |
| D3 | Pointeur pendant (`absorbed_by` NULL, ou saison absente — la table est advisory, pas de FK) : la ligne **garde** `absorbed`. Une ignorance ne se troque pas contre un autre mensonge. | Cas limite |
| D4 | Le filtre « Statut » suit le pointeur — mais **en JavaScript**, dans le panneau, pas en SQL ni en Python. Le panneau charge déjà toutes les lignes. | Filtre |

D4 mérite sa justification : filtrer sur le statut résolu **en SQL** (`LEFT JOIN` +
`CASE WHEN`) serait une deuxième implémentation de la règle, exactement ce que la §13
désigne comme la garantie d'une divergence. Filtrer **en JS sur la valeur déjà résolue par
le backend** donne une seule dérivation, et le filtre lit littéralement la même valeur que
la pastille.

---

## 3. Architecture

### 3.1 Backend — `GET /api/acquisition/wanted`

`personalscraper/web/routes/acquisition.py`, fonction `get_wanted`.

Aujourd'hui la route lit une page de lignes puis sert `row["status"]` verbatim.

Après :

1. La page de lignes est lue comme aujourd'hui (même `ORDER BY w.enqueued_at DESC`, même
   `LIMIT`/`OFFSET`, même clause `WHERE` — **inchangée**, cf. §3.4).
2. Les `absorbed_by` non-NULL de la page sont collectés ; **une** requête charge les lignes
   saison correspondantes (`SELECT id, status, last_search_outcome, last_search_found
   FROM wanted WHERE id IN (…)`). Les lignes saison peuvent être sur une autre page — d'où
   la requête dédiée plutôt qu'une lecture de la page courante.
3. Les lignes de la page passent par `substitute_absorbed_facts` avec ce
   `season_facts`. Le statut servi est le statut résolu.
4. Pointeur non résolvable → `substitute_absorbed_facts` conserve `absorbed` (D3), sans
   traitement particulier côté route : la règle est dans le seam.

La route n'implémente **aucune** logique de résolution : elle appelle le seam.

### 3.2 Frontend — le panneau vivant

`frontend/src/components/acquisition/FileDAcquisitionPanel.tsx` charge déjà **toutes** les
pages (`ALL_PAGE_SIZE`, boucle jusqu'à `HARD_CAP`) et groupe côté client.

Après : le panneau **cesse d'envoyer `status`** à l'API (fetch toujours « tous ») et filtre
en JS sur le statut résolu reçu. Conséquences :

- Le filtre et la pastille lisent la **même** valeur — coïncidence garantie par
  construction, pas par convention.
- Le compte affiché (« N résultats ») devient le compte **filtré** côté client.
- La clé de requête TanStack ne dépend plus du filtre : changer de filtre ne re-fetch plus,
  il re-filtre.

`WantedPanel.tsx` est **superseded et non monté** (son en-tête le déclare). Il n'est pas
modifié ; il continue d'utiliser le filtre serveur, sans effet sur l'interface.

### 3.3 Frontend — le vocabulaire

`frontend/src/components/acquisition/meta.ts` :

- `STATUS_LABEL.absorbed` **reste** « En cours d'acquisition » et `STATUS_TONE.absorbed`
  reste `info` — mais ne décrivent plus que le **pointeur pendant** (D3), seul cas où
  l'API sert encore `absorbed`.
- Deux commentaires portent le raisonnement périmé et deviennent **faux** :
  - `meta.ts:117-119` — « `absorbed` … il lit déjà "En cours d'acquisition" dans la file ».
  - `meta.ts:504-506` et `meta.ts:525` — « Un épisode absorbé EST un épisode en cours
    d'acquisition ».
  Ils sont réécrits : un épisode absorbé n'est « en cours » que **tant que sa saison l'est**.
- `meta.test.ts` épingle l'alias avec ce même raisonnement (« the backend already reads it
  that way: states.py maps absorbed -> en_acquisition »). Le test reste — l'alias reste vrai
  pour le cas pendant — mais sa justification est corrigée.

### 3.4 Ce qui n'est délibérément PAS touché

- **La clause `WHERE` de la route.** Le paramètre `status=` continue de filtrer sur le
  statut *stocké*. Un consommateur direct de l'API demandant `status=done` n'obtiendra donc
  pas les lignes absorbées dont la saison est terminée. C'est inerte aujourd'hui — le seul
  panneau monté cesse d'utiliser ce paramètre (§3.2) — et c'est le prix accepté de D4 :
  aucune seconde implémentation de la règle. **Écart assumé, consigné ici.**
- **Les compteurs.** Le badge de `AppShell` et `AcquisitionSummaryCard` comptent
  `status=pending` : insensibles à l'absorption (vérifié).

---

## 4. La garde

`scripts/check-acquisition-coherence.py` doit couvrir la surface qui ment. **Une** règle
nouvelle, un mode de défaillance (la convention du script) :

| Règle | Déclenche quand | Sévérité |
| ----- | --------------- | -------- |
| `QUEUE_ABSORBED_DANGLING` | une ligne `absorbed` dont `absorbed_by` est NULL ou pointe vers une ligne inexistante : le pointeur ne peut pas être suivi, et la file affirme « En cours d'acquisition » sur une **ignorance**. | warning |

**Pourquoi une seule, et pas deux.** Une deuxième règle du type « la file affirme une
acquisition en vol sans torrent derrière » avait été envisagée, en analogue de
`UI_ACQUIRING_NO_TORRENT` (qui ne couvre que la surface Suivis). Elle est **écartée** :
après correctif, les seuls statuts que la file affiche comme étant en vol sont `grabbed` —
dont l'absence de torrent est déjà exactement `GRABBED_HASH_MISSING` — et le `absorbed`
pendant, qui est le mode de `QUEUE_ABSORBED_DANGLING`. Cette règle ne pourrait donc jamais
tirer sur autre chose qu'un doublon. Une règle de garde incapable de se déclencher est un
faux témoin : elle donne le sentiment d'une couverture sans en fournir.

**Ce que la garde ne peut pas faire, et pourquoi les tests s'en chargent** : la garde
appelle le même seam que la route. Elle détecte donc les anomalies de **données**, jamais
une divergence de **code** entre ce que la route sert et ce que le seam résout. Cette
divergence-là est du ressort des tests (§5), pas d'un contrôle runtime — le prétendre
serait circulaire.

### État existant (§13.4)

§13 exige : « (1) le code corrigé, (2) l'état existant réparé, (3) le contrôle exécutable à
zéro anomalie ». Ici **il n'y a pas d'état à réparer**, et c'est un constat vérifié, pas une
hypothèse : les 31 lignes `absorbed` pointent toutes vers une ligne saison qui **existe** et
vaut `done`. La base était cohérente ; seule la lecture mentait. Le constat est re-vérifié
après le correctif plutôt qu'affirmé.

---

## 5. Tests

| Test | Prouve |
| ---- | ------ |
| Régression route — 4 lignes American Dad (S15E21/E22, S17E23/E24, `absorbed` → saison `done`) | la route sert `done`, pas `absorbed`. **Écrit et rouge avant le fix.** |
| Route — pointeur pendant (`absorbed_by` NULL) et pointeur cassé (saison inexistante) | la route sert `absorbed` (D3). |
| Route — la ligne saison référencée est sur une **autre page** | la résolution ne dépend pas de la pagination. |
| Route — saison `pending` / `searching` | la ligne absorbée suit sa saison **vivante** aussi, pas seulement terminée. |
| Panneau — filtre JS sur statut résolu | choisir « Terminé » ramène les lignes absorbées résolues ; le compte suit. |
| Garde — `QUEUE_ABSORBED_DANGLING` sur fixtures (pointeur NULL, pointeur cassé, pointeur sain) | la règle tire sur son mode, et **seulement** sur le sien. |

---

## 6. Critères d'acceptation

1. Sur les **données réelles**, `GET /api/acquisition/wanted` sert `done` pour les lignes
   #5, #6, #7, #8 — et pour les 31 lignes `absorbed`.
2. L'écran **File d'acquisition** affiche « Terminé » sur ces lignes, vérifié en Chrome à
   **390 px** (largeur mobile réelle, cf. harnais iframe).
3. `scripts/check-acquisition-coherence.py` rend **0 anomalie** sur les données réelles
   **après** correctif.
4. Le filtre « Terminé » ramène les lignes absorbées résolues.
5. `make check` vert ; OpenAPI régénéré et commité (la CI échoue sur la dérive sinon).
6. Aucun verdict « conforme » sans déroulé daté sur données réelles.
