# Reprise — auditer le passage à l'anglais, PUIS finir SP4 et attaquer SP5

> **Prompt de reprise pour une session neuve.** Le contexte a été vidé : tout ce
> qu'il faut savoir est ici, et rien ici ne suppose de se souvenir d'une session
> précédente.

## L'ordre est non négociable

1. **D'ABORD** : faire auditer la campagne « plus de français » par plusieurs
   sous-agents **adversariaux**, en parallèle. Pas une relecture — une
   recherche de défauts.
2. **ENSUITE seulement**, une fois zéro défaut confirmé : finir SP4-fin, puis
   attaquer SP5.

L'opérateur l'a posé ainsi, mot pour mot : « avant de continuer et de terminer
SP4 tout doit être propre et parfait mais surtout il ne doit pas y avoir la
moindre régression, ni sur le design, ni sur la production. »

## État vérifié au moment d'écrire ces lignes

|                             |                                                                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `main`                      | `754c890a`, version **0.98.1**                                                                                          |
| Les trois PR de la campagne | **#455** (les noms), **#456** (les valeurs, les routes, les paramètres), **#457** (les deux derniers noms + le journal) |
| Suite de règles maquette    | **49 vertes / 0 rouge / 568 tenues** — la référence de `main`                                                           |
| `make test` · front         | **10 710** · **1 364**                                                                                                  |
| Portes                      | lint, mypy (484 fichiers), les 9 bras de `check-no-french`, extraction CSS, design-gaps, OpenAPI, feature-map, bump     |
| Production                  | `https://tm.iznogoudatall.xyz` → 200, clone de prod au MÊME commit que `main`                                           |
| Hôte design                 | `https://tm-design.iznogoudatall.xyz` → 401 (page de connexion = sain)                                                  |

**L'arbre est propre, tout est fusionné, rien n'est en attente de commit.**

---

# PHASE 1 — l'audit adversarial

## Ce qui a changé, et qu'il faut donc attaquer

- **Le vocabulaire d'états** est passé à l'anglais de bout en bout :
  `en_attente`→`pending`, `a_jour`→`up_to_date`, `non_verifie`→`unverified`,
  `en_acquisition`→`acquiring`, `a_recuperer`→`to_grab`,
  `en_mediatheque`→`in_library`, `verification_en_cours`→`verifying`,
  `annonce`→`announced`, `termine`→`ended`. Backend, OpenAPI, `schema.d.ts`,
  front, classes CSS, fixture de la maquette. **Rien n'était persisté** — aucune
  migration : les états sont dérivés à la lecture depuis SQLite.
- **Les routes et leurs paramètres**, prototype ET production :
  `/fiche/$titre`→`/mediasheet/$title`, `/profil/$titre`→`/profile/$title`,
  `/ajout`→`/add`, `/resolution/$dossier`→`/resolution/$folder` ;
  `/medias`→`/media`, `/systeme`→`/system`, `/controle`→`/control`.
  **Les trois adresses françaises de production répondent en redirection.**
- **La forme des données** du référentiel embarqué, les ids d'état, les types de
  réglage, huit seams `window.__*`, `id="coquille"`→`shell`, les trois scripts
  shell traduits, et l'hôte design qui se relance quand son code change.

## Les missions à dispatcher

Lancer ces agents **en parallèle**, chacun avec la consigne d'être adversarial :
son travail est de trouver un défaut, pas de confirmer que tout va bien. Un
agent qui rend « rien trouvé » sans montrer ce qu'il a exécuté n'a rien prouvé.

### Agent 1 — régression de PRODUCTION

Le seul périmètre qui touche des gens. Vérifier que l'app déployée fonctionne :

- Les trois anciennes URL (`/medias`, `/systeme`, `/controle`) **redirigent**
  vers les nouvelles, et n'aboutissent pas à une page « non trouvée ».
