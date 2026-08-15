# SP4 kickoff — solliciter d'abord, puis enchaîner tout SP4 en autonomie

Paste-ready brief for a fresh session. Everything below is measured state, not memory.

## Reprise

Tu reprends la conversion de la maquette TorrentMate. `main` = `d4d7e6bd`, v0.97.9 —
SP4a (la machinerie, PR #437), les boutons/apparence (PR #438) et la clôture registre
(#439) y sont mergés. Spec : `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
(les vagues y sont définies ; les verdicts de spikes y sont gravés). Le plan SP4a exécuté :
`docs/superpowers/plans/2026-08-15-maquette-sp4a-machinerie.md` — le motif à reproduire.

## L'ordre de la session (instruction opérateur — 2026-08-16)

**Solliciter l'opérateur UNE FOIS, au début, pour tout SP4 — puis être aussi autonome que
possible jusqu'à la fin de SP4** (SP4b → SP4c → SP4d… → SP4-fin), en n'interrompant que
pour les quatre cas d'arrêt (irréversible/destructif, sensible-sécurité, effet hors
périmètre, plan cassé au point que tout chemin serait une devinette). Concrètement :

1. **D'abord, TOUS les briefs/arbitrages en une salve** (AskUserQuestion groupées) : les
   questions du plan SP4b (§ ci-dessous), le découpage des vagues pages de SP4d (une par
   page ou par paires ? ordre proposé : sys/maint/config → arr → lib avec E-001 → acq),
   le sort de B-024/025/026 (traiter en SP4b ou statuer), le périmètre CI (levier 2 TIA
   sur PR : maintenant ou après confiance locale ? couverture hors PR : oui/non), et tout
   arbitrage que la lecture de la spec fait émerger. Rien ne doit rester qui exigerait de
   re-solliciter en cours de route.
2. **Ensuite, la PR d'optimisation CI** (avant SP4b, pour que toutes les vagues en
   profitent) : filtre par chemins AU NIVEAU DES JOBS (`dorny/paths-filter` — un job
   `changes` calcule des booléens python/frontend/maquette/docs ; chaque job lourd
   démarre toujours et rapporte vert mais sort en secondes hors de son périmètre — le
   `paths-ignore` naïf au déclenchement a DÉJÀ été rejeté ici : required checks coincés
   en « expected », le commentaire en tête de ci.yml le dit) + cible locale
   `make test-impacte` (pytest-testmon). La suite complète RESTE la gate (main + phase
   gates). Bump patch, PR, merge.
3. **Puis SP4b** (plan → exécution), et enchaîner les vagues suivantes sans pause :
   chaque vague = branche, plan, sous-agents, revues, revue finale adversariale, PR,
   CI, squash-merge (instruction permanente), post-merge live check — puis la suivante.

## La mission de la première vague

SP4b : **la fiche + le panneau**. L'écran le plus connecté (artwork, saisons, cast,
trailers, actions) devient la route `/fiche/$titre` en composant final ; le **panneau du
bas** (`openSheet` + `panneauHTML`, le constructeur dérivé UNIQUE — R56) migre avec elle,
et les sites legacy l'ouvrent via la coquille. Ensuite SP4c (résolution + releases, où
M11 se corrige), SP4d… (les pages, E-001 dans la vague Médiathèque), SP4-fin (la mort du
moteur : fragment vide, refonte.html retiré comme source, pont/alias retirés, __go/__states
réimplémentés côté coquille, R72/R74 renégociées — enregistrées).

## Ce qui est vrai aujourd'hui (mesuré, pas supposé)

- **La machinerie SP4a** : magasin TanStack (`design/src/magasin.ts`, notification
  synchrone) ; hooks (`design/src/donnees.ts` : useEtat/useMonde/useContenu/useReferentiel
  - `ecrireEtat` — LA porte des composants) ; inversion du démarrage
    (`window.__demarrerMoteur({magasin, base})`, pré-pont mort, module cassé = splash
    visible) ; `aller()` seul navigateur ; `window.__ecrans.{profil,ajout}`.
