# La méthode de l'opérateur — TorrentMate, refonte de l'interface

Dictée le 2026-09-12 au soir, question par question, à la session d'audit. Les §§ 1–9 sont ses mots ;
l'opérateur seul les amende. Depuis son mot du 2026-09-13 ~10:35 (§ Décisions datées), l'AUDITEUR en cours
maintient ce fichier — décisions datées, ordres des audits et leur sort, attentes nommées — et ne le commite
jamais : l'orchestrateur l'atterrit dans la PR docs du lot. Rien ici n'est l'avis d'un auditeur : une ligne
porte les mots de l'opérateur ou une mesure, avec sa source.

## 1. Le critère de fin de la maquette

L'app doit fonctionner sur Mac. C'est une PWA ; presque tous les bugs rencontrés sur Android existaient
aussi sur Mac. L'objectif : la maquette complète, l'app prête graphiquement sur toute sa surface, avec
une ergonomie qui permet de faire tout ce qui est attendu de l'app — pour que le test soit complet.
Quand la surface est suffisante (« 90 % peut-être »), la refonte du backend commence ; le reste
s'accroche au front à ce moment-là.

## 2. Ce qu'est un bug qui compte

Principalement s'il bloque dans un parcours et/ou gêne visuellement même sans bloquer. « Je veux
pouvoir faire fonctionner la maquette comme je ferai fonctionner l'app. » Un défaut d'instrument se
file, il n'arrête pas le travail.

## 3. Comment il teste

Sur son Android (PWA sur tm-design) principalement — la version smartphone est prioritaire — et
parfois sur le Mac. Il teste quand il veut ; les retours sont pris comme ils viennent. Il accepte
d'être invité à tester une nouveauté, avec une capture d'écran quand c'est nécessaire, jamais
systématiquement.

## 4. Sa place dans les décisions

« Quand c'est possible, décide sans moi. Surtout s'il s'agit seulement de faire avancer les merges ou
les lots. On continue. » Une décision fonctionnelle (domaine) lui est posée, mais on avance sur tout
ce qui n'en dépend pas. Il balaie régulièrement les questions en attente avec `/orchestrator:decide`.

## 5. Le grain de ce qui atterrit

Gros lots, qui avancent ; des petits changements après coup, ce n'est pas grave. C'est moins vrai
pour les grosses décisions d'architecture, où l'on prend le temps avant.

## 6. Gaspillage et rigueur

« Un refactor nécessaire pour rendre l'app vraiment fiable et propre architecturalement, c'est
légitime. La rigueur doit être légitime ; si elle est contre-productive, elle est illégitime. »

## 7. Les documents

Il lit la session qui le guide, les questions qu'on lui pose et ce qu'il voit sur l'appareil. Le
reste (registre, plan, état, office, corps de PR) est pour les agents.

## 8. La liaison au backend

Pas encore défini ; à définir dans la mesure du possible. Une fois la surface suffisante, on reprend
ce qui existe : adapter, réarchitecturer, transformer — refaire seulement s'il le faut.

## 9. L'audit

Un auditeur est lancé par commande depuis l'orchestrateur (`Audit : <sujet>`, même modèle, Remote
Control), sans succession ; il indique à l'orchestrateur ce qu'il doit changer, peut resserrer ou
desserrer la méthodologie, et vérifie que les changements portent, sont appliqués et applicables.
`audit-end` met fin à l'audit ; l'orchestrateur ferme la session de l'auditeur.

## 10. La délégation à l'auditeur (dicté le 2026-09-13 ~11:40, à `Audit : TM refonte`)

Quand deux de ses préférences se contredisent (la surface d'abord, l'implémentation la plus propre) : « Seulement quand le
détour est court. Il faut peser ce qui est le mieux pour l'implémentation, le plan et la productivité quand il faut
trancher. »

Portée de la délégation : « Oui la délégation vaut pour tout quand tu es là (audit en cours) : tu te substitues autant que
faire se peut à l'opérateur. Mais pour ça tu dois poser des questions à l'opérateur pour apprendre et approcher au mieux sa
méthodologie. Retiens ça ! »

Conséquence (mesure, pas avis) : pendant un audit, une décision qui n'est ni périmètre fonctionnel ni cadre est tranchée par
l'auditeur, pesée sur trois termes — l'implémentation, le plan, la productivité — et rapportée après ; l'auditeur pose ses
questions de méthode au fil des décisions, et chaque réponse s'écrit ici.

## 11. Ce qui remonte dans le plugin (dicté le 2026-09-13 ~21:25, à l'auditeur)

« Si la méthodologie de la diète d'échange porte ses fruits, on la fera remonter directement dans le plugin orchestrator. D'ailleurs
tout ce qui est prolifique et généralisable doit remonter dans le plugin. »

Règle dérivée (mesure, pas avis) : un candidat remonte (`LounisBou/claude-orchestrator`) quand son chiffre a bougé ; le texte de l'issue
lui est montré avant ouverture (rien de public sans son mot). Liste tenue par l'auditeur, § Attentes nommées, « Candidats au plugin ».

## Les sept mesures en vigueur depuis le 2026-09-12 (réversibles sur son mot)

1. Geler l'appareil : aucune garde, aucun bras, aucune vague tooling sans un défaut qui l'a atteint.
2. Un tour de lecture par lot, zéro par micro-vague ; les mineurs d'instruments sont filés.
3. Le geste post-fusion est un script exécuté par l'orchestrateur, sans agent.
4. Une PR docs de l'office par lot, en fin de lot.
5. Un train de correctifs par jour, pas une micro-vague par bug.
6. Deux agents en parallèle au plus.
7. L13 (la mort du moteur) en priorité après les vagues en vol.

« On remettra la rigueur en place si elle s'avère nécessaire. »

## Les mesures entérinées le 2026-09-13 au soir (son mot : « On entérine ce qui marche dans la méthodologie pour rendre les améliorations pérennes ! On ne s'arrête pas là, on continue les efforts ! »)

Mesurées sur L13a et le début de L13b, elles s'ajoutent aux sept du 12 septembre et s'inscrivent dans l'office (`frontend-steward.md`)
pour que chaque brief en hérite ; leur chiffre est celui qui les a fait entrer.

8. **La porte de contexte des agents est à 80 %** ; un agent démarre une phase si jauge + coût mesuré de sa dernière phase ≤ 80 ; jamais
   de rotation en milieu de phase. (son mot, 19:2x ; 13 rotations à 60 % sur L13a)
9. **Un sous-lot démarre EMPILÉ sur la tête finale du précédent**, pendant son tour de lecture, dans son worktree ; rebase après le
   squash. (b·1 commité 20:48, avant la fusion de L13a ; deux agents pour la première fois)
10. **Le démarrage à froid est au régime** : brief de reprise = état ≤ 40 lignes + journal en ajout seul ; rulings dans un fichier
    numéroté ; lecture requise = brief + état + fichier de phase + rulings. (26 min → 14 min au premier commit de b·1)
11. **Budget de contexte ≤ 15 points par phase** : journaux lus à la ligne de verdict, corps de commit ≤ 12 lignes, amendements en une
    ligne, grep avant toute lecture entière ; jauge avant/après chaque phase. (25–33 points par phase sur L13a)
12. **Les instruments lisent vrai** : `heavy.sh` compte la mémoire récupérable (9 et 20 min de mutex tenu pour rien avant ; 17 portes
    sur 17 sans attente après) ; `mutate.sh` lit le code de sortie d'une règle (un vert faux depuis le 29 août) ; `run.sh` build une
    fois pour contrats + oracle.

**Provisoires jusqu'à leur chiffre** (ordonnées, appliquées, non encore mesurées) : la pleine suite à mi-sous-lot (ordre 5, à b·6) ; la
lentille affordance du tour unique (6) ; la mutation des re-visages de conversion jouée au tour (9) ; la lecture de la phase suivante
pendant la porte et les STOP D groupés (11) ; la paire « In flight » supprimée (15) ; la lecture à sec des bras avant un sous-lot (audit
L13a, ordre 2 — 5 refus trouvés à froid, STOP D « bras » de L13b à compter).

**Prochaines mesures à prendre** (« on continue ») : le travail du steward seul entre la PR et les lancements (55 min ce soir) ; la
durée du tour de lecture unique ; la chaîne fusion → geste → PR docs ; phases par agent sur L13b.

## Décisions datées de l'opérateur (relayées ; source entre parenthèses)

Heures lues sur l'horloge de la machine sauf « ~ » (estimées par la session qui les a reçues).

