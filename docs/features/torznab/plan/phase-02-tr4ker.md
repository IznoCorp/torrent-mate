# Phase 02 — Client Tr4ker + activation + config

**Goal**: Tr4ker = seconde config du générique. Preuve que « nouveau tracker = config + doc,
zéro code » — la classe Tr4ker doit être ~vide (descriptor + ClassVars).

**Design**: DESIGN §3 D2.

## Surface

| Fichier                                                                                                                 | Action                                                                                                  |
| ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `personalscraper/api/tracker/tr4ker.py`                                                                                 | **NEW** — descriptor tr4ker (base https://tr4ker.net, api_path /api/torznab)                            |
| `personalscraper/api/_contracts.py`                                                                                     | `ProviderName.TR4KER = "tr4ker"`                                                                        |
| `personalscraper/api/_activation.py`                                                                                    | `PROVIDER_CREDS["tr4ker"]=["TR4KER_API_KEY"]`, `PROVIDER_OPTIONAL_SECRETS["tr4ker"]=["TR4KER_PASSKEY"]` |
| `personalscraper/acquire/_factory.py` (ou le site réel de construction — vérifier `tests/unit/test_tracker_factory.py`) | construction tr4ker                                                                                     |
| `config/tracker.json5` + `config.example/tracker.json5`                                                                 | entrée tr4ker enabled:true, priority ["c411","tr4ker"], commentaires PROVIDER_CREDS à jour              |
| `tests/unit/test_tr4ker_client.py`                                                                                      | **NEW** — descriptor + URL construction + auth param                                                    |
| `tests/unit/test_activation.py`, `test_tracker_factory.py`, `test_tracker_capabilities_composition.py`                  | étendus à tr4ker                                                                                        |

## Points de vigilance

- L'auth est `apikey=` query param (clé API du profil) — PAS la passkey. Les entrées
  `.env` opérateur `TR4KER_USERNAME/PASSWORD` sont des restes torr9 : ne PAS les câbler.
- La priority place c411 avant tr4ker (c411 = tracker principal éprouvé ; l'opérateur
  pourra inverser en config).
- Registry naming : `ProviderName` (transport) vs `RegistryProviderName` (registry) — suivre
  la convention (archive registry DESIGN §5.3) ; vérifier si le tracker registry consomme
  l'un ou l'autre avant d'ajouter.

## Sous-phases

### 2.1 — `feat(torznab): add tr4ker as a torznab descriptor`

### 2.2 — `feat(torznab): wire tr4ker activation and construction`

### 2.3 — `test(torznab): tr4ker descriptor, activation gating, factory`

## Gate

1. `pytest tests/unit/ -q -k "tr4ker or torznab or activation or tracker"` — vert.
2. `python3 -m mypy personalscraper/` — 0.
3. Boot réel : `python3 -c "..."` charge la config et construit le registry avec
   `active_trackers=['c411','tr4ker']` (les creds TR4KER_API_KEY existent-elles dans le
   .env ? si NON : l'activation doit proprement dégrader — tr4ker inactif + log clair —
   et la gate le constate ; l'opérateur ajoutera la clé).
4. `pytest tests/acquire/ tests/conf/ -q` — vert.
