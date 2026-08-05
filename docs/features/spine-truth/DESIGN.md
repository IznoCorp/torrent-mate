# DESIGN — `spine-truth` : la spine de provenance ne perd plus aucun parcours

**Type**: fix · **Bump**: 0.79.2 → 0.80.0 (minor — migration + nouvelle règle de garde + backfill)
**Branche**: `fix/spine-truth`
**Constitution servie**: §13 (l'interface reflète l'état réel des données), §12 (mobile first),
§8 (rien en silence), DOIT-1, NE-DOIT-PAS-5.

Source du diagnostic : `docs/analysis/2026-08-05-provenance-spine-hole-handoff.md`. Le diagnostic
n'est pas refait ici ; ce document ajoute **le mécanisme exact de la cause B**, établi depuis les
logs prod, parce que la conception du correctif en dépend.

---

## 1. Le mécanisme exact (cause B, établi 2026-08-05 depuis `~/.pm2/logs/personalscraper-watch-error.log`)

Le journal du watch couvre 2026-07-08 → 2026-08-05 sans rotation. Il montre le parcours réel
d'un item TV (run `2026-08-05T03:40:50`) :

```
torrent_marked   dest_path='…/A TRIER/097-TEMP/American.Dad.S15.…-FRAIG'  hash=d412a663…
sort_item_moved  dest='…/A TRIER/002-TVSHOWS/American Dad/American.Dad.S15.…-FRAIG'
media_folder_renamed  source='American Dad'  dest='American Dad! (2005)'
```

Trois faits, tous vérifiables sur ces trois lignes :

1. **Le sort imbrique.** Un item TV n'atterrit pas à plat dans `002-TVSHOWS/` : il atterrit dans
   `002-TVSHOWS/{show}/{dossier de release}`. La spine enregistre donc
   `current_path = …/002-TVSHOWS/American Dad/American.Dad.S15.…-FRAIG`.
2. **Le scrape renomme l'ANCÊTRE.** `_track_scrape_rename` appelle
   `move_path(input_dir, final)` avec `input_dir = …/002-TVSHOWS/American Dad` — le dossier de
   **show**, pas le dossier de release. Or `move_path` fait un `UPDATE … WHERE current_path IN (?, ?)`,
   c'est-à-dire une **égalité exacte**. Le `current_path` de la ligne est un **descendant** de
   `input_dir`, pas `input_dir` : **l'UPDATE matche 0 ligne**.
3. **Le dossier de release disparaît.** Le scrape aplatit les épisodes dans `Saison NN/` et
   supprime le dossier de release. À partir de cet instant `current_path` désigne un chemin qui
   n'existe plus ET dont l'ancêtre a été renommé.

