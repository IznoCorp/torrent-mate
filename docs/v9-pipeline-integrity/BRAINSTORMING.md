# V9 — PIPELINE INTEGRITY : Brainstorming

> Pipeline sequentiel exhaustif avec check de coherence avant dispatch.

## Contexte

V0-V8 implementes. Le pipeline fonctionne mais l'execution reelle a revele des problemes d'integrite :

1. Des fichiers ingerés et triés dans le même run arrivent dans 001-MOVIES/002-TVSHOWS mais ne sont pas toujours scrapes correctement (noms bruts non-reconnus, doublons non-fusionnes).
2. Le dispatch tourne même si des items sont "blocked" — il dispatch les items deja clean et ignore les nouveaux.
3. Des residus persistent : dossiers vides apres fusion, fichiers orphelins, doublons non-detectes.
4. Les tests E2E ne detectent pas ces problemes car ils testent chaque step isolement.
5. Des noms de dossiers mal nettoyes ("Avatar de feu et de cendres 7 1 neostark") passent a travers le sort sans detection.
6. Le scrape renomme les series avec le titre TVDB anglais au lieu du titre FR local.

Le pipeline doit être restructure en phases exhaustives avec gates : chaque phase 100% terminee avant la suivante.

## Decisions prises

### D1 — Architecture 5 phases avec gates

Pipeline sequentiel : INGEST → SORT → PROCESS → VERIFY → DISPATCH. Gate entre sort et process (097-TEMP doit être vide). Gate entre verify et dispatch (dispatch seulement si items dispatchable).

**Rationale :** Le pipeline lineaire actuel ne garantit pas que les items sont entierement traites avant dispatch. Les gates forcent la completion.

### D2 — Dispatch partiel

Le dispatch envoie les items valid/fixed. Les items blocked restent dans 001/002 avec un rapport detaille. Le dispatch ne tourne PAS si aucun item dispatchable.

**Rationale :** Bloquer tout le dispatch pour un seul item en erreur serait trop strict. Les items clean doivent avancer.

### D3 — Phase PROCESS = 3 StepReports

La Phase 3 produit 3 rapports separes dans le panel final : "clean" (re-clean + dedup), "scrape" (NFO + artwork), "cleanup" (dossiers vides). Plus de visibilite qu'un seul compteur agrege.

**Rationale :** L'utilisateur doit voir combien de dossiers ont ete re-nettoyes et combien de doublons fusionnes, pas juste "5 OK".

### D4 — Detection des noms pollues en deux passes

1. Passe locale rapide (guessit) : si le titre extrait contient des tokens de release (codec, resolution, release_group), c'est pollue → re-clean.
2. Passe API (TMDB/TVDB) : si un dossier sans NFO ne matche rien avec confidence > 0.5 sur le titre actuel → re-clean via guessit et retenter.

**Rationale :** La passe locale detecte les cas evidents sans appel API. La passe API attrape les cas ou le titre est "propre" syntaxiquement mais ne correspond a rien (ex: titre tronque ou mal extrait). C'est le fix pour #25 (Avatar).

### D5 — Titre local (FR) prefere pour le renommage

Configurable via `SCRAPER_PREFER_LOCAL_TITLE` dans `.env` (defaut: `true`). Quand active, le scrape utilise le titre dans `scraper_language` (fr-FR) depuis les donnees detaillees TMDB pour renommer les dossiers, avec fallback sur le titre API si pas de traduction.

**Rationale :** TVDB renvoie les titres en anglais, TMDB permet de specifier la langue. Le titre local est plus naturel pour l'utilisateur. Configurable car certains users preferent les titres originaux. C'est le fix pour #28 (Jury Duty).

### D6 — Mode interactif pour les matches ambigus

`--interactive` : quand un match API echoue, propose les resultats proches. L'utilisateur choisit ou skip. Skip → blocked au verify. En mode auto (cron) : log warning, l'item reste blocked.

**Rationale :** Le mode interactif existe deja pour le scrape. On l'etend au re-clean de la Phase 3.

### D7 — Criteres verify renforces

Films : nom `Title (Year)`, video presente, NFO valide, poster present, pas de dossiers vides.
Series : nom `Show (Year)`, tvshow.nfo valide, >= 1 Saison XX/ avec episodes, episodes renommes `S01E01 - Title.ext`, poster present, pas de dossiers vides.

**Rationale :** Les criteres actuels ne verifient pas les episodes renommes ni les dossiers vides. Ces residus causent des problemes apres dispatch.

## Contraintes techniques

1. Les 898 tests existants ne doivent pas casser
2. Les commandes standalone (`personalscraper ingest`, `sort`, `scrape`, `verify`, `dispatch`) continuent de fonctionner independamment
3. Le format StepReport/PipelineReport ne change pas (ajout de steps, pas de modification)
4. Le circuit breaker V8 reste actif pendant la Phase 3 (scrape)
5. `--dry-run` doit fonctionner pour toutes les phases
6. Le lock pipeline empeche les executions concurrentes (inchange)
7. Le panel final rich affiche 7 lignes au lieu de 5 (ingest, sort, clean, scrape, cleanup, verify, dispatch)

## Flux propose

```
complete/ ──[INGEST]──→ 097-TEMP/
                           │
                    [SORT + CLEAN]
                           │
                    ┌──────┴──────┐
                    │ GATE: empty │
                    └──────┬──────┘
                           │
              001-MOVIES/, 002-TVSHOWS/
                           │
                ┌──────────┴──────────┐
                │   PHASE 3: PROCESS  │
                │  a) re-clean names  │
                │  b) dedup folders   │
                │  c) scrape API      │
                │  d) episode rename  │
                │  e) cleanup empties │
                └──────────┬──────────┘
                           │
                ┌──────────┴──────────┐
                │  PHASE 4: VERIFY    │
                │  coherence check    │
                └──────┬────────┬─────┘
                       │        │
                  valid/fixed  blocked
                       │        │
                [DISPATCH]   [STAY]
                       │        │
                  Disk1-4    001/002
```

## Points de design a trancher

Aucun — toutes les decisions sont prises.
