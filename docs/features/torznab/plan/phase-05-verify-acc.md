# Phase 05 — Vérification réelle + ACC + gate finale

**Goal**: prouver sur le réseau réel que Tr4ker répond, parse, et s'intègre à la chaîne —
puis ré-exercer les 7 ACC du DESIGN. Aucun verdict « conforme » sans run daté.

**Design**: DESIGN §5.

## Pré-requis opérateur (bloquant, à demander AVANT cette phase si absent)

`TR4KER_PASSKEY` dans le `.env` réel — DÉJÀ en place (confirmé opérateur 2026-07-28). Si la
recherche réelle rend « error 100 Invalid API Key », la clé API du profil (Mon compte →
Paramètres) doit remplacer la valeur actuelle de TR4KER_PASSKEY.

## Étapes

1. **Boot réel** : registry construit, `active_trackers` attendu `['c411','tr4ker']`.
2. **UNE recherche réelle contrôlée** (NE-DOIT-PAS-8) : requête bénigne unique via un
   script scratch (pattern probe_c411 de la session acq-states) — assert : résultats
   parsés (title/seeders/size non vides), zéro write, zéro ajout torrent.
3. `personalscraper search --dry-run` sur la base réelle — zéro tracker contacté, liste
   cohérente.
4. Ré-exercice des 7 ACC (DESIGN §5) — commandes exécutées + sorties collées dans
   IMPLEMENTATION.md. ACC-02 (grep torr9 zéro), ACC-04 (grep secrets zéro), ACC-05
   (delta env vide) re-exécutés ici même s'ils ont été vérifiés en phase.
5. `make check` + `audit_design_coverage --strict` + `update_feature_map --check` +
   smoke import.

## Gate

Les 7 ACC verts (ou explicitement différés avec protocole si un pré-requis opérateur
manque — le dire, jamais le contourner). make check vert. IMPLEMENTATION.md à jour.
