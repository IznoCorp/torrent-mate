# Implementation Plan — acq-debt

**Feature**: Reliquat de review PR #320 + dette de modules · **Ticket**: #324
**Binding design**: `docs/features/acq-debt/DESIGN.md` · **Branch**: `fix/acq-debt` · **Merge**: auto

## Phase table

| #   | Phase                                         | File                                               | Status |
| --- | --------------------------------------------- | -------------------------------------------------- | ------ |
| 1   | M9 — hash d'intention pré-add (D2)            | [phase-01-intent-hash.md](phase-01-intent-hash.md) | [ ]    |
| 2   | m15 — taxons d'erreur SearchOutcome (D4)      | [phase-02-error-taxa.md](phase-02-error-taxa.md)   | [ ]    |
| 3   | M6 + m23 — I/O borné + registry fermé (D1+D5) | [phase-03-bounded-io.md](phase-03-bounded-io.md)   | [ ]    |
| 4   | D3 + m24 — carte film + index partiel         | [phase-04-film-index.md](phase-04-film-index.md)   | [ ]    |
| 5   | D6 — splits de modules (pin comportemental)   | [phase-05-splits.md](phase-05-splits.md)           | [ ]    |
| 6   | ACC + gate finale (+ ACC-12 réel de #320)     | [phase-06-acc.md](phase-06-acc.md)                 | [ ]    |

## Sequencing rationale

1 d'abord (M9) : c'est le seul item touchant l'exactly-once du grab — isolé, testé à froid.
2 ensuite (m15) : la taxonomie d'erreurs change la chaîne search — avant les splits pour que
le split de service.py (phase 5) parte d'un comportement stabilisé. 3 (M6+m23) partagent le
même seam de construction des clients — une seule phase. 4 est indépendant (web + indexer).
5 en avant-dernier : les splits sont des refactors comportement-pinnés — tout le
comportement doit être figé avant. 6 : ACC + garde-fous.

## Invariants transverses

1. Chaque marqueur « PR #320 review » soldé disparaît du code dans la phase qui le solde.
2. Splits = comportement-pinnés : les tests existants passent inchangés (imports exceptés).
3. Un test de régression par bug/fenêtre corrigé, rouge-avant vérifié.
4. `make openapi` à chaque contrat touché ; jamais de secret nulle part.
