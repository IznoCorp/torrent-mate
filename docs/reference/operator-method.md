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

**Entérinées par la mesure le 2026-09-14 13:10** (chiffres au tableau des ordres) : la pleine suite à mi-sous-lot (une chute sous six
portes vertes) ; le chemin « docs seuls » du hook pre-push (secondes contre minutes) ; la porte en une invocation (≈ 270 s contre 7–9 min) ;
les journaux hors de /private/tmp ; et la porte à 80 % avec le budget de contexte : un agent a fait SIX phases de L13b.

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

- **2026-09-14 22:0x — sur la nomenclature des phases, à l'auditeur** : « Faut que t'arrêtes avec les phases N-bis. N était censé être
  le numéro de la phase dont la “bis” est une répétition pour correction. Nommer les phases N-bis c'est ridicule. L20 ⇒ L20-bis ⇒ L21 ;
  dans le brief, N-bis voulait dire la phase qui s'insère entre deux phases. » → « N-bis » est réservé à une phase de CORRECTION de la
  phase N (même sujet, après son tour) ; une phase NOUVELLE insérée dans un plan prend un numéro et décale les suivantes (b·10-bis →
  b·10, b·11… renumérotés). Ordre 38.

- **2026-09-14 22:4x — défaut qui l'a atteint (tm-design sur main `4f242ecb3`), au steward** : un balayage ferme la barre latérale et
  elle « apparaît rouverte une fraction de seconde au moment où l'animation de fermeture se termine » (précision 22:5x : un FLASH, pas un tiroir resté ouvert). Cause possible : le registre de taps de L13a (capture) à côté du garde de balayage
  du moteur (inerte) ; réparé sur L13b à b·8 (`078209c73`), pas encore sur main. Décision du steward (mesure 5, tranchée seule) : le TRAIN
  DE CORRECTIFS du jour sur main dès le prochain créneau libre — le garde cherry-pické de b·8 avec sa prise, le seed des releases
  (son défaut du 13/09), et « Choisir » si sa forme est tranchée. Ligne de registre B-530.

- **2026-09-14 22:4x — round de décision, question 1/3 : la carte candidate de résolution = A** (à l'auditeur) : une pastille
  « Choisir » sur chaque carte (44 px, primaire), aucune coche avant le choix, la seule carte choisie marquée pendant les 7 s
  d'annulation. Refusés : B (chevron « › » : dit « ouvrir »), C (coche vide/pleine : signe de la sélection multiple). Troisième wagon
  du train du 14/09 ; remplace la coche `card/pick` de #585 (B-393).

- **2026-09-14 22:4x — round de décision, question 2/3 : le restart hebdomadaire = A** : lundi 05:00 gardé, outil de reprise armé
  (testé 10:06) ; repli B (déplacer à une heure de présence) si la reprise échoue lundi prochain — sort à lire lundi 05:1x dans
  `~/Library/Logs/tm-resume-after-reboot.log`. Refusé : C (supprimer le restart).

- **2026-09-14 22:5x — round de décision, question 3/3 : les deux essais = C** : l'ordre 32 (une PR de CONVERSION ne cite pas les §§
  de la constitution ; une PR de comportement ou de surface les cite) est ENTÉRINÉ sur son mot — CLAUDE.md perd la mention « essai »
  à la prochaine PR docs ; l'ordre 31 (chiffres de baseline hors des corps de commit) attend son chiffre à la PR de L13b (corps ≤ 12
  lignes tenus, aucun lecteur n'a manqué un nombre). Round complet 3/3.

- **2026-09-15 03:2x — Q5 tranchée par l'auditeur sous la délégation § 10, faute de mot depuis 01:21 (deux heures, zéro
  implémenteur vivant) : B.** L13b CLÔT à b·12 (son sujet de comportement est atterri : verbes par feature, gestes, une échelle,
  retour du panneau, lecture d'appartenance, statut du pipeline ; `legacy.js` 3 593 → 1 600) ; le résidu (1 601 lignes vivantes, six
  phases mesurées, dont une de ≈ 72 points) devient un SOUS-LOT DE CONVERSION, « L13r — The engine's residue » (r·1–r·6, ruling 99),
  AVANT L13c — sa table du 13/09 gagne une ligne, mêmes trois sortes. Raisons : la règle du dessin « une sorte par vague » ; la phase
  de 72 points ne tient dans aucun agent sans coupe ; « gros lot, je veux que ça avance ». Son mot renverse ; A resterait possible
  tant que la PR de L13b n'est pas fusionnée.

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

| TM refonte 11:23 | 1 — la re-coupe du plan L20 (15 lignes nomment `engine/states.js`, mort à a·1 : `plan/INDEX.md:96`, `phase-02` ×7, `phase-03:52`, `phase-09:82`, `DESIGN.md:437,481,607,610,615`) entre dans la PR docs de fin de L13a, avant le brief L20, avec le grep des noms retirés passé sur `docs/features/maquette-l20/` | accusé et programmé par le steward 11:24 (sa mesure : 15, re-dérivée) ; sort à lire à la PR docs | **CLOS 12:3x : `f959a8b1f` (L20) — 0 nom mort non cité hors notes de re-ciblage** |
| TM refonte 11:19 | 2 — les 174 anciens `/tmp/l13a-*.log` (5,4 Mo) effacés, prouvé par `ls` | appliqué 11:2x (`ls` → 0, vérifié 11:23 ; 16 journaux de porte gardés sous `tm-l13a/earlier-phases/`) | — |

| TM refonte 11:41 | 3 — `harness/page_host.py` à 999/1 000 (main et tête a·10), nommé par a·12/a·15/a·16 : la première phase qui le touche en EXTRAIT un module au lieu de compacter ; une ligne au RESUME, lue au handshake | appliqué : RESUME:80 (`bc7cf8e0c`, ruling 43, vérifié 11:47) ; verbatim `f7e1a82a7` ; précisé 11:58 (ruling 46 confirmé) : compaction refusée, zéro ligne nette permise, la première édition qui AJOUTE extrait | à mesurer : 0 chute de `check-module-size` sur L13a |

| TM refonte 13:2x | 3 — `heavy.sh` compte les pages spéculatives (macOS les relâche en premier ; la branche Linux lit déjà `MemAvailable`) : lecture 3 869 → 5 763 Mo récupérables, planchers intouchés ; une ligne + son test, par l'implémenteur qui attend la porte | appliqué 13:26 (aucun ruling croisé : la mesure 1 gèle les ajouts ; test rouge d'abord, une ligne, commit `fix(maquette-l13a)` par l13a 9, porte a·13 relancée) | oui : portes a·13 → a·18 démarrées sans attente à 5 140–5 787 Mo lus ; 15/15 à 0 min depuis le correctif (9 et 20 min avant) |

