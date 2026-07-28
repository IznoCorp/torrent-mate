# DESIGN — plex-refresh : scan Plex déclenché après dispatch

**Codename**: `plex-refresh` · **Ticket**: #328 · **Type**: `feat` · **Bump**: 0.58.0 → 0.59.0
**Constitution**: NE-DOIT-PAS-5 (échec silencieux), fail-soft contract (modèle Telegram).

## Bug prouvé (Margin Call, 2026-07-28)

Acquisition→dispatch→indexation complète, film sur disque avec NFO/artwork, **invisible dans
Plex** : aucun déclencheur de scan n'existe dans le pipeline, et les disques macFUSE/NTFS ne
délivrent aucun événement filesystem à Plex. Réparation manuelle exécutée (scan partiel ciblé
HTTP 200 → film visible) ; ce design corrige la cause.

## D1 — L'événement porte le dossier cible

`ItemDispatched` (dispatch/events.py) gagne un champ **additif** `target_path: Path | None = None`
— le dossier destination exact, que le dispatcher connaît au moment de l'émission (move/merge/
replace). Additif + défaut None : aucun émetteur/consommateur existant ne casse ; le dispatcher
le remplit. (Contrat event_bus REQUIS partout inchangé.)

## D2 — PlexClient + PlexSubscriber

`personalscraper/api/plex.py` : client minimal — `sections()` (GET /library/sections, cache
process, lazy au premier événement), `refresh(path)` (GET /library/sections/{id}/refresh?path=…,
section résolue par le **plus long préfixe** parmi les `Location` paths des sections ; aucun
mapping en dur). Token en query/`X-Plex-Token` header, **jamais loggé** (répr/str des URLs
expurgées). Timeouts courts, 1 tentative (déclencheur best-effort, pas une API métier).

`personalscraper/subscribers/plex.py` : `PlexSubscriber` consomme `ItemDispatched` →
`target_path` non-None → `client.refresh(target_path)`. **Fail-soft absolu** : Plex down /
token invalide / section introuvable ⇒ warning loggé, le dispatch reste un succès (modèle
TelegramSubscriber). Un refresh par événement (un dossier), pas de rafale.

## D3 — Config et câblage

`Settings` : `PLEX_URL` (défaut http://localhost:32400) + `PLEX_TOKEN` (None ⇒ subscriber non
câblé, log info une fois). `.env.example` documenté. Câblage aux mêmes frontières que le
TelegramSubscriber (les chemins pipeline/runners qui dispatchent).

## ACC

| ID     | Critère                                                                                                                                  |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | Dispatch simulé → le subscriber appelle refresh avec le bon dossier et la bonne section (préfixe le plus long, fixtures multi-sections). |
| ACC-02 | Plex injoignable/401 ⇒ dispatch succès + warning ; token absent ⇒ subscriber non câblé, zéro requête.                                    |
| ACC-03 | Le token n'apparaît dans AUCUN log/exception (test scannant les records).                                                                |
| ACC-04 | Réel : un refresh ciblé sur un dossier existant de la médiathèque → HTTP 200 (une requête, lecture seule côté données).                  |
| ACC-05 | make check vert ; .env.example à jour ; docs/reference/plex-api.md présent + indexé.                                                     |

## Hors périmètre

Scan des sections temporaires (097-TEMP) ; suppression côté Plex ; webhooks Plex entrants.
