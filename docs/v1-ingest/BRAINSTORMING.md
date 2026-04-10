# V1 — INGEST : Brainstorming

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

## Contexte

Les torrents terminés atterrissent dans `/Volumes/IznoServer SSD/torrents/complete`.
Actuellement, les fichiers sont déplacés manuellement vers `A TRIER/`.
Cette étape doit être automatisée.

### État actuel du dossier complete/

```
Jury.Duty.Presents.Company.Retreat.S01.MULTi.1080p.WEB.H264-FW/
Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX/
The.Boys.S05E01.MULTi.DV.HDR.2160p.AMZN.WEBRiP.DDP5.1.x265-R3MiX/
The.Boys.S05E02.MULTi.DV.HDR.2160p.AMZN.WEBRiP.DDP5.1.x265-R3MiX/
Your.Friends.and.Neighbours.S02E01.MULTi.VFF.1080p.WEB.EAC3.5.1.Atmos.H265-TFA.mkv
Your.Friends.and.Neighbours.S02E02.MULTi.VFF.1080p.WEB.EAC3.5.1.Atmos.H265-TFA.mkv
```

Mix de **dossiers** (les 4 premiers) et de **fichiers isolés** (les 2 derniers .mkv).

## Décisions prises

### Client torrent

- **qBittorrent** — client principal
- Web API accessible sur `http://localhost:8081/api/v2/`
- Auth requise : user `izno` + mot de passe
- Config : `~/.config/qBittorrent/qBittorrent.ini`

### Déclenchement

- **Cron 1x/jour à 3h du matin**
- **Commande manuelle** disponible à tout moment
- Pas de watcher (plus robuste, évite les fichiers en cours d'écriture)

### Copie vs déplacement

- Si le torrent est **encore en seed** → **copier** vers A TRIER/
- Si le torrent est **terminé (pas en seed)** → **déplacer** (move)
- Détection via l'**API qBittorrent** (statut du torrent)

### Archives .rar/.zip

- **Reporté** — cas trop rare pour justifier la complexité en V1
- Sera traité comme une amélioration future (V1.x ou V2)
- Pour l'instant, les archives sont simplement copiées/déplacées telles quelles

## Contraintes techniques

1. **Chemins avec espaces** — `/Volumes/IznoServer SSD/` → toujours quoter
2. **Types d'entrées** — dossiers ET fichiers isolés dans complete/
3. **Doublons** — ne pas re-copier un fichier déjà présent dans A TRIER/
4. **Espace disque** — A TRIER/ est sur le SSD, vérifier l'espace avant copie
5. **Permissions** — s'assurer que les fichiers copiés gardent les bonnes permissions

## API qBittorrent — Endpoints utiles

```
POST /api/v2/auth/login          → { username, password } → SID cookie
GET  /api/v2/torrents/info       → liste tous les torrents + état
GET  /api/v2/torrents/info?filter=completed  → torrents terminés
GET  /api/v2/torrents/info?filter=seeding    → torrents en seed
GET  /api/v2/torrents/files?hash=xxx         → fichiers d'un torrent
```

Champs utiles dans la réponse `torrents/info` :

- `state` : "uploading" (seed), "stalledUP" (seed inactif), "pausedUP" (fini), "missingFiles", etc.
- `save_path` : chemin du dossier de téléchargement
- `content_path` : chemin complet du contenu (fichier ou dossier)
- `name` : nom du torrent
- `progress` : 1.0 = complètement téléchargé

## Flux proposé

```
┌─────────────────────────────────┐
│  1. Authentification qBit API   │
│     POST /auth/login            │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  2. Lister torrents terminés    │
│     GET /torrents/info          │
│     filter: completed + seeding │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  3. Pour chaque torrent :       │
│     - Résoudre le content_path  │
│     - Vérifier si déjà présent  │
│       dans A TRIER/             │
│     - Vérifier espace disque    │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  4. Transférer                  │
│     - Seeding → shutil.copytree │
│     - Terminé → shutil.move     │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  5. Log des opérations          │
│     (stdout + fichier log)      │
└─────────────────────────────────┘
```

## Décisions de design (validées)

1. **Mot de passe qBit** → fichier `.env` (non gitté), avec `.env.example` toujours synchronisé
2. **Détection "déjà ingéré"** → fichier JSON trackant les hash de torrents traités. Les entrées sont retirées quand le torrent est supprimé de qBittorrent.
3. **Espace insuffisant** → skip + warning (notification via V5 plus tard)
4. **Fichiers isolés** → déplacés/copiés tels quels à la racine de A TRIER/, FileMate (V2) s'occupe de l'organisation
5. **Nettoyage post-ingest** → aucun, l'utilisateur gère manuellement les torrents dans qBit
