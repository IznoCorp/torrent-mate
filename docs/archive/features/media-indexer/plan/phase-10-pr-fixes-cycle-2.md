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

### 10.4 — Fix: `bootstrap_disk_identity` ne supporte pas `disk.path` en sous-dossier d'un mount point

**Finding (CRITICAL — feature bug)** : `personalscraper.indexer.merkle.bootstrap_disk_identity(mount_path)` appelle `diskutil info -plist <mount_path>`. Si `mount_path = /Volumes/Disk1/medias` (sous-dossier configuré dans `Config.disks[].path`), diskutil retourne `ExitCode=1` avec `Could not find disk: /Volumes/Disk1/medias`. La fonction lève `BootstrapError` avec stderr vide → message peu informatif (`diskutil failed: `).

**Step concerné — multi-site** : la même hypothèse "disk.path/mount_path = mount root" est répétée à plusieurs endroits :

1. `personalscraper.indexer.merkle.bootstrap_disk_identity:240` → `diskutil info -plist <mount_path>` rejette les sous-dossiers (`Could not find disk: /Volumes/Disk1/medias`)
2. `personalscraper.indexer.merkle.verify_disk_mounted:283` → `os.path.ismount(disk.mount_path)` retourne `False` pour un sous-dossier → `DiskMountStatus.UNMOUNTED` → scanner skip systématique
3. (probablement aussi le scanner walker pour le Merkle root computation)

**Reproductible** :

```python
# Bug 1: bootstrap fails
from personalscraper.indexer.merkle import bootstrap_disk_identity
from pathlib import Path
bootstrap_disk_identity(Path('/Volumes/Disk1/medias'))  # raises BootstrapError

# Bug 2: verify_disk_mounted returns UNMOUNTED even with valid sentinel + diskutil-resolved UUID
import os
os.path.ismount('/Volumes/Disk1/medias')  # → False (subdir, not mount)
os.path.ismount('/Volumes/Disk1')         # → True
```

**Conséquence en pratique** : avec `disk.path = /Volumes/Disk1/medias` (la config v1 du projet), **la nouvelle feature media-indexer est inutilisable** :

- `library-index --mode full` rapporte `files_walked=0, status=ok` silencieusement
- Aucun disque ne peut être enregistré, aucun fichier ne peut être indexé
- L'outbox reste vide
- Le pipeline tourne en mode legacy sans bénéficier du nouvel indexer

**Root cause structurel** : la nouvelle feature présume que `disk.path` IS le mount root du volume. Le projet (v1 config) utilise délibérément un sous-dossier (`<volume>/medias`) car les disques sont partagés. La feature ne supporte pas cette topologie.

**Fix shape** :

- **Décision design needed** : `disk.path` doit-il rester le sous-dossier configuré (et la feature doit résoudre le mount root séparément) OU forcer `disk.path = mount root` dans la migration v1→v2 ?
- Si on garde `disk.path = subdir` :
  - Ajouter helper `find_mount_root(p: Path) -> Path` qui remonte les ancêtres avec `os.path.ismount`
  - `bootstrap_disk_identity` appelle `diskutil` sur le mount root, écrit la sentinelle au mount root (pas au subdir)
  - `verify_disk_mounted` check `os.path.ismount(find_mount_root(disk.mount_path))` ET sentinel au mount root
  - `disk.mount_path` reste le subdir (pour le scanner walker)
  - Ajouter peut-être un champ `disk.scan_root` distinct si nécessaire
- Si on force `disk.path = mount root` :
  - Mettre à jour la migration v1→v2 pour remonter automatiquement
  - Le scanner walker n'a alors aucun moyen de scope au sous-dossier `medias` → mauvaise expérience pour les disques partagés
- Améliorer aussi le message d'erreur `BootstrapError` : parser `<key>ErrorMessage</key>` du plist de retour quand stderr est vide

**Acceptance** :

- `library-index --mode full` sur la config actuelle (avec `disk.path = /Volumes/Disk1/medias`) walk effectivement les fichiers, registre 4 disques, peuple `media_file`/`media_item`
- Re-run pipeline : outbox events publiés, drainés au prochain `library-index`

---

### 10.5 — Fix: `indexer.disk.skipped_unmounted` warning : champ `reason` contient l'UUID au lieu du motif

**Finding (Mineur — observability)** : quand un disque est skip pour cause de sentinelle absente / UUID mismatch, le log warning `indexer.disk.skipped_unmounted` retourne `reason=<UUID>` au lieu d'un code lisible (ex: `reason=sentinel_missing`, `reason=sentinel_mismatch`, `reason=mount_path_inaccessible`).

**Reproductible** :

```
[warning] indexer.disk.skipped_unmounted disk_id=1 label=disk_1 reason=F7E3C03C-48B7-4C23-BFEE-3E19B052C014
```

**Fix shape** : dans le scanner, séparer le `reason` (un str enum: `sentinel_missing`, `sentinel_mismatch`, `mount_inaccessible`, `bootstrap_failed`) et un champ optionnel `disk_uuid` ou `expected_uuid`. Le `reason` doit être lisible/grep-able.

**Acceptance** : `reason` est une chaîne lisible, l'UUID est dans un champ séparé.

---

## Out of scope

- Bugs Cycle 1 déjà corrigés (C1, C2, M1–M4)
- Items déjà déclassés à minor / deferred (~30 items dans IMPLEMENTATION.md cycle 1)
