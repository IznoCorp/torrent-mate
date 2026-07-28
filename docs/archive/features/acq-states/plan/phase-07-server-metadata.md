# Phase 07 — Enrichissement serveur des métadonnées

**Goal**: le serveur récupère lui-même poster / overview / year quand le client ne les fournit
pas. Ferme la classe de bug entière plutôt qu'un seul chemin d'ajout.

**Constitution servie**: §5 (l'ajout par recherche), DOIT-1 (tout montrer).

**Design**: `DESIGN.md` §2 RC3 + §4 D4.

## Le défaut corrigé

Le poster ne provient **que** du candidat de recherche envoyé par le client
(`_write_follow_metadata` sort si les trois champs sont nuls). Le formulaire d'ajout manuel par
ID TVDB (`FollowedPanel.tsx:159`) n'envoie que `{tvdb_id, kind, title}` — donc aucun poster,
jamais, pour ce chemin. Or l'information existait : TVDB expose **6 posters** pour la série
468000 et `/search` renvoie l'URL.

Aggravant relevé après dispatch : la médiathèque contient `poster.jpg` pour Furious pendant que
la carte d'acquisition reste vide — deux champs indépendants que rien ne réconcilie.

## Surface

| Fichier                                                | Action                                                           |
| ------------------------------------------------------ | ---------------------------------------------------------------- |
| `personalscraper/web/routes/acquisition.py`            | `create_follow` enrichit côté serveur quand le client se tait    |
| `personalscraper/commands/follow.py`                   | le backfill CLI réutilise la même fonction (plus de duplication) |
| `tests/unit/web/routes/test_create_follow_metadata.py` | **NEW** — reproduit RC3                                          |

## Décisions d'implémentation

**Le serveur est responsable, pas le client.** On ne corrige pas `FollowedPanel.tsx` pour qu'il
envoie le poster : on rend le serveur capable de se débrouiller quel que soit l'appelant. Un
futur chemin d'ajout (CLI, script, API tierce) hérite de la correction sans y penser.

**Une seule fonction d'enrichissement**, partagée entre `create_follow` et le backfill CLI de
`commands/follow.py:597` — aujourd'hui deux implémentations pour le même besoin.

**Fail-soft, jamais bloquant.** Un provider injoignable ne doit pas faire échouer la création du
suivi : le follow est créé, les métadonnées restent nulles, et l'amorce de la phase 5 les
rattrapera. Le suivi lui-même prime sur sa vignette.

**Ordre des sources** : le candidat client s'il en fournit un (il vient d'une recherche que
l'opérateur a validée visuellement), sinon le provider par ID, en respectant la séparation
stricte TVDB primaire / TMDB en complément.

**Repli médiathèque** : quand aucun provider ne rend de poster mais que la médiathèque en a un
pour ce provider-ID, la carte l'utilise — précédent existant, `season_count` est déjà backfillé
depuis l'indexeur.

## Sous-phases

### 7.1 — Test-first : reproduire RC3

**Commit**: `test(acq-states): a follow added by ID alone still gets its poster`

```python
def test_follow_added_by_tvdb_id_alone_gets_server_side_metadata() -> None:
    """Adding by bare TVDB id must still yield poster + overview + year.

    Reproduces the founding incident: Furious was added through the manual
    by-ID form, which posts {tvdb_id, kind, title} and nothing else, so
    _write_follow_metadata early-returned on three NULLs and the card stayed
    posterless forever — while TVDB exposed six posters for that very series.
    """


def test_provider_outage_does_not_fail_follow_creation() -> None:
    """Metadata enrichment is a nicety; the follow itself must still be created."""
```

### 7.2 — L'enrichissement serveur

**Commit**: `feat(acq-states): enrich follow metadata server-side on every add path`

### 7.3 — Réparation des suivis existants

**Commit**: `feat(acq-states): backfill metadata for follows added before this fix`

Le backfill CLI existant est réutilisé (pas réécrit) et étendu à `year`. À exécuter une fois sur
la base réelle après merge — Furious (id 10) en est le premier bénéficiaire.

## Gate

1. `make lint` + `make test`.
2. Les deux tests de 7.1 échouaient avant 7.2, passent après.
3. `rg -n "poster_url" --type py personalscraper/web/routes/acquisition.py` — une seule
   fonction d'enrichissement, partagée.
4. Sur la base réelle : `sqlite3 .data/acquire.db "SELECT id,title,poster_url IS NOT NULL FROM followed_series"` — aucune ligne sans poster après backfill, sauf absence provider avérée.
5. Une panne provider simulée ne fait pas échouer la création (test).
6. `make openapi` si le contrat change.
