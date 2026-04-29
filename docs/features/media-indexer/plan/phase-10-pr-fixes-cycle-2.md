# Phase 10 — PR fixes cycle 2

## Context

Bugs détectés pendant le smoke-test pipeline du 2026-04-29 sur la branche `feat/media-indexer`.

**Scope** : ces bugs ne sont **pas** introduits par la feature media-indexer (ils sont pré-existants) mais ont été révélés par le run pipeline. On les regroupe ici pour les corriger en un seul cycle avec les bugs spécifiques à la feature qui seront trouvés au prochain run pipeline (après bootstrap de l'indexer).

**Ne pas lancer cette phase** tant que les bugs feature-spécifiques n'ont pas été ajoutés (post-bootstrap + 2nd pipeline run).

## Sub-phases

### 10.1 — Fix: Silent scrape failure on common-title movies (The Butterfly Effect)

**Finding (Major)** : `personalscraper process` a "réussi" (`Scrape: 8 OK / 6 skipped / 0 errors`) mais le dossier `001-MOVIES/The Butterfly Effect (2004)/` reste avec uniquement le `.mkv` brut — **aucun .nfo, aucun artwork**. Aucune erreur loggée. VERIFY le marque ensuite `blocked`.

**Step concerné** : process / scrape
**Item reproductible** : `The.Butterfly.Effect.2004.DC.MULTi.TRUEFRENCH.1080p.BluRay.mHD.x264.DTS-PATOMiEL.mkv`

**Hypothèse root cause** : le matcher TMDB renvoie soit 0 soit plusieurs candidats pour "The Butterfly Effect" (titre commun, plusieurs films), ne franchit pas le seuil de confidence, et est silencieusement skip — mais le compteur `error_count` n'est pas incrémenté et l'item disparaît du flux.

**Fix shape** :

- Identifier où `match_movie` / `match_tvshow` (`personalscraper/scraper/matcher.py` ou `confidence.py`) bail-out sans logger.
- Soit logger en `warning` avec `event="scraper.match.below_threshold"` + `title`, `year`, `candidates_count`, `top_score`.
- Soit incrémenter un compteur `unmatched` séparé du `error` et le surfacer dans la sortie finale (`Scrape: X OK / Y skipped / Z unmatched / W errors`).
- **Acceptance** : le run reproduit Butterfly Effect → soit le NFO est généré, soit le log warning est visible et le compteur `unmatched=1` apparaît.

---

### 10.2 — Fix: Raw torrent dir not flattened when title has no year (Les secrets du Prince Andrew)

**Finding (Major)** : après PROCESS, `002-TVSHOWS/Les secrets du Prince Andrew/` contient encore le sous-dossier brut du torrent `Les.secrets.du.Prince.Andrew.2023.S01.DOC.FRENCH.1080p.WEB.H264-BOUBA/` au lieu d'être aplati à la structure Plex (`Saison 01/...`). Pas de `tvshow.nfo`, pas de poster.

**Step concerné** : process / clean (sub-step de `process`)
**Item reproductible** : `Les.secrets.du.Prince.Andrew.2023.S01.DOC.FRENCH.1080p.WEB.H264-BOUBA`

**Hypothèse root cause** : le clean phase dépend du match scraper pour décider de la structure cible. Quand le scraper échoue (cf 10.1 ou autre), le clean ne sait pas quoi faire et laisse l'arborescence brute. Le folder est renommé canoniquement (`Les secrets du Prince Andrew` au lieu de `Les.secrets.du.Prince.Andrew.2023...`) mais le contenu n'est pas réorganisé.

**Fix shape** :

- Idéalement résolu par 10.1 (si le matcher loggue son échec, le clean peut décider explicitement de skip plutôt que de partial-action).
- En complément : `personalscraper.process.cleaner` doit refuser d'opérer sur un dossier dont le scraper n'a pas réussi à matcher → ne pas renommer le dossier, laisser le torrent brut tel quel pour rescrape ultérieur.
- **Acceptance** : reproduire Les secrets du Prince Andrew → soit le scrape réussit, soit le dossier reste à son nom torrent original, et un log `process.clean.skipped_unmatched` apparaît.

---

### 10.3 — Fix: First-run UX broken — `library-index` ne bootstrappe pas les disques depuis Config.disks

**Finding (CRITICAL — feature bug)** : sur une DB fraîche (`disk` table vide), `personalscraper library-index --mode full` retourne `files_walked=0, dirs_walked=0, disks_skipped=0, status=ok` en moins d'1 seconde. Aucune erreur, aucun warning. L'utilisateur n'a aucun moyen de savoir que rien ne s'est passé sans inspecter la DB.

**Step concerné** : `personalscraper.indexer.cli.library_index_command`
**Reproductible** : `rm -rf .personalscraper/library.db && personalscraper library-index --mode full`

**Root cause** : `personalscraper/indexer/cli.py:340-358` lit les disques uniquement depuis la table `disk` :

```python
raw_rows = conn.execute("SELECT ... FROM disk").fetchall()
disks: list[DiskRow] = [DiskRow(...) for r in raw_rows]
```

Si la table est vide, `disks=[]`, `filter_disks([], None) = []`, `scan(disks=[], ...)` ne fait rien. **Il n'existe aucun chemin de code qui peuple la table `disk` depuis `Config.disks`.**

**Fix shape** :

- Dans `library_index_command`, après `apply_migrations` et avant le SELECT FROM disk : si la table `disk` est vide ET `cfg.disks` est non-vide, bootstrapper la table en INSERTant chaque `DiskConfig` (id, uuid via `bootstrap_disk_identity`, label, mount_path).
- Logger `indexer.bootstrap.disk_registered` à `info` pour chaque insert.
- Surfacer dans la sortie JSON un nouveau champ `disks_bootstrapped: int` quand le bootstrap a tourné.
- **Acceptance** : `rm -rf .personalscraper/library.db && personalscraper library-index --mode full` enregistre les 4 disques + scanne le contenu, files_walked > 0 et disks_bootstrapped=4.

**Sévérité** : Critical — la feature est inutilisable telle quelle au premier run. C'est exactement le bug que cycle 1 visait C1/C2 mais l'UX bootstrap a été oublié.

---

### 10.4 — _(placeholder, à remplir avec autres bugs feature trouvés au 2ᵉ pipeline run)_

Après bootstrap manuel + re-run pipeline avec outbox actif.

---

## Out of scope

- Bugs Cycle 1 déjà corrigés (C1, C2, M1–M4)
- Items déjà déclassés à minor / deferred (~30 items dans IMPLEMENTATION.md cycle 1)
