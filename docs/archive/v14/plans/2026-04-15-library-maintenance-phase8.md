# Phase 8: Documentation — CLAUDE.md, MANUAL.md, ROADMAP.md, --help

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Update all documentation to reflect V14: CLAUDE.md (commands, config, version table), MANUAL.md (French user guide), ROADMAP.md (polish), and CLI --help (Rich formatting, grouped commands).

**Architecture:** Documentation-only phase — no code changes. All files already exist, this phase updates them.

**Tech Stack:** Markdown, Typer help strings

---

## Task 1: Update CLAUDE.md

**Files:**

- Modify: `CLAUDE.md`

- [ ] **Step 1: Add V14 to Package section**

Update the Package line:

```markdown
V0-V14 implemented (ingest, sort, scrape, verify, dispatch, pipeline run + notifications, E2E tests, test audit, robustness, pipeline integrity, resilience, pipeline hardening, pipeline correctness, library maintenance).
```

- [ ] **Step 2: Add library commands to Commands section**

After the existing `personalscraper enforce` command, add:

```markdown
# Library maintenance (V14)

personalscraper library-scan # Scan library structure/metadata on storage disks
personalscraper library-scan --disk Disk1 # Scan single disk
personalscraper library-clean # Dry-run: show what would be cleaned
personalscraper library-clean --apply # Delete .actors/, empty dirs, junk
personalscraper library-clean --only actors --apply # Only .actors/ dirs
personalscraper library-validate # Validate NFO/artwork/naming conformity
personalscraper library-validate --fix --apply # Auto-fix what's possible
personalscraper library-analyze # Deep ffprobe scan (codec, audio, subs)
personalscraper library-analyze --incremental # Skip already-analyzed files
personalscraper library-recommend # Generate re-download recommendation list
personalscraper library-recommend --export csv # Export to CSV
personalscraper library-report # Library health statistics
personalscraper library-report --format json # Export as JSON
```

- [ ] **Step 3: Add V14 to Pipeline Versions table**

Add row:

```markdown
| V14 | LIBRARY MAINTENANCE | Scan, clean, validate, analyze, recommend, report library | 9 |
```

- [ ] **Step 4: Update Directory Structure**

Add under `personalscraper/`:

```markdown
│ ├── library/ # V14: library maintenance (scan, clean, validate, analyze, recommend, report)
│ ├── nfo_utils.py # V14: shared NFO validation (moved from scraper)
```

Add under `tests/`:

```markdown
│ ├── library/ # V14 unit tests
```

- [ ] **Step 5: Add library configuration notes**

Add to the "Important Notes" section:

```markdown
- Library preferences live in `.personalscraper/library_preferences.json` — codec, audio, subtitle preferences + encoding override rules
- Library commands use disk-side category names (`films`, `series`, etc.) for `--category`, NOT staging names (`001-MOVIES`, `002-TVSHOWS`)
- `library-clean` and `library-validate --fix` acquire pipeline lock; all other library commands are read-only
- Language codes in library preferences use ISO 639-2/T (`fra`, `eng`) — NOT 639-2/B (`fre`)
- Audio profile detection: `multi` (≥2 languages) > `vf` (French audio) > `vostfr` (non-FR audio + FR subs) > `vo` (no French)
```

- [ ] **Step 6: Commit**

```bash
git add -f CLAUDE.md
git commit -m "v14.8.1: Update CLAUDE.md with V14 library commands, config, structure"
```

---

## Task 2: Update MANUAL.md

**Files:**

- Modify: `MANUAL.md`

- [ ] **Step 1: Read current MANUAL.md structure**

Read the file to understand existing sections and language (French).

- [ ] **Step 2: Add "Maintenance médiathèque" section**

Add after the existing pipeline section:

````markdown
## Maintenance de la médiathèque

Les commandes `library-*` permettent d'entretenir la médiathèque existante sur les disques de stockage (Disk1-4). Contrairement au pipeline qui traite les **nouveaux** médias, ces commandes analysent et nettoient les médias **déjà stockés**.

### Scanner la médiathèque

```bash
# Scanner tous les disques (structure, NFO, artwork — pas de ffprobe)
personalscraper library-scan

# Scanner un seul disque
personalscraper library-scan --disk Disk1

# Scanner une seule catégorie
personalscraper library-scan --category films
```
````

Produit `library_scan.json` dans `.personalscraper/`.

### Nettoyer la médiathèque

```bash
# Aperçu (dry-run par défaut — ne supprime rien)
personalscraper library-clean

# Supprimer les dossiers .actors/ (inutiles pour Plex)
personalscraper library-clean --apply --only actors

# Supprimer les répertoires vides
personalscraper library-clean --apply --only empty

# Supprimer les fichiers système (.DS_Store, Thumbs.db, desktop.ini)
personalscraper library-clean --apply --only junk

# Tout nettoyer sur un seul disque
personalscraper library-clean --apply --disk Disk1
```

⚠️ `--apply` est requis pour supprimer. Sans `--apply`, la commande affiche ce qui serait supprimé.

### Valider la médiathèque

```bash
# Vérifier la conformité (NFO, artwork, nommage, structure)
personalscraper library-validate

# Vérification rapide (NFO + poster seulement)
personalscraper library-validate --level quick

# Corriger automatiquement les problèmes fixables
personalscraper library-validate --fix --apply
```

