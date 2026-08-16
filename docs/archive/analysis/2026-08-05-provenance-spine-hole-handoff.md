# Handoff — provenance spine is losing almost every journey (+ overview tiles)

**Written**: 2026-08-05, end of a long session. **Status**: diagnosed and verified, NOT yet fixed.
**Operator mandate (verbatim)**: « 1, 2 et 3 dans la même feature, on corrige tout de manière
fiable, pas de rustine. On s'assure de fermer le trou afin qu'il n'y ait plus de régression. On
trouve le moyen de reconstruire les lignes manquantes à partir des logs (si possible de le faire
proprement). »

---

## 0. Where things stand

Already shipped and verified in prod this session (nothing to redo):

| PR | Version | What |
| --- | --- | --- |
| #394 | 0.78.2 | D1 escalade saison sur évidence · D2 `trackers_degraded` · D3 déclenchement · D4 bus post-dispatch (+D4-bis ordre du subscriber) |
| #396 | 0.79.0 | §5 — le run manuel est montré jusqu'au résultat chiffré (`PrimeResult` + `run_uid`) |
| #397 | 0.79.1 | §12 Mobile first gravé · carte média · remboursement d'essai étendu à tout verdict INCONCLUSIVE |
| #398 | 0.79.2 | §13 gravé · seam unique `governing_facts_by_episode` · garde `UI_ACQUIRING_NO_TORRENT` |

`main` = `821009d7`, v0.79.2. Prod web + watch redémarrés dessus. Tous les gates verts sur main
(10335 backend, 1244 frontend, lint/typecheck/eslint 0, OpenAPI sans drift).

**Constitution** : §12 (l.172), Composition d'une carte média (l.200), §13 (l.214) dans
`docs/reference/product-intent.md` sur main.

---

## 1. The bug to fix

### Symptôme opérateur

Écran Acquisition → Vue d'ensemble, sur mobile : la tuile **« Dispatchés » affiche 1** (Marjorie
Prime) alors que des dizaines d'items ont été dispatchés depuis. Et **le clic vers le détail ne
marche que sur une zone restreinte** de la première carte, avec des hauteurs de tuiles inégales.

### Cause A — les saisons sont rejetées à l'écriture (PROUVÉE)

