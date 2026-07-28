# DESIGN — acq-debt : reliquat de review PR #320 + dette de modules

**Codename**: `acq-debt` · **Ticket**: #324 · **Type**: `fix` · **Bump**: 0.57.1 → 0.58.0 (minor)
**Constitution**: NE-DOIT-PAS-1 (mentir), NE-DOIT-PAS-5 (échec silencieux), NE-DOIT-PAS-8.

Solde les ouverts tracés `PR #320 review` dans le code, plus deux modules au-delà du
seuil advisory. Chaque item a son marqueur au site exact — les retrouver par
`rg -n "PR #320 review" -t py personalscraper/`.

## D1 — M6 : borner l'I/O provider du POST /followed

L'enrichissement métadonnées construit un registry par requête ; pire cas mesuré
~2 min (4 tentatives × timeouts pleins × 2 providers) dans le threadpool du POST.
**Décision** : seam d'override de politique par construction — les deux clients
métadonnées construits pour l'enrichissement reçoivent une `TransportPolicy`
resserrée (attempts=1, timeouts existants), via un paramètre optionnel du
constructeur de contexte/factory (PAS de mutation d'attributs privés). Pire cas
visé ≤ ~25 s. Fail-soft inchangé.

## D2 — M9 : fenêtre add()→mark_grabbed

Le hash n'est persisté qu'après l'add → un crash entre les deux laisse un torrent
orphelin dans qBittorrent sans obligation de seed, et la reprise est une nouvelle
recherche (pas un replay). **Décision** : ligne d'intention pré-add —
`record_search_outcome`-style : avant `add()`, persister le hash choisi sur la ligne
wanted (colonne existante `grabbed_hash`, statut encore `searching`) ; `mark_grabbed`
devient la confirmation de statut. La reprise stale voit un hash → réconcilie contre
le client (le torrent y est → confirmer grabbed + obligation ; absent → nettoyer le
hash et re-chercher). Les docstrings « OPEN » de service.py/domain.py tombent.
Invariant §11d (exactly-once emit) re-testé.

## D3 — Carte film sur ligne fermée unique

`compute_movie_truth` garde la règle « most-recent-any-status » : un film dont la
seule ligne est `abandoned` lit « En attente ». **Décision** (complétion TODO,
règle unifiée) : alignement sur **open-rows-latest** — une ligne fermée est de
l'histoire ; sans ligne ouverte ni possession → `non_verifie`. Changement visible
sur cartes films assumé, testé, noté au CHANGELOG.

## D4 — m15 : surfacer tracker_auth (et circuit_open)

`SearchOutcome` ne porte que `errored_names` → une clé cassée est un
`trackers_unavailable` perpétuel (jamais terminal), et le label search-stage
`circuit_open` a été folded en #322. **Décision** : `SearchOutcome.errors:
dict[str, str]` (nom → taxon d'erreur : `auth`/`circuit`/`api`) en complément de
`errored_names` (conservé). `_search_chain` : tous les trackers en `auth` ⇒
verdict terminal `tracker_auth` ; tous en `circuit` ⇒ `circuit_open` ; mélange ⇒
`trackers_unavailable` (inchangé). Les états UI ne bougent pas (INCONCLUSIVE
couvre déjà ces outcomes ; `tracker_auth` reste terminal → abandon guardé).

## D5 — m23 + m24

m23 : le registry par requête de l'enrichissement/recherche web se ferme
(context manager sur le seam de construction — couvre aussi D1). m24 : migration
indexer — index partiel `pipeline_run(command) WHERE ended_at IS NULL` (la
requête d'amorce du GET /followed scanne la table à chaque poll).

## D6 — Splits de modules

`web/routes/acquisition.py` (~990) : extraire les blocs cohérents vers
`web/acquisition/` (helpers de métadonnées, construction d'items) — routes fines.
`acquire/service.py` (~900) : scinder passe search / passe grab en modules
consommés par la façade `AcquisitionService` (surface publique inchangée, tests
existants = pin). Cible : les deux sous 800 non-blank.

## ACC (exécutables)

| ID     | Critère                                                                                                                                                                                 |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | POST /followed avec providers simulés lents : durée totale bornée ≤ 30 s (test chronométré avec fake sleep hooks).                                                                      |
| ACC-02 | Crash simulé entre add() et mark_grabbed : au run suivant, le torrent est confirmé `grabbed` + obligation enregistrée — zéro orphelin (test d'intégration store+client fake).           |
| ACC-03 | Film dont la seule ligne est `abandoned` ⇒ carte `non_verifie` (plus jamais « En attente »).                                                                                            |
| ACC-04 | Clé tracker cassée sur TOUS les trackers ⇒ verdict `tracker_auth` terminal (test registry→chain) ; `rg "PR #320 review" -t py personalscraper/` ⇒ 0 hit restant pour M6/M9/m15/m23/m24. |
| ACC-05 | `python3 scripts/check-module-size.py` : acquisition.py et service.py sous 800 ; zéro WARN nouveau.                                                                                     |
| ACC-06 | `make check` vert ; `make openapi` sans drift non commité.                                                                                                                              |
| ACC-07 | ACC-12 de #320 (réel) : clic « Récupérer maintenant » + preuve 390 px — exercé dans la fenêtre 15:10-15:20 si disponible, sinon documenté différé avec date.                            |

## Hors périmètre

Ticket config/-partagé-prod (item 8 du ticket #324) → ticket séparé, créé en fin de
feature. `FreeleechAware`/`TorrentDetailsProvider` restent (artefacts design R1).