- Les nouvelles URL rendent bien leur page.
- Les états d'acquisition s'affichent : aucun libellé vide, aucun état brut
  affiché à la place de son texte français (le symptôme d'une clé qui a bougé
  d'un côté seulement).
- `/api/version` sert bien le commit déployé, et l'OpenAPI servi correspond au
  `schema.d.ts` du front.
- **Piège connu** : le service web tourne depuis `~/deploy/torrentmate`, PAS
  depuis le dépôt de dev. Lire `pm_exec_path` avant de conclure quoi que ce soit.
- **Piège connu** : le front est une PWA ; un bundle en cache peut faire croire
  à une régression qui n'existe pas. Comparer le chunk servi à `/index.html` en
  `no-store`, et désinscrire le service worker avant de juger.

### Agent 2 — régression du DESIGN (la maquette)

- Relancer la suite complète et exiger **49/0/568**. Le lanceur est
  `/tmp/suite-run3.sh` ; s'il a été purgé, il boucle sur `frontend/maquette/harness/*.py`
  en sautant `common.py`, `server.py`, `chrome.py`, et somme les « rules EXECUTED ».
- **Le harnais sert un build FIGÉ** dans `/tmp/tm-refonte`. Reconstruire d'abord
  (`npm run build` dans `frontend/maquette/design`), recopier `dist/index.html`
  en `wrapped.html` et `dist/vite`, sinon on mesure l'état d'avant.
- **Le vrai danger n'est pas une règle rouge, c'est une règle VERTE qui ne
  mesure plus rien.** Chercher les tenues dont l'aiguille a été renommée : le
  français qu'une tenue ASSERTE est la sortie rendue de l'app. Trois l'ont été
  et ont été réparées (« bande-annonce », « recherche », « dernier passage ») —
  en chercher d'autres, en comparant les chaînes du harnais à celles de `main`
  avant la campagne (`git show 684ba069:<fichier>`).

### Agent 3 — la prose et les textes d'interface

Le défaut le plus coûteux de la campagne : un mode de renommage trop large a
réécrit **429 lignes de prose** au premier passage (« conforme au profil »
devenu « au profile », « Voir mes suivis » devenu « mes follows »). L'arbre a
été remis à zéro et les lots rejoués avec un critère correct — mais il faut le
vérifier, pas le croire.

- Comparer les **littéraux de chaînes** entre `684ba069` (avant la campagne) et
  `main`, fichier par fichier, et exiger que chaque changement soit délibéré et
  explicable : chemin d'import, clé de registre, id, valeur d'état. Toute phrase
  modifiée est un défaut.
- Vérifier que `frontend/maquette/design/src/i18n/fr.json` n'a **pas bougé** du
  tout, et que chaque clé demandée par `t("…")` existe bien dedans — une clé
  renommée d'un seul côté rend une chaîne vide à l'écran, en silence.

### Agent 4 — l'outil de renommage lui-même

`scripts/rename-identifiers.py` a payé trois défauts de fond pendant la
campagne. Les re-tester, et chercher le quatrième :

- **UTF-16** : JavaScript compte en unités, Python en points de code ; quatre
  emoji dans `legacy.js` décalaient chaque zone de 4 caractères au-delà du
  88 847ᵉ, et les renommages **rataient en silence**. Corrigé par
  `utf16_offsets()` — le vérifier sur un fichier contenant un emoji.
- **`regions()` est un scanner JavaScript** : un commentaire Python `#` portant
  une apostrophe le désynchronisait pour tout le reste du fichier. Python passe
  par `python_spans()` maintenant.
- **Le mode `--values`** décide sur **la chaîne entière**, jamais sur le mot : un
  id n'a ni majuscule, ni apostrophe, ni point. Vérifier que `i18n/` est exclu
  par construction.
- **La preuve de l'aller-retour à table vide est AVEUGLE** aux erreurs de
  classement : un fichier mal découpé se réassemble à l'octet près. La vraie
  preuve se prend sur ce qui a été ÉCRIT, en relisant par le parseur.

### Agent 5 — la garde, et ce qu'elle NE lit pas

`scripts/check-no-french.py` a 9 bras. La question qui a tout trouvé jusqu'ici
n'est pas « est-ce que ça passe ? » mais **« qu'est-ce que ça regarde ? »**.

- Pour chaque bras : quels répertoires, quelles extensions, quelle liste de
  mots. Puis **muter** pour prouver qu'il mord — un bras qui n'a jamais été vu
  rougir ne prouve rien.
- Chercher les types de fichiers qu'aucun bras ne lit (c'est ainsi qu'on a
  trouvé les `.sh` entièrement français et `id="coquille"` dans `index.html`).