`staging_provenance` déclare `kind TEXT CHECK (kind IN ('movie', 'episode'))`. Season-grab (#378)
a introduit `kind='season'` ; la table n'a jamais été migrée. L'écriture est best-effort, donc
l'erreur est avalée. Logs PM2 (7 occurrences) :

```
2026-08-04T15:20:01  acquire.provenance.write_failed
   error="CHECK constraint failed: kind IN ('movie', 'episode')"
2026-08-05T03:20:03  acquire.provenance.write_failed   (idem)
```

Site d'écriture : `personalscraper/acquire/_grab_pass.py:290` → `provenance.upsert_grab(..., kind=item.kind, ...)`.

### Cause B — les épisodes sont écrits puis effacés (PROUVÉE par lecture de code + données)

`_provenance_store.py::record_dispatch_by_path` (l.~285) fait :

```sql
UPDATE staging_provenance SET dispatch_path=?, dispatched_at=?, status='dispatched', ...
WHERE current_path IN (?, ?)
```

`current_path` est le dossier de staging VIVANT. Pour une série, le pipeline fusionne l'épisode
dans un dossier de show existant ; si `current_path` n'a pas suivi les renommages, l'UPDATE ne
matche rien → la ligne reste « en vol ». Puis `PostDispatchReconcileSubscriber` appelle
`provenance.prune_stale`, qui **supprime les lignes en vol dont le dossier a disparu** et ne
garde que les `dispatched`. Un film garde un dossier corrélable → il survit. D'où l'unique
survivant, un film.

État constaté : `SELECT COUNT(*) FROM staging_provenance` = **1** (Marjorie Prime, 2026-08-01).

### Conséquence §13

La tuile « Dispatchés » ne montre structurellement **que les films**. C'est une violation du §13
gravé le jour même.

### Cause C — les tuiles (indépendante, triviale)

`frontend/src/components/acquisition/OverviewPanel.tsx` l.65/75/85 :

```jsx
<Link to="/acquisition?tab=parcours" aria-label="…">   {/* AUCUN className */}
  <StatPanel … />                                       {/* .ps-stat = display:flex + padding + border */}
</Link>
```

`<Link>` rend un `<a>` **`display:inline`**. Dans `grid grid-cols-2` : la surface cliquable se
réduit à la boîte inline, et la carte ne s'étire pas à la hauteur de cellule. La 4ᵉ tuile
(« Dispatchés ») n'a **pas** de `<Link>` — elle est enfant direct de la grille et s'affiche
correctement : l'asymétrie est visible sur la capture opérateur.

---

## 2. The plan (arbitré par l'opérateur : les trois dans UNE feature)

### 2.1 Migration `staging_provenance`

Le `CHECK` doit accepter `'season'`. SQLite ne modifie pas un CHECK en place → migration
versionnée dans `personalscraper/acquire/migrations/` : table neuve, copie, bascule.

### 2.2 Le trou de fond — changer la clé de corrélation

Le chemin bouge à chaque étape ; le **hash est stable de bout en bout**. Basculer
`record_dispatch_by_path` (et le pendant scrape) sur `info_hash`, avec le tracker d'ingestion
(`.data/ingested_torrents.json`, hash → dossier de staging) comme pont hash↔dossier. Garder le
chemin en **repli seulement**, jamais comme clé primaire de jointure.

À vérifier au début : `personalscraper/dispatch/run.py` a-t-il le hash par item, ou faut-il le
faire descendre depuis l'ingest ? C'est LA question de conception à trancher en premier.

### 2.3 Tuiles

`className="block h-full"` sur les trois `<Link>` + carte pleine hauteur. Test §12 gardant la
surface de clic (le conteneur cliquable couvre la carte) et l'égalité des hauteurs.

### 2.4 Fermer le trou — 3 gardes, c'est le cœur de la demande

1. **Test d'égalité** entre le `CHECK` de `staging_provenance.kind` et les `WantedKind` du
   domaine. Un futur `kind` ne pourra plus être rejeté en silence.
2. **`acquire.provenance.write_failed` ne doit plus être un `log.warning` muet.** C'est ce qui a
   caché le bug quatre jours. Le remonter en anomalie visible (compteur run-row, ou règle du
   garde-fou).
3. **Nouvelle règle `check-acquisition-coherence.py`** : tout `wanted` en `done` portant un
   `grabbed_hash` DOIT avoir sa ligne de spine en `dispatched`. Elle aurait crié dès le 2 août.
   La mutation-tester (cf. leçon ci-dessous).

### 2.5 Réparation de l'état (§13)

Backfill des lignes perdues. **Sources en base, PAS les logs** (rotatifs et déjà incomplets) :

| Champ | Source | Fiabilité |
| --- | --- | --- |
| `info_hash`, `kind`, `media_ref_json`, `followed_id` | `wanted` (`grabbed_hash` + colonnes) | exacte |
| `grabbed_at` | `seed_obligation.added_at` (posée au grab, indépendante — 36 lignes) | exacte |
| `dispatch_path` | `library.db` : `media_file → path.rel_path` par épisode | exacte (vérifié : `series/Widow's Bay (2026)/Saison 01`) |
| `dispatched_at` | `media_file.last_verified_at` | ≈ à la minute |

**NON reconstructible, à laisser NULL** : `ingest_path`, `current_path`, `scraped_at`. Les
dossiers de staging sont supprimés, l'information n'existe plus. **Ne pas inventer** — §méthode.
Une ligne reconstruite doit dire « grabbé ici, atterri là, milieu inconnu ».

Requête de départ pour identifier les manquantes :

```sql
SELECT w.id, w.kind, w.grabbed_hash, w.followed_id, w.media_ref_json
FROM wanted w
WHERE w.grabbed_hash IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM staging_provenance sp
                  WHERE lower(sp.info_hash) = lower(w.grabbed_hash));
```

---

## 3. Environnement

- **Worktree** : `/Users/izno/dev/PersonalScraper/.claude/worktrees/acq-escalade`, branche
  `verif-main` sur `821009d7`. Repartir par `git remote update origin && git checkout -B <branche> origin/main`.
- **Ne PAS lancer `pip install -e .`** dans le worktree : le package est résolu par cwd, l'install
  editable globale et les crons prod restent intacts.
- **Frontend** : `frontend/node_modules` absent du worktree. Lien symbolique temporaire
  `ln -sfn /Users/izno/dev/PersonalScraper/frontend/node_modules frontend/node_modules`
  (manifests identiques, vérifié) — **le retirer avant tout commit** : le pattern `node_modules/`
  du `.gitignore` ne matche pas un symlink.
- **Version** : bump obligatoire à chaque PR. main = 0.79.2 → prochaine 0.79.3 (ou 0.80.0).
- **Topologie prod (corrigée cette session, la mémoire était fausse)** : TOUS les process PM2
  (web ET crons) tournent depuis `/Users/izno/deploy/torrentmate` avec
  `/Users/izno/deploy/torrentmate-venv`. Lire `pm2 jlist` → `pm_exec_path` / `pm_cwd`, **jamais**
  déduire d'un `python -c "import personalscraper"`. `torrentmate-web` est redémarré par
  l'autodeploy ; **`personalscraper-watch` NE l'est PAS** — le relancer explicitement après
  vérification qu'il est inactif (aucun `pipeline_run` ouvert, pas de `.data/pipeline.lock`,
  aucun processus enfant).