### Analyser les encodages

```bash
# Analyse approfondie avec ffprobe (codec, audio, sous-titres)
personalscraper library-analyze

# Mode incrémental (ne réanalyse pas les fichiers déjà connus)
personalscraper library-analyze --incremental

# Limiter le nombre de médias analysés
personalscraper library-analyze --max-items 100

# Analyser un seul disque
personalscraper library-analyze --disk Disk2
```

⏱️ Commande la plus lente — à planifier en heures creuses.

### Recommandations de retéléchargement

```bash
# Générer la liste de recommandations
personalscraper library-recommend

# Trier par gain d'espace potentiel
personalscraper library-recommend --sort size

# Exporter en CSV
personalscraper library-recommend --export csv
```

Les recommandations sont basées sur les préférences dans `library_preferences.json` :

- Codec préféré (HEVC par défaut)
- Taille maximale par film/épisode
- Priorité audio (MULTI > VF > VOSTFR > VO)
- Sous-titres requis (français par défaut)
- Règles de surcharge par titre, ID IMDB, genre

### Rapport de santé

```bash
# Rapport complet dans le terminal
personalscraper library-report

# Exporter en JSON
personalscraper library-report --format json
```

### Planification par cron

Chaque commande est indépendante et planifiable séparément :

```bash
# Scan léger quotidien à 2h
0 2 * * * /path/to/personalscraper library-scan

# Nettoyage hebdomadaire le dimanche à 3h
0 3 * * 0 /path/to/personalscraper library-clean --apply

# Analyse profonde mensuelle le 1er à 4h
0 4 1 * * /path/to/personalscraper library-analyze --incremental

# Recommandations après chaque analyse
30 4 1 * * /path/to/personalscraper library-recommend
```

### Configuration des préférences

Le fichier `.personalscraper/library_preferences.json` contient toutes les préférences :

```json
{
  "video": {
    "preferred_codec": "hevc",
    "fallback_codecs": ["av1"],
    "rejected_codecs": ["mpeg2", "mpeg4"],
    "preferred_resolution": "1080p",
    "max_size_movie_gb": 4.0,
    "max_size_episode_gb": 2.0
  },
  "audio": {
    "profile_priority": ["multi", "vf", "vostfr", "vo"],
    "min_channels": 2
  },
  "subtitles": {
    "required_languages": ["fra"],
    "preferred_languages": ["fra", "eng"]
  },
  "encoding_rules": [
    { "criteria": { "imdb_id": "tt4154796" }, "resolution": "2160p" }
  ]
}
```

````

- [ ] **Step 3: Commit**

```bash
git add -f MANUAL.md
git commit -m "v14.8.2: Add 'Maintenance médiathèque' section to MANUAL.md (French)"
````

---

## Task 3: Polish ROADMAP.md

**Files:**

- Modify: `ROADMAP.md`

- [ ] **Step 1: Move V14 from "In Progress" to "Implemented"**

Update the tables in ROADMAP.md to reflect V14 completion.

- [ ] **Step 2: Commit**

```bash
git add ROADMAP.md
git commit -m "v14.8.3: Update ROADMAP.md — V14 complete"
```

---

## Task 4: Polish CLI --help grouping

**Files:**

- Modify: `personalscraper/cli.py`

- [ ] **Step 1: Add Rich help panels to group commands**

Typer supports `rich_help_panel` to group commands visually. Update each library command decorator:

```python
@app.command(rich_help_panel="Library (existing media)")
```

And each existing pipeline command:

```python
@app.command(rich_help_panel="Pipeline (new media)")
```

This produces grouped output in `personalscraper --help`.

- [ ] **Step 2: Verify --help output**

Run: `personalscraper --help`

Expected output should show two panels:

```
╭─ Pipeline (new media) ──────────╮
│  ingest, sort, scrape, ...      │
╰─────────────────────────────────╯
╭─ Library (existing media) ──────╮
│  library-scan, library-clean, . │
╰─────────────────────────────────╯
```

- [ ] **Step 3: Verify each command --help**

Run each command with `--help` and verify descriptions, options, and examples are shown:

```bash
personalscraper library-scan --help
personalscraper library-clean --help
personalscraper library-validate --help
personalscraper library-analyze --help
personalscraper library-recommend --help
personalscraper library-report --help
```

- [ ] **Step 4: Commit**

```bash
git add personalscraper/cli.py
git commit -m "v14.8.4: Add Rich help panels — group Pipeline vs Library commands"
```

---

## Task 5: Update docs/IMPLEMENTATION.md

**Files:**

- Modify: `docs/IMPLEMENTATION.md`

- [ ] **Step 1: Fill in the phase table**

Update the Global Status table with all 9 phases and their completion status.

- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v14.8.5: Update IMPLEMENTATION.md with V14 phase completion"
```

---

## Acceptance Criteria — Phase 8

- [ ] CLAUDE.md has V14 commands, config notes, version table entry, directory structure
- [ ] MANUAL.md has complete French "Maintenance médiathèque" section with all 6 commands
- [ ] ROADMAP.md updated with V14 in "Implemented"
- [ ] `personalscraper --help` shows grouped Pipeline / Library panels
- [ ] Each `library-*` command has descriptive --help with examples
- [ ] `docs/IMPLEMENTATION.md` reflects all completed phases
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`
