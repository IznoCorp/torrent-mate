# Phase 04 — Docs + .env.example

**Goal**: doc de référence Tr4ker distillée (SANS secrets), doc c411 mise à jour,
brut supprimé, `.env.example` synchronisé.

**Design**: DESIGN §3 D4 + D5. Tâche opérateur #7 repliée ici.

## Surface

| Fichier                          | Action                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/reference/tr4ker-api.md`   | **NEW** — distillé de `docs/tr4ker.md` (1 035 L) : auth API-key (recherche) vs passkey (RSS/announce), endpoints (/api/torznab, /api/torznab/all cross-seed — documenté non câblé, /api/rss + filtres freeleech/cat), catégories, règles utiles (freeleech, upload, seed), erreurs connues (Doctype = mauvais chemin, DNS). Style : mirror des autres `<provider>-api.md`                                                                                                                            |
| `docs/reference/c411-api.md`     | maj : c411 = première config du Generic Torznab                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `docs/reference/architecture.md` | mention torznab.py dans la carte des modules si le fichier liste les clients                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `docs/tr4ker.md`                 | **SUPPRIMÉ** (brut jetable — contient la passkey réelle)                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `.env.example`                   | audit COMPLET du delta .env → .env.example : chaque clé réelle présente (noms seulement, valeurs vides/factices), TORR9_* conservées mais `# DEPRECATED (tracker closed 2026-07, replaced by tr4ker)`, TR4KER_API_KEY + TR4KER_PASSKEY documentées (l'API key vient du profil « Mon compte → Paramètres », PAS la passkey), TR4KER_ANNOUNCE_URL/API_URL documentées comme notes non consommées par le code — ou retirées si l'opérateur n'en veut pas (choix : les garder en commentaire descriptif) |
| `CHANGELOG.md`                   | entrée 0.57.0                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| CLAUDE.md (racine projet)        | ligne d'index reference pour tr4ker-api.md (le tableau « Read » liste `<provider>-api.md` génériquement — vérifier si une édition est nécessaire)                                                                                                                                                                                                                                                                                                                                                    |

## Règles

- **AUCUN secret** : `rg -n "<passkey réelle du brut>" docs/ .env.example` → 0 avant commit.
  Idem pour l'API key si elle apparaît dans le brut.
- `.env` réel : JAMAIS touché par cette phase (c'est le fichier de l'opérateur). La
  correction des entrées TR4KER_* réelles (ajouter TR4KER_API_KEY) est signalée à
  l'opérateur — c'est lui qui met sa clé.

## Sous-phases

### 4.1 — `docs(torznab): distill the tr4ker reference from the raw notes`

### 4.2 — `docs(torznab): c411 is the first generic-torznab config + changelog`

### 4.3 — `chore(torznab): sync .env.example — torr9 deprecated, tr4ker real shape`

## Gate

1. Grep secrets zéro (règle ci-dessus, commande + sortie dans le commit).
2. `docs/tr4ker.md` absent ; `docs/reference/tr4ker-api.md` présent.
3. Delta noms de clés .env → .env.example vide (script inline dans la gate, secrets exclus).
4. `make check` — vert.