- **Branches distantes mergées non supprimées** : `fix/acq-escalade`, `feat/acq-run-visible`,
  `feat/mobile-first`, `fix/absorbed-truth`. Nettoyage proposé, non fait (l'opérateur n'a pas
  tranché). Ne PAS utiliser `gh pr merge --delete-branch` (bascule le checkout local).

## 4. Recettes de vérification

```bash
# les deux garde-fous du §méthode
python scripts/check-acquisition-coherence.py; echo $?   # doit finir à 0
python scripts/check-media-complete.py; echo $?          # 1 = Top Chef Le Concours Parallèle,
                                                         # ouvert connu, PAS une régression

# état de la spine
sqlite3 -readonly .data/acquire.db "SELECT status, COUNT(*) FROM staging_provenance GROUP BY status;"

# les rejets silencieux
grep -rh "acquire.provenance.write_failed" ~/.pm2/logs/*.log | tail

# UI à largeur mobile réelle (le viewport Chrome est épinglé) — iframe 390px same-origin
# sur https://tm.iznogoudatall.xyz, puis lire scrollWidth vs clientWidth du document interne.
# Buster le SW avant : unregister + caches.delete, sinon bundle périmé.
```

## 5. Leçons de méthode de cette session (à ne pas réapprendre)

- **Mutation-tester chaque garde.** Ma première version de `UI_ACQUIRING_NO_TORRENT` était
  **vacuous** : elle testait l'état `en_acquisition` alors que `derive_episode_state` rend
  `absorbed` et que l'UI affiche les deux pareil. Un garde doit lire **ce que l'opérateur lit**.
- **Une règle = un mode de défaillance.** La même règle doublonnait `GRABBED_HASH_MISSING` ; il a
  fallu la restreindre au cas qu'elle seule voit.
- **`ruff format scripts/`** reformate onze scripts sans rapport → dérive de périmètre. Formater
  fichier par fichier, et relire `git status` avant de committer.
- **Vérifier les preuves d'exécution, pas les intentions.** Un `python -c "import X"` depuis un
  cwd arbitraire ne dit PAS ce que tourne un service.
