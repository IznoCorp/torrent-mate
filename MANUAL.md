# Manuel d'utilisation — Zone de tri media

Ce document explique comment utiliser la zone de tri "A TRIER" et les outils disponibles pour organiser les fichiers media.

## Vue d'ensemble

```
Torrents terminés  →  A TRIER (staging)  →  Disques de stockage
                    torrent-sort          /move-to-disk
                    MediaElch (scraping)
```

**Pipeline complet :**

1. Les torrents terminés arrivent dans `/Volumes/IznoServer SSD/torrents/complete`
2. `torrent-sort` dispatche les fichiers dans les sous-dossiers (001-MOVIES, 002-TVSHOWS, etc.)
3. Renommer/nettoyer les noms de fichiers si nécessaire
4. Scraper les metadonnées avec **MediaElch** (posters, fanart, .nfo)
5. Déplacer vers un disque de stockage avec `/move-to-disk`

---

## Commandes shell

### torrent-sort

Trie les fichiers à la racine de A TRIER dans les bons sous-dossiers.

```bash
# Trier (mode normal)
torrent-sort

# Prévisualiser sans déplacer
torrent-sort --dry-run

# Trier + supprimer les restes
torrent-sort --verbose --clean
```

L'outil **FileMate** (`~/dev/FileMate/`) est appelé en arrière-plan. Les associations type → dossier sont configurées dans `~/dev/FileMate/.env`.

### Nettoyage des dossiers vides

Supprime les dossiers media vides (sans fichier vidéo) sur tous les disques.

```bash
# Prévisualiser
python3 099-SCRIPTS/plex/cleanFileSystem.py --dry-run

# Exécuter
python3 099-SCRIPTS/plex/cleanFileSystem.py
```

### Espace disque

```bash
df -h /Volumes/Disk{1,2,3,4}
```

---

## Commandes Claude Code

Ces commandes sont utilisables dans une session Claude Code ouverte sur le dossier A TRIER.

### /check-staging

Affiche un rapport de l'état de la zone de tri :
- Espace disque sur les 4 disques de stockage
- Liste des films dans 001-MOVIES avec leur statut (prêt / à scraper)
- Liste des séries dans 002-TVSHOWS avec leur statut
- Résumé et prochaines actions recommandées

```
/check-staging
```

### /move-to-disk

Déplace un media de A TRIER vers le bon disque de stockage.

```
/move-to-disk                                    # Affiche la liste et demande lequel déplacer
/move-to-disk Peaky Blinders L'Immortel (2026)   # Déplace un film spécifique
/move-to-disk 001-MOVIES/La Femme de ménage (2025)
```

**Comportement :**
- Cherche si le dossier existe déjà sur un des 4 disques
- **Film existant** → remplace l'ancien dossier par le nouveau
- **Série existante** → fusionne (merge) les nouveaux fichiers dans le dossier existant
- **Nouveau media** → déplace vers le disque avec le plus d'espace libre
- Demande toujours une confirmation avant d'agir
- Avertit si le scraping n'est pas terminé (pas de .nfo)

---

## Disques de stockage

| Disque | Montage | Catégories disponibles |
|--------|---------|----------------------|
| Disk1  | /Volumes/Disk1/medias | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk2  | /Volumes/Disk2/medias | series, series animes |
| Disk3  | /Volumes/Disk3/medias | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk4  | /Volumes/Disk4/medias | films, films animations, series, series animations, series documentaires, emissions |

---

## Structure des dossiers

### Zone de tri

```
A TRIER/
├── 001-MOVIES/     Films en attente
├── 002-TVSHOWS/    Séries en attente
├── 003-EBOOKS/     Ebooks
├── 004-AUDIO/      Livres audio
├── 005-APPS/       Applications
├── 006-ANDROID/    APK Android
├── 097-TEMP/       Espace temporaire
├── 098-AUTRES/     Divers
└── 099-SCRIPTS/    Scripts utilitaires (Python)
```

### Nommage des films

