# Phase 6 — Format unification + heavy documentation reference

**Effort** : 3-4 jours (revised — heavy doc rot work post REDO)
**Theme** : standardiser output formats + docs reference exhaustives + sync archive
references avec post-refactor reality.

## Coverage matrix

| Item                               | Sub-phase | Source pattern |
| ---------------------------------- | --------- | -------------- |
| SH-13 / DEV #22 / CL-D + CL-E      | 6.1       | P22            |
| SH-12 / CL-J                       | 6.2       | P8, P29        |
| SH-18 + SH-19 + AR-A + AR-B + AR-E | 6.3       | P26, P27, P29  |
| SH-1 / BD-E                        | 6.4       | (doc)          |
| SH-2 / BD-R / CF-H                 | 6.5       | P30            |
| **DEV #5 counter asymmetry doc**   | 6.6 NEW   | (audit)        |
| **DEV #4 ENFORCE scope doc**       | 6.6 NEW   | (audit)        |

DESIGN sections impacted : §10 CLI, §11 architecture, §12 doc conformity.

## Gate

- Phase 5 commited (library-doctor existant pour valider --format)
- Phases 3+5 ont introduit les nouveaux events / commands à documenter

## Sub-phases

### 6.1 --format global flag (SH-13 / DEV #22 / CL-D + CL-E)

**Site** : `personalscraper/commands/__init__.py` ou `cli_helpers.py` — callback top-level.

**Implementation** :

```python
# Top-level callback
@app.callback()
def main(
    ctx: typer.Context,
    ...,
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: json | plain | rich (default: rich)",
    ),
) -> None:
    state["format"] = output_format
    ...
```

Chaque commande qui produit un summary respecte `state["format"]` :

- `rich` → console.print Typer rich (current behavior)
- `plain` → simple text + newlines (pour grep, pipes)
- `json` → JSON serialization du dict summary

Commandes prioritaires à plumber : `library-status`, `library-reconcile`, `library-doctor`,
`info`, `torrents-list`, `library-show`, `library-search`, `library-report`.

`library-reconcile` retire son `print(json.dumps(...))` hardcodé, utilise format flag.

**Commit** : `feat(tech-debt): global --format json|plain|rich flag (DEV #22)`

- commits per commande plumbée.

### 6.2 docs/reference/commands.md exhaustive (SH-12 / CL-J)

**Site** : `docs/reference/commands.md` (existe — réécrire exhaustivement)

**Structure** : une section par commande exposée :

```markdown
## `personalscraper <cmd>`

**Purpose** : ...

**Side effects** : mutate FS / mutate BDD / read-only

**Args** :

- `--flag` : ...

**Examples** :

    personalscraper <cmd> --flag value

**Ordre canonique** : (post-dispatch / post-scrape / etc.)

**Related** : `<other-cmd>`
```

À couvrir : 30 commands top-level + 5 sub-commands = 35 entries.

**Commit** : `docs(tech-debt): exhaustive commands.md reference (SH-12)`

### 6.3 docs/reference/architecture.md — state ownership + module relationships (SH-18 / SH-19 / AR-A + AR-B)

**Site** : `docs/reference/architecture.md` (existe — étendre)

**Nouvelles sections** :

- **State ownership matrix** : table FS owns X / BDD owns Y / Pipeline owns Z / EventBus
  owns W. Reference au pattern P27.
- **Module relationships** : diagramme + texte expliquant library/scanner ↔ indexer/scanner
  ↔ scraper ↔ commands ↔ trailers (pattern P19 + P26 + critique items 12 §1.A/B/C/E).
- **Anti-décisions 1.0** (AR-E) : "Out of scope for 1.0" — no microservices, no auth, no
  network server, no plugin loader, no cloud.

**Commit** : `docs(tech-debt): architecture.md state ownership + module relationships +
anti-decisions (SH-18, SH-19, AR-E)`

### 6.4 docs/reference/indexer.md — lifecycle media_file (SH-1 / BD-E)

**Site** : `docs/reference/indexer.md` (existe — étendre)

**Section nouvelle** : State machine media_file :

```
discovered (oshash=NULL, Stage A)
  → enriched (oshash set, Stage B)
  → linked (release_id set, by release_linker)
  → verified (last_verified_at bumped on full scan)
  → missed (miss_strikes++ when not visited in scan_generation)
  → tombstoned (deleted_at set + deleted_item row inserted)
```

- diagramme + transitions + sites code (drift.py, release_linker.py, etc.).

**Commit** : `docs(tech-debt): media_file lifecycle state machine (SH-1)`

### 6.5 docs/reference/runbook-backfill-ids.md (SH-2 / BD-R / CF-H)

**Site** : `docs/reference/external-ids-flow.md` (existe — vérifier + étendre)

**Contenu** :

- Quand lancer backfill-ids (post merge provider-ids, post library-scan, etc.)
- Comment vérifier le résultat (queries SQL, library-doctor)
- Backoff / API quota (TMDB / TVDB / OMDB)
- Cron / launchd entry exemple

**Commit** : `docs(tech-debt): runbook backfill-ids ops (SH-2)`

### 6.6 Behavioral nuances doc (DEV #4 + DEV #5)

**DEV #4 — ENFORCE scope-limited `.DS_Store` cleanup**

Document explicitement dans `docs/reference/pipeline-internals.md` ou
`docs/reference/architecture.md` §ENFORCE :

> "ENFORCE.sanitize_action `deleted_ds_store` scope is **per-item only** (only `.DS_Store`
> in the show/movie folder being enforced). Disk-wide cleanup is NOT done by ENFORCE.
> Operator runs `library-clean` for disk-wide sweep (Plex/Kodi compatibility,
> non-destructive on media files)."

→ Closes DEV #4 as "documented by design" (not a bug, but absence of doc was misleading).

**DEV #5 — Counter asymmetry PROCESS:scrape**

Document dans `docs/reference/pipeline-internals.md` §PROCESS:scrape :

> "Summary line `Scrape: N OK, M skipped, X errors` counts include `nfo_valid action=repaired`
> as OK. Per-section counters `movies_done/tvshows_done scraped=X` count only `action=scraped`,
> not `action=repaired`. This is intentional — a repair is not a fresh scrape. To get the
> total processed, sum (scraped + repaired)."

→ Documents DEV #5 as design intent. Optional follow-up : unify counter naming (0.17+).

**Commit** : `docs(tech-debt): document ENFORCE scope + PROCESS counter semantics (DEV #4, #5)`

## Phase 6 Gate

- [ ] 6.1 `personalscraper --format json library-doctor` outputs JSON (SH-13, DEV #22)
- [ ] 6.2 chaque commande a une section dans `commands.md` (SH-12)
- [ ] 6.3 architecture.md a state ownership + module relationships + anti-décisions (SH-18, SH-19, AR-E)
- [ ] 6.4 indexer.md a lifecycle media_file (SH-1)
- [ ] 6.5 external-ids-flow.md a section runbook (SH-2)
- [ ] 6.6 DEV #4 + #5 documented as design intent
- [ ] `make check` vert
- [ ] `scripts/audit-cli-coverage.py` exit 0

**Phase gate commit** : `chore(tech-debt): phase 6 gate — format + heavy doc work (DEV #4, #5, #22)`
