# Phase 03 — La garde couvre la surface qui mentait

**Défaut visé** : `scripts/check-acquisition-coherence.py` rend « 0 anomalie » au moment
exact où la file affiche 31 faux « En cours d'acquisition ». Sa règle
`UI_ACQUIRING_NO_TORRENT` (l.350-420) modélise la surface **Suivis** via
`governing_facts_by_episode` + `derive_episode_state` — jamais la file.

## 03.1 — `QUEUE_ABSORBED_DANGLING`

Une seule règle nouvelle, un seul mode de défaillance (la convention du script).

**Déclenche quand** : une ligne `wanted` de statut `absorbed` dont `absorbed_by` est NULL,
ou désigne une ligne inexistante. Le pointeur ne peut pas être suivi ; la file affiche alors
« En cours d'acquisition » sur une ignorance.

**Sévérité** : `warning`. Ce n'est pas un mensonge prouvé (la saison *pourrait* être en vol),
c'est une affirmation sans support — la §13 demande qu'on la voie, pas qu'on la traite comme
une erreur.

**Explication rendue** : nommer le pointeur (`absorbed_by=NULL` ou `absorbed_by=#N
introuvable`) et dire ce que l'écran affirme du coup. Le format du script est
`[RULE] title SxxEyy (wanted #id): explanation`.

Emplacement : à côté des autres règles par-ligne (boucle `for w in wanted_rows`, l.424+).
Les lignes `wanted` sont déjà chargées avec `absorbed_by` (l.325-327) — aucune requête
supplémentaire.

## 03.2 — Ce qui n'est délibérément PAS ajouté

Une seconde règle « la file affirme une acquisition en vol sans torrent derrière », analogue
de `UI_ACQUIRING_NO_TORRENT` pour la surface file, a été envisagée puis **écartée** (DESIGN
§4). Après correctif, les seuls statuts que la file affiche comme en vol sont :

- `grabbed` sans torrent → c'est exactement `GRABBED_HASH_MISSING`, mode déjà couvert ;
- `absorbed` pendant → c'est `QUEUE_ABSORBED_DANGLING`, ci-dessus.

La règle ne pourrait donc jamais tirer sur autre chose qu'un doublon. **Une règle de garde
incapable de se déclencher est un faux témoin** : elle donne le sentiment d'une couverture
sans en fournir. Cette phase n'en écrit pas.

## 03.3 — Tests de la règle

Fichier : le module de test existant du script de cohérence (le localiser ; ne pas en créer
un second si l'existant couvre déjà les règles par-ligne).

Trois fixtures, une par comportement :

1. `absorbed` + `absorbed_by=NULL` → **1** anomalie `QUEUE_ABSORBED_DANGLING`.
2. `absorbed` + `absorbed_by` pointant vers une ligne absente → **1** anomalie.
3. `absorbed` + `absorbed_by` pointant vers une ligne saison **existante** → **0** anomalie.
   C'est le cas des 31 lignes réelles : la règle ne doit pas les signaler, sinon la garde
   passe de muette à criarde et devient tout aussi inutilisable.

## 03.4 — Vérification de non-régression de la garde

Après ajout, relancer `scripts/check-acquisition-coherence.py` sur les **données réelles** :
il doit toujours rendre **0 anomalie** — les 31 pointeurs réels sont tous résolvables. Un
non-zéro ici signifierait soit une règle trop large, soit une anomalie de données réelle à
instruire (et dans ce cas : l'instruire, pas la faire taire).

## Critères de sortie

- Les 3 tests de fixture passent.
- Le script rend 0 anomalie sur les données réelles.
- `make check` vert.
