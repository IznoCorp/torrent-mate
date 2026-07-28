# DESIGN — torznab : retrait Torr9, base Generic Torznab, tracker Tr4ker

**Codename**: `torznab`
**Ticket**: #321
**Commit type**: `feat`
**SemVer bump**: minor — 0.56.1 → 0.57.0
**Constitution**: NE-DOIT-PAS-8 (maltraiter les dépendances), NE-DOIT-PAS-5 (échec
silencieux) ; invariants durables : fail-soft multi-tracker, jamais de clé/passkey
dans docs ou exemples.

---

## 1. Contexte et ordre opérateur

Torr9.net a fermé (2026-07-28, ordre : « Tu peux retirer Torr9 on va le remplacer par
Tr4ker »). Chaque passe search payait un timeout sur le tracker mort — coupé
immédiatement (`config/tracker.json5` : `torr9.enabled=false`, retiré de `priority`,
commit porté par cette feature).

L'opérateur veut aussi une base **Generic Torznab** : 9 trackers sur 10 parlent
Torznab — l'ajout d'un futur tracker doit devenir _config + doc, zéro code_.

## 2. Constats techniques (vérifiés)

- `personalscraper/api/tracker/c411.py` est **déjà** un client Torznab complet :
  XML Torznab/Newznab, `apikey=` en query param, aplatissement des `torznab:attr`,
  pas d'endpoint détail par torrent. C'est le socle à extraire, pas à réécrire.
- `torr9.py` était le **seul** client non-Torznab (API JSON propriétaire, login JWT
  deux temps, transport lazy « TVDB pattern »). Sa disparition supprime la dernière
  raison d'un client sur mesure.
- **Tr4ker est nativement Torznab** (doc brute `docs/tr4ker.md`, 1 035 lignes) :
  - recherche : `https://tr4ker.net/api/torznab` (alias zéro-config `/api`) —
    le tracker attend l'**API key du profil** dans `apikey=` (Mon compte →
    Paramètres), qui n'est PAS la passkey d'annonce ;
  - catalogue complet cross-seed : `/api/torznab/all` (inclut les 0-seeders) ;
  - RSS : `/api/rss?passkey=…` (+ `freeleech=1`, `cat=<slug>`) — auth par passkey.
