# Calibrage des pondérations du ranking — `recherche-juste`

Relevé exécuté le 2026-08-05 (sous-phase 2.4), sur les 12 fixtures provider capturées.
Balayage : `WEIGHT_TITLE` ∈ [0.30, 0.70], `WEIGHT_POPULARITY` et `WEIGHT_RECENCY` ∈ [0, 0.70],
`WEIGHT_EXACT` déduit pour que la somme fasse 1.0 et borné à 0.20. Critère du plan (§2.4) :
retenir le jeu qui satisfait le golden avec **la marge la plus large**, la marge étant
`min(rang_max_toléré − rang_obtenu)` sur les 9 cas.

## Résultat

**328 combinaisons** satisfont l'intégralité du jeu golden. La marge maximale atteignable est
**2**, et elle est atteinte par un large plateau — le jeu golden contraint donc **faiblement**
les pondérations. C'est une information utile en soi : il n'existe pas de réglage « fin » à
trouver, seulement une zone large de réglages corrects.

| titre | popularité | récence | exact | marge | cas en #1 | pire rang |
| --- | --- | --- | --- | --- | --- | --- |
| 0.70 | 0.25 | 0.05 | 0.00 | 2 | 9/9 | 1 |
| 0.60 | 0.30 | 0.10 | 0.00 | 2 | 9/9 | 1 |
| 0.55 | 0.35 | 0.10 | 0.00 | 2 | 9/9 | 1 |
| **0.55** | **0.30** | **0.10** | **0.05** | **2** | **8/9** | **2** |
| 0.45 | 0.45 | 0.10 | 0.00 | 2 | 9/9 | 1 |

## Décision : les valeurs du DESIGN sont conservées

`0.55 / 0.30 / 0.10 / 0.05`, inchangées.

Le critère du plan (marge la plus large) **ne discrimine pas** : les valeurs du DESIGN sont
dans le plateau optimal, à marge 2 comme les autres. En l'absence de discrimination mesurée,
dévier du DESIGN serait un réglage à l'oreille — précisément ce que la sous-phase interdit.

Le seul cas qui n'atteint pas la première place est `monarch` sur la fixture **TVDB seule**
(rang 2). Ce n'est pas un défaut de pondération : TVDB n'expose aucune popularité, donc rien
ne sépare `Monarch` (2022, titre exact) de `Monarch: Legacy of Monsters` sinon le titre. La
phase 3 (union TVDB ∪ TMDB) apporte le signal manquant et le cas passe en première place —
c'est `TestUnionRanking` qui en fait la preuve.

## Observation à porter au corps de PR

Toutes les combinaisons qui placent les **9** cas en première place ont `WEIGHT_EXACT = 0`.

Le terme « titre exact » est en effet **redondant** : un titre exact obtient déjà `WRatio = 1.0`
**et** le bonus de préfixe, et la somme est plafonnée à 1.0. Son unique effet marginal est de
départager en faveur du titre **le plus court** — soit une forme atténuée de la préférence que
RC2 (`_superstring_penalty`) faisait peser sur les extensions de titre, et qui est justement le
défaut qu'on corrige.

Il est conservé ici parce qu'il sert le comportement « je tape le titre complet, je l'obtiens »
et que le seul cas où il nuit est réglé par l'union. **À réexaminer** si un futur cas golden le
prend à nouveau en défaut : la suppression pure et simple est une option sérieuse, pas un
bricolage.
