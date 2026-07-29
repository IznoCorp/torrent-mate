# DESIGN — scrape-follow-id : au scrape d'une série suivie, réutiliser l'ID TVDB du suivi

**Codename** : `scrape-follow-id` · **Type** : `fix` · **Bump** : minor (0.62.0 → 0.63.0)
**Ticket** : #338 · **Merge** : auto

## Constitution produit (CONTRAIGNANT)

Sert `docs/reference/product-intent.md` **§2 (véridicité)** : un épisode suivi et acquis doit
atterrir sous la MÊME identité que le suivi, dans le MÊME dossier que ses autres épisodes —
jamais splitté sous une identité concurrente qui rend l'acquisition incohérente.

## Problème (incident Rooster, 2026-07-29)

Le scraper re-matche librement chaque dossier de staging (titre → recherche TVDB → meilleur
match). Pour une série suivie, ce re-match peut résoudre une **fiche TVDB différente** de celle
du suivi quand TVDB a des doublons (ex. « Rooster » tvdb **457770** = le suivi, vs
« ニワトリ・ファイター » tvdb **452575** = titre japonais). Résultat : les épisodes E06-E10 ont
été dispatchés dans un **2ᵉ dossier** sous 452575, splittant la série et **cassant le reconcile**
d'acquisition (les `wanted` restent `grabbed` / « en cours d'acquisition » à vie, car
`ownership.owns(media_ref = tvdb du suivi 457770)` ne trouve pas les épisodes sous 452575).

Voir `[[project_tvdb_duplicate_split_reconcile_break]]`.

## Approche : forcer l'ID du suivi au scrape (provenance depuis la file wanted)

Le primitive existe déjà : `TvServiceMixin.scrape_tvshow_forced(show_dir, source, provider_id)`
scrape en **contournant le matching** (utilisé aujourd'hui par la resolve-queue manuelle,
`commands/scrape_resolve.py`). Il suffit de l'appeler automatiquement quand le dossier provient
d'une série suivie, avec l'ID TVDB du suivi.

### Résolveur de provenance — `resolve_followed_tvdb(show_dir, store) -> int | None`

Auto-contenu, sans modifier l'ingest. Au scrape, pour un dossier de show :

1. Extraire l'ensemble `(saison, épisode)` du dossier (mêmes parseurs que le sorter/scraper).
2. Interroger le store d'acquisition : les `wanted` **`grabbed`** (kind=`episode`) dont le
   `media_ref.tvdb_id` est défini et dont `(season, episode)` **recouvre** les épisodes du dossier.
3. **Garde de sûreté (anti-collision)** : la similarité entre le titre du dossier (nettoyé) et le
   titre du suivi correspondant doit dépasser un seuil (rapidfuzz) — pour ne pas forcer un mauvais
   suivi qui partagerait un `S01E06`. Si plusieurs `tvdb_id` distincts recouvrent le dossier → abstention.
4. Si **un seul** `tvdb_id` recouvre le dossier et passe la garde → le renvoyer. Sinon `None`.

Les `wanted` sont encore `grabbed` au moment du scrape (le reconcile `grabbed→done` n'a lieu
qu'après dispatch), donc la provenance est disponible.

### Injection dans l'orchestrateur de scrape

`Scraper.__init__` gagne une dépendance optionnelle `follow_tvdb_resolver: Callable[[Path], int | None] | None`.
Dans la boucle de scrape (`orchestrator.py`, avant `self.scrape_tvshow(show_dir)`) :

```
forced = self._follow_tvdb_resolver(show_dir) if self._follow_tvdb_resolver else None
result = (self.scrape_tvshow_forced(show_dir, "tvdb", forced) if forced is not None
          else self.scrape_tvshow(show_dir))
```

La composition du pipeline (là où le `Scraper` et l'`AcquireStore` coexistent) lie le résolveur au
store. **Fail-soft** : toute exception du résolveur ⇒ `None` (on retombe sur le match libre — jamais
de blocage du scrape). Rétro-compatible : sans résolveur (None), comportement inchangé.

## Séparation multi-provider

TVDB reste le primaire. Le résolveur n'utilise que le `tvdb_id` du suivi ; aucun re-match, aucune
cross-contamination. Films : hors périmètre (cycle titre §5, pas de split épisode).

## Non-buts

- Pas de modification de l'ingest (le résolveur lit la file wanted au scrape).
- Pas de fusion rétroactive des splits existants (fait par la réparation manuelle ; ici on
  **prévient** les futurs).
- Pas de forçage pour un dossier non-suivi (match libre inchangé).

## ACCEPTANCE (commandes exécutables)

- **ACC-01** — `resolve_followed_tvdb` golden : un dossier `Rooster Fighter S01E06-E10` + des
  `wanted` grabbed (tvdb 457770, S01E06-E10, titre suivi « Rooster ») ⇒ renvoie `457770`.
  `pytest tests/scraper/test_resolve_followed_tvdb.py` → passed.
- **ACC-02** — garde anti-collision : deux suivis partageant `S01E06` (tvdb A et B) ⇒ `None`
  (abstention) ; titre dissemblable ⇒ `None`.
- **ACC-03** — fail-soft : store indisponible / exception ⇒ `None`, jamais d'exception propagée.
- **ACC-04** — orchestrateur : quand le résolveur renvoie un id, `scrape_tvshow_forced` est appelé
  (spy) au lieu de `scrape_tvshow` ; sans id, `scrape_tvshow` (libre) est appelé. Rétro-compat : sans
  résolveur, comportement inchangé.
- **ACC-05** — `make check` vert ; pas de dérive OpenAPI (aucun changement de contrat web).

## Phases (indicatif — `/implement:plan` fait foi)

1. **Résolveur** — `resolve_followed_tvdb` (parse épisodes + lookup wanted grabbed + garde titre) + tests (ACC-01→03).
2. **Injection orchestrateur + composition** — `Scraper.follow_tvdb_resolver` + branchement + wiring pipeline + tests (ACC-04).
3. **ACC + gate** — `make check`, preuve (le scrape d'une série suivie force l'ID du suivi).