- Le `.env` opérateur porte déjà des entrées `TR4KER_*` mais calquées sur le JWT
  torr9 (`USERNAME`/`PASSWORD`). Le modèle retenu est **une seule variable**,
  `TR4KER_PASSKEY` (convention opérateur : un secret par tracker) : c'est le
  conteneur, pas le type du secret — la valeur qu'on y met doit être l'API key du
  profil exigée par `apikey=`. La valeur actuellement présente est la passkey RSS,
  d'où le 401 et le report d'ACC-03 (cf. §5). `ANNOUNCE_URL`/`API_URL` ne
  sont consommés par aucun code (notes d'opérateur).
- La doc brute contient la **passkey réelle en clair** → le doc de référence
  distillé ne doit JAMAIS la reprendre ; le brut est supprimé en fin de feature.

## 3. Décisions d'architecture

### D1 — `torznab.py` : un client générique, des configs nommées

Extraire de `c411.py` un `TorznabClient` paramétré par un petit descriptor
(dataclass) : `provider_name`, `base_url`, `api_path`, variable d'API key, mapping
catégories, particularités (éléments `<category>` présents/absents, etc.).
`C411Client` devient la **première instanciation** du générique — comportement
**pinné byte-identique** par les tests existants (aucune régression tolérée :
c'est le seul tracker actif en prod). `Tr4kerClient` = seconde instanciation.

Rejeté : réécrire un client Torznab from scratch (c411.py est éprouvé en prod) ;
un « registre de trackers en pure config JSON5 » sans classe nommée (l'activation
par `PROVIDER_CREDS`, les enums `ProviderName`/`RegistryProviderName` et le typage
du registre attendent des noms statiques — on garde une classe fine par tracker,
mais vide de logique).

### D2 — Auth et activation Tr4ker

`PROVIDER_CREDS["tr4ker"] = ["TR4KER_PASSKEY"]` (gating — convention opérateur
2026-07-28 : une seule variable, PAS de `TR4KER_API_KEY`). Cohérent avec §2 : le
tracker attend l'API key du profil dans `apikey=`, et ce dépôt stocke cette
valeur dans l'unique variable `TR4KER_PASSKEY` — le nom de la variable désigne le
slot « secret tracker », pas la nature du secret. Tant que le slot contient la
passkey RSS, la recherche répond `401 <error code="100">` (ACC-03 différé, tracker
laissé `enabled: false`). Recherche via `/api/torznab` (le chemin documenté non
déprécié pour la recherche) ; `/api/torznab/all` réservé à un futur cross-seed
(non câblé ici, documenté seulement).

### D3 — Retrait torr9 complet

Client, tests, entrées `PROVIDER_CREDS`/`PROVIDER_OPTIONAL_SECRETS`,
`ProviderName.TORR9`, mentions dans `api_config.py`, docs. Règle phase-gate :
grep imports résiduels à zéro sur `personalscraper/` ET `tests/`. La config
`config/tracker.json5` garde une entrée `torr9` commentée « closed » jusqu'au
merge puis est purgée (les 4 obligations de seed historiques torr9 en base restent
des données valides — on ne touche pas à l'historique).

### D4 — Documentation

`docs/reference/tr4ker-api.md` distillé du brut (auth API-key vs passkey, endpoints,
RSS, catégories, règles utiles au ranking : freeleech, etc.) — **sans aucun
secret**. `docs/reference/torznab-api.md` court pour le protocole générique (ou
section dans architecture.md — au choix du plan). `c411-api.md` mis à jour
(désormais une config du générique). Brut `docs/tr4ker.md` **supprimé**.

### D5 — `.env.example` synchronisé (tâche opérateur #7)

Toutes les clés du `.env` réel mappées (noms seulement, jamais de valeurs) :
`TR4KER_PASSKEY` (unique, convention opérateur), `C411_*`, `TORR9_*` marquées `# DEPRECATED
(tracker closed 2026-07, replaced by tr4ker)`. Les entrées non-tracker manquantes
sont ajoutées aussi (audit complet du delta .env → .env.example).

## 4. Périmètre

1. Commit de la coupure prod (`config/tracker.json5`, déjà éditée).
2. `api/tracker/torznab.py` générique extrait de c411 ; C411 re-basé dessus,
   comportement pinné.
3. `Tr4kerClient` + activation + config (`config/tracker.json5` +
   `config.example/`) + enums provider.
4. Retrait torr9 (code + tests + docs + activation) ; grep résiduel zéro.
5. Docs : `tr4ker-api.md` (sans secrets), maj `c411-api.md`, suppression du brut.
6. `.env.example` complet ; entrées torr9 deprecated.
7. Vérification réelle : une recherche Tr4ker réelle (requête bénigne unique,
   NE-DOIT-PAS-8) prouve auth + parsing avant merge.

## 5. Critères d'acceptation (exécutables)

| ID     | Critère                                                                                                                                                                                                   |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | `pytest tests/api/tracker/ -q` vert ; les tests C411 existants passent inchangés (comportement pinné).                                                                                                    |
| ACC-02 | `rg -n "torr9                                                                                                                                                                                             | Torr9 | TORR9" -t py personalscraper/ tests/` → 0 hit (hors CHANGELOG/archives). |
| ACC-03 | Recherche Tr4ker réelle : `personalscraper search --dry-run` charge le registry avec tr4ker actif sans erreur, et UNE recherche réelle contrôlée renvoie des résultats parsés (titre + seeders + taille). |
| ACC-04 | `rg -n "<la passkey réelle>" docs/ .env.example` → 0 hit (aucun secret committé).                                                                                                                         |
| ACC-05 | `.env.example` : chaque clé du `.env` réel présente (diff des noms de clés vide, secrets exclus) ; TORR9_* marquées deprecated.                                                                           |
| ACC-06 | `docs/tr4ker.md` supprimé ; `docs/reference/tr4ker-api.md` existe et est référencé dans l'index CLAUDE.md des references.                                                                                 |
| ACC-07 | `make check` vert (lint + mypy + tests + guardrails).                                                                                                                                                     |

## 6. Hors périmètre

- Cross-seed Tr4ker (`/api/torznab/all`) — documenté, non câblé (le cross-seed
  actuel reste tel quel).
- Radar freeleech RSS (R1, ticket #168) — la passkey est câblée en optional
  secret, le radar reste à venir.
- Migration des 4 obligations de seed torr9 historiques — données conservées.