```
Titre du Film (Année)/
  Titre du Film.mkv
  Titre du Film.nfo
  Titre du Film-poster.jpg
  Titre du Film-fanart.jpg
  Titre du Film-banner.jpg
  Titre du Film-clearlogo.png
  Titre du Film-clearart.png
  Titre du Film-discart.png
  Titre du Film-landscape.jpg
  .actors/
```

### Nommage des séries

```
Nom de la Série (Année)/
  tvshow.nfo
  poster.jpg
  fanart.jpg
  banner.jpg
  clearlogo.png
  season01-poster.jpg
  .actors/
  Saison 01/
    S01E01 - Titre de l'Episode.mkv
    S01E01 - Titre de l'Episode.nfo
    S01E01 - Titre de l'Episode-thumb.jpg
  Saison 02/
    ...
```

- Dossiers de saison en français : `Saison 01`, `Saison 02`, etc.
- Fichiers d'épisodes : `S{nn}E{nn} - {Titre}.{ext}`

---

## Scraping avec MediaElch

MediaElch est une application de bureau (GUI) utilisée pour récupérer les métadonnées et les images.

**Pour un film :**
1. Ouvrir MediaElch
2. Charger le dossier 001-MOVIES
3. Pour chaque film, lancer la recherche (TMDb/IMDb)
4. Sélectionner le bon résultat
5. Télécharger poster, fanart, banner, etc.
6. Sauvegarder → génère le fichier `.nfo`

**Pour une série :**
1. Ouvrir MediaElch
2. Charger le dossier 002-TVSHOWS
3. Pour chaque série, lancer la recherche (TheTVDB/TMDb)
4. Sélectionner le bon résultat
5. Télécharger les images de la série et des saisons
6. Sauvegarder → génère `tvshow.nfo` et les `.nfo` par épisode

**Un media est prêt à déplacer quand il a au minimum :** un fichier vidéo + un fichier `.nfo`.

---

## Protections Claude Code

Deux hooks de sécurité sont actifs dans `.claude/settings.json` :

1. **Protection des fichiers media** — Claude ne peut pas éditer les fichiers .mkv, .mp4, .nfo, .jpg, .png, etc. Seuls les fichiers .py, .md, .json, .txt, .sh sont éditables.

2. **Protection des disques de stockage** — Claude ne peut pas exécuter de commandes destructrices (rm, mv depuis) sur les chemins /Volumes/Disk1 à Disk4. Les commandes en lecture seule (ls, find, du, df) sont toujours autorisées.

---

## Scripts legacy (099-SCRIPTS/)

Ces scripts sont d'anciens outils, la plupart remplacés par FileMate et MediaElch.

| Script | Usage | Statut |
|--------|-------|--------|
| PackUnpack.py | Aplatir les sous-dossiers + nettoyer les noms | Legacy (chemins Windows) |
| Unpack.py | Variante d'unpack seul | Legacy (chemins Windows) |
| TVDBNameToNum.py | Matcher les noms d'épisodes via TheTVDB | Legacy (chemins Windows) |
| EpisodesTVDBNamer.py | Renommage d'épisodes TVDB | Legacy |
| videoCutter.py | Couper des vidéos | Fonctionnel |
| videoMerger.py | Fusionner des vidéos | Fonctionnel |
| SensCritiqueScrapper.py | Scraping SensCritique | Legacy |
| plex/cleanFileSystem.py | Supprimer les dossiers media vides | **Actif** |
| plex/trailerScraper.py | Télécharger les bandes-annonces YouTube | Fonctionnel |

---

## Notes importantes

- **Espaces dans les chemins** — Toujours mettre les chemins entre guillemets dans le terminal : `"/Volumes/IznoServer SSD/A TRIER/"`
- **Casse des disques** — Les vrais points de montage sont `/Volumes/Disk1` (pas DISK1). Certains vieux scripts utilisent DISK1 en majuscules.
- **Configuration FileMate** — Les associations dossier-type sont dans `~/dev/FileMate/.env`
