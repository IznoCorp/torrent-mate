# Naming Conventions

Folder and file naming conventions for movies and TV shows.

## Movie Folders

```
Title (Year)/
  Title.mkv
  Title.nfo
  Title-poster.jpg
  Title-fanart.jpg
  Title-banner.jpg
  Title-clearlogo.png
  Title-clearart.png
  Title-discart.png
  Title-landscape.jpg
  .actors/           # Actor thumbnail images
```

## TV Show Folders

```
Show Name (Year)/
  tvshow.nfo
  poster.jpg, fanart.jpg, banner.jpg, clearlogo.png, etc.
  season01-poster.jpg
  .actors/
  Saison 01/
    S01E01 - Episode Title.mkv
    S01E01 - Episode Title.nfo
    S01E01 - Episode Title-thumb.jpg
  Saison 02/
    ...
```

- Season folders use **French** naming: `Saison 01`, `Saison 02`, etc.
- Episode files follow the pattern: `S{nn}E{nn} - {Episode Title}.{ext}`.
- TV folder creation: sorter creates `Show Name/` (no year), scraper renames to `Show Name (Year)/` after API matching (idempotent).

## Filename Sanitization

`sanitize_filename()` (in `personalscraper/text_utils.py`) strips `<>:"/\|?*` and normalizes U+00A0→space. Applied:

- In `NamingPatterns.format()` — all artwork and NFO filenames
- In scraper `clean_name` — folder renames

TMDB titles often contain `:` (e.g. "Spirale : L'Héritage de Saw") and non-breaking spaces (French typography convention before `:`) — sanitization is mandatory for NTFS compatibility.

## Trailer File Naming

Plex-conformant placement — convention depends on media type.

**Movies** (Plex Local Media Assets — flat, same folder as the media file):

{media_dir}/{media_name}-trailer.{ext}
Fight Club (1999)/Fight Club (1999)-trailer.mp4

**TV shows — show level** (Plex TV Series agent extras — `Trailers/` subfolder required):

{show_dir}/Trailers/{show_name}.{ext}
Breaking Bad (2008)/Trailers/Breaking Bad (2008).mp4

**TV shows — season level** (opt-in via trailers.seasons.enabled):

{show_dir}/Saison {NN}/Trailers/{show_name} - Saison {NN}.{ext}
Breaking Bad (2008)/Saison 01/Trailers/Breaking Bad (2008) - Saison 01.mp4

Season path pattern: `{show_dir}/Saison {SS:02d}/Trailers/{show_dir.name} - Saison {SS:02d}.{ext}`

The Plex TV Series agent only recognises the `Trailers/` subfolder for show-level and
season-level extras. Using the flat `{show}-trailer.{ext}` suffix at show or season
level produces an unrecognised orphan video in Plex.

Accepted extensions in priority order: .mp4, .mkv, .webm.

NFO <trailer> tag: populated with the YouTube watch URL so Plex/Kodi can
display the remote trailer as a fallback when the local file is absent.

## Video Extensions

Handled across the pipeline:
`.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.mpg`, `.mpeg`, `.m4v`, `.webm`, `.ts`, `.m2ts`, `.mts`, `.3gp`, `.vob`, `.ogv`, `.rmvb`

## FileMate Integration

FileMate's directory name mappings (001-MOVIES, 002-TVSHOWS, etc.) are defined in `~/dev/FileMate/.env` — update there if folder naming changes.