| TM refonte 13:50 | 4 — point (g) du tour a·19 : chaque mutation revendiquée par L13a rejouée par le `mutate.sh` réparé (ruling 49 : le code de sortie d'une règle était jeté — « violation(s) » littéral — vert faux depuis le 2026-08-29), compte rejoué / tombé / pas tombé ; l'exposition antérieure filée au registre, pas rejouée | enregistré 13:5x ; outil réparé `4c0e1d036` | **lu au tour 23:3x : 31 rejouées / 27 tombées / 3 NON tombées (les trois angles morts que la vague avait déclarés, confirmés) / 1 expirée ; le point (g) paie** |

| TM refonte 18:35 | 5 — une pleine suite au MILIEU de chaque sous-lot (L13b après b·6, L13c après c·5), en plus de celle de fin : 4 régressions invisibles aux portes de phase trouvées à a·19 seulement, la plus vieille latente depuis a·1 (15 h), 0 pleine suite entre a·1 et a·19 ; coût 25 min par sous-lot | appliqué 18:4x (liste de la PR docs : brief L13b § Method + `plan/INDEX.md` « Gates ») ; aucun ruling croisé | **porte, trois lectures : L13b mi-lot 1 chute (R55, vrai défaut) ; L20 mi-lot 1 (seed) ; L13b pré-PR 2 chutes déterministes sous six portes vertes (b·7→b·12) — la pleine suite paie à chaque passage ; entérinée** |

| TM refonte 18:45 | 6 — l'unique tour de lecture d'un lot porte une lentille AFFORDANCE (« un lecteur qui découvre la surface comprend-il ce qu'il doit faire ? », une question par surface changée, répondue sur capture) : le tour de #585 a lu la zone de tap et la fenêtre d'annulation, pas l'affordance, et le défaut a atteint l'opérateur ; coût : une question dans le brief, aucune règle | appliqué 18:5x (reader-A.md de L13a en contrôle ; brief L13b § tour ; une ligne des règles de revue de l'office) | à mesurer : défauts d'affordance atteignant l'opérateur après un tour |

| TM refonte 19:1x | 7 — deux agents (mesure 6) : L13b démarre empilée sur la tête finale de L13a à l'ouverture du tour de lecture, dans son worktree ; coût : un rebase après le squash ; gain : l'écriture de L13b commence ce soir | appliqué 19:2x : BRIEF-L13b écrit maintenant, `feat/maquette-l13b` coupée de la tête finale de L13a dès la PR READY, agent spawné à l'ouverture du tour ; croise la lettre du plan (`INDEX.md:14` « opens from main »), écrite avant le ruling B qui ne dit rien de la base — amendée dans le premier commit docs de L13b | **porte : b·1 commité 20:48 (13/09), L13a fusionnée 10:35 (14/09) — L13b a ~14 h d'avance sur un départ depuis main ; cinq phases de L13b écrites avant la fusion de L13a** |
| TM refonte 19:1x | 8 — régime du démarrage à froid : RESUME en ajout seul (état ≤ 40 lignes), un fichier de rulings numéroté, lecture requise = brief + état + fichier de phase + rulings ; mesure : spawn → premier commit 236 min sur 9 spawns (moyenne 26, plancher 13–15), RESUME 1 372 lignes insérées en 19 commits | appliqué 19:2x (BRIEF-L13b § Communication ; `RULINGS.md`) | premier spawn de L13b : 20:34 → 20:38 (outil) / 20:48 (b·1) ; portes b·2 270 s, b·4 267 s |
| TM refonte 19:1x | 9 — en phase de conversion, la mutation d'un re-visage se joue UNE fois au tour de lecture (point g), pas par phase ; en phase de comportement, règle rouge d'abord inchangée ; mesure : 0 défaut produit sur ~25 mutations par phase aujourd'hui, toutes rejouées par le lecteur | appliqué 19:2x (BRIEF-L13b § Method, règle des phases de conversion) | — |

| TM refonte 19:3x | 10 — budget de contexte par phase ≤ 15 points (journaux lus à la ligne de verdict, corps ≤ 12 lignes, amendements en une ligne, grep avant lecture entière), mesuré à chaque frontière ; un agent < 45 % prend la phase suivante ; mesure : 25–33 points par phase, 13 rotations, 5 h 30 | appliqué 19:4x (BRIEF-L13b § Method) | **porte : `l13b 2` a fait SIX phases (b·1–b·6) et se retire à 56 % — contre 1 phase par agent sur L13a ; ordres 10 + 14 entérinables** |
| TM refonte 19:3x | 11 — pendant la porte (7 min), l'agent lit la phase suivante et re-prend ses chiffres ; STOP D groupés à l'ouverture de phase | appliqué 19:4x (BRIEF-L13b § Method) | à mesurer : temps porte → premier commit suivant |
| TM refonte 19:3x | 12 — `run.sh` build UNE fois pour contrats + oracle (~2 min × 20) — le refus de la mesure 1 est levé par le mot de l'opérateur de 19:2x | appliqué 19:4x : premier commit de `l13b 1`, test vu rouge | à mesurer : durée d'une porte de phase |
| TM refonte 19:3x | 13 — L13b en DEUX pistes parallèles (b·1–b·3 / b·4–b·6, puis b·7–b·11 en une) si la surface de conflit mesurée le permet (fichiers touchés par les deux : blocs de legacy.js, ledger, INDEX) — mesure au steward, décision à l'auditeur ; après le tour de lecture de L13a (mesure 6 : lecteur d'abord, puis deux implémenteurs) | mesuré 19:4x (six blocs de verbes entrelacés dans un seul listener `legacy.js:2378–2849`, six adjacences ≤ 12 lignes, cinq fichiers à point unique réécrits à chaque phase) → DÉCIDÉ : UNE piste pour L13b ; le second créneau (mesure 6) va aux sept phases SANS moteur de L20, écrites en parallèle, L20 fusionnant après b·11 (sa phase 8 attend) — raffine la décision de 11:3x ; préconditions : re-coupe du plan L20 (ordre 1) dans le premier commit docs de sa branche, BRIEF-L20 avec les ordres 8–11 | à mesurer : heure du spawn de `l20 1` ; conflits au rebase |

| TM refonte 19:3x | 14 — porte de contexte 80 % (mot de l'opérateur) ; pré-dispatch : jauge + coût mesuré de la dernière phase ≤ 80 ; brief de reprise toujours écrit avant l'arrêt ; mesure : 25–33 points par phase, 13 rotations à 60 % | ordonné 19:3x | **porte : l13b 2 six phases, l20 1 six phases, l13b 3 quatre phases (b·6→b·9) — rotations décidées par l'arithmétique (65 + 12 + porte ≈ 80) et non par un plancher ; entérinée** |

| TM refonte 19:59 | 15 — la paire « In flight » écrite à l'ouverture / « None » au dernier commit n'est pas écrite (2 commits, 2 suites pre-push, 1 run CI pour une ligne vraie quelques secondes) ; la trace est celle de la PR docs (mesure 4) ; les lignes de registre `fixed #PR` restent | appliqué 20:0x (INDEX et BRIEF-L13b précision 3 réécrits ; le commit de clôture `56561ad36` déjà écrit : amendé si le push n'est pas parti, sinon pas de commit « None », la ligne remise par le steward à la PR docs) | — |

| TM refonte 20:5x | 16 — les mesures 8–12 (ci-dessus) s'inscrivent dans `frontend-steward.md` à la PR docs de fin de L13a, avec leur chiffre, et le gabarit de brief du projet en hérite ; les provisoires y entrent quand leur sort est lu | ordonné 20:5x | à lire à la PR docs |

| TM refonte 21:0x | 17 — la copie du lecteur épinglée à la tête de la DERNIÈRE porte de phase, re-pointée à la PR READY (`git checkout --detach`) ; mesure : PR READY 19:33 → lecteur 20:08 = 35 min ce soir | ordonné 21:0x | **oui (15/09) : #601 3 min 30 ; #603 9 min ; #605 READY 19:13 → reader R 19:14 = 1 min ; entériné** |
| TM refonte 21:0x | 18 — la branche du sous-lot suivant coupée à cette même tête, son commit docs poussé PENDANT la pleine porte de la dernière phase ; mesure : 26 min lecteur → push L13b ce soir | ordonné 21:0x | **non tel qu'écrit sur L13r (04:43, 55 min de créneau vide) ; TENU sur L13c (15/09 18:3x) : `feat/maquette-l13c` coupée à la tête de la porte de r·17 et `docs l13c 1` spawné PENDANT la porte finale de L13r** |
| TM refonte 21:0x | 19 — hook pre-push : chemin « docs seuls » (gardes docs + les modules de test qui lisent `docs/`/`*.md`, liste écrite dans le hook avec le grep qui l'a produite, ≤ 1 min) ; le double-run de `run_check` réparé ; mesure : ≈ 16 pushes de prose × 5 min = 80 min de suites aujourd'hui ; écrivain : `l13b 1`, prochain commit d'outillage | ordonné 21:0x | **porte : vivant depuis l'ordre 35 — un push docs seuls joue 9 contrôles en secondes (5 min avant) ; entérinée 13:10** |

| TM refonte 21:1x | 20 — la succession du steward à 80 % (son mot), même arithmétique : passation à une frontière calme seulement, jamais un verdict ou une fusion en cours ; mesure : trois successions aujourd'hui (08:29, 16:50, 21:00), ~30 min de travail sériel chacune | appliqué 21:1x (mesure 13 de l'office, liste PR docs) | à mesurer : successions par jour, heure de la prochaine |
| TM refonte 21:1x | 21 — régime des écritures du steward et des agents : journal mémoire ≤ 1 ligne par événement, message ≤ 6 lignes sauf décision (deux lectures + coût), pas de triple écriture (journal, brief de succession, ligne à l'auditeur disent la même chose une fois) ; mesure : ~50 points de contexte en 4 h, journal 1 007 lignes à 11:12 → 1 474 à 21:07 (+467 en 10 h), quatre briefs de succession de 9–12 Ko dans la journée (00:33, 08:28, 16:49, 21:00), lignes de 300–500 mots | appliqué 21:1x (mesure 14 de l'office ; en vigueur dès cette ligne) | à mesurer : points par heure du steward |

| TM refonte 21:2x | 22 — Sonnet autorisé (son mot) : la carte des paliers suit `model-routing` (light/standard → Sonnet pour les classes que la table y met : recherche en lecture seule, commits docs, agent de commentaires, phases mécaniques de conversion ; deep → Opus/Fable pour ce que personne ne relit : lecteurs, verdicts, phases de comportement) ; les trois lieux de l'interdiction amendés à la PR docs (`CLAUDE.md:316`, `frontend-steward.md:74`, `feature-lifecycle.md:176` ; carte des paliers lue tout-Opus à 21:12) ; **attente qui a besoin d'un mot, le sien** : le harnais du steward refuse la réécriture de `models.json` sur la parole d'un pair (deux fois) — une ligne de l'opérateur dans l'onglet du steward la débloque ; rien n'attend derrière ; qualité mesurée par palier (chutes de porte par phase, STOP D, commits de réparation, verdict du lecteur) ; fausse économie → retour au palier supérieur | ordonné 21:2x | **porte, quatre builders standard : 46 / 30 / 67 (dont CI, un fixup) / 29 min, 0 tour, fausse économie jamais déclenchée ; entérinable 15/09** |
| TM refonte 21:2x | 23 — diète au plus strict : message ≤ 3 lignes sauf décision (deux lectures + coût), journal aux seules frontières (1 ligne), brief de succession = bloc d'état ≤ 40 lignes + pointeurs ; garde de l'auditeur : chaque ligne porte tête, heure, verdict, jauge — un champ manquant ou une vérification qui cesse de concorder = un cran de moins ; entérinée sinon à la prochaine lecture | ordonné 21:2x | à mesurer : champs manquants sur 20 lignes ; points du steward par heure |

| TM refonte 21:2x | 24 — une seule invocation de porte par phase (`run.sh` : un build, contrats, oracle, les règles re-visées nommées, un verdict) ; mesure : 2–6 runs enveloppés par phase, a·14.2 a rejoué 16 règles une à une, chaque run paie mutex + build | atterri `108904b51` 22:00 | **porte : 267–271 s sur trois phases (7–9 min étalées avant ; cible 240) ; entérinée 13:10** |
| TM refonte 21:2x | 25 — tier contrats à 3 règles en parallèle, mesuré une fois mémoire surveillée (19 règles à 2 ≈ 3–4 min ; ~400 Mo par règle, 5,5 Go récupérables) ; retour à 2 si swap | atterri : JOBS=3 ; b·2 : swap inchangé | oui (270 s la porte entière ; swap 0,00 Mo lu le 15/09 05:3x) ; entérinable |
| TM refonte 21:2x | 26 — plus de `make check` local avant la PR d'une vague maquette : le job `test` de la CI (inconditionnel, 8 min, hors machine) est l'autorité ; local = lint + portes du harnais + pre-push ; mesure : 15 min sous le mutex, 3e exécution de la même suite, 0 défaut | appliqué 21:2x (porte pré-PR de L13b sans make check ; croise CLAUDE.md § Phase Gate Checklist item 3 — amendé pour les vagues maquette à la PR docs avec le mot daté ; mesure 19) | **oui (15/09) : #601 READY 03:49 → CI verte 03:58 (9 min), 0 rouge ; entérinable** |

| TM refonte 22:0x | 27 — (a) délai par invocation de règle et de mutation (10 min, verdict « TIMED OUT » = chute de l'instrument) ; (b) `heavy.sh` ne brise un verrou que si le processus tenant est parti (pid dans le verrou), sinon attend et le dit ; mesure : 47 min de pendaison de `panel.py`, mutex brisé sous un tenant vivant, porte b·1 refusée (B-256), ~1 h du créneau 2 | atterri `63f6674a4` 22:16 (« a hung rule is a timed-out instrument, and a living holder's lock is… ») | **oui (15/09) : 0 « timed out » non nul sur tm-l13b/l20/l13r/repair, 0 verrou brisé ; entérinable** |

| TM refonte 22:2x | 28 — la règle « audit remplacé à 80 %, jamais arrêté avant audit-end » remonte dans le plugin (`LounisBou/claude-orchestrator` : audit.md, audit-end.md, gabarit § 8, rulebook) ; issue groupée avec les candidats dont le chiffre a bougé ; texte montré à l'opérateur avant ouverture | texte rédigé 15/09 03:4x ; **« ouvre » donné 21:1x (round Q3 = A)** ; la relance à 80 % est en vigueur chez le steward | **issue #56 ouverte 21:18 sur LounisBou/claude-orchestrator (auteur LounisBou, vérifié `gh issue view`) ; à lire : la version installée** |

| TM refonte 22:2x | 29 — l'effort de raisonnement entre dans le plugin, CHOISI INDÉPENDAMMENT du modèle (amendé 22:3x sur son mot) : lanceur `--effort` séparé de `--tier`, défaut par palier dans `models.json`, surcharge libre par lancement, colonne effort par CLASSE de travail dans la table de model-routing ; même issue groupée que 28 ; essai mesuré ensuite : standard/medium sur commits docs + agent de commentaires, qualité lue par les sorts habituels | dans l'issue #56 (21:18) | à lire : le drapeau `--effort` dans une version, puis l'essai |

| TM refonte 22:3x | 30 — PR docs « régime des directives » après la fusion de L13a (no-version-bump) : CLAUDE.md aux directives seules (une règle = une phrase + son bras ; l'histoire archivée `@sha` ; cible ≤ 150 l.) ; frontend-architecture : les 16 lots atterris en table PR/sha, corps = décisions + invariants + lots restants (cible ≤ 800 l.) ; office et README : récits d'incident → registre/mémoire ; un ruling vit une fois dans RULINGS.md, le fichier de phase pointe ; mesure : 5 446 mots × 15 sessions/jour, 122 dates dans un plan binding, 20 noms morts | ordonné 22:3x | **CLOS 15/09 02:0x (#599) : CLAUDE.md 517→215, plan 2 326→1 135, office 652→495, README 1 262→1 115 ; 0 règle perdue ; un fixup ; Sonnet** |

| TM refonte 22:3x | 31 — les chiffres de baseline ne sont plus recopiés dans les corps de commit (le diff du JSON est le registre ; le corps nomme le fichier et le sens en une ligne) ; essai dès b·3 ; mesure : corps de 40 lignes sur L13a pour un budget de 12 | appliqué 22:33 (ruling 71 à l13b 1 dès b·3) | **entérinable (15/09) : 88 commits de L13b, corps moyen 4,2 lignes, 5 > 12 (max 17), le lecteur B a re-dérivé chaque chiffre** |
| TM refonte 22:3x | 32 — la citation des §§ de la constitution n'est plus exigée d'une PR de CONVERSION (rien d'observable ne change, aucun § servi) ; exigée de toute PR de comportement ou de surface (L13b, L13c, L20) ; mesure : L13a a cité des §§ pour un diff que l'oracle prouve sans effet | appliqué 22:33 (ruling 72 ; CLAUDE.md « every web PR cites the §§ » amendé à la PR docs) | **ENTÉRINÉ 14/09 22:5x sur son mot (round Q3 = C) ; CLAUDE.md : « essai » → entériné à la prochaine PR docs** |

| TM refonte 22:37 | 33 — frontière calme avant le restart programmé de lundi 05:00 (`pmset -g sched`) : tout poussé à 04:30, aucun spawn après 04:15, aucune porte chevauchant 05:00, ligne d'état 04:45, lignes de relance dans le brief de succession ; levée si l'opérateur repousse le restart | appliqué et VÉRIFIÉ 22:42 sur `steward-succession-2026-09-13e.md` (22:40:04 ; lignes de relance et cas post-redémarrage présents) ; la première ligne (13d) était une claim, corrigée en 2 min | à lire à 04:45 |

| TM refonte 09-14 09:3x | 34 — les journaux de porte d'une vague vivent hors de `/private/tmp` (`~/Library/Logs/tm-<vague>/` ou `review-archive/<vague>/logs/`) ; mesure : le reboot de 05:00 a effacé `tm-l13a/` et `tm-l13b/` (0 fichier), un lecteur n'aurait rien eu à lire | appliqué 09:40 (dit aux deux agents ; ligne RESUME/brief au premier gate de l13b 2) | **porte : 112 journaux sous ~/Library/Logs/tm-l13b à 12:43 ; entérinée** |

| TM refonte 09-14 11:12 | 35 — `core.hooksPath` relatif (`hooks`) dans la config partagée et dans `hooks/install.sh`, pour que chaque worktree exécute les hooks de SA branche ; mesure : chemin absolu lu sur wave-l13b, l'ordre 19 jamais exécuté, 3 flakes à preuve jetée (~25 min) | appliqué 11:1x (config relative, prouvé sur wave-l13b ; install.sh = ruling 80) | à lire au prochain push de L13b |

| TM refonte 09-14 14:25 | 36 — (1) chaque brief : un run long s'attend DANS l'appel d'outil (timeout ≤ 600 s ou boucle bornée en un appel), jamais de tour fini sur un run en arrière-plan ; (2) à chaque avis d'inactivité le steward lit le mtime du dernier journal de l'agent et le réveille s'il postdate l'avis ; mesure : 65 min × 2 créneaux perdus, la règle était au rulebook et pas dans les briefs | ratifié 14:25 (proposé par le steward, appliqué par lui) | oui (15/09) : 0 agent perdu sur un run depuis le 14/09 17:47 ; l13r 1 attend sa porte dans l'appel |

| TM refonte 19:5x | 37 — un agent bloqué (refus, plateforme, silence) reçoit une SONDE toutes les 15 min : un message court, réponse attendue en 60 s ; l'écran ne se lit qu'en complément, jamais comme état courant ; mesure : accès rétabli ~15:00, agents réveillés 17:47 (2 h 45 × 2 créneaux), deux « vérifications » d'écran entre les deux | appliqué 19:5x ; **second membre 20:0x : un mot de l'opérateur (« continue ») reçu dans une session pendant un blocage vaut SONDE IMMÉDIATE de tous les agents, par celui qui le reçoit** — mesure : « continu » à 14:24 dans deux sessions, agents réveillés 17:47 | au prochain blocage |

| TM refonte 22:0x | 38 — nomenclature (son mot) : « N-bis » = correction de la phase N seulement ; toute phase insérée prend un numéro entier et décale les suivantes — L13b (corrigé par le steward sur le plan : b·10 « le retour du panneau » existe déjà) : b·10-bis → b·11, b·10-ter → b·12, `legacy.js` meurt en b·13 ; L20 : rien à renuméroter ; le brief de L13c et les suivants naissent sans « bis » ; renumérotation dans le prochain commit docs de L13b (INDEX, fichiers de phase, RESUME, RULINGS), citations comprises | **CLOS 22:51 : `09d02815e`, 73 références renumérotées, quatre fichiers de phase b10–b13, grep « bis|ter » → 0 hors citations et hors la phrase du RESUME qui décrit ce grep** | fait |

| TM refonte 15/09 05:4x | 39 — le brief et le RESUME du sous-lot SUIVANT (L13c) existent sur disque, lint 0, avant que L13r n'ouvre r·5, écrits par le bâtisseur de la PR docs du lot dans la même session (un démarrage à froid, pas deux) ; mesure : second créneau vide 55 min (03:52 → 04:47) sur la coupe de L13r, 26 min la veille sur L13b ; cible : L13r READY → spawn de `l13c 1` ≤ 5 min (la forme de l'ordre 17) | appliqué 05:40 (`review-archive/l13b/docs-pr-list.md` item 8, vérifié sur disque ; le brief du bâtisseur s'écrit, spawn au prochain stand-down) | **fait et MESURÉ : L13r #605 READY 19:13 → `l13c 1` spawné 19:17 = 4 min (cible ≤ 5) ; entériné** |
| TM refonte 15/09 05:4x | 40 — le bâtisseur standard de la PR docs du lot L13b prend le PREMIER créneau libéré, avant l'implémenteur de remplacement (routage § 10, ni périmètre ni cadre) ; mesure : `IMPLEMENTATION.md` en retard d'un sous-lot depuis la fusion de 05:24, les deux créneaux pris (l13r 1, l20 3) ; coût du bâtisseur 29–46 min sur quatre mesurés | appliqué 05:40 (docs-pr-list item 9 ; le geste a ré-enregistré `taken_at_commit` = 5df76af33 sur docs/steward-l13b-close `7b1076220` 05:59, vérifié ancêtre ; brief du bâtisseur sur disque 05:5x) | **fait (15/09) : l13r 1 retiré 09:1x à 69 %, `Agent : docs l13b 1` spawné 09:16 (prompts/launch-Agent---docs-l13b-1), ttys000 réutilisé — le premier créneau libéré, avant l13r 2** |
| TM refonte 15/09 07:1x | 41 — les deux commandes de relance de l'auditeur dans `steward-succession-2026-09-13e.md` (l.5, l.17) nomment le rapport COURANT (elles pointaient `2026-09-13-TM-refonte` et `[001360]` après la réécriture de 07:00, alors que le bloc d'état nommait `[2bc37f]` et le rapport du 15/09) ; mesure : grep → 2 pointeurs anciens contre 1 courant ; lundi 05:00 l'outil de reprise relancerait l'audit sur un rapport clos | appliqué 07:1x (vérifié par grep : anciens 0, courants 3) | fait |
| TM refonte 15/09 13:4x | 42 — avant le spawn du premier agent d'un sous-lot (L13c d'abord), chaque fichier de phase porte sa mesure d'ouverture (la commande que le STOP D aurait prise : sites à déplacer, lecteurs, familles) et les coupes se font en UN commit docs ; mesure : L13r coupée cinq fois à l'ouverture le 15/09 (r·3, r·6, r·10-bis, r·10 ×2), 6 phases planifiées → 14 réelles, ~10 min de créneau par STOP D + un commit de renumérotation chacun ; coût ≤ 30 min au plan | appliqué 13:5x ; fait 18:59 (`2facfd922` sur feat/maquette-l13c : neuf mesures d'ouverture, 0 coupe, moyenne 6,9 — 28 % de contexte du bâtisseur) | à lire à l'ouverture de L13c : 0 coupe de taille après le premier spawn |
| TM refonte 15/09 21:2x | 44 — sur le mot de l'opérateur (« encore très lent… commençons par le levier 1 ») : les DESIGN + plans de L16 (§ 18), puis L17 (§ 19), puis L18 (§ 17) s'écrivent MAINTENANT, en parallèle de L13c, par un bâtisseur standard dans le premier créneau libéré, chacun sa PR docs sur main (forme de #587), mesures d'ouverture au plan ; les questions de dessin ouvertes viennent d'un round de l'auditeur ; mesure : L20 dessin #587 le 12/09 → lot ouvert le 14/09, ~1 jour perdu à l'ouverture de chaque lot restant sans chevauchement | appliqué 21:5x (brief L16 écrit, `design l16 1` spawné 22:1x) puis **SUSPENDU 22:3x sur le mot de l'opérateur** (l'organisation de l'app se tranche d'abord ; bâtisseur retenu, brief gardé) | suspendu ; reprise sur ses rulings d'organisation |
| TM refonte 15/09 18:2x | 43 — avant la PR READY de L13r : `git grep -n legacy.js -- frontend/maquette/design/src` lit 0 mention sans citation `@sha` et au présent (mesure : 18 lignes / 17 fichiers à r·16 `76952efbb`, 0 citée, dont B-517 toujours présente) ; le brief lecteur gagne le grep ; ≈ 20–30 min dans r·17/r·18 | appliqué 18:2x ; **fait à r·17 `6839dd913` : 0 mention non citée sur 15 (grep de l'auditeur)** | fait |

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

| 09-14 | R164 intermittente sous charge à la porte b·6 (2 rouges / 2 vertes), capture armée | ~45 min du créneau 2 | une règle à état dérivé du temps sous charge | filée (ruling 84) ; à lire avec sa capture | au tour de L13b |

| 09-14 | deux agents à l'arrêt : accès abonnement coupé 13:12 → **~15:00 (rétabli par l'opérateur)**, puis NON RÉVEILLÉS jusqu'à 17:47 | plateforme 13:12 → ~15:00 (~1 h 50 × 2) ; **steward + auditeur 15:00 → 17:47 (2 h 45 × 2)** | « continu » de l'opérateur à 14:24 dans les quatre sessions (transcripts lus) : les deux agents (Opus) répondaient ENCORE le refus à 14:24:25 et au réveil de 14:25, les sessions Fable répondaient ; rétabli ~15:00 (son mot) ; ensuite le steward a lu l'écran figé (15:31, 16:45, 17:45) sans sonder | ordre 37 : un agent bloqué reçoit une SONDE (message, 60 s) toutes les 15 min ; un écran figé n'est pas un état | au prochain blocage |

| 09-14 | `oracle.py --accept` nu a mesuré la copie servie de l'autre vague (deux agents, une copie) | ~5 min, rien commité | un pas hors run.sh/mutate.sh n'acquiert pas la copie | ruling L20-6 livré (`a487ffaeb`) : 4 tests rouges → verts, la garde a refusé la copie vivante aussitôt | fait |

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
- **2026-09-14 11:3x — PR docs du lot L13a fusionnée (#597)** : ce fichier est sur main (472 l.) ; office mesures 8–19 ; Sonnet
  autorisé dans les trois fichiers ; essais 26 et 32 écrits ; premier agent Sonnet (docs) : 46 min, une reprise.
- **2026-09-14 14:27 — attente qui a besoin de SON mot (plateforme)** : l'organisation a coupé l'accès abonnement de Claude Code pour les
  sessions Opus ; les deux agents sont à l'invite depuis ~13:12. Réactiver l'accès, ou une clé API pour les agents. Rien ne route autour.
- **2026-09-14 18:5x — ruling 87 (steward)** : un bras de garde meurt avec son sujet (forwarders) ; la classe « littéral de balisage non comparé » reste sans garde dès b·7, perte écrite (B-513) ; un bras côté registre sera ordonné après L13 seulement si un défaut de cette classe atteint l'opérateur (mesure 1).
- **2026-09-14 19:5x — l'opérateur : « Ça n'a pas été coupé jusqu'à 17h45, c'est faux » ; « Vers 15 h je l'ai remis » ; « j'ai relancé les
  agents, toi et l'orchestrateur à 15 h en écrivant continue dans toutes les sessions. »** → lu dans les transcripts : « continu » à 14:24
  locale dans la session de l'auditeur ET celle du steward ; transcripts des agents lus par l'auditeur : refus encore à 14:24:25 et 14:25 ; registre final : plateforme 13:12 → ~15:00 ; steward et
  auditeur 15:00 → 17:47 (2 h 45 × 2). Second membre de l'ordre 37 : un mot de l'opérateur reçu pendant un blocage vaut sonde immédiate.
  L'auditeur a répété la ligne du steward sans lecture propre : sa faute est écrite au rapport.
- **2026-09-14 23:19 — ruling 95 (steward, b·11)** : le panneau de suivi adopte les conventions de la fiche (« à venir », « possédés/? », « N ép. ») — application de son mot du 11/09 sur « manquant » ; confirmé par l'auditeur, pas une question pour lui. Fait § 13 : le panneau dit vrai comme la fiche.
- **2026-09-15 00:5x — train de correctifs du 14/09 fusionné (#598, v0.98.93)** : tiroir (cause = l'impulsion de retour, un mécanisme que personne n'avait nommé — trouvé par la mesure image par image), releases par titre, pastille « Choisir ». Mesure 5 : un train, une PR, 2 h de spawn à fusion.
- **2026-09-15 00:5x — succession du steward** `[e60098]` → `[31ca3c]` à 77 % (porte 80), après la fusion du train ; le brief 13e réécrit sous le même chemin (outil de reprise).
- **2026-09-15 05:28 — audit RELANCÉ** `Audit : TM refonte [2bc37f]` (ttys003) au 80 % du prédécesseur `[001360]`, fermé par le steward sur la poignée de main vérifiée (05:3x, `ps -t ttys001`) ; rapport `audits/2026-09-15-TM-refonte/REPORT.md`. Aucun mot de l'opérateur entre le 14/09 22:5x et le 15/09 05:3x.
- **2026-09-15 05:4x — attente nommée (§ 10, ordre 40)** : la PR docs du lot L13b (sept items, `review-archive/l13b/docs-pr-list.md`) n'a pas de créneau (l13r 1 + l20 3 = mesure 6) ; `IMPLEMENTATION.md` lit « Last landed L13a » depuis la fusion de L13b à 05:24 → le bâtisseur prend le premier créneau libéré.
- **2026-09-15 05:4x — Q5 : la lecture A n'est plus ouverte** (L13b fusionnée 05:24, `5df76af33`) ; un mot contraire de l'opérateur ne renverserait plus que par une re-coupe de L13r. Deux items lui restent posés dans l'onglet de l'auditeur : Q4 (l'écran de résolution pendant les 7 s — reco A : le message nomme le choix, B-500 se ferme) et le texte de l'issue plugin (son « ouvre »).
- **2026-09-15 05:4x — décision tranchée par l'auditeur (§ 10, routage 11:40) : L20 phase 8, un second passage pipeline = A** — le mock répond 409 (file seulement sous un verrou de maintenance), comme le dessin L20 § 3.2 sur main depuis #587 (l.222–228, « the interface follows the BACKEND ») et comme `routes/pipeline.py` ; b·12 avait repris la file de L20 mot pour mot (ruling 97). Refusé B (garder la file du mock + une demande backend, ~6 pts) : une interface qui promet une file que le moteur refuse (§ 13). Coût : ~10 pts, une mutation de plus. Renversable au mot de l'opérateur.
- **2026-09-15 06:0x — décision tranchée par l'auditeur (§ 10) : conséquence de L20-8 = (a)** — « Lancer ensuite » (Arrivées, `features/arrivals/page.tsx:138`) devient « Lancer » désactivé pendant un passage, réactivé à l'inactivité, la file offerte sous verrou de maintenance seulement (§ 12) ; propriétaire **L20 phase 9** (le lot qui déplace la prémisse porte sa conséquence, même PR, même tour) ; ligne de registre à la PR docs de L20. Refusé (b) : une action dessinée qui refuse toujours. Coût ≈ 3 pts. Renversable au mot de l'opérateur.
- **2026-09-15 09:1x — mesure 20 (pleine suite à mi-sous-lot), troisième sort** : sur L13r, la suite de mi-lot lit UNE chute (`poster.py` R114) sous quatre portes de phase vertes (r·1–r·4), bissectée à r·2, réparée par `l13r 2` avant r·5 (RESUME-L13r l.15, 20, 81). Trois sous-lots, trois prises.
- **2026-09-15 10:01 — PR docs du lot L13b #602 FUSIONNÉE** (`cdde26731`, no-version-bump, CI verte, un fixup : un worktree mort nommé dans BRIEF-L13c ; bâtisseur standard 09:16 → READY 09:44 = 28 min, fusion 10:01) : lignes d'état (Last landed L13b, Next L13r), ligne L13r au tableau du DESIGN, B-465 `fixed #601`, B-514–B-517 filées, **ce fichier commité byte-identique à ma copie** (le checkout principal est propre ; j'écris désormais sur la copie de main, qui monte à la prochaine PR docs). Ordres 39 et 40 clos. Cinq bâtisseurs standard mesurés : 46 / 30 / 67 / 29 / 45 min, deux corrections d'une ligne, 0 tour.
- **2026-09-15 10:2x — règle de brief (steward, née d'une mesure)** : « la PR READY se rapporte à la seconde où elle existe, avant tout autre commit » — l20 3 a ouvert #603 à 10:04 et enchaîné ses commits de clôture sans le dire, lecteur spawné 10:13 (9 min contre 3 min 30 sur #601). Dans BRIEF-L13c et les suivants.
- **2026-09-15 11:5x — décision tranchée par l'auditeur (§ 10) : L20 C7 = (a)** — la barre d'arr-queued dit la nouvelle prémisse (en file derrière une MAINTENANCE, ni jauge ni étape d'un passage qui ne tourne pas ; ruling 8), ≈ 2 pts ; refusé (b) : un écran qui contredit son toast. Mesure du tour L20 : 2 bloquants / 6 majeurs / 5 mineurs par UN lecteur sur neuf phases vertes ; réparation par `l20 4`, relecture des sondes par le steward (mesure 2).
- **2026-09-15 11:32 — quatrième succession du steward** `[31ca3c]` → `[ba1693]` à 66 % (porte 80, mesure 13), frontière calme après le tour L20 ; brief 13e rafraîchi 11:2x avec les ordres 39–41.
- **2026-09-15 13:2x — ordre 38 rappelé au steward** : le ruling 106 nommait « r·10-bis » une phase NEUVE de L13r (familles système) ; le mot de l'opérateur du 14/09 réserve « bis » à une correction → r·11 / r·12 / r·13, renumérotation dans le commit docs du ruling — appliqué 13:3x (13e corrigé, grep « r·10-bis » → 0 ; relayé à l13r 2 avant son commit docs) ; sort final à lire au push de r·8.
- **2026-09-15 13:4x — ruling 107 (steward, rapporté)** : r·10 mesurée 18 pts à l'ouverture → r·10 réglages + secrets, r·11 bibliothèque + maintenance + compte, r·12 familles système + JOURNAL + SCHEDULERS, r·13 la fiche, r·14 legacy.js meurt + PR ; nombres entiers, docs avant code. L13r = 14 phases (6 au plan).
- **2026-09-15 15:20 — L20 fusionnée (#603, `60c6d9b1d`, v0.98.95)** : les leviers globaux et l'historique (Q1 = B du 12/09) ; un tour de lecture (2 bloquants / 6 majeurs / 5 mineurs), réparation par un agent frais, relecture des sondes par le steward ; READY 10:04 → fusion 15:20. PR docs de L20 à suivre (bâtisseur standard).
- **2026-09-15 16:2x — décision tranchée par l'auditeur (§ 10, méthode) : le push d'un bâtisseur docs tourne sous le mutex du harnais** (`heavy.sh --class test`), jamais sur un sondage du verrou ; mesure : 16:17, push de docs l20 1 à côté de la porte de l13r 3, 121 Mo libres, charge 8,7, ~15 min perdues. Refusé : garder le sondage. Dans chaque brief de bâtisseur.
- **2026-09-15 16:35 — PR docs du lot L20 #604 fusionnée** (`c0a5062ac`) : le lot L20 est clos ; ruling 109 : L13r = r·1–r·15 (la projection meurt en r·14, le fichier en r·15).
- **2026-09-15 17:2x — ruling 111 (steward)** : L13r = r·1–r·17 (r·15 le dernier code du moteur, r·16 ses instruments, r·17 porte + PR) ; 6 phases au plan → 17 réelles, huit STOP D de taille — le chiffre de l'ordre 42.
- **2026-09-15 19:3x — question de domaine posée à l'opérateur (via l'auditeur, L13c c·1, B-312)** : le dialogue de suppression multiple nomme les quatre premiers titres cochés puis « et N autres » ; avec ≥ 5 cochés dont un caché par le filtre, ce titre caché n'est que compté. A (appliqué en attendant, coût 0) : le repli reste, la garde tient jusqu'à 4, le cas ≥ 5 en ligne de ledger ; B (≈ 2 pts, redessin du dialogue, divergence d'oracle acceptée, phase de comportement ultérieure) : chaque titre coché est nommé quel que soit le nombre. Recommandation A. **Mot attendu : A / B.**
- **2026-09-15 20:3x — round de décision (auditeur), question 1/3 : Q4 = A** — après le choix d'un candidat, l'écran de résolution se ferme comme aujourd'hui ; le message « Identifié comme … · Annuler » nomme le choix pendant les 7 s ; la moitié « carte marquée pendant la fenêtre » n'est pas construite ; **B-500 se ferme** sur la pastille livrée (#598). Refusé B (écran gardé ouvert 7 s, ~1 h d'agent).
- **2026-09-15 20:4x — round de décision, question 2/3 : le dialogue de suppression multiple = A** — le repli « et N autres » reste tel que dessiné ; la garde de B-312 (« chaque titre coché nommé, cachés compris ») tient jusqu'à quatre titres ; le cas ≥ 5 avec un titre caché par le filtre est consigné au ledger de c·1, pas redessiné. Refusé B (tous les titres listés, ≈ 2 pts).
- **2026-09-15 20:5x — décision du steward (rapportée), étend celle de l'auditeur de 16:2x** : TOUT push de TOUTE vague tourne sous le mutex du harnais, sans override — le push de c·1 avait démarré sous le seul verrou tests pendant les 23 passes mutate.sh du lecteur R (la course de 16:17 par construction). Coût : un push attend une passe (5–10 min). Le verrou tests reste pour les pytest sans harnais.
- **2026-09-15 21:1x — round de décision, question 3/3 : l'issue plugin = A, « ouvre »** — le steward ouvre `review-archive/plugin-issue-2026-09-15.md` tel quel sur `LounisBou/claude-orchestrator` (ordres 28 + 29 amendé, huit candidats mesurés) ; B (attendre la fin de L13) refusé. Round complet 3/3.
- **2026-09-15 21:2x — l'opérateur : « Et on peut pas accélérer ? Je trouve encore ça très lent ! » puis « j'ai pas de machine supplémentaire sous la main là, mais commençons par le levier 1 »** → trois leviers mesurés par l'auditeur (1 : ses dessins de L16–L18 dès maintenant, en parallèle de L13c ; 2 : une seconde machine pour les lectures, le seul qui double le débit — un mutex, 16 Go ; 3 : trois agents, impossible sans le 2) ; levier 1 retenu → ordre 44 ; round de dessin L16–L18 ouvert dans l'onglet de l'auditeur.
- **2026-09-15 22:0x — L13r fusionnée (#605, `08400a22a`, v0.98.96) : `design/src/engine/` n'existe plus sur main** — le moteur de 31 444 lignes (13/09) est mort en trois jours (L13a #596, L13b #601, L13r #605) ; un tour de lecture, un bloquant réparé. Ordre 44 en exécution : `design l16 1` (standard) spawné dans le créneau libéré.
- **2026-09-15 22:3x — l'opérateur, sur le round des dessins L16–L18 (verbatim)** : « Faisons une pause sur tes questions pour les lots suivants. Parce que ce que je remarque avec les questions, c'est que l'organisation, pour le moment, n'est pas complète et ne suit pas le dessin que je veux pour l'app. Je voudrais d'abord qu'on tranche certaines questions avant de se lancer dans le dessin des futures phases et des futures surfaces de l'application. C'est ce qu'on va trancher et qui va définir mes réponses par la suite. » → **ordre 44 SUSPENDU** (le bâtisseur du dessin L16 retenu, rien d'écrit ; L17/L18 non ouverts) ; le round 2 (trois questions de dessin, question 1 sans réponse) et la question 4 (Arrivées sous le § 20) sont SUSPENDUS ; une série de questions d'organisation de l'app s'ouvre à SA main dans l'onglet de l'auditeur ; L13c continue. Ses trois questions précédentes (22:2x : « À quoi sert Arrivées ? Lancer le pipeline à l'heure d'un pipeline au média ? Quelle différence entre les arrivées et les acquisitions ? ») ont reçu leur réponse (§ 20 point 3 : Acquisition suit le parcours par média, Arrivées dit ce qui est bloqué et pourquoi ; la barre de lancement d'Arrivées décrit le moteur par lots d'aujourd'hui).
- **2026-09-15 22:5x — ORGANISATION DE L'APP, série de rulings dictés à l'auditeur (round 3, à sa main).** Contexte donné par lui (verbatim, extraits) : « je me demande si les arrivées ne devraient pas rentrer dans les acquisitions, comme peut-être un onglet supplémentaire. Finalement, les arrivées, c'est des acquisitions faites en direct dans qBittorrent » ; « Je veux trouver un moyen de faire revenir les torrents qui sont téléchargés dans les acquisitions, de façon naturelle […] les torrents qui sont les médias, parce qu'il peut y avoir d'autres torrents » ; « quand on fait une récupération par qBittorrent d'une saison de série, on ne veut pas forcément que cette série soit en suivi ». Fait rappelé par lui : le tri du moteur classe chaque arrivée (épisode détecté → série ; sinon vidéo → film ; sinon → autre).
- **2026-09-15 22:5x — ruling d'organisation 1 = A** : **une arrivée crée une acquisition PONCTUELLE (film, épisode, saison), jamais un suivi ; le suivi reste un acte — « Suivre », sur la fiche — que l'interface PROPOSE sur la carte d'arrivée d'une série non suivie, sans le faire d'office ; les arrivées classées « autre » (non média) n'entrent pas dans les acquisitions.** Refusé B (suivi d'office avec « Ne plus suivre »). En brainstorm, non tranché encore : les arrivées comme cartes d'acquisition (une carte par média, « Arrivées »/« À traiter » = un onglet ou un filtre d'Acquisition) contre un simple onglet déplacé ; demandes backend à écrire : la naissance d'une carte depuis un torrent sans demande, le demandeur d'un ajout manuel.
- **2026-09-15 22:49 — ruling d'organisation 2 = A** : **les arrivées deviennent des cartes d'acquisition** — un torrent média terminé (tri du moteur) devient une carte d'acquisition à l'état « arrivé » (demandeur = le compte connu, sinon le propriétaire Plex), avec sur elle son tunnel (à résoudre, bloqué avec sa raison, en traitement, rangé, vérifié dans Plex) ; « À traiter » (onglet ou filtre d'Acquisition) ne montre que les cartes qui attendent sa main ; l'écran des candidats s'ouvre depuis la carte ; **la page Arrivées disparaît**, la barre passe à trois onglets ou libère une place ; la barre de lancement par lots disparaît avec elle (leviers à Système › Pipeline depuis L20). Refusé B (un onglet déplacé tel quel). Coût accepté : un lot de comportement après L13c (~1 jour), une demande backend (une famille de données ; la naissance d'une carte depuis un torrent sans demande ; le demandeur d'un ajout manuel), le § 20 point 3 à amender par lui. Ce ruling RÉVISE Q1 = B du 12/09 (démarrer/arrêter sur la barre d'Arrivées) : la barre meurt avec la page.
- **2026-09-15 22:5x — ruling d'organisation 3 = A** (ses mots : « quand un film est arrivé et qu'il est confirmé comme arrivé dans la médiathèque […] il peut disparaître du suivi. Ce n'est pas le cas pour une série, parce qu'une série peut avoir plein d'épisodes qui vont sortir […] qu'on veut continuer à suivre. Un film, on sait : quand il est arrivé dans la médiathèque, c'est terminé. ») : **le suivi d'un film se termine de lui-même quand le film est CONFIRMÉ dans la médiathèque (match Plex validé, § 4) et quitte « Suivis » sans trace là** — sa trace vit sur sa fiche média (acquis le …, release, demandeur) et dans l'historique de son tunnel ; tant qu'il n'est pas confirmé, il reste dans les suivis (on l'attend). **Le suivi d'une série ne se termine jamais seul** ; il ne cesse que par « Ne plus suivre ». Refusé B (une section « Terminés » avec « × = vu »).
- **2026-09-15 23:0x — ruling d'organisation 4 = A** : **une seule échelle d'étapes sur la carte d'acquisition, du souhait à Plex** (proposée : demandé → cherché → attrapé → téléchargement → arrivé → identifié → trié → enrichi → rangé → vérifié dans Plex ; les noms des crans s'ajustent au dessin) ; l'état du tunnel (en attente, bloqué + raison) se lit sur l'étape courante ; une carte née d'une arrivée manuelle commence à « arrivé ». Refusé B (deux rails : acquisition puis traitement). Demande backend : une source d'étapes unique (les étapes d'acquisition et celles du pipeline dans une même échelle).
- **2026-09-15 23:0x — ruling d'organisation 5 = A + un verbe** (ses mots : « la carte existe sans identité, mais avec une possibilité de la recaser comme n'étant pas un film ou une série, donc de la renvoyer dans autre, logiciel, ce genre de choses ») : **un dossier arrivé non reconnu a sa carte d'acquisition sans identité** (nom du dossier en titre, pas d'affiche, étape « identifié » en attente avec sa raison, « Résoudre » ouvre l'écran des candidats depuis la carte) ; **l'écran des candidats offre « Ce n'est pas un média »** : le dossier est reclassé « autre » (logiciel…), rangé où le tri range cette catégorie, et sa carte quitte les acquisitions. Refusé B (une liste « À identifier » à part). Demande backend : le reclassement d'une arrivée hors média.
- **2026-09-15 23:0x — ruling d'organisation 6 = A** (ses mots : « Oui, elle reste à trier. Mais si je la mets moi-même à la main dans logiciel ou autre, dans ce cas-là elle disparaît, je la vois plus. ») : **« Laisser tel quel » = « plus tard »** — la carte reste en acquisition, étape « identifié » en attente, raison « mis de côté par vous, le … », hors de « À traiter » mais visible dans « En cours », le fichier reste en transit ; **elle ne disparaît que par un reclassement de sa main hors média** (« Ce n'est pas un média » → logiciel, autre), et alors il ne la voit plus. Refusé B (écartée sans carte, retrouvable par la Maintenance seule).
- **2026-09-15 23:1x — ruling d'organisation 7 = A** : **« À traiter » = ce que seule sa main débloque** — à résoudre (aucun candidat, égalité), match Plex à confirmer (§ 3), une erreur du tunnel qui attend une décision (relancer / abandonner) ; « mis de côté par vous » n'y est pas (ruling 6) ; ce qui stagne pour une autre raison (file derrière une maintenance, release introuvable, téléchargement bloqué) se lit sur sa carte dans « En cours » avec sa raison, et à Système pour les leviers. Refusé B (tout ce qui n'avance pas).
- **2026-09-15 23:1x — ruling d'organisation 8 = A** : **« Suivant » reste sur l'écran des candidats** et enchaîne les cartes « à résoudre » de « À traiter » dans leur ordre, puis ramène à la liste quand il n'y en a plus (la règle existante se re-vise sur la nouvelle file). Refusé B (retour à la liste entre chaque). Note de méthode : la question a dû être reposée en mots simples (« Suivant » lu comme « Suivre ») — une question de l'auditeur se formule sur le geste concret, jamais sur le nom du bouton.
- **2026-09-15 23:1x — ruling d'organisation 8 RÉVISÉ par l'opérateur = B** (ses mots : « j'ai une entrée qui représente un dossier, je sais pas ce que c'est, je clique dessus pour résoudre, j'ai la résolution et je reviens à la liste. Non, je préfère revenir à la liste. ») : **après une résolution on revient à « À traiter » ; le bouton « Suivant » disparaît de l'écran des candidats.** Remplace le A de 23:14 (deux minutes plus tôt) ; son mot renverse le sien.
- **2026-09-15 23:1x — ruling d'organisation 9 = A** : **une carte née d'un ajout direct dans qBittorrent porte le propriétaire du serveur Plex (lui) comme demandeur**, affiché « ajouté par Izno, dans qBittorrent », réaffectable à un autre compte depuis la carte (§ 17, droit de l'Opérateur). Refusé B (« sans demandeur »). **Série d'organisation close : 9 rulings (22:47 → 23:1x)**, résumés : (1) une arrivée = acquisition ponctuelle, jamais un suivi, « Suivre » proposé ; (2) les arrivées = cartes d'acquisition, la page Arrivées et sa barre de lancement meurent (révise Q1 = B du 12/09), un lot de comportement après L13c ; (3) le suivi d'un film finit seul à sa confirmation, jamais celui d'une série ; (4) une seule échelle d'étapes sur la carte, du souhait à Plex ; (5) carte sans identité + « Ce n'est pas un média » (reclassement « autre ») ; (6) « Laisser tel quel » = plus tard, la carte reste ; (7) « À traiter » = ce que seule sa main débloque ; (8) retour à la liste après une résolution, « Suivant » disparaît ; (9) demandeur = le propriétaire, « dans qBittorrent ». Demandes backend nées de la série : naissance d'une carte depuis un torrent sans demande ; une source d'étapes unique ; le reclassement hors média ; le demandeur d'un ajout manuel. Le § 20 point 3 de la constitution est à amender par lui (« les Arrivées disent ce qui est bloqué » → « À traiter »).
- **2026-09-15 23:2x — décision de l'auditeur (délégation sur l'ordre des lots) : L22 « Arrivées dans Acquisition » s'insère AVANT L16** (dépend de L13, L19, L20, L21) — les trois lots suspendus dépendent de ce que L22 change (place dans la barre, carte et son échelle, demandeur) ; coût : L16–L18 reculent d'un jour ; L22 démarrable empilée sur la tête de L13c à sa PR READY. Son dessin s'écrit dès que l'opérateur lève sa pause (question posée). Attente nommée : le § 20 point 3 de la constitution (« les Arrivées disent ce qui est bloqué et pourquoi ») est à amender par lui.
- **2026-09-15 23:2x — l'opérateur (verbatim)** : « On va faire une pause sur le brainstorming et demain matin on tranchera les questions qui restent. On garde ça en mémoire et le brief qu'on vient de faire et on continuera ce brainstorming. En attendant, on continue d'avancer à l'implémentation. » → **reprise demain matin (16/09)** sur les cinq questions d'organisation restantes, dans l'ordre proposé par l'auditeur : (1) les onglets d'Acquisition — « À traiter » onglet ou filtre, onglet par défaut (débloque le dessin de L22) ; (2) la place libérée dans la barre du bas ; (3) où l'application parle (alertes de ratio, cross-seed refusé, tunnel bloqué : un seul endroit ou chaque page) ; (4) le partage Système / Trackers / Maintenance ; (5) où l'on gère les comptes (rubrique « Comptes » de Réglages vs Profil). À confirmer seulement : la Médiathèque sous les droits, le SSO qui s'ajoute. **En attendant** : L13c continue, la PR docs de L13r part ; les dessins de L22 et de L16–L18 restent retenus jusqu'à son mot.