- Vérifier que `scripts/code-vocabulary.txt` n'a pas repris de mots français
  au-dessus de sa bannière de dette.
- **Croiser avec un oracle EXTERNE au dépôt** plutôt qu'avec la garde qu'on
  juge : `aspell --lang=en list` et `aspell --lang=fr list` sur les mots dont
  les noms déclarés sont faits ; un mot inconnu de l'anglais et connu du
  français est un suspect.

## Ce qui est français À JUSTE TITRE — ne pas « corriger »

- **`frontend/maquette/design/src/engine/legacy.js`** : 25 mots, 29 noms. Dette
  **déclarée** sous bannière dans `scripts/code-vocabulary.txt` et **bornée** par
  le bras `check_french_debt` — aucun autre fichier ne peut emprunter ces mots.
  Elle meurt avec le fichier, en SP4-fin.
- **Les traductions** : `frontend/maquette/design/src/i18n/fr.json` et le
  namespace `server` qu'il porte.
- **Les données réelles** : titres de médias, vocabulaire des fournisseurs
  (`returning series`, `continuing`), noms de dossiers sur le disque (`Saison XX`),
  ids de catégories (`autres`, `livres`).
- **`docs/`** : des enregistrements datés ne se réécrivent pas.
- **`refonte.html`** et le mot **`maquette`** : nommés par R72 et par la
  constitution §15.
- Une poignée de faux positifs de dictionnaire : `api`, `env`, `conf`, `redis`,
  `mut`, `dur`, `vals`, `sep`, `lucide`, `sonner`, `vite`, `sel`, `ver`.

## La règle de preuve

**Rien n'est « conforme » sans une exécution datée à l'appui.** Un agent qui
conclut sans montrer la commande et sa sortie n'a rien prouvé ; un agent qui
conclut sur une sortie tronquée non plus. Et une porte verte ne prouve que ce
qu'elle lit.

---

# PHASE 2 — SP4-fin, puis SP5

À n'ouvrir **qu'une fois la phase 1 close** et les défauts trouvés corrigés.

## Où en est SP4

**SP4 est close**, et ses affirmations ont été vérifiées une par une :
`refonte.html` fait exactement **4 217 lignes** — un titre et une feuille de
style : zéro `<script>`, zéro gestionnaire inline, pas de `<body>` ;
`PAGES_OF()` ne porte **aucun** `render:` ; `LEGACY_OWNED` est **vide**.

## Ce que SP4-fin doit encore emporter

Le plan est `docs/superpowers/plans/2026-08-18-maquette-sp4fin-le-moteur-meurt.md`.
Il reste le morceau principal : **`design/src/engine/legacy.js`**, 35 000 lignes,
qui doit se démonter en composants. C'est lui qui porte la dette française
déclarée — **elle disparaît avec lui**, et la section correspondante de
`scripts/code-vocabulary.txt` disparaît en même temps (le bras `check_french_debt`
le dit lui-même : il rougit si la bannière part sans le fichier).

## Puis SP5

Sujet : **le contrat CSS**, fixé là par la spec
`docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`.
C'est ce que `refonte.html` porte encore et la raison pour laquelle SP4 l'a
délibérément laissé en place.

## Les règles de travail qui tiennent

- **La maquette est modifiée AVANT le code** (constitution §15). Une divergence
  entre l'app et la maquette est un défaut de l'app.
- **Jamais de renommage à la main ni par regex ad hoc** — toujours
  `scripts/rename-identifiers.py`. Chaque contournement a cassé quelque chose.
- **Committer entre les lots.** Ne pas l'avoir fait a coûté une remise à zéro
  complète de l'arbre et le rejeu de toute la campagne.
- **Un contrat a trois bouts** — le balisage qui l'émet, le `dataset.X` qui le
  lit, les règles qui le tapent — et ils bougent en UNE fois.
- **Avant tout renommage en mode propriété** : vérifier que le nom cible
  n'existe pas déjà comme contrat. Préférer un nom plus long à une fusion.
- Un bump de version par PR, et le journal `docs/superpowers/shell-mobile-wave-log.md`
  reçoit son entrée à chaque vague.
