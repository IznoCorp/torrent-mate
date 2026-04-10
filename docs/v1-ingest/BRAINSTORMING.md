# V1 — INGEST : Brainstorming

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

## Contexte

Les torrents terminés atterrissent dans `/Volumes/IznoServer SSD/torrents/complete`.
Actuellement, les fichiers sont déplacés manuellement vers `A TRIER/`.
Cette étape doit être automatisée.

## Contraintes connues

- **Cron 1x/jour à 3h** + possibilité de lancement manuel via commande
- Fichiers potentiellement encore en écriture (seed en cours) → détection nécessaire
- Le dossier `complete/` peut contenir des dossiers ou des fichiers isolés
- Les noms contiennent des tags release-group, codec, résolution
- Certains torrents sont en seed → **copie** (pas move) ou vérification que le seed est terminé

## Questions ouvertes

- [ ] Comment détecter qu'un torrent est encore en seed ? (interroger le client torrent ? vérifier la taille stable ?)
- [ ] Quel client torrent est utilisé ? (Transmission, qBittorrent, etc.) — API disponible ?
- [ ] Copie ou déplacement ? (si on move, le seed s'arrête)
- [ ] Faut-il gérer les .rar/.zip (extraction automatique) ?
- [ ] Faut-il un dossier intermédiaire (quarantaine) avant A TRIER/ ?

## Options identifiées

### Détection "prêt à ingérer"

1. **Taille stable** — vérifier que la taille n'a pas changé entre 2 checks (simple mais fragile)
2. **API client torrent** — interroger Transmission/qBittorrent pour le statut du torrent (fiable)
3. **Fichier marqueur** — le client torrent crée un fichier `.done` à la fin (nécessite config client)

### Structure du script

- Script Python autonome dans `099-SCRIPTS/pipeline/`
- Appelable via cron ET en ligne de commande
- Support `--dry-run` obligatoire
- Logging des opérations

## Notes de brainstorming

_À compléter lors de la session de brainstorming dédiée_
