# Implementation Progress — acq-debt

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Reliquat de review PR #320 + dette de modules
**Type**: fix
**Version bump**: 0.57.1 → 0.58.0 (minor)
**Branch**: fix/acq-debt
**Ticket**: #324 — claimed (session locale, heartbeat actif)
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/acq-debt/DESIGN.md
**Master plan**: `docs/features/acq-debt/plan/INDEX.md`

## Contexte

Solde les ouverts « PR #320 review » (M6 I/O borné, M9 hash d'intention pré-add,
carte film open-rows-latest, m15 taxons d'erreur SearchOutcome, m23 close registry,
m24 index partiel) + splits `routes/acquisition.py` et `acquire/service.py` sous 800.
ACC-12 de #320 (clic réel + 390 px) rattaché — fenêtre visée : 15:10-15:20 du jour
si tr4ker rend les épisodes American Dad disponibles.

## Phases

| #   | Phase                                     | File                                                            | Status |
| --- | ----------------------------------------- | --------------------------------------------------------------- | ------ |
| 1   | M9 — hash d'intention pré-add             | [phase-01](docs/features/acq-debt/plan/phase-01-intent-hash.md) | [x]    |
| 2   | m15 — taxons d'erreur SearchOutcome       | [phase-02](docs/features/acq-debt/plan/phase-02-error-taxa.md)  | [x]    |
| 3   | M6 + m23 — I/O borné + registry fermé     | [phase-03](docs/features/acq-debt/plan/phase-03-bounded-io.md)  | [x]    |
| 4   | D3 + m24 — carte film + index partiel     | [phase-04](docs/features/acq-debt/plan/phase-04-film-index.md)  | [x]    |
| 5   | D6 — splits de modules                    | [phase-05](docs/features/acq-debt/plan/phase-05-splits.md)      | [x]    |
| 6   | ACC + gate finale (+ ACC-12 réel de #320) | [phase-06](docs/features/acq-debt/plan/phase-06-acc.md)         | [x]    |

## ACC — vérification exécutée (2026-07-28)

| ID     | Verdict | Preuve                                                                                                                                                                                                                                          |
| ------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | ✅      | test_bounded_provider_io.py : attempts==1 par client sous _REQUEST_RETRY (contrôle : 4 sous la politique pipeline) — borne ≈25 s                                                                                                                |
| ACC-02 | ✅      | test_grab_intent_hash.py 18/18 : crash simulé add→mark_grabbed ⇒ run suivant confirme grabbed + obligation, zéro orphelin ; torrent absent ⇒ hash nettoyé                                                                                       |
| ACC-03 | ✅      | film à ligne unique abandoned ⇒ non_verifie (rouge-avant 3, mutation re-vérifiée)                                                                                                                                                               |
| ACC-04 | ✅      | all-auth ⇒ tracker_auth terminal (rouge-avant 13/18, 2 sondes de mutation) ; grep « PR #320 review » : 2 survivants légitimes (M8 documenté-open hors scope, note historique m10) — M6/M9/m15/m23/m24 = 0                                       |
| ACC-05 | ✅      | check-module-size : service.py 945→478, routes/acquisition.py 735 — un WARN de MOINS qu'au départ, zéro nouveau                                                                                                                                 |
| ACC-06 | ✅      | make check : 9368 passed, 0 ERROR, mypy 461 fichiers ; make openapi sans drift                                                                                                                                                                  |
| ACC-07 | ⏸ défér | ACC-12 de #320 : aucun item « À récupérer » n'existe en réalité (passe 15:10 du 28/07 : les 4 épisodes American Dad introuvables sur c411 ET tr4ker). Prochaine occasion naturelle : Furious E04 (03/08). Jamais de faux média pour une preuve. |

Ticket #326 créé (config/ partagé = boot-break armable — décision d'architecture opérateur).

## Review cycles

_(après implement:pr-review)_

## Next action

feature-pr : push + PR + CI + review + merge auto + deploy.
