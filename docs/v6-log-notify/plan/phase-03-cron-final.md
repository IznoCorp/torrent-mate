# Phase 3 — Scheduling (launchd) + alias + validation finale

## Objectif

Configurer l'exécution automatique via launchd (natif macOS) et valider le projet complet.

> **Choix launchd vs crontab** : Le projet tourne sur macOS (Darwin). launchd est le mécanisme
> natif de scheduling, offrant : restart on failure (KeepAlive), intégration logs système
> (Console.app), resource limits, et pérennité (Apple pousse launchd activement).
> crontab fonctionne sur macOS mais est un wrapper émulé, sans gestion de restart.

## Sous-phases

### 6.3.1 — Setup launchd

- [ ] Supprimer toute entrée cron legacy (media-ingest, ingest.py) — vérifier avec `crontab -l`
- [ ] Créer le fichier plist `~/Library/LaunchAgents/com.personalscraper.pipeline.plist` :
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
      <key>Label</key>
      <string>com.personalscraper.pipeline</string>
      <key>ProgramArguments</key>
      <array>
          <string>/path/to/venv/bin/personalscraper</string>
          <string>run</string>
      </array>
      <key>StartCalendarInterval</key>
      <dict>
          <key>Hour</key>
          <integer>3</integer>
          <key>Minute</key>
          <integer>0</integer>
      </dict>
      <key>StandardOutPath</key>
      <string>/Users/izno/.personalscraper/launchd-stdout.log</string>
      <key>StandardErrorPath</key>
      <string>/Users/izno/.personalscraper/launchd-stderr.log</string>
      <key>WorkingDirectory</key>
      <string>/Volumes/IznoServer SSD/A TRIER</string>
  </dict>
  </plist>
  ```
- [ ] Charger l'agent : `launchctl load ~/Library/LaunchAgents/com.personalscraper.pipeline.plist`
- [ ] Vérifier le chargement : `launchctl list | grep personalscraper`
- [ ] Tester un run manuel : `launchctl start com.personalscraper.pipeline`
- [ ] Documenter les commandes utiles :
  - `launchctl load/unload` pour activer/désactiver
  - `launchctl start` pour déclencher manuellement
  - `launchctl list | grep personalscraper` pour vérifier le statut

> **Note compatibilité Linux** : sur Linux, utiliser un crontab classique
> `0 3 * * * /path/to/venv/bin/personalscraper run`. Le pipeline est portable,
> seul le scheduling est spécifique à la plateforme.

**Commit** : `v6.3.1: Configure daily launchd agent at 3am`

### 6.3.2 — Documentation et CLAUDE.md

- [ ] Mettre à jour CLAUDE.md avec toutes les commandes finales
- [ ] Documenter le .env.example complet
- [ ] Mettre à jour le Directory Structure dans CLAUDE.md
- [ ] Mettre à jour IMPLEMENTATION.md : marquer V5 et toutes les versions complètes

**Commit** : `v6.3.2: Update CLAUDE.md and finalize documentation`

### 6.3.3 — Validation finale du projet

- [ ] `personalscraper run --dry-run --verbose` fonctionne end-to-end
- [ ] `make test` passe (tous les tests V0→V6)
- [ ] `make lint` passe
- [ ] Le scheduling (LaunchAgent) est configuré
- [ ] Le .env contient toutes les valeurs nécessaires
- [ ] Git status propre, tout committé

**Commit** : `v6.3.3: Project complete — full pipeline validated`