- **La loi de propriété** : le dispatcher transmet TOUT pop ; la propriété est dans la
  FORME des entrées (`layer` / `tm:"nav"` / `tm:"garde"` / rien = routeur) ; le legacy
  écrit ses adresses sur `adresseBase` fournie par la poignée de main (matchRoute au
  boot : route d'écran → « / », sinon le pathname — le routeur est la SEULE liste).
- **`#coquille` est relogé DANS `.device`** (insertBefore devant `#screen`) — les écrans
  React sont contenus par le cadre à toute largeur, l'ordre de peinture garde `#screen`
  legacy au-dessus.
- **48 scripts de règles**, tous verts sur `main`. R75 (`adresses_ecrans.py`, 8 tenues)
  et R76 (`navigation.py`) gardent adresses et navigation. `commun.py` épingle
  `color_scheme: "dark"`. CI porte le typecheck maquette.
- **`resynchro.py`** resynchronise compteurs de recherche ET pied du tiroir (version/sha
  lus du checkout prod `~/deploy/torrentmate`) — le lancer quand `contenu.py` ou le pied
  dérivent, committer en data.
- Le rituel de mesure (inchangé) :
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
  Serveur statique 127.0.0.1:8899 ; brouillons 8913/8917/8918 ; JAMAIS 8710/8711/8712.
  Python : `command python3` (3.12.4, chromium `channel="chrome"`). Node :
  `/Users/izno/.nvm/versions/node/v22.13.1/bin`.

## Les pièges payés cette voie (ne pas les repayer)

1. **Un filtre/refus par pathname est TOUJOURS un pas trop court** — deux fois payé
   (R-5 puis R-10). La propriété se lit dans la forme des entrées et dans `adresseBase`,
   jamais dans une liste recopiée.
2. **Un sous-agent qui lance la suite en fond et termine son tour ne se réveille JAMAIS**
   — poser un garde-fou horloge (sleep 25-30 min en fond) à CHAQUE dispatch long ; au
   réveil, mesurer (processus + logs + git) et relancer l'agent endormi par SendMessage
   avec l'état mesuré.
3. **Les écouteurs de gestes ancrés sur `#device` sont un piège latent** pour tout écran
   migré : le long-press a été rebranché sur `document` en SP4a, mais pull-to-refresh,
   swipe entre vues et glisse de feuille restent ancrés — LA FICHE VA LES RENCONTRER
   (carrousel cast, feuille). Audit obligatoire au plan SP4b.
4. **`.screen.open` est ambigu** dès que deux couches empilables le portent — les règles
   lisent `#screen` explicitement à côté (ecrans.py/pont.py, tenues renforcées).
5. **Les arbitrages de l'orchestrateur sont des findings comme les autres** : les
   soumettre explicitement à contestation à la revue suivante. La revue finale
   adversariale sur TOUT le diff est obligatoire avant la PR — c'est elle qui a attrapé
   le Critical de SP4a.
6. Commentaires sources/harnais en anglais, intemporels (aucun tag de phase). Commits
   français scope `(shell-mobile)`, bump patch à chaque PR, `git add -f` docs/ seulement.
   Vérifier le SHA distant après chaque push. R59/R69/R71 à code inchangé = gate de
   chaque vague ; toute exception = amendement ENREGISTRÉ dans regions.json.

## Les questions que le plan SP4b doit trancher

- **L'empilement route-sur-route** : la fiche s'ouvre depuis PARTOUT (délégation
  `data-fiche`), y compris depuis `/ajout` (résultats → fiche = un écran SUR un écran,
  R71). En legacy c'était `pileEcrans` dans `#screen` ; en routes c'est `/fiche/X` poussé
  sur `/ajout?q=…` — le retour doit redécouvrir l'écran couvert (query et scroll compris).
  C'est LE morceau délicat de la vague, l'équivalent du pont en SP3.
- **Le panneau** : `openSheet`/`panneauHTML` devient React (un seul constructeur, blocs
  déclarés, R56) — ou reste legacy un cran de plus ? La spec dit : il migre avec la fiche,
  son plus gros producteur. Les producteurs legacy restants passent par la couture.
- **Les données de la fiche** : `sheetFor`, `saisonsDe`, HEROS/POSTERS/ACTEURS,
  trailerIds — quoi expose la poignée (référentiel) vs le monde (mutable). L'identité
  reste le titre (NFC) jusqu'à la mission de liaison.
- **Les gestes de la fiche** (cast carrousel pan-x, feuille qui se tire) sous un écran
  React — doigt.py/souris.py doivent traverser inchangés.

## Ouverts au registre et différés (ne pas perdre)

**B-024 → B-029** (au registre, arrivés d'une revue adversariale du fix #434 par une AUTRE
session — lire leurs entrées dans `BUGS.md` avant de planifier) : B-024 `data-go` ne règle
qu'UNE entrée d'historique quand plusieurs couches sont enterrées (latent ; vérifier ce que
la refonte dispatcher/base de SP4a en a changé avant de le traiter) ; B-025 le check 10b de
`bugs.py` ne presse jamais Back (la moitié écran du fix sans garde) ; B-026 le `catch {}`
du handler peut laisser URL et interface en désaccord en silence ; B-027/B-028
`resynchro.py` (extraction `t:` naïve ; les titres inconnus lisent comme « à jour ») ;
B-029 la règle compteur de `contenu.py` rate la dérive par suffixe (« 1 » dans « 11 »).
B-024/025/026 touchent le code que SP4b va re-traverser — les traiter ou les statuer au
plan de vague, pas en silence.

- B-021/B-022 `to confirm` (opérateur, sur appareil). B-019/020/023 : CLOS (#439).
- M11 : le flux Associer fait deux `history.back()` dans la même tâche — différé, SE
  CORRIGE NATURELLEMENT en SP4c quand l'écran résolution migre (son code est réécrit).
- Règle dédiée au composant d'erreur visible (`EcranEnErreur`, câblé) — à écrire quand un
  chemin d'erreur d'écran devient exerçable.
- `audit2.py` R11 : le fallback de sélection d'éléments ignore `.screen.open` (couverture
  rétrécie en silence). Cache npm CI sans le lockfile de design/ (lent, jamais faux).

## État de départ attendu

`main` = `d4d7e6bd`, v0.97.9, suite 48/48 verte, `make check` vert, hôte design (pm2
`torrentmate-design`, 8712) sert ce checkout. Squash-merge autorisé une fois CI verte +
revue finale propre (instruction opérateur permanente : « on enchaîne », « le travail
doit être bien fait », « tu es le garant — jamais te cacher derrière les sous-agents »).
