# Evaluation de guessit pour le pipeline PersonalScraper

> Date : 2026-04-10 | Contexte : Review architecturale V2 (SORT+CLEAN)

## Qu'est-ce que guessit ?

[guessit](https://github.com/guessit-io/guessit) (v3.8.0) est une librairie Python spécialisée dans le
parsing de noms de fichiers media. Elle utilise un moteur de règles (`rebulk`) — pas du simple regex — pour
extraire des propriétés structurées à partir de noms de torrents, releases, fichiers vidéo.

**Propriétés détectées** (26+) : `title`, `year`, `season`, `episode`, `episode_title`, `source`,
`screen_size`, `video_codec`, `audio_codec`, `audio_channels`, `language`, `subtitle_language`,
`release_group`, `streaming_service`, `container`, `edition`, `other` (HDR, DV, Rip, Complete...), `type`
(movie/episode), `color_depth`, `country`, etc.

**Utilisé par** : Subliminal, Bazarr, Medusa, SickChill, FlexGet et de nombreux outils d'automatisation media.

## Tests avec les noms réels du pipeline

### Noms issus de `torrents/complete/`

| Input                                                                                | title                       | season | episode | year | language  | source | codec | release_group |
| ------------------------------------------------------------------------------------ | --------------------------- | ------ | ------- | ---- | --------- | ------ | ----- | ------------- |
| `Shrinking.S03.MULTi.1080p.WEBRiP.DDP5.1.x265-R3MiX`                                 | Shrinking                   | 3      | —       | —    | mul       | Web    | H.265 | R3MiX         |
| `The.Boys.S05E01.MULTi.DV.HDR.2160p.AMZN.WEBRiP.DDP5.1.x265-R3MiX`                   | The Boys                    | 5      | 1       | —    | mul       | Web    | H.265 | R3MiX         |
| `Your.Friends.and.Neighbours.S02E01.MULTi.VFF.1080p.WEB.EAC3.5.1.Atmos.H265-TFA.mkv` | Your Friends and Neighbours | 2      | 1       | —    | [mul, fr] | Web    | H.265 | TFA           |
| `Avatar.de.feu.et.de.cendres.7.1.neostark.2025.1080p`                                | Avatar de feu et de cendres | —      | —       | 2025 | —         | —      | —     | neostark      |
| `The.Piano.Lesson.2024.MULTi.1080p.WEB.H264`                                         | The Piano Lesson            | —      | —       | 2024 | mul       | Web    | H.264 | —             |

Tous les noms sont correctement parsés. Notamment `Avatar.de.feu.et.de.cendres.7.1.neostark.2025.1080p` :
le titre français avec des points est correctement reconstruit, `7.1` identifié comme channels audio (pas
comme saison/épisode), et `2025` comme année.

### Cas edge critiques

| Input                        | Résultat                                  | Note                         |
| ---------------------------- | ----------------------------------------- | ---------------------------- |
| `2001.A.Space.Odyssey.1968`  | titre "2001 A Space Odyssey", année 1968  | Titre commence par un nombre |
| `Blade.Runner.2049.2017`     | titre "Blade Runner 2049", année 2017     | Titre contient une année     |
| `Se7en.1995`                 | titre "Se7en", année 1995                 | Chiffre dans le titre        |
| `300.Rise.of.an.Empire.2014` | titre "300 Rise of an Empire", année 2014 | Titre = nombre seul          |
| `24.S05E07`                  | titre "24", S05E07                        | Titre très court + numérique |
| `S02E01E02`                  | épisodes [1, 2]                           | Double épisode               |
| `S01-S08.COMPLETE`           | saisons [1..8]                            | Pack multi-saisons           |

Tous ces cas seraient **extrêmement difficiles** à gérer avec du regex custom. La détection de la frontière
entre le titre et les métadonnées est le point fort du moteur de règles de guessit.

## Support français

guessit a un support natif des conventions françaises dans sa config intégrée :

| Pattern             | Détection  | Résultat               |
| ------------------- | ---------- | ---------------------- |
| `MULTi`             | langue     | `mul` (multiple)       |
| `VFF`               | langue     | `fr` (français)        |
| `VFQ`               | langue     | `fr`                   |
| `VOSTFR`            | sous-titre | `fr`                   |
| `TRUEFRENCH`        | langue     | `fr`                   |
| `FRENCH`            | langue     | `fr`                   |
| `Saison 1`          | saison     | `1`                    |
| `Saison VII`        | saison     | `7` (numéraux romains) |
| `Saisons` (pluriel) | saison     | oui                    |

La config contient aussi les séparateurs discrets français (`et`), et les mots-clés de saison
dans 6 langues (français, néerlandais, espagnol, portugais, italien, anglais).

## Limitations connues

### Bug épisodes 3 chiffres sans préfixe

`One.Piece.-.576.VOSTFR` est parsé comme S05E76 au lieu de E576. Ce bug se produit uniquement
quand un numéro d'épisode à 3 chiffres n'a pas de préfixe `E`. Avec `E576` ou `Episode 576`, le
parsing est correct.

**Impact pipeline** : Faible. Les épisodes du pipeline sont au format `S01E04`, pas `576` nu.

### Formats très inhabituels

`Friends.Intégrale.Saison.1.à.10` est mal parsé (le `à` est interprété comme episode_title, `10`
comme épisode). C'est un format extrêmement rare.

**Impact pipeline** : Nul. Ce format n'est pas utilisé par les sources de torrents.

### Maintenance

- Dernier commit : décembre 2023
- 77 issues ouvertes, pas de réponse du mainteneur sur les récentes
- Le projet est **mature mais plus activement maintenu**

**Risque réel** : Faible. Le domaine (noms de fichiers media) évolue lentement. La config est
extensible via `~/.config/guessit/options.json` pour ajouter de nouveaux services de streaming
ou patterns sans modifier le code.

## Dépendances

| Package     | Taille     | Fichiers    | Rôle                                   |
| ----------- | ---------- | ----------- | -------------------------------------- |
| `guessit`   | 1.4 Mo     | 62 .py      | Librairie principale                   |
| `rebulk`    | 716 Ko     | 32 .py      | Moteur de pattern matching             |
| `babelfish` | 376 Ko     | 15 .py      | Gestion langues ISO 639                |
| **Total**   | **3.7 Mo** | **109 .py** | Pur Python, pas de dépendance compilée |

Dépendances transitives : `python-dateutil` (probablement déjà installé). Pas d'extension C.

Licence : **LGPLv3** (pas de contrainte pour un projet personnel).

## Performance

~6.9 ms par nom de fichier = ~146 fichiers/seconde. Pour un pipeline traitant quelques dizaines
de fichiers par batch, c'est négligeable.

## Comparaison avec le NameCleaner regex custom (plan V2 initial)

### Ce que le NameCleaner custom devrait gérer

Le plan V2 prévoyait 8 catégories de regex :

```
RESOLUTION    : 1080p, 720p, 480p, 2160p, 4K, UHD
CODEC         : [HhXx]26[45], HEVC, AVC, AV1, VP9
AUDIO         : DDP?\d?\.\d, AC3, DTS(-HD)?, AAC, FLAC, Atmos, TrueHD, EAC3
SOURCE        : WEB(-?DL|-?Rip)?, Blu-?Ray, BDRip, HDRip, DVDRip, HDTV, AMZN, ATVP, NF, DSNP
VIDEO         : HDR\d*, DV, Dolby.Vision, SDR, 10bit
LANGUAGE      : MULTi, VFF?, VFQ, VOST(FR)?, FRENCH, TRUEFRENCH
RELEASE_GROUP : -[A-Za-z0-9]+$ (le tag après le dernier tiret)
MISC          : REPACK, PROPER, EXTENDED, REMASTERED, COMPLETE, INTERNAL
```

### Avantages de guessit

| Aspect                   | Regex custom                              | guessit                  |
| ------------------------ | ----------------------------------------- | ------------------------ |
| Streaming services       | ~6 (AMZN, NF, DSNP, ATVP...) à maintenir  | 140+ intégrés            |
| Titres avec chiffres     | Très difficile (`2001`, `24`, `300`)      | Géré nativement          |
| Titres avec années       | Très difficile (`Blade Runner 2049`)      | Géré nativement          |
| Français (VFF, VOSTFR)   | À coder manuellement                      | Intégré                  |
| Double épisodes          | Regex complexe                            | Natif                    |
| Maintenance              | Chaque nouveau codec/source = mise à jour | Config extensible        |
| Frontière titre/metadata | Heuristique fragile                       | Moteur de règles robuste |

### Avantages du regex custom

| Aspect                 | Avantage                       |
| ---------------------- | ------------------------------ |
| Zéro dépendance        | Stdlib uniquement              |
| Contrôle total         | Comportement prévisible à 100% |
| Pas de risque upstream | Pas d'abandon possible         |

## Impact sur le plan V2

### Avant (plan actuel)

La phase 2 du plan V2 prévoyait :

- **2.2.1** : Créer `cleaner.py` avec 8 catégories de regex, `clean()`, `extract_year()`,
  `extract_season_episode()`, `clean_for_folder()`
- **2.2.2** : Tests exhaustifs du cleaner avec les noms réels

### Après (avec guessit)

Le NameCleaner devient un **thin wrapper** autour de guessit :

```python
from guessit import guessit as guess

class NameCleaner:
    """Media filename cleaner powered by guessit."""

    def clean(self, name: str) -> str:
        """Return clean title (+ season/episode if present)."""
        r = guess(name)
        title = r.get("title", name)
        season = r.get("season")
        episode = r.get("episode")
        if season and episode:
            return f"{title} S{season:02d}E{episode:02d}"
        if season:
            return f"{title} S{season:02d}"
        return title

    def extract_year(self, name: str) -> int | None:
        return guess(name).get("year")

    def extract_season_episode(self, name: str) -> tuple[int | None, int | None]:
        r = guess(name)
        return r.get("season"), r.get("episode")

    def clean_for_folder(self, name: str) -> str:
        """Return 'Title (Year)' or 'Title'."""
        r = guess(name)
        title = r.get("title", name)
        year = r.get("year")
        return f"{title} ({year})" if year else title
```

~30 lignes au lieu de ~150+ lignes de regex. La phase 2.2 est considérablement simplifiée.

## Recommandation

**Utiliser guessit. Supprimer le plan de NameCleaner regex custom.**

Le gain en robustesse (titres avec chiffres, 140+ streaming services, support français natif)
dépasse largement le coût de la dépendance supplémentaire (3.7 Mo, pur Python, pas de compilé).

Le risque d'abandon est faible : la librairie est stable, la config est extensible, et le domaine
(noms de fichiers media) évolue lentement.

### Modifications à appliquer

1. **V0 `pyproject.toml`** : ajouter `guessit>=3.8.0` aux dépendances
2. **V2 `DESIGN.md`** : réécrire `cleaner.py` comme wrapper guessit
3. **V2 `plan/phase-02-cleaner.md`** : simplifier les sous-phases
4. **V2 `BRAINSTORMING.md`** : documenter le choix guessit vs regex custom
