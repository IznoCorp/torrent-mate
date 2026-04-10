# V2 — SORT + CLEAN : Brainstorming

> Tri automatique des fichiers par type + nettoyage agressif des noms

## Contexte

Après V1 (ingest), les fichiers arrivent à la racine de `A TRIER/` avec des noms bruts de torrent :

```
Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX/
The.Boys.S05E01.MULTi.DV.HDR.2160p.AMZN.WEBRiP.DDP5.1.x265-R3MiX/
Your.Friends.and.Neighbours.S02E01.MULTi.VFF.1080p.WEB.EAC3.5.1.Atmos.H265-TFA.mkv
```

V2 doit :

1. Trier dans les bons dossiers (001-MOVIES, 002-TVSHOWS, etc.)
2. Nettoyer les noms pour ne garder que le strict nécessaire au scraping (titre + année)
3. Retourner une liste structurée de ce qui a été trié (pour V3/V4)

## Décisions prises

### Intégration FileMate

- **Intégré directement dans ce projet** (pas de dépendance externe)
- FileMate n'est utilisé que pour ce workflow → maintenance centralisée
- L'architecture strategy pattern est conservée et améliorée
- Le code est adapté au nouveau système de config (pydantic-settings, V0)

### Nettoyage des noms — tout virer sauf titre + année

**Objectif** : après nettoyage, un fichier/dossier ne contient que ce qui est nécessaire au scraping TMDB.

Exemples de transformation attendue :

```
AVANT                                                          APRÈS
Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX/       → Shrinking/
The.Boys.S05E01.MULTi.DV.HDR.2160p.AMZN.WEBRiP              → The Boys S05E01
Avatar.de.feu.et.de.cendres.7.1.neostark.2025.1080p          → Avatar de feu et de cendres (2025)
```

**Approche** : utiliser la librairie **`guessit`** (moteur de règles, pas du simple regex) :

- Parse les noms de fichiers media et retourne titre, année, saison, épisode, codec, etc.
- Gère nativement 140+ streaming services, conventions françaises (VFF, VOSTFR, MULTi, Saison)
- Gère les cas edge impossibles en regex : titres avec chiffres (`2001`, `24`, `300`), titres
  contenant des années (`Blade Runner 2049`), double épisodes
- Voir `docs/guessit-evaluation.md` pour l'évaluation complète

> **Choix guessit vs regex custom** : le regex custom était l'approche initiale mais guessit
> est strictement supérieur en robustesse pour un coût minimal (3.7 Mo, pur Python, LGPLv3).
> Le NameCleaner devient un thin wrapper de ~30 lignes au lieu de ~150+ lignes de regex.

### Dossiers `Saison XX/`

- **PAS créés en V2** — c'est V3 (scraper) qui s'en charge
- V2 met les épisodes dans `002-TVSHOWS/Show Name/` sans sous-dossiers saison
- V3 créera `Saison XX/` en même temps que les .nfo et artwork

### Retour de valeur pour le pipeline

- **FileMate modifié pour retourner une liste structurée** de ce qui a été trié
- Format : liste de `{source, destination, media_type, detected_title, detected_year, detected_season, detected_episode}`
- Permet à V3 et V4 de savoir exactement quoi traiter sans re-scanner les dossiers

## État actuel de FileMate — ce qui fonctionne

| Composant                                     | Status                   | Action V2                        |
| --------------------------------------------- | ------------------------ | -------------------------------- |
| Strategy pattern (Movie/TVShow/Default)       | Bon                      | Conserver                        |
| Fuzzy directory matching                      | Bon (récent, testé)      | Conserver                        |
| Détection TV : `s01e04`, `saison X episode Y` | OK                       | Étendre (`1x04`, `ep.1`, ranges) |
| clean_words.txt (218 mots)                    | Fragile, ratés fréquents | Remplacer par regex dynamiques   |
| clean_chars.txt (14 chars)                    | OK                       | Intégrer dans le cleaner         |
| `Sorter.sort()` retourne None                 | Problème                 | Retourner liste structurée       |
| Détection conflit avant move                  | Absent                   | Ajouter                          |
| Support dry-run/verbose                       | Bon                      | Conserver                        |

## Patterns de nettoyage à implémenter (regex)

### Catégories à supprimer

```
RESOLUTION    : 1080p, 720p, 480p, 2160p, 4K, UHD
CODEC         : [HhXx]26[45], HEVC, AVC, AV1, VP9
AUDIO         : DDP?\d?\.\d, AC3, DTS(-HD)?, AAC, FLAC, Atmos, TrueHD, EAC3
SOURCE        : WEB(-?DL|-?Rip)?, Blu-?Ray, BDRip, HDRip, DVDRip, HDTV, AMZN, ATVP, NF, DSNP
VIDEO         : HDR\d*, DV, Dolby.Vision, SDR, 10bit
LANGUAGE      : MULTi, VFF?, VFQ, VOST(FR)?, FRENCH, TRUEFRENCH, ENGlish
RELEASE_GROUP : -[A-Za-z0-9]+$ (le tag après le dernier tiret)
MISC          : REPACK, PROPER, EXTENDED, REMASTERED, COMPLETE, INTERNAL
```

### Ce qui est conservé

- **Titre** : tout ce qui précède le premier tag technique
- **Année** : `(19|20)\d{2}` — extraite et formatée en `(YYYY)`
- **Saison/Épisode** : `S\d{2}E\d{2}` — conservé pour les séries

## Contraintes techniques

1. FileMate intégré → son code vit dans le package Python du projet (V0)
2. Le cleaner doit être testable unitairement (entrée string → sortie string)
3. Dry-run obligatoire — ne rien déplacer sans confirmation en mode normal
4. Les fichiers isolés `.mkv` à la racine doivent être triés comme les dossiers
5. Gestion des sous-titres `.srt/.sub` associés (même nom de base que la vidéo)

## Questions ouvertes

_Toutes les questions ont été résolues._
