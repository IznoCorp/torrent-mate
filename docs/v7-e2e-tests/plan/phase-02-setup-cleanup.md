# Phase 2 — Setup torrents + cleanup sécurisé

## Objectif

Implémenter l'ajout des magnets à qBittorrent et le nettoyage sécurisé des fichiers de test.

## Sous-phases

### 7.2.1 — TorrentSetup

- [ ] Créer `tests/e2e/setup_torrents.py`
- [ ] `load_magnets(config_path)` : charge et valide `test_magnets.json`
- [ ] `add_magnets(magnets, category="e2e-test")` : ajoute à qBit avec catégorie dédiée
  - La catégorie "e2e-test" identifie les torrents de test pour le cleanup
  - Enregistre les hashes dans le registre
- [ ] `wait_for_completion(hashes, timeout=3600)` : poll qBit toutes les 30s, timeout par torrent
- [ ] `get_downloaded_paths(hashes)` : récupère les chemins des fichiers téléchargés
- [ ] Tests avec un mock qBit client

**Commit** : `v7.2.1: Implement torrent setup with qBittorrent API`

### 7.2.2 — TestCleanup (staging + A TRIER)

- [ ] Créer `tests/e2e/cleanup.py`
- [ ] `TestCleanup.__init__(registry, dry_run=True)` — dry_run par DÉFAUT
- [ ] `cleanup_staging()` : supprime les fichiers de test dans A TRIER/
  - Pour chaque path du registre dans A TRIER :
    - Vérifier marker + session_id
    - Supprimer fichier par fichier (PAS rm -rf)
    - Supprimer le dossier vide après
  - Retourne la liste des paths supprimés
- [ ] Tests avec tmp_path simulant A TRIER/

**Commit** : `v7.2.2: Implement staging cleanup with marker verification`

### 7.2.3 — TestCleanup (disques — sécurité maximale)

- [ ] `cleanup_disks()` : supprime les fichiers de test sur Disk1-4
  - TRIPLE VÉRIFICATION par dossier :
    1. `.e2e-test-marker` existe dans le dossier
    2. Le contenu du marker = session_id de cette session
    3. Le chemin est dans le registre
  - Si UN SEUL check échoue → NE PAS SUPPRIMER, logger l'alerte
  - Suppression fichier par fichier, pas rm -rf
  - Suppression du dossier vide après
- [ ] `cleanup_torrents()` : supprime de qBit les torrents catégorie "e2e-test"
  - Supprime le torrent ET ses données dans torrents/complete/
- [ ] Tests avec tmp_path simulant un disque

**Commit** : `v7.2.3: Implement disk cleanup with triple safety verification`

### 7.2.4 — Cleanup complet + vérification post-cleanup

- [ ] `cleanup_all(force=False)` : enchaîne staging → disques → torrents
  - Si dry_run et pas force : affiche le plan, retourne sans supprimer
  - Retourne résumé `{staging: N, disks: N, torrents: N}`
- [ ] `verify_clean()` : scan tous les emplacements pour markers orphelins
  - Scan : A TRIER/, Disk1-4/, torrents/complete/
  - Retourne la liste des paths encore marqués
- [ ] Intégrer en `atexit` / `finally` dans les fixtures pytest pour garantir le cleanup
- [ ] Tests complets

**Commit** : `v7.2.4: Implement full cleanup orchestration and post-cleanup verification`
