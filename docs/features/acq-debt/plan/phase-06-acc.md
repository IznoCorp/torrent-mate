# Phase 06 — ACC + gate finale (+ ACC-12 réel de #320)

**Goal**: les 7 ACC du DESIGN exercés, sorties collées dans IMPLEMENTATION.md ; ticket
config/-partagé créé ; CHANGELOG 0.58.0.

## Étapes

1. ACC-01→ACC-06 : commandes exécutées, sorties collées (voir DESIGN §ACC).
2. **ACC-07 = ACC-12 de #320** : si des items « À récupérer » existent (fenêtre tr4ker),
   clic réel « Récupérer maintenant » via Chrome sur tm. + preuve mobile 390 px (harnais
   iframe, scrollWidth-innerWidth==0). Sinon : documenter le différé daté + condition.
3. Ticket kanban séparé : « config/ tracké + partagé prod/staging = boot-break armable
   depuis une branche » (classe du BLOCKER #322 + fenêtre B1 #320) — créé, PAS traité ici.
4. CHANGELOG 0.58.0 (dont le changement visible cartes films).
5. make check + audit_design_coverage --strict + update_feature_map --check + smoke.

## Gate

ACC 7/7 (ou différé documenté daté pour ACC-07) ; make check vert ; grep global
`rg -n "PR #320 review" -t py personalscraper/` ⇒ **0 hit** (tous soldés).
