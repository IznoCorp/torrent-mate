# Implementation Plan — torznab

**Feature**: Retrait Torr9, base Generic Torznab, tracker Tr4ker
**Ticket**: #321 · **Binding design**: `docs/features/torznab/DESIGN.md`
**Branch**: `feat/torznab` · **Merge mode**: auto (assomption, cf. IMPLEMENTATION.md)

## Phase table

| #   | Phase                                   | File                                                       | Status |
| --- | --------------------------------------- | ---------------------------------------------------------- | ------ |
| 1   | Generic Torznab extrait de C411 (pinné) | [phase-01-generic-torznab.md](phase-01-generic-torznab.md) | [ ]    |
| 2   | Client Tr4ker + activation + config     | [phase-02-tr4ker.md](phase-02-tr4ker.md)                   | [ ]    |
| 3   | Retrait torr9 (code, tests, activation) | [phase-03-remove-torr9.md](phase-03-remove-torr9.md)       | [ ]    |
| 4   | Docs + .env.example                     | [phase-04-docs-env.md](phase-04-docs-env.md)               | [ ]    |
| 5   | Vérification réelle + ACC + gate finale | [phase-05-verify-acc.md](phase-05-verify-acc.md)           | [ ]    |

## Sequencing rationale

**1 d'abord** : le générique est extrait de c411.py avec comportement **pinné
byte-identique** (c411 = seul tracker actif en prod ; toute régression casse la
recherche réelle). Rien d'autre ne bouge tant que ce socle n'est pas vert.

**2 ensuite** : Tr4ker n'est qu'une seconde config du générique — il prouve que
l'objectif « nouveau tracker = config + doc, zéro code » est atteint.

**3 après 2** : on ne retire torr9 qu'une fois le remplaçant en place (l'enum,
la factory et l'activation changent dans le même mouvement ; grep résiduel zéro).

**4 puis 5** : docs distillées + .env.example, puis vérification sur le réseau
réel (UNE recherche contrôlée — NE-DOIT-PAS-8) et ré-exercice des 7 ACC.

## Invariants transverses

1. Les tests C411 existants passent **inchangés** (comportement pinné).
2. Jamais de clé/passkey dans docs, exemples, ou messages de commit.
3. Fail-soft multi-tracker préservé (un tracker en erreur n'abat jamais la passe).
4. Suppression de module ⇒ grep du chemin d'import sur `personalscraper/` ET `tests/` à zéro.
5. `make openapi` si un contrat web bouge (aucun attendu ici — vérifier quand même).