Conséquence en chaîne : `record_dispatch_by_path(staging_source = …/American Dad! (2005))` ne
matche rien (le `current_path` stocké est un descendant de l'ancien nom du show), la ligne reste
« en vol », puis `prune_stale` — qui supprime toute ligne non `dispatched` dont le `current_path`
a disparu — l'efface. **47 lignes `wanted done|episode` ont été perdues ainsi.**

Un **film** survit parce que le sort le pose à plat (`001-MOVIES/Marjorie Prime (2017)`) sous son
nom déjà canonique : aucun renommage de scrape, `current_path` reste exact et égal à la source de
dispatch. D'où l'unique survivant, un film — exactement ce que l'opérateur voit.

**La cause A** (le `CHECK (kind IN ('movie','episode'))` qui rejette `kind='season'` depuis
season-grab #378) est indépendante et déjà prouvée : 7 `acquire.provenance.write_failed` dans les
logs, 6 `wanted` de kind `season` porteurs d'un hash, zéro ligne de spine.

**Ce que le mécanisme impose au correctif** : le problème n'est pas « le chemin bouge » au sens
d'un renommage manqué — c'est que **la clé de jointure est une égalité de chaîne sur un chemin
dont un ANCÊTRE est renommé et dont le nœud lui-même est supprimé**. Aucune discipline
supplémentaire d'appel à `move_path` ne ferme ça : c'est la sémantique de l'opération qui est
fausse.

---

## 2. Décision de conception n°1 — d'où vient le hash au dispatch ?

**Réponse : `dispatch/run.py` n'a PAS le hash, et il ne peut pas l'avoir.**

Vérifié dans le code : le dispatch itère des **dossiers d'item** de staging
(`Dispatcher.dispatch_movie` / `dispatch_tvshow` ← `disk_scanner`), et l'unique point qui touche
la spine est `DeleteAuthority.record_dispatch(staging_source, dispatched_dest)`
(`personalscraper/acquire/delete_authority.py:264`). Les deux voies possibles pour un hash y sont
mortes :

- **Corrélation client torrent** (`get_completed()` + nom/taille) : le commentaire de
  `_grab_pass._record_seed_obligation` le dit déjà et les logs le confirment — pour une série le
  nom du dossier dispatché (`American Dad! (2005)`) ne sera **jamais** le nom de la release. De
  plus, aucun `acquire.record_dispatch.hit|miss` n'apparaît dans un mois de logs : sous PM2 le
  recorder n'a pas de client torrent du tout.
- **`.data/ingested_torrents.json`** (le pont proposé dans le handoff) : il porte
  `hash → {name, dest_path}` où `dest_path` est le chemin **d'ingest**, et `sort` appelle
  `prune_consumed_dest_paths` juste après. Il n'apporte rien de plus que la colonne `ingest_path`
  que la spine possède déjà.

**Donc le hash descend de l'ingest, et son unique porteur durable entre deux invocations CLI est
la spine elle-même.** La correction porte alors sur les deux seules choses qui rendaient ce
porteur inutilisable :

### 2.a — `move_path` devient une opération de SOUS-ARBRE (et non d'égalité)

`move_path(old_root, new_root)` signifie désormais ce qu'elle a toujours voulu dire :
« l'arborescence qui était en `old_root` est maintenant en `new_root` ».

- une ligne dont `current_path == old_root` → `new_root` (comportement actuel, préservé) ;
- une ligne dont `current_path` est **sous** `old_root` → `new_root` également (**collapse**).

Le collapse n'est pas une approximation : au moment où le scrape appelle `move_path`, il a déjà
aplati les dossiers de release dans `Saison NN/` et les a supprimés. **Le dossier de show EST la
localisation vivante de l'item.** Écrire autre chose serait inventer.

La résolution se fait en Python sur les composants de chemin (pas de `LIKE`, dont les
métacaractères `%`/`_` sont légaux dans un nom de fichier), en NFC/NFD, et **l'écriture est faite
par `info_hash`** — la clé stable. C'est le point exact du mandat : le chemin redevient une
*entrée de recherche*, jamais une clé d'écriture.

### 2.b — le dispatch corrèle par contenance, écrit par hash

`record_dispatch_by_path(staging_source, …)` devient :

1. `resolve_hashes_under(staging_source)` → les `info_hash` des lignes non terminales dont le
   `current_path` est `staging_source` **ou un descendant** de `staging_source` ;
2. pour chacun : `set_dispatch(info_hash, …)` — **UPDATE keyé sur `info_hash`**.

La contenance est la relation vraie : dispatcher `…/American Dad! (2005)` dispatche bien les deux
packs de saison qu'il contient. C'est aussi la ceinture de sécurité si une étape future oublie de
re-pointer : une ligne restée en descendant est quand même clôturée.

`prune_stale` gagne la même protection : une ligne en vol dont le `current_path` a disparu **mais
qui vit sous un dossier de staging encore présent** n'est pas orpheline — elle est en cours de
traitement. Sans ça, le correctif du dispatch serait annulé par le prune dans tout run où le
dispatch est sauté.

---

## 3. Migration 015 — le `CHECK` accepte `season`

SQLite ne modifie pas un `CHECK` en place → reconstruction de table (même patron que 013) :
table neuve avec le `CHECK` élargi + **toutes** les colonnes F0/F2/F3, copie, bascule,
recréation des **deux** index (`idx_provenance_current_path`,
`idx_provenance_resolution_state` partiel), `schema_version` + `user_version = 15` dans la même
transaction.

---

## 4. Fermer le trou — trois gardes, une défaillance chacune

| Garde | Ce qu'elle voit — et qu'elle SEULE voit | Où |
| --- | --- | --- |
| **G1** — égalité `CHECK kind` ↔ `WantedKind` | un `kind` du domaine que la table rejetterait | test unitaire comportemental |
| **G2** — `SPINE_ROW_MISSING` | un `wanted` porteur d'un `grabbed_hash` **sans aucune ligne** de spine : l'écriture du grab a été rejetée/perdue (la forme exacte de la cause A) | `check-acquisition-coherence.py` |
| **G3** — `SPINE_DISPATCH_MISSING` | un `wanted` `done` porteur d'un `grabbed_hash` dont la ligne de spine **existe mais n'est pas** `dispatched` : le parcours s'est arrêté en route (la forme exacte de la cause B) | `check-acquisition-coherence.py` |

**G1 est comportementale, pas déclarative.** Elle n'inspecte pas le texte du `CHECK` dans
`sqlite_master` : pour **chaque** littéral de `WantedKind`, elle fait un `upsert_grab` réel sur une
base migrée et exige que la ligne soit là. Un test qui lit le texte du `CHECK` passerait encore si
le store cessait d'écrire `kind` ; celui-ci teste ce que le domaine peut réellement enregistrer.

**G2 ≠ G3 : une règle = un mode de défaillance** (leçon de la session précédente). G2 ne voit que
l'absence totale de ligne, G3 que la ligne présente mais non terminée. Aucune ne double
`GRABBED_HASH_MISSING`, qui parle du client torrent.

**Le `log.warning` muet disparaît** : `_safe_write` remonte en `log.error` avec `exc_info` et le
nom de l'opération fautive. C'est ce qui a caché le bug quatre jours ; la trace devient
grep-able et l'anomalie devient **exécutable** via G2 — la forme que §méthode reconnaît comme
preuve.

---

## 5. Réparer l'état (§13)

`scripts/backfill-provenance-spine.py`, **dry-run par défaut**, `--apply` pour écrire.

| Champ | Source | Exactitude |
| --- | --- | --- |
| `info_hash`, `kind`, `media_ref_json`, `followed_id` | `wanted` | exacte |
| `grabbed_at` | `seed_obligation.added_at` (posée au grab depuis 2026-07-15) | exacte quand elle existe, sinon NULL |
| `dispatch_path` | `library.db` → `item_attribute[key='dispatch_path']` de l'item joint par provider-ID, **la valeur que le dispatcher lui-même a écrite** | exacte |
| `dispatched_at` | `media_file.last_verified_at` du fichier de l'œuvre | à la minute |
| `status` | `dispatched` si un chemin de dispatch est établi, sinon `grabbed` | dérivé |
| `ingest_path`, `current_path`, `scraped_at`, `*_run_uid` | — | **NULL, jamais inventés** |

Une ligne reconstruite dit « grabbé ici, atterri là, milieu inconnu ». C'est la vérité
disponible ; le reste a été détruit avec les dossiers de staging.

---

## 6. §12 — les tuiles de la Vue d'ensemble

`<Link>` rend un `<a>` `display:inline` : dans `grid grid-cols-2`, la zone cliquable se réduit à
la boîte inline et la carte ne s'étire pas à la hauteur de cellule. Les trois `<Link>` reçoivent
`className="block h-full"` et `StatPanel` `className="h-full"`. La 4ᵉ tuile (« Dispatchés »), sans
lien, garde sa hauteur de cellule : les quatre s'alignent.

Test §12 : l'ancre porte bien `block` + `h-full` (surface cliquable = la carte entière) **et** la
tuile est bien dans l'ancre — le test lit la structure que l'opérateur touche du doigt, pas un nom
de classe isolé.

---

## 7. Invariants non négociables

- Le caractère **advisory** de la spine est préservé : aucune écriture de provenance ne fait
  échouer une étape du pipeline. Ce qui change est la **visibilité** de l'échec, pas sa gravité.
- La **contenance** ne remplace jamais l'exactitude : une ligne dont le `current_path` est égal à
  la source de dispatch est traitée par le même chemin, sans changement de comportement.
- Le backfill **n'invente rien** : tout champ non reconstructible reste NULL.
- Aucun verdict « conforme » sans `scripts/check-acquisition-coherence.py` à **exit 0** sur les
  données réelles, après déploiement.
