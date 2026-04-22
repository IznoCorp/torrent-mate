# V10 — PIPELINE RESILIENCE : Brainstorming

> Idempotence renforcee, reprise apres crash, nettoyage artefacts, tests filesystem realistes.

## Contexte

V9 a introduit le pipeline sequentiel 7 etapes avec isolation d'erreurs par step. Mais le pipeline ne peut pas reprendre apres un crash : il redemarre tout depuis le debut. Certaines phases ne sont pas idempotentes (clean re-rename, verify re-applique les fixes). Les artefacts partiels (NFO tronque, merge incomplet) ne sont pas detectes.

Les tests existants utilisent des mocks pour la resilience. L'utilisateur veut des tests sur vrai filesystem.

## Decisions prises

| #   | Decision            | Choix                                     | Raison                                                                   |
| --- | ------------------- | ----------------------------------------- | ------------------------------------------------------------------------ |
| D1  | Scope version       | Une seule version (resilience + tests)    | Les tests de resilience necessitent les mecanismes pour etre ecrits      |
| D2  | Strategie reprise   | Hybride (idempotence + fast-skip)         | Simplicite de l'idempotence, vitesse du skip par phase                   |
| D3  | Detection artefacts | Validation par contenu (pas de marqueurs) | Zero pollution filesystem, fonctionne retroactivement                    |
| D4  | Type de tests       | Filesystem uniquement (pas de mocks)      | Tests les plus fiables possible                                          |
| D5  | Dispatch dans tests | Dry-run uniquement                        | Protection des disques de stockage (fragiles, eviter surcharge ecriture) |
| D6  | Phases traitees     | Les 7 phases                              | Couverture complete                                                      |

## Contraintes techniques

1. Pas de `pipeline_state.json` ni checkpoint file
2. Pas de fichiers marqueurs (`.done`, `.complete`)
3. Pas de nouveau module — renforcement des existants
4. Dispatch en dry-run dans tous les tests
5. Disques de stockage jamais touches par les tests
6. Validation NFO = XML parsable + `<uniqueid>` present

## Points de design a trancher

Aucun — tous les points ont ete resolus pendant le brainstorming.
