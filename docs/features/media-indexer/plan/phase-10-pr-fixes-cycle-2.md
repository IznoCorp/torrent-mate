# Phase 10 — PR fixes cycle 2

## Context

Bugs détectés pendant le smoke-test pipeline du 2026-04-29 sur la branche `feat/media-indexer`.

**Scope** : ces bugs ne sont **pas** introduits par la feature media-indexer (ils sont pré-existants) mais ont été révélés par le run pipeline. On les regroupe ici pour les corriger en un seul cycle avec les bugs spécifiques à la feature qui seront trouvés au prochain run pipeline (après bootstrap de l'indexer).

**Ne pas lancer cette phase** tant que les bugs feature-spécifiques n'ont pas été ajoutés (post-bootstrap + 2nd pipeline run).

## Sub-phases

### 10.1 — Fix: Silent scrape failure on common-title movies (The Butterfly Effect)

**Finding (Major)** : `personalscraper process` a "réussi" (`Scrape: 8 OK / 6 skipped / 0 errors`) mais le dossier `001-MOVIES/The Butterfly Effect (2004)/` reste avec uniquement le `.mkv` brut — **aucun .nfo, aucun artwork**. Aucune erreur loggée. VERIFY le marque ensuite `blocked`.

**Step concerné** : process / scrape
**Item reproductible** : `The.Butterfly.Effect.2004.DC.MULTi.TRUEFRENCH.1080p.BluRay.mHD.x264.DTS-PATOMiEL.mkv`

**Hypothèse root cause** : le matcher TMDB renvoie soit 0 soit plusieurs candidats pour "The Butterfly Effect" (titre commun, plusieurs films), ne franchit pas le seuil de confidence, et est silencieusement skip — mais le compteur `error_count` n'est pas incrémenté et l'item disparaît du flux.

**Fix shape** :

- Identifier où `match_movie` / `match_tvshow` (`personalscraper/scraper/matcher.py` ou `confidence.py`) bail-out sans logger.
- Soit logger en `warning` avec `event="scraper.match.below_threshold"` + `title`, `year`, `candidates_count`, `top_score`.
- Soit incrémenter un compteur `unmatched` séparé du `error` et le surfacer dans la sortie finale (`Scrape: X OK / Y skipped / Z unmatched / W errors`).
- **Acceptance** : le run reproduit Butterfly Effect → soit le NFO est généré, soit le log warning est visible et le compteur `unmatched=1` apparaît.

---

### 10.2 — Fix: Raw torrent dir not flattened when title has no year (Les secrets du Prince Andrew)

**Finding (Major)** : après PROCESS, `002-TVSHOWS/Les secrets du Prince Andrew/` contient encore le sous-dossier brut du torrent `Les.secrets.du.Prince.Andrew.2023.S01.DOC.FRENCH.1080p.WEB.H264-BOUBA/` au lieu d'être aplati à la structure Plex (`Saison 01/...`). Pas de `tvshow.nfo`, pas de poster.

**Step concerné** : process / clean (sub-step de `process`)
**Item reproductible** : `Les.secrets.du.Prince.Andrew.2023.S01.DOC.FRENCH.1080p.WEB.H264-BOUBA`

**Hypothèse root cause** : le clean phase dépend du match scraper pour décider de la structure cible. Quand le scraper échoue (cf 10.1 ou autre), le clean ne sait pas quoi faire et laisse l'arborescence brute. Le folder est renommé canoniquement (`Les secrets du Prince Andrew` au lieu de `Les.secrets.du.Prince.Andrew.2023...`) mais le contenu n'est pas réorganisé.

**Fix shape** :

- Idéalement résolu par 10.1 (si le matcher loggue son échec, le clean peut décider explicitement de skip plutôt que de partial-action).
- En complément : `personalscraper.process.cleaner` doit refuser d'opérer sur un dossier dont le scraper n'a pas réussi à matcher → ne pas renommer le dossier, laisser le torrent brut tel quel pour rescrape ultérieur.
- **Acceptance** : reproduire Les secrets du Prince Andrew → soit le scrape réussit, soit le dossier reste à son nom torrent original, et un log `process.clean.skipped_unmatched` apparaît.

---

### 10.3 — _(placeholder, à remplir avec les bugs de la feature media-indexer trouvés au 2ᵉ pipeline run)_

Après le bootstrap `library index --mode full` et le re-run pipeline avec l'outbox actif, ajouter ici les bugs trouvés (publish_event qui rate, drift detection qui rate, etc.).

---

## Out of scope

- Bugs Cycle 1 déjà corrigés (C1, C2, M1–M4)
- Items déjà déclassés à minor / deferred (~30 items dans IMPLEMENTATION.md cycle 1)