- **2026-09-12 (matin) — « Round »** sur #585 : un tour de lecture indépendant avant le mot de fusion ; l'exception
  ci-draft reste sienne et ponctuelle. (mémoire `project_operator_rulings_2026_09_12`)
- **2026-09-12 — A6 = A** : « "×" veut dire "vu" partout dans l'interface ; la porte de sortie est "Annuler", visible et
  distincte. » (même mémoire ; DESIGN § 7 de #585)
- **2026-09-12 ~14:00 — Q1 = B pour L20** : les leviers globaux dans une section « Pipeline » de Système ; l'historique
  reste à Système ; démarrer/arrêter restent sur la barre de pilotage d'Arrivées. Lecture A (une page à part) refusée.
- **2026-09-12 ~18:55 — « C » pour la micro-vague settings (#588)** : le moteur COMPTE la pile d'historique au lieu d'un
  nombre fixe — une expression de `switchPageFromLayer`, exception à D5 pour cette vague et cette expression seules.
- **2026-09-12 ~19:05 — round 4/4** : Q1 = A #585 fusionnée sans tour trois (sept mineurs filés) ; Q2 = B nom accessible
  de la carte candidate (« Titre Année · 90 % · TMDB ») par la prochaine vague qui ouvre le fichier ; Q3 = B les étapes
  du pipeline se lisent PAR MÉDIA sur la carte (capture d'écran Lucky S02E07) — `GET /api/pipeline/stages` passe à la
  famille du tunnel, demande backend d'une forme par média ; Q4 = A #587 (dessin et plan L20) fusionnée.
- **2026-09-12 ~20:20 — round 2/2** : Q1 = A #590 fusionnée sur les gardes ; Q2 = B l'index du registre ré-ordonné une
  fois, PR docs après les trois vagues en vol, le bras `index-order` sans liste de descentes gelées.
- **2026-09-12 ~22:45 — les sept mesures** (section ci-dessus) : « OK on applique les 7, mais on remettra la rigueur en
  place si elle s'avère nécessaire. » (à `Orch : TM audit [93c2f1]`)
- **2026-09-13 ~00:55 — « Ne t'arrête pas maintenant, prends les décisions de merge et de fusion. Avance ! »** (au
  steward `[8e18d6]`) : le mot de fusion est DÉLÉGUÉ au steward pour les vagues en vol — PR verte vérifiée sur l'artefact
  → squash sans demander, rapport après. Périmètre, cadre et STOP-and-ask restent siens.
- **2026-09-13 08:10–08:27 (round mené par le steward) — L13 : Q1 = B**, trois sous-lots L13a → L13b → L13c, chacun sa
  branche, son squash, UN tour de lecture, sa marche Mac ; A (une vague) refusée. **Q2 = B, le panneau ≡ du harnais
  MEURT** : « Je ne l'utilise pas ! À la base il était fait pour le contrôle des agents, pour vérifier facilement un
  état, pas pour moi. » **Q3 = A, D-L13-1 ratifiée telle qu'écrite** : une couche quittée pour une arrivée garde son
  entrée, Retour la rouvre ; un redessin remplace ; les dix temporisateurs partent ; STOP E de L13b levé. (mémoire
  `project_operator_rulings_2026_09_13` ; plan `INDEX.md` lignes 38–42, 138)
- **2026-09-13 ~09:00 — l'audit finit à son mot, jamais en automatique** : « L'audit doit se terminer à mon mot et non
  en automatique. C'est moi qui lance l'audit, c'est moi qui définis quand il est terminé. L'auditeur peut m'inviter à
  terminer la session mais ça reste mon mot via la commande audit-end. » (mémoire `user_methodology_operator_2026_09_12`
  § 9-bis ; plugin 0.29.1 #53)
- **2026-09-13 ~09:10 — « OK on fait comme ça »** : la veille `Orch : TM audit` reste jusqu'à (1) 0.29.1 fusionné, tagué,
  installé et (2) la clôture de L13a ; puis il la ferme ; les audits suivants par `/orchestrator:audit`, à son mot.
- **2026-09-13 ~10:35 — « Avance, merge, déploie… N'attends pas après moi. Ta mission est aussi de faire avancer les
  choses en prenant des décisions, que ce soit toi, l'auditeur dans la skill, ou l'orchestrateur qu'il audite. […] La
  mission de l'auditeur est aussi de faire avancer l'orchestrateur et de l'aider dans sa prise de décisions en
  maintenant et alimentant un fichier de projet (propre à chaque projet) qui s'imprègne de la méthodologie de
  l'opérateur et de ses décisions. »** (§ 9-ter ; plugin 0.29.2 #54 ; ce fichier)
- **2026-09-13 ~10:36 — « Quand est-ce qu'on attaque toutes les surfaces manquantes ? … j'attends ça avec impatience et
  les phases s'enchaînent sans nouvelle surface »** ; **10:40 — « Ma question n'impose pas de changement de plan ; si le
  plan est bon on continue. »** (à la veille). Suite : § Attentes nommées, entrée 11:1x.
- **2026-09-13 ~10:43 — « Maintenant avance sur les changements de l'auditeur, merge, déploie, lancement d'un auditeur
  qui te remplace ! Vérifie qu'il fait bien le boulot attendu avant de demander à l'orchestrateur de fermer ta
  session. »** → audit continu `Audit : TM refonte` lancé 11:12 (enregistrement `audits/a0fcb896-….json`).

- **2026-09-13 11:2x — l'ordre des lots est DÉLÉGUÉ à l'auditeur, avec son critère** (à `Audit : TM refonte`) :
  « Concernant L13 ou L20. Je veux ce qu'il y a de mieux et de plus logique pour l'implémentation. Tranche toi même le plus
  simple et le moins perturbant qui serve au mieux l'implémentation. Tu es là pour ça aussi tranché ce genre de chose. Au
  besoin pose de question pour affiner la méthodologie de l'opérateur pour trancher au mieux et être le plus indépendant
  possible. » → tranché par l'auditeur (§ Attentes nommées, 11:2x) : **le plan tient, L13b après L13a**.

- **2026-09-13 18:37–18:40 — défaut qui l'a atteint, sur son Android (capture des candidats « Lucky », quatre cartes cochées)**, au
  steward : « C'est quoi ce design pourquoi une coche sur les cards ? On dirait qu'elle sont déjà sélectionnées. On ne voit pas qu'elles
  sont selectionnable/cliquable. Le choix de design n'est pas du tout adapté on ne comprend pas qu'on doit choisir le candidat qui
  correspond. » (la coche `card/pick` de #585, B-393). Traitement : ligne de registre + train de correctifs du jour après la fusion de
  L13a (mesure 5) ; forme recommandée par le steward : une pastille « Choisir » par carte (44 px), aucune coche avant le choix, la seule
  carte choisie marquée pendant les 7 s d'annulation. **Son mot sur la forme : en attente (dessin = le sien).**

- **2026-09-13 18:40 — second défaut qui l'a atteint (capture : écran des releases de « L'Odyssée », 0 candidat)** : « Rechercher une
  autre release donne systématiquement une page avec 0 candidats ». Cause lue par le steward : `mocks/seeds/releases.json` porte quatre
  releases, toutes « Silo.S03E07… », et le handler filtre par le titre dans le NOM → tout titre sauf Silo répond vide (§ 13 : la maquette
  doit dire vrai). Traitement : registre + train de correctifs du jour (un seed par titre où le verbe est offert, ou une liste générée,
  plus une règle lisant une liste non vide).

- **2026-09-13 19:2x — sur la lenteur, à l'auditeur qui avait répondu « normal pour cette méthode »** : « C'est plus qu'anormal et
  c'est ton rôle de trouver des solutions. Seul 35 % du temps produit le code. C'est inacceptable ! Ton rôle est de contrôler le
  steward et d'optimiser la productivité. » → le jugement de l'auditeur est renversé ; la part du code dans l'horloge est la mesure à
  faire monter (cible écrite : un sous-lot en 8–10 h au lieu de 17) ; ce mot lève, pour les changements d'outil qui rendent du temps
  sans retirer une porte qui a mordu, le refus de la mesure 1.

- **2026-09-13 19:2x — porte de contexte des agents relevée, à l'auditeur** : « Tu peux monter le contexte des agents à 80 % au
  lieu de 60 si ça peut aider. » → la porte du règlement (~60 %) devient 80 % sur ce projet ; règle de pré-dispatch dérivée par
  l'auditeur : un agent démarre une phase si jauge + coût mesuré de sa dernière phase ≤ 80 ; jamais de rotation en milieu de phase.

- **2026-09-13 19:3x — à l'auditeur** : « Tu es le garant : assure-toi que ça marche et que c'est appliqué et respecté. Renforce si
  nécessaire. » → chaque application se vérifie sur le fichier ou le processus, jamais sur la ligne du steward ; les sorts se mesurent
  avec l'instrument de l'auditeur (heures de spawn lues sur les scripts de lancement, premiers commits lus sur git).

- **2026-09-13 20:5x — « On entérine ce qui marche dans la méthodologie pour rendre les améliorations pérennes ! On ne s'arrête pas là,
  on continue les efforts ! »** (à l'auditeur) → section « Les mesures entérinées le 2026-09-13 au soir » ci-dessus ; ordre 16 au
  steward : les inscrire dans l'office à la PR docs du lot.

- **2026-09-13 21:1x — à l'auditeur** : « Tu renouvelles l'orchestrateur à combien, 60 % de contexte ? On peut monter à 80 % facile.
  Quoi d'autre pour optimiser la rapidité et l'efficacité ? » → la porte de succession du steward passe à 80 % (mesure 8 étendue à
  l'orchestrateur) ; ordres 20–21.

- **2026-09-13 21:1x — à l'auditeur** : « Sonnet interdit par votre règle : non, Sonnet autorisé, on retire ça, c'est plus d'actualité ;
  l'orchestrateur choisit, c'est dans la skill d'orchestrator. Diète : on va au plus strict, et tu vérifies, t'assures que ça fonctionne
  bien sans dérive ni baisse de qualité, et tu entérines si c'est le cas. » → (1) l'interdiction de Sonnet (`CLAUDE.md` § Implementation
  Workflow, office « no tier … Sonnet », carte des paliers tout-Opus) est LEVÉE : le steward route par `orchestrator:model-routing`,
  règle de la fausse économie comprise ; (2) la diète d'écriture passe au plus strict, entérinée par l'auditeur si aucune dérive ni
  perte n'est mesurée.

- **2026-09-13 21:1x — « Quoi d'autre ? On peut optimiser les gates, les tests ? »** (à l'auditeur) → ordres 24–26 sur les portes,
  mesurés : CI de la PR #596 = 9 min (20:06 → 20:15), job test 8 min ; la même suite pytest jouée trois fois avant fusion (pre-push 5 min,
  make check 15 min sous le mutex, CI) pour 0 défaut hors de la suite du harnais.

- **2026-09-13 21:19 — à l'auditeur, autorisation formelle d'écrire la carte des paliers** : « Pour models.json mets-le à jour toi-même,
  je t'autorise cette exception et je t'en donne l'autorisation formelle ici et maintenant ! Sonnet et Haïku sont autorisés, c'est
  l'orchestrateur qui crée les agents et qui décide. Attention la skill orchestrator dit que Haïku ne fonctionne pas avec le mode auto,
  il doit être lancé qu'avec allow edits ! » → `~/.claude/claude-orchestrator/models.json` réécrit par l'auditeur 21:2x :
  `{"deep": "opus", "standard": "sonnet", "light": "haiku"}` (avant : tout Opus) ; un agent en palier `light` se lance avec
  `--permission-mode acceptEdits` (le lanceur refuse une session venue dans un autre mode que celui demandé) ; le steward route par la
  table de `model-routing`.

- **2026-09-13 22:0x — à l'auditeur** : « Il faut tenir compte du temps perdu et des erreurs, elles doivent servir de leçon et plus se
  reproduire. Ne cesse pas tes efforts pour réduire le temps et les coûts de développement. » → registre du temps perdu (ci-dessous,
  tenu par l'auditeur) ; toute perte ≥ 10 min entre dans la ligne du steward avec sa cause.

- **2026-09-13 22:2x — à l'auditeur, sur sa propre porte** : « Non, tu es replacé à 80 %. » → la porte de contexte de l'auditeur est
  80 % (le brief disait 60) ; même procédure à 80 : état du rapport écrit, « audit at 80 %, continue from § 8 » au steward, relance sur
  son mot. La mesure 8 vaut pour les trois rôles : agents, steward, auditeur.

- **2026-09-13 22:2x — à l'auditeur, règle d'audit** : « L'audit est remplacé à 80 %, il ne s'arrête pas tant que l'opérateur ne l'a pas
  arrêté. Cette nouvelle règle est à inscrire dans le plugin. » → à 80 % l'auditeur écrit l'état du rapport et envoie « audit at 80 % …
  continue from § 8 » ; l'orchestrateur RELANCE un auditeur frais sans attendre de mot (le mot est donné ici, une fois pour toutes) ; l'audit
  ne finit que par `audit-end` de l'opérateur. Candidat plugin n° 9, à remonter sur son instruction.

- **2026-09-13 22:2x — à l'auditeur** : « Est-ce que comme pour le modèle de l'agent on peut jouer sur le niveau d'effort pour
  fluidifier le travail ? Est-ce une bonne idée ? Étudie ça pour savoir si ajouter l'effort au plugin est une bonne stratégie. » →
  étude de l'auditeur : le CLI accepte `--effort low|medium|high|xhigh|max`, `settings.json` fixe `high`, le lanceur ne le passe pas
  (tous les agents du jour à `high`) ; recommandation : l'effort LIÉ AU PALIER dans `models.json` (deep/high, standard/medium,
  light/low), surchargeable au lancement, même règle de fausse économie ; essai mesuré sur L13b/L20 après la remontée au plugin.

- **2026-09-13 22:2x — à l'auditeur** : « Est-ce qu'il y a des éléments comme les règles ou la constitution qu'on devrait remettre en
  question ou alléger ? » → mesuré : CLAUDE.md 508 l. / 5 446 mots chargés dans chaque session (15 aujourd'hui), office 595 l. (41 dates),
  frontend-architecture 2 319 l. / 29 104 mots (122 dates, 20 noms morts), README maquette 1 253 l. — ~60 000 mots de directives écrites
  en journal ; ordre 30 (régime des directives). Mis en question sans ordre, pour son mot : les chiffres de baseline recopiés dans les
  corps de commit ; la citation des §§ de la constitution dans les PR maquette de conversion. La constitution n'est pas touchée.

- **2026-09-13 22:3x — à l'auditeur** : « L'orchestrateur doit pouvoir choisir l'effort indépendamment du modèle pour optimiser. Pour
  les règles, prends des décisions, teste-les et entérine-les si elles portent leurs fruits. » → l'ordre 29 est amendé : l'effort est un
  choix par lancement, indépendant du palier (défaut par palier, surcharge libre, colonne effort par CLASSE dans la table de routage) ;
  les deux règles mises en question sont tranchées par l'auditeur (ordres 31, 32), essayées sur L13b, entérinées si le chiffre bouge.

## Ordres des audits et leur sort

| Audit | Ordre | Sort (commande) | Porte ses fruits |
| --- | --- | --- | --- |
| Veille 09-12 (§ Productivité) | les sept mesures | appliquées (rapport L13a § 5 : 0 instrument ajouté, 0 tour avant a·19, 1 agent, gestes en script) | instruments +439 −120 pour 9 873 lignes de produit dans L13a ; 5 fusions le 13/09 avant 03:19 |
| L13a 08:53 | 1 — grep des noms retirés élargi à `scripts/ tests/` et `.mjs .txt .json` | appliqué `9ddb1677e` 08:58 (RESUME § Traps) | oui : à a·17-bis (`f4b0732ae`, 17:22) le grep des cinq noms du panneau sur harness + scripts + tests lit **0** — zéro lecteur oublié, contre le trou d'a·1 trouvé trois phases plus tard |
| L13a 08:53 | 2 — lecture à sec des trois bras sur les homes de L13b/L13c | appliqué `review-archive/l13/arms-dry-read-2026-09-13.md` 10:12 : b·5, b·6 refusés fan-in, b·8 refusé no-french, 5 « at risk » | à mesurer : STOP D de L13b contre 13 sur L13a |
| L13a 08:53 | 3 — un répertoire de journaux par vague, effacement prouvé ; six verrous vides retirés | appliqué : `/private/tmp/tm-l13a/` reçoit les journaux (RESUME ruling 36) ; verrous : 2 restent, tous deux VIVANTS ; les 174 anciens `/tmp/l13a-*.log` ont survécu à trois stand-downs et sont tombés 11:2x sur une seconde demande | oui |
| L13a 08:53 | 4 — README `states.js` et BRIEF-L13a « not ruled yet » corrigés | appliqué `9ddb1677e` | — |
| L13a 08:53 | 2.5 — `rhythm.sh` date nue = minuit | appliqué en amont, plugin 0.29.1 (`rhythm.sh:47-51`) | oui : `--since 2026-09-13` lit 5 fusions |
| Veille 09-13 (SUCCESSION.md § 3) → audit TM refonte | **cinq points pour l'UNIQUE tour de lecture de L13a (mesure 2), à donner au lecteur à a·19** : (a) la note datée d'a·2 porte les cinq chiffres de la projection fan-in (history-bridge 1→9, toast-host 1→9, panel-host 1→7, store 3→7, acquisition/queries 2→5) et le lecteur les rejoue ; (b) `bridge.py` hold f′ re-visé sur `history.state.tm == "nav"` — VU tomber quand `installArrival` n'est pas appelé ; (c) le lecteur rejoue la suite harness ENTIÈRE sur la tête finale (le trou d'a·1, `url_state.py`, était invisible à contracts + oracle) ; (d) le hold « the media sheet is gone » d'`audit2.py` re-visé à a·5 doit tomber ; les dix en-têtes « hold count unchanged » vérifiés par le compte de la référence ; (e) `residue.py` PAIRS_FLOOR 15→10→25→29 : grep que `.sec .sechead .empty .surferr .endmark` n'existent nulle part ; **(f, ajouté 12:3x, ruling 47)** l'oracle ne voit pas les IMAGES : le lecteur rejoue le compare hors ligne du champ `poster` contre `POSTERS[t] ?? POSTERS[baseTitle(t)]` sur les 17 familles et lit 0 manque | transmis au steward le 2026-09-13 11:2x ; sort à lire à a·19 | à mesurer au tour |

| TM refonte 11:23 | 1 — la re-coupe du plan L20 (15 lignes nomment `engine/states.js`, mort à a·1 : `plan/INDEX.md:96`, `phase-02` ×7, `phase-03:52`, `phase-09:82`, `DESIGN.md:437,481,607,610,615`) entre dans la PR docs de fin de L13a, avant le brief L20, avec le grep des noms retirés passé sur `docs/features/maquette-l20/` | accusé et programmé par le steward 11:24 (sa mesure : 15, re-dérivée) ; sort à lire à la PR docs | à mesurer : 0 STOP D « fichier absent » dans la première heure de L20 |
| TM refonte 11:19 | 2 — les 174 anciens `/tmp/l13a-*.log` (5,4 Mo) effacés, prouvé par `ls` | appliqué 11:2x (`ls` → 0, vérifié 11:23 ; 16 journaux de porte gardés sous `tm-l13a/earlier-phases/`) | — |

| TM refonte 11:41 | 3 — `harness/page_host.py` à 999/1 000 (main et tête a·10), nommé par a·12/a·15/a·16 : la première phase qui le touche en EXTRAIT un module au lieu de compacter ; une ligne au RESUME, lue au handshake | appliqué : RESUME:80 (`bc7cf8e0c`, ruling 43, vérifié 11:47) ; verbatim `f7e1a82a7` ; précisé 11:58 (ruling 46 confirmé) : compaction refusée, zéro ligne nette permise, la première édition qui AJOUTE extrait | à mesurer : 0 chute de `check-module-size` sur L13a |

| TM refonte 13:2x | 3 — `heavy.sh` compte les pages spéculatives (macOS les relâche en premier ; la branche Linux lit déjà `MemAvailable`) : lecture 3 869 → 5 763 Mo récupérables, planchers intouchés ; une ligne + son test, par l'implémenteur qui attend la porte | appliqué 13:26 (aucun ruling croisé : la mesure 1 gèle les ajouts ; test rouge d'abord, une ligne, commit `fix(maquette-l13a)` par l13a 9, porte a·13 relancée) | oui : portes a·13 → a·18 démarrées sans attente à 5 140–5 787 Mo lus ; 15/15 à 0 min depuis le correctif (9 et 20 min avant) |

| TM refonte 13:50 | 4 — point (g) du tour a·19 : chaque mutation revendiquée par L13a rejouée par le `mutate.sh` réparé (ruling 49 : le code de sortie d'une règle était jeté — « violation(s) » littéral — vert faux depuis le 2026-08-29), compte rejoué / tombé / pas tombé ; l'exposition antérieure filée au registre, pas rejouée | enregistré 13:5x ; outil réparé `4c0e1d036` | **lu au tour 23:3x : 31 rejouées / 27 tombées / 3 NON tombées (les trois angles morts que la vague avait déclarés, confirmés) / 1 expirée ; le point (g) paie** |

| TM refonte 18:35 | 5 — une pleine suite au MILIEU de chaque sous-lot (L13b après b·6, L13c après c·5), en plus de celle de fin : 4 régressions invisibles aux portes de phase trouvées à a·19 seulement, la plus vieille latente depuis a·1 (15 h), 0 pleine suite entre a·1 et a·19 ; coût 25 min par sous-lot | appliqué 18:4x (liste de la PR docs : brief L13b § Method + `plan/INDEX.md` « Gates ») ; aucun ruling croisé | à mesurer à b·6 : chutes trouvées à mi-lot contre à b·11 |

| TM refonte 18:45 | 6 — l'unique tour de lecture d'un lot porte une lentille AFFORDANCE (« un lecteur qui découvre la surface comprend-il ce qu'il doit faire ? », une question par surface changée, répondue sur capture) : le tour de #585 a lu la zone de tap et la fenêtre d'annulation, pas l'affordance, et le défaut a atteint l'opérateur ; coût : une question dans le brief, aucune règle | appliqué 18:5x (reader-A.md de L13a en contrôle ; brief L13b § tour ; une ligne des règles de revue de l'office) | à mesurer : défauts d'affordance atteignant l'opérateur après un tour |

| TM refonte 19:1x | 7 — deux agents (mesure 6) : L13b démarre empilée sur la tête finale de L13a à l'ouverture du tour de lecture, dans son worktree ; coût : un rebase après le squash ; gain : l'écriture de L13b commence ce soir | appliqué 19:2x : BRIEF-L13b écrit maintenant, `feat/maquette-l13b` coupée de la tête finale de L13a dès la PR READY, agent spawné à l'ouverture du tour ; croise la lettre du plan (`INDEX.md:14` « opens from main »), écrite avant le ruling B qui ne dit rien de la base — amendée dans le premier commit docs de L13b | **porte : b·1 commité 20:48 (13/09), L13a fusionnée 10:35 (14/09) — L13b a ~14 h d'avance sur un départ depuis main ; cinq phases de L13b écrites avant la fusion de L13a** |
| TM refonte 19:1x | 8 — régime du démarrage à froid : RESUME en ajout seul (état ≤ 40 lignes), un fichier de rulings numéroté, lecture requise = brief + état + fichier de phase + rulings ; mesure : spawn → premier commit 236 min sur 9 spawns (moyenne 26, plancher 13–15), RESUME 1 372 lignes insérées en 19 commits | appliqué 19:2x (BRIEF-L13b § Communication ; `RULINGS.md`) | premier spawn de L13b : 20:34 → 20:38 (outil) / 20:48 (b·1) ; portes b·2 270 s, b·4 267 s |
| TM refonte 19:1x | 9 — en phase de conversion, la mutation d'un re-visage se joue UNE fois au tour de lecture (point g), pas par phase ; en phase de comportement, règle rouge d'abord inchangée ; mesure : 0 défaut produit sur ~25 mutations par phase aujourd'hui, toutes rejouées par le lecteur | appliqué 19:2x (BRIEF-L13b § Method, règle des phases de conversion) | — |

| TM refonte 19:3x | 10 — budget de contexte par phase ≤ 15 points (journaux lus à la ligne de verdict, corps ≤ 12 lignes, amendements en une ligne, grep avant lecture entière), mesuré à chaque frontière ; un agent < 45 % prend la phase suivante ; mesure : 25–33 points par phase, 13 rotations, 5 h 30 | appliqué 19:4x (BRIEF-L13b § Method) | **porte : `l13b 1` à 54 % après QUATRE phases (b·1–b·4) + 5 commits d'outillage, aucune rotation ; L13a : 1 phase par agent** |
| TM refonte 19:3x | 11 — pendant la porte (7 min), l'agent lit la phase suivante et re-prend ses chiffres ; STOP D groupés à l'ouverture de phase | appliqué 19:4x (BRIEF-L13b § Method) | à mesurer : temps porte → premier commit suivant |
| TM refonte 19:3x | 12 — `run.sh` build UNE fois pour contrats + oracle (~2 min × 20) — le refus de la mesure 1 est levé par le mot de l'opérateur de 19:2x | appliqué 19:4x : premier commit de `l13b 1`, test vu rouge | à mesurer : durée d'une porte de phase |
| TM refonte 19:3x | 13 — L13b en DEUX pistes parallèles (b·1–b·3 / b·4–b·6, puis b·7–b·11 en une) si la surface de conflit mesurée le permet (fichiers touchés par les deux : blocs de legacy.js, ledger, INDEX) — mesure au steward, décision à l'auditeur ; après le tour de lecture de L13a (mesure 6 : lecteur d'abord, puis deux implémenteurs) | mesuré 19:4x (six blocs de verbes entrelacés dans un seul listener `legacy.js:2378–2849`, six adjacences ≤ 12 lignes, cinq fichiers à point unique réécrits à chaque phase) → DÉCIDÉ : UNE piste pour L13b ; le second créneau (mesure 6) va aux sept phases SANS moteur de L20, écrites en parallèle, L20 fusionnant après b·11 (sa phase 8 attend) — raffine la décision de 11:3x ; préconditions : re-coupe du plan L20 (ordre 1) dans le premier commit docs de sa branche, BRIEF-L20 avec les ordres 8–11 | à mesurer : heure du spawn de `l20 1` ; conflits au rebase |

| TM refonte 19:3x | 14 — porte de contexte 80 % (mot de l'opérateur) ; pré-dispatch : jauge + coût mesuré de la dernière phase ≤ 80 ; brief de reprise toujours écrit avant l'arrêt ; mesure : 25–33 points par phase, 13 rotations à 60 % | ordonné 19:3x | à mesurer : phases par agent sur L13b (cible ≥ 2, ≥ 3 avec l'ordre 10) |

| TM refonte 19:59 | 15 — la paire « In flight » écrite à l'ouverture / « None » au dernier commit n'est pas écrite (2 commits, 2 suites pre-push, 1 run CI pour une ligne vraie quelques secondes) ; la trace est celle de la PR docs (mesure 4) ; les lignes de registre `fixed #PR` restent | appliqué 20:0x (INDEX et BRIEF-L13b précision 3 réécrits ; le commit de clôture `56561ad36` déjà écrit : amendé si le push n'est pas parti, sinon pas de commit « None », la ligne remise par le steward à la PR docs) | — |

| TM refonte 20:5x | 16 — les mesures 8–12 (ci-dessus) s'inscrivent dans `frontend-steward.md` à la PR docs de fin de L13a, avec leur chiffre, et le gabarit de brief du projet en hérite ; les provisoires y entrent quand leur sort est lu | ordonné 20:5x | à lire à la PR docs |

| TM refonte 21:0x | 17 — la copie du lecteur épinglée à la tête de la DERNIÈRE porte de phase, re-pointée à la PR READY (`git checkout --detach`) ; mesure : PR READY 19:33 → lecteur 20:08 = 35 min ce soir | ordonné 21:0x | à mesurer : PR READY → handshake du lecteur ≤ 5 min sur L13b |
| TM refonte 21:0x | 18 — la branche du sous-lot suivant coupée à cette même tête, son commit docs poussé PENDANT la pleine porte de la dernière phase ; mesure : 26 min lecteur → push L13b ce soir | ordonné 21:0x | à mesurer : premier commit de L13c vs PR READY de L13b |
| TM refonte 21:0x | 19 — hook pre-push : chemin « docs seuls » (gardes docs + les modules de test qui lisent `docs/`/`*.md`, liste écrite dans le hook avec le grep qui l'a produite, ≤ 1 min) ; le double-run de `run_check` réparé ; mesure : ≈ 16 pushes de prose × 5 min = 80 min de suites aujourd'hui ; écrivain : `l13b 1`, prochain commit d'outillage | ordonné 21:0x | à mesurer : durée du prochain push de stand-down |

| TM refonte 21:1x | 20 — la succession du steward à 80 % (son mot), même arithmétique : passation à une frontière calme seulement, jamais un verdict ou une fusion en cours ; mesure : trois successions aujourd'hui (08:29, 16:50, 21:00), ~30 min de travail sériel chacune | appliqué 21:1x (mesure 13 de l'office, liste PR docs) | à mesurer : successions par jour, heure de la prochaine |
| TM refonte 21:1x | 21 — régime des écritures du steward et des agents : journal mémoire ≤ 1 ligne par événement, message ≤ 6 lignes sauf décision (deux lectures + coût), pas de triple écriture (journal, brief de succession, ligne à l'auditeur disent la même chose une fois) ; mesure : ~50 points de contexte en 4 h, journal 1 007 lignes à 11:12 → 1 474 à 21:07 (+467 en 10 h), quatre briefs de succession de 9–12 Ko dans la journée (00:33, 08:28, 16:49, 21:00), lignes de 300–500 mots | appliqué 21:1x (mesure 14 de l'office ; en vigueur dès cette ligne) | à mesurer : points par heure du steward |

| TM refonte 21:2x | 22 — Sonnet autorisé (son mot) : la carte des paliers suit `model-routing` (light/standard → Sonnet pour les classes que la table y met : recherche en lecture seule, commits docs, agent de commentaires, phases mécaniques de conversion ; deep → Opus/Fable pour ce que personne ne relit : lecteurs, verdicts, phases de comportement) ; les trois lieux de l'interdiction amendés à la PR docs (`CLAUDE.md:316`, `frontend-steward.md:74`, `feature-lifecycle.md:176` ; carte des paliers lue tout-Opus à 21:12) ; **attente qui a besoin d'un mot, le sien** : le harnais du steward refuse la réécriture de `models.json` sur la parole d'un pair (deux fois) — une ligne de l'opérateur dans l'onglet du steward la débloque ; rien n'attend derrière ; qualité mesurée par palier (chutes de porte par phase, STOP D, commits de réparation, verdict du lecteur) ; fausse économie → retour au palier supérieur | ordonné 21:2x | **premier agent standard (Sonnet) : `docs l13a` 14/09 10:38 (PR docs du lot) — à mesurer : reprises, chutes de garde, relecture du steward** |
| TM refonte 21:2x | 23 — diète au plus strict : message ≤ 3 lignes sauf décision (deux lectures + coût), journal aux seules frontières (1 ligne), brief de succession = bloc d'état ≤ 40 lignes + pointeurs ; garde de l'auditeur : chaque ligne porte tête, heure, verdict, jauge — un champ manquant ou une vérification qui cesse de concorder = un cran de moins ; entérinée sinon à la prochaine lecture | ordonné 21:2x | à mesurer : champs manquants sur 20 lignes ; points du steward par heure |

| TM refonte 21:2x | 24 — une seule invocation de porte par phase (`run.sh` : un build, contrats, oracle, les règles re-visées nommées, un verdict) ; mesure : 2–6 runs enveloppés par phase, a·14.2 a rejoué 16 règles une à une, chaque run paie mutex + build | atterri `108904b51` 22:00 | porte b·2 : **270 s** en une invocation (23 règles + 26 gardes + oracle), contre 7–9 min étalées sur L13a |
| TM refonte 21:2x | 25 — tier contrats à 3 règles en parallèle, mesuré une fois mémoire surveillée (19 règles à 2 ≈ 3–4 min ; ~400 Mo par règle, 5,5 Go récupérables) ; retour à 2 si swap | atterri : JOBS=3 ; b·2 : swap inchangé | oui (270 s la porte entière) |
| TM refonte 21:2x | 26 — plus de `make check` local avant la PR d'une vague maquette : le job `test` de la CI (inconditionnel, 8 min, hors machine) est l'autorité ; local = lint + portes du harnais + pre-push ; mesure : 15 min sous le mutex, 3e exécution de la même suite, 0 défaut | appliqué 21:2x (porte pré-PR de L13b sans make check ; croise CLAUDE.md § Phase Gate Checklist item 3 — amendé pour les vagues maquette à la PR docs avec le mot daté ; mesure 19) | à mesurer : PR READY → CI verte, rouges CI évitables |

| TM refonte 22:0x | 27 — (a) délai par invocation de règle et de mutation (10 min, verdict « TIMED OUT » = chute de l'instrument) ; (b) `heavy.sh` ne brise un verrou que si le processus tenant est parti (pid dans le verrou), sinon attend et le dit ; mesure : 47 min de pendaison de `panel.py`, mutex brisé sous un tenant vivant, porte b·1 refusée (B-256), ~1 h du créneau 2 | atterri `63f6674a4` 22:16 (« a hung rule is a timed-out instrument, and a living holder's lock is… ») | à mesurer : 0 pendaison > 10 min ; 0 verrou brisé sous un vivant |

| TM refonte 22:2x | 28 — la règle « audit remplacé à 80 %, jamais arrêté avant audit-end » remonte dans le plugin (`LounisBou/claude-orchestrator` : audit.md, audit-end.md, gabarit § 8, rulebook) ; issue groupée avec les candidats dont le chiffre a bougé ; texte montré à l'opérateur avant ouverture | enregistré 22:23 (liste PR docs, créneau 2 après le tour L13a) ; la relance à 80 % est en vigueur chez le steward | à lire : numéro de l'issue, puis la version installée |

| TM refonte 22:2x | 29 — l'effort de raisonnement entre dans le plugin, CHOISI INDÉPENDAMMENT du modèle (amendé 22:3x sur son mot) : lanceur `--effort` séparé de `--tier`, défaut par palier dans `models.json`, surcharge libre par lancement, colonne effort par CLASSE de travail dans la table de model-routing ; même issue groupée que 28 ; essai mesuré ensuite : standard/medium sur commits docs + agent de commentaires, qualité lue par les sorts habituels | ordonné 22:2x | à lire : l'issue, puis la mesure de l'essai |

| TM refonte 22:3x | 30 — PR docs « régime des directives » après la fusion de L13a (no-version-bump) : CLAUDE.md aux directives seules (une règle = une phrase + son bras ; l'histoire archivée `@sha` ; cible ≤ 150 l.) ; frontend-architecture : les 16 lots atterris en table PR/sha, corps = décisions + invariants + lots restants (cible ≤ 800 l.) ; office et README : récits d'incident → registre/mémoire ; un ruling vit une fois dans RULINGS.md, le fichier de phase pointe ; mesure : 5 446 mots × 15 sessions/jour, 122 dates dans un plan binding, 20 noms morts | ordonné 22:3x | à lire : lignes des quatre fichiers après la PR ; min/spawn |

| TM refonte 22:3x | 31 — les chiffres de baseline ne sont plus recopiés dans les corps de commit (le diff du JSON est le registre ; le corps nomme le fichier et le sens en une ligne) ; essai dès b·3 ; mesure : corps de 40 lignes sur L13a pour un budget de 12 | appliqué 22:33 (ruling 71 à l13b 1 dès b·3) | à entériner si : corps ≤ 12 lignes tenus et aucun lecteur n'a manqué un chiffre |
| TM refonte 22:3x | 32 — la citation des §§ de la constitution n'est plus exigée d'une PR de CONVERSION (rien d'observable ne change, aucun § servi) ; exigée de toute PR de comportement ou de surface (L13b, L13c, L20) ; mesure : L13a a cité des §§ pour un diff que l'oracle prouve sans effet | appliqué 22:33 (ruling 72 ; CLAUDE.md « every web PR cites the §§ » amendé à la PR docs) | à entériner à la prochaine PR de conversion |

| TM refonte 22:37 | 33 — frontière calme avant le restart programmé de lundi 05:00 (`pmset -g sched`) : tout poussé à 04:30, aucun spawn après 04:15, aucune porte chevauchant 05:00, ligne d'état 04:45, lignes de relance dans le brief de succession ; levée si l'opérateur repousse le restart | appliqué et VÉRIFIÉ 22:42 sur `steward-succession-2026-09-13e.md` (22:40:04 ; lignes de relance et cas post-redémarrage présents) ; la première ligne (13d) était une claim, corrigée en 2 min | à lire à 04:45 |

| TM refonte 09-14 09:3x | 34 — les journaux de porte d'une vague vivent hors de `/private/tmp` (`~/Library/Logs/tm-<vague>/` ou `review-archive/<vague>/logs/`) ; mesure : le reboot de 05:00 a effacé `tm-l13a/` et `tm-l13b/` (0 fichier), un lecteur n'aurait rien eu à lire | appliqué 09:40 (dit aux deux agents ; ligne RESUME/brief au premier gate de l13b 2) | à lire au premier gate de l13b 2 |

| TM refonte 09-14 11:12 | 35 — `core.hooksPath` relatif (`hooks`) dans la config partagée et dans `hooks/install.sh`, pour que chaque worktree exécute les hooks de SA branche ; mesure : chemin absolu lu sur wave-l13b, l'ordre 19 jamais exécuté, 3 flakes à preuve jetée (~25 min) | appliqué 11:1x (config relative, prouvé sur wave-l13b ; install.sh = ruling 80) | à lire au prochain push de L13b |

## Attentes nommées et décisions recommandées

- **2026-09-13 02:53 (veille)** — recommandation : ouvrir L13a sans attendre le mot sur la découpe (19 phases identiques
  sous A et B). Acceptée 02:5x ; a·1 commité 03:33 ; le mot est venu 08:27. **Gain mesuré : 4 h 54 de travail
  d'implémenteur** (a·1 → a·6 verts avant le ruling).
- **2026-09-13 10:49–10:52 — STOP D d'a·10 (ruling 41, steward)** : `LIBRARY`/`INCOMPLETE`/`knownMedium` ne meurent pas
  en a·10, b·10-bis créé avant b·11. Pris par le steward sous « décide et avance », 3 minutes, rapporté à la veille
  10:53, renversable au mot de l'opérateur. (commit `c8995c858` 11:00)
- **2026-09-13 11:1x — décision de l'opérateur pré-digérée : l'ordre des lots après L13a** (posée dans l'onglet de
  l'auditeur ; estimation du steward : L13b = 12 phases de comportement, 60–75 min/phase → 1,5 à 2 jours, mesuré sur
  L13a 9 phases en 7 h 13 = 48 min/phase). Lecture 1, le plan : L13b → L13c → L20, nouvelle surface dans ~3 jours.
  Lecture 2, option C : L20 (9 phases, dépend de L15/L19/L10, pas de L13) dès la fusion de L13a, puis L13b ; nouvelle
  surface dans ~1 jour ; coût : L13b retardée d'un jour et la phase 8 de L20 soustrait dans un moteur que L13b refond.
  Mesure commune aux deux : le plan L20 nomme encore `engine/states.js` (`plan/INDEX.md:96` ;
  `plan/phase-02-named-states.md:10,13,20,28,33,35,70`, commandes comprises), fichier supprimé par a·1 (`123816c93`,
  03:33) — le plan L20 est à re-couper avant son brief quel que soit l'ordre (dû à la PR docs du lot, mesure 4).
  Ce qui précède : à 10:38 la veille a pré-digéré A / B (L20 en parallèle) / C et recommandé C ; l'opérateur a répondu
  10:40 « Ma question n'impose pas de changement de plan ; si le plan est bon on continue. » ; la veille a décidé (son
  mot « décide et avance ») : le plan tient, C revient à la clôture de L13a si l'estimation de L13b dépasse un jour.
  11:14 : l'estimation du steward dépasse (1,5–2 jours) → la question lui est reposée, en un mot.
  **11:2x — TRANCHÉ par l'auditeur sur sa délégation (critère : « le plus simple et le moins perturbant qui serve au mieux
  l'implémentation ») : le plan tient, L13b suit L13a, L20 après L13.** Mesures : le plan L20 soustrait dans `legacy.js` en
  deux phases (2 et 8) et nomme 15 lignes mortes ; construit avant L13b, L20 enregistre ses verbes dans un mécanisme que b·7
  déplace (double re-coupe) ; après L13b le fichier n'existe plus et L20 perd ses phases de soustraction. Coût accepté : la
  première surface neuve dans ~3 jours au lieu de ~1. Deux questions posées pour affiner la délégation (préférence par
  défaut quand deux se contredisent ; portée à tout ordre de lots) — répondues ~11:40, § 10.
- **2026-09-13 09:48 → 10:34 — attente qui n'avait pas besoin de mot (la veille)** : PR #53 (plugin 0.29.1) verte et
  MERGEABLE à 09:48, fusionnée à 10:34 sur « Avance, merge, déploie… » — 46 min, alors que § 4 (dicté le 12 ~23:00) disait
  déjà « décide sans moi… faire avancer les merges ». A retenu la chaîne 0.29.1 → #54 → 0.29.2 → auditeur (lancé 11:12).
  Signal à reconnaître : « sur le mot de l'opérateur » écrit à côté d'une fusion verte. (rapport TM refonte § 2.2)
- **2026-09-13 11:52–11:53 — STOP D d'a·11 (ruling 45, steward)** : `POSTERS` survit jusqu'à a·13 (trois lecteurs sans champ
  `poster` ; phase-a13:28 contredisait phase-a11). Pris sous « décide et avance », 1 minute. 14 STOP D sur L13a, 6 de l'espèce
  « home refusé par le code ».
- **2026-09-13 13:10 → 13:2x — attente d'instrument (porte a·13)** : le mutex tenu 13 min et plus pour 400 Mo que la machine a
  (1 894 Mo de pages spéculatives non comptées). Tranché par l'auditeur (délégation, terme productivité) : réparer la lecture, pas le
  plancher. (rapport § 2.7)
- **2026-09-13 13:5x — a·14.2 : lecture (1) tranchée par l'auditeur** (délégation ; implémentation : état final identique,
  différence en vol sur adresse tapée seulement, même espèce qu'a·13 ; plan : (2) aurait livré L13a avec ~20 500 lignes de moteur
  vivantes et grossi L13b ; productivité : une phase contre une phase + deux re-coupes). Coût accepté : une différence en vol
  nommée, marchée par le lecteur et par l'opérateur sur Mac (adresse tapée).
- **2026-09-13 14:40 — ruling 53 (steward)** : `SEASONS` part en b·10-bis (lecture par ids = comportement : la fixture contredit
  les fiches servies sur 6/10 titres, Silo 3 saisons pour 4). À dire à l'opérateur en une ligne quand b·10-bis atterrit : « le panneau
  de suivi dit vrai depuis b·10-bis » (§ 13 de la constitution, données réelles).
- **2026-09-13 14:5x — ruling 51 amendé par l'auditeur, lecture (B)** : l'entrée de navigation porte ce que la carte savait
  (titre, poster, ids, année, genre) ; synopsis et distribution squelettes en vol sur chaque tap — différence nommée au brief
  lecteur et en première étape de la marche Mac de l'opérateur ; si elle lui déplaît sur l'appareil : réparation b·, pas de re-coupe.
  **15:0x — précondition tombée** (4 schémas sur 7 sans année/genre dans le contrat) → lecture (A) : l'entrée porte titre, poster,
  ids ; année et genre aussi en squelette en vol. Demande backend enregistrée à la PR docs (année + genre sur les quatre schémas).
- **2026-09-13 16:50 — succession du steward** `[e1c26b]` → `Orch : TM frontend [bf636a]` à sa porte des 60 %, frontière calme
  (a·16 verte, a·17 en mesure) ; le brief de succession nomme l'auditeur en première ligne ; la règle de routage de 11:40 et la
  délégation § 10 restituées au successeur en une ligne chacune.
- **2026-09-13 16:58 — le dossier du lot L13 survit à ses sous-lots** (tranché par l'auditeur, routage) : « vague » se lit « lot »
  pour un lot coupé en sous-lots ; le dossier meurt au geste du dernier (L13c) ; chaque sous-lot efface ses seuls brief et RESUME.
  Mesure : une re-création depuis l'histoire = une seconde naissance et toutes les citations déplacées.
- **2026-09-13 18:5x — perte produit d'a·14.2 (« Voir la fiche » absent sur un panneau de suivi ouvert à froid) : tranché par
  l'auditeur, réparer dans L13a comme restauration** (une conversion doit l'observable d'avant la vague) ; refusé : re-viser la règle
  pour attendre la donnée (une garde qui cesse de mesurer) ; refusé : rétablir la table synchrone. Différence en vol (≤ 400 ms à froid)
  nommée à la marche Mac.
- **2026-09-13 19:07 — l'opérateur : « Ça me semble encore beaucoup trop long… l'avancée du développement est encore très très
  très lente. Est-ce qu'il y a quelque chose à faire ? Est-ce que c'est normal d'après toi en tant qu'auditeur ? »** Réponse de
  l'auditeur (mesures § 2.10 du rapport) : normal pour cette méthode ; un tiers de l'horloge hors du code (démarrages à froid 35 %,
  portes 15 %, prose 10 %) ; ordres 7–9. Question posée pour la méthode : un sous-lot peut-il démarrer sur une tête non fusionnée ?
- **2026-09-13 19:2x — proposition de l'auditeur REFUSÉE par le steward, avec sa raison** : `run.sh` en un seul build pour contrats +
  oracle (~2 min × 20 phases) — un changement d'outil sous la mesure 1 sans défaut d'app ayant atteint l'opérateur ; filé dans la
  liste outillage avec sa mesure, pour le jour où il le nomme. L'auditeur lit ce refus comme conforme aux sept mesures.
- **2026-09-13 19:4x — L20 écrite en parallèle de L13b (décision de l'auditeur, délégation)** : ses sept phases sans moteur dans le
  second créneau de la mesure 6 dès la clôture du tour de lecture de L13a ; fusion après b·11 ; la mesure 7 tient (L13b garde le premier
  créneau et l'ordre de fusion). Coût : deux briefs du steward, un rebase de L20, portes alternées sur le mutex.
- **2026-09-13 21:00 — seconde succession du steward** `[bf636a]` → `Orch : TM frontend [7977d1]` à 51 %, frontière calme (lecteur au point (g), l13b 1 en file) ; le brief nomme l'auditeur.

### Candidats au plugin (2026-09-13, tenus par l'auditeur)

| Candidat | Généralisable | Fruit mesuré | Remonté |
| --- | --- | --- | --- |
| Diète d'échange (messages ≤ 3 lignes, journal aux frontières, brief = état + pointeurs) | oui (protocole) | en mesure, 2/20 lignes tenues | non |
| Porte de contexte 80 % + arithmétique de pré-dispatch | oui | à lire sur L13b | non |
| Régime du démarrage à froid (brief en ajout seul, RULINGS, quatre lectures) | oui (gabarits de brief) | 26 → 14 min | non |
| Sous-lot empilé pendant le tour du précédent | déjà au règlement, à expliciter dans le gabarit | b·1 avant la fusion de L13a | non |
| Heure de spawn lue sur `ps -o etime`, pas sur le mtime du fichier de prompt (le lanceur le réécrit) | oui (fait du lanceur) | vérifié 20:35 | non |
| Routage des décisions vers l'auditeur d'abord ; délégation pendant l'audit (§ 10) | oui (skill audit) | 12 décisions en 10 h | non |
| Instrument des sorts (`measure-fates.sh`) | oui (skill audit) | fonctionne | non |
| « Une porte qui mesure faux tient un run pour rien » (heavy.sh, mutate.sh) — la leçon, pas les scripts | oui (rulebook) | 17/17 portes sans attente | non |
| **L'effort de raisonnement lié au palier** (`--effort` passé par le lanceur ; `models.json` : `{tier: {model, effort}}` ; deep/high, standard/medium, light/low ; surcharge par spawn ; fausse économie → un cran de plus) | oui (lanceur + model-routing) | étude 22:2x ; essai impossible avant le drapeau | à remonter (ordre 29, même issue) |
| **L'audit est remplacé à 80 %, jamais arrêté avant `audit-end`** : au seuil, l'orchestrateur relance un auditeur frais depuis le rapport sans attendre de mot (son instruction du 22:2x : « à inscrire dans le plugin ») | oui (skill audit : commands/audit.md, audit-end.md, gabarit § 8, rulebook § The audit) | son mot | à remonter (ordre 28) |
- **2026-09-13 ~21:00 → 21:59 — attente d'instrument** : la rejoue (g) du lecteur pendue 47 min (`panel.py` sans délai), le briseur de
  verrou de `heavy.sh` a libéré le mutex sous un tenant vivant, b·1 refusée à la porte ; ~1 h du second créneau perdue. (rapport § 2.11)

## Registre du temps perdu et des leçons (tenu par l'auditeur ; une ligne par perte ≥ 10 min, sa cause, la mesure qui l'empêche de revenir)

| Date | Perte | Durée mesurée | Cause | Ne se reproduit plus par | Sort à lire |
| --- | --- | --- | --- | --- | --- |
| 09-13 | 13 rotations d'agent sur L13a | ~5 h 30 (spawn → premier commit 236 min sur 9 spawns + la rotation elle-même) | une phase par agent (25–33 points), porte 60 %, briefs relus | mesures 8, 10, 11 (porte 80 %, budget 15 points, régime du démarrage) | rotations et min/spawn sur L13b |
| 09-13 | suites pytest sur des pushes de prose | ~80 min (16 × 5) | hook pre-push sans chemin docs | ordre 19 | durée du prochain push de RESUME |
| 09-13 | 4 régressions trouvées à a·19 | ~1 h + 1 rotation | 0 pleine suite entre a·1 et a·19 | ordre 5 (pleine suite à mi-lot) | chutes à b·6 |
| 09-13 | mutation pendue + mutex brisé sous tenant vivant | ~1 h du créneau 2 (21:00 → 21:59) | pas de délai par règle ; briseur aveugle au pid | ordre 27 | 0 pendaison > 10 min |
| 09-13 | travail sériel du steward PR → lancements | 35 + 26 min | copies et branche préparées après la PR ; 3 pushes | ordres 17, 18 | L13b : PR READY → lecteur ≤ 5 min |
| 09-13 | portes retenues pour une mémoire fausse | 9 + 20 min | `heavy.sh` sans les pages spéculatives | ordre 3 (fait) | 17/17 sans attente |
| 09-13 | `make check` local avant la PR | 15 min sous le mutex | 3e exécution de la même suite | ordre 26 | PR READY → CI verte |
| 09-13 | 20 STOP D « home refusé par le code » | ~1 h de re-prises (1–3 min chacun + re-take) | plan écrit en 1 h sans passer les bras | ordre 2 de l'audit L13a (lecture à sec) | STOP D « bras » sur L13b |
| 09-13 | fusion #53 attendue sur le mot | 46 min | « sur le mot de l'opérateur » à côté d'une PR verte | § 9-ter « décide et avance » | 0 fusion verte en attente |
| 09-13 | 4 successions du steward | ~2 h de son temps sériel | porte 60 %, triple écriture | ordres 20, 21 | successions/jour |
| 09-13 | phase a·12 vide | ~10 min (porte + commit docs) | plan du 02:51 non re-pris | « re-take before trusting » (déjà au plan) | — |
| 09-13 | `gh pr merge \| tail` a masqué un 502 (veille) | 6 min + un tag faux réparé | code de sortie perdu dans un pipe | mémoire : jamais `\| tail` sur une commande dont le code décide | — |
| 09-13 | paire « In flight » | 2 commits + 2 suites pre-push | directive du brief pour une ligne vraie quelques secondes | ordre 15 | — |
| 09-13/14 | **AppleEvents vers iTerm2 bloqués 23:10 → (boîte Automation pendante de l'outil de reprise de l'AUDITEUR)** : N-bis de L13a non lançable, fusion #596 reportée au réveil | ≈ 6 h de créneau 1 | un outil de persistance testé sans l'opérateur devant l'écran | règle : aucun premier appel AppleScript depuis launchd sans l'opérateur présent ; l'agent est désarmé | boîte cliquée (Parsec) ou tccd relancé sur son mot |

| 09-14 | pre-push pytest flaké et sa preuve jetée par le hook de MAIN (push de b·4) | 12 min | le correctif de l'ordre 19 est sur la branche L13b, pas sur main avant sa fusion | ordre 19 à la fusion de L13b ; d'ici là un push depuis un worktree utilise le hook de main | à lire au prochain push |

| 09-14 | machine vide de 05:00 à 09:30 (reboot hebdo, relance à la main) ; créneau 1 vide depuis 23:10 | ~4 h 30 machine ; ~10 h créneau 1 | reprise automatique impossible sans l'opérateur devant l'écran (boîte Automation) | outil de reprise TESTÉ OK le 09-14 10:06 (opérateur présent, boîte cliquée), armé pour lundi prochain ; condition : le brief de succession pointé par le script est le courant | à lire lundi prochain 05:1x (journal `~/Library/Logs/tm-resume-after-reboot.log`) |
| 09-14 | journaux de porte effacés par le reboot (`/private/tmp`) | preuve perdue, 0 min direct | répertoire de journaux sous /private/tmp | ordre 34 | — |

| 09-14 | `mutate.sh` « FELL » sur une règle absente (exit 2) — 8 runs verts sur rien | 10 min | la réparation du 13 (« exit non nul = chute ») ne distinguait pas chute et plantage | ruling 77 : exit 64 « RULE NOT FOUND », « RULE CRASHED » sur exit 2 sans FAIL | à lire au prochain rejeu |

| 09-14 | trois flakes pre-push à preuve jetée depuis un worktree | ~25 min | `core.hooksPath` absolu → les worktrees exécutent les hooks de main, jamais ceux de leur branche | ordre 35 (chemin relatif) | au prochain push |

Total identifié le 2026-09-13 : ~13 h sur 17 h d'horloge de L13a.
- **2026-09-13 22:37 — décision de l'opérateur pré-digérée : le restart de lundi 05:00** (garder : mémoire noyau rendue, toutes les
  sessions mortes, travail arrêté jusqu'à sa main ; repousser de sa main : un jour de noyau en plus, sans pression). Recommandé :
  repousser à une frontière où il est présent. Mot attendu : « garde » / « repousse ».
- **2026-09-13 22:4x — l'opérateur : « garde » le restart ; « il faut que tu gères le redémarrage … que tout soit enregistré pour ne rien
  perdre, mais aussi la reprise après le redémarrage pour ne pas perdre de temps »** → la reprise automatique au login (dessinée par
  l'auditeur) est refusée à sa main par son classificateur ; attente qui a besoin de SON mot : installer lui-même ou autoriser
  formellement. Leçon : une reprise après coupure machine se prépare AVANT le jour de la coupure, par la main de l'opérateur.
- **2026-09-13 22:45 — autorisation formelle de l'opérateur** : « Je te donne mon autorisation pour mettre en place tout outil de
  relance automatique après la coupure de 5 h. » → outil installé par l'auditeur 22:47 (agent de session à usage unique, deux garde-fous,
  journal `~/Library/Logs/tm-resume-after-reboot.log`) ; test d'Automation en attente de son clic.
- **2026-09-13 23:1x — reprise automatique : NON DISPONIBLE ce soir** (l'opérateur absent de la machine, boîte Automation non cliquable ;
  le chemin sans autorisation est refusé à l'auditeur par son classificateur). Reprise après 05:00 = sa main depuis 13e. Leçon
  (registre du temps perdu) : l'outil de reprise s'installe et se teste un jour où l'opérateur est devant l'écran, avant la coupure.
- **2026-09-13 23:3x — le tour de lecture unique de L13a a trouvé deux bloquants et confirmé trois angles morts déclarés** sur une vague aux portes vertes
  deux fois : la forme du tour (a–g, marches, angles morts, affordance) est ENTÉRINÉE par la mesure ; son démarrage seul se raccourcit
  (mesure 17). Décision du steward : N-bis ce soir plutôt que fusionner un défaut visible (§ 2 : « gêne visuellement »).
- **2026-09-14 00:21 — perte de la main de l'auditeur** : sa boîte Automation pendante bloque le lanceur depuis 23:10 ; le N-bis de L13a
  attend le réveil de l'opérateur (ou un clic via Parsec, ou son mot pour relancer `tccd`). Registre du temps perdu mis à jour.
- **2026-09-14 00:4x — ruling 74 (steward)** : le verbe `pipe` devient une phase b·10-ter (la garde de propriété de l'état refuse qu'un composant écrive l'état serveur) ; L13b = 13 phases ; tranché seul, rapporté après.
- **2026-09-14 10:06 — « L'outil de reprise est testable aujourd'hui, je suis devant l'écran. »** → testé OK, armé pour le restart de
  lundi prochain ; le steward tient le chemin du brief de succession que le script lit (`steward-succession-2026-09-13e.md`) à jour.
- **2026-09-14 10:2x — ruling 77 (steward)** : la preuve par code de sortie distingue désormais la chute de la règle (1) du plantage ou de l'absence de l'outil (2, 64) — l'angle mort de la réparation du 13 confirmée par l'auditeur.
- **2026-09-14 10:35 — L13a fusionnée** (`304346145`, 0.98.92) après un N-bis d'une heure (deux bloquants du tour) ; le moteur est à 3 593 lignes sur main ; PR docs du lot à suivre.
- **2026-09-14 10:41 — le fichier de méthode a changé de place** : mis de côté par le steward pour nettoyer main avant le geste
  (`review-archive/operator-method.aside.md`, la copie vivante que l'auditeur écrit) et copié dans le worktree de la PR docs, qui le
  reprend à son dernier commit ; après la fusion, la copie de main redevient la vivante. Lu par l'auditeur comme une perte de 0 ligne
  (10 min de vérification) et une leçon : une copie non commitée n'a qu'un lieu, dit à l'auditeur AVANT de la déplacer.
