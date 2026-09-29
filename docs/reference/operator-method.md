# La méthode de l'opérateur — TorrentMate, refonte de l'interface

Trois parties, et rien d'autre : **(1)** ses principes, un par ligne, avec sa phrase et sa date ; **(2)** les règles de
méthode en vigueur, en table — règle, raison, mesure de retour ; **(3)** ses décisions par surface, une ligne chacune, avec
sa date. L'opérateur seul amende ses mots ; l'auditeur en cours tient ce fichier et ne le commite jamais (l'orchestrateur
l'atterrit dans la PR docs du lot). Rien ici n'est l'avis d'un auditeur : une ligne porte les mots de l'opérateur ou une
mesure.

**Le journal daté n'est plus ici.** Du 2026-09-12 au 2026-09-29, il est dans l'archive citée
`docs/reference/operator-method.md@5a763b90a` (`git show 5a763b90a:docs/reference/operator-method.md`), avec le
texte intégral de chaque décision, les ordres des audits 1 à 82 et leur sort, les attentes nommées, les candidats au plugin
et le registre du temps perdu. Il n'est pas lu par défaut. Désormais, le détail daté d'une décision (verbatim, contexte,
lectures refusées) va au § 8 du rapport d'audit en cours ; ce fichier n'en garde que la ligne.
**Retour :** une décision reposée à l'opérateur faute de la trouver dans cet index → la ligne manquante est rapatriée de
l'archive, et la famille (le genre de ligne perdue) est rapatriée avec elle.

Heures lues sur l'horloge de la machine, sauf « ~ » (heure estimée par la session qui a reçu le mot). « Rd R Q q » = round
de décision R, question q ; « ruling N » = ruling d'organisation N (numérotation : `docs/features/maquette-l22/DESIGN.md@232a908ca` § 0).

## 1. Les principes de l'opérateur

| Date | Principe | Sa phrase |
| --- | --- | --- |
| 09-12 | La fin de la maquette : l'app prête graphiquement sur toute sa surface, testée sur Mac et Android ; la refonte du back-end commence quand la surface suffit | « 90 % peut-être » ; le reste « s'accroche au front à ce moment-là » |
| 09-12 | Un bug qui compte bloque un parcours ou gêne visuellement, même sans bloquer ; un défaut d'instrument se file, il n'arrête pas le travail | « Je veux pouvoir faire fonctionner la maquette comme je ferai fonctionner l'app. » |
| 09-12 | Il teste sur son Android (PWA sur tm-design), le smartphone d'abord, parfois le Mac ; quand il veut ; une invitation à tester, avec capture si nécessaire, jamais systématique | — |
| 09-12 | Il décide le fonctionnel ; tout le reste avance sans lui | « Quand c'est possible, décide sans moi. Surtout s'il s'agit seulement de faire avancer les merges ou les lots. On continue. » |
| 09-12 | Gros lots qui avancent ; les petits changements après coup ne sont pas graves ; on prend le temps sur les grosses décisions d'architecture | — |
| 09-12 | La rigueur doit se justifier | « Un refactor nécessaire pour rendre l'app vraiment fiable et propre architecturalement, c'est légitime. La rigueur doit être légitime ; si elle est contre-productive, elle est illégitime. » |
| 09-12 | Il lit la session qui le guide, les questions qu'on lui pose et ce qu'il voit sur l'appareil ; le reste (registre, plan, état, office, corps de PR) est pour les agents | — |
| 09-12 | Le back-end : on reprend ce qui existe (adapter, réarchitecturer, transformer), refaire seulement s'il le faut | — |
| 09-12 | La rigueur se retire et se remet sur mesure | « OK on applique les 7, mais on remettra la rigueur en place si elle s'avère nécessaire. » |
| 09-13 | Fusionner et avancer sans l'attendre | « Ne t'arrête pas maintenant, prends les décisions de merge et de fusion. Avance ! » ; ~10:35 « Avance, merge, déploie… N'attends pas après moi. » |
| 09-13 | L'audit : lancé à son mot, fini à son mot, remplacé à 80 %, jamais arrêté en automatique | « C'est moi qui lance l'audit, c'est moi qui définis quand il est terminé. » ; 22:2x « L'audit est remplacé à 80 %, il ne s'arrête pas tant que l'opérateur ne l'a pas arrêté. » |
| 09-13 | L'auditeur le remplace pendant l'audit, et pose ses questions de méthode pour apprendre | « tu te substitues autant que faire se peut à l'opérateur. Mais pour ça tu dois poser des questions à l'opérateur pour apprendre et approcher au mieux sa méthodologie. » |
| 09-13 | Deux de ses préférences qui se contredisent (la surface d'abord, l'implémentation la plus propre) | « Seulement quand le détour est court. Il faut peser ce qui est le mieux pour l'implémentation, le plan et la productivité quand il faut trancher. » |
| 09-13 | L'ordre des lots : le plus simple et le moins perturbant | « Je veux ce qu'il y a de mieux et de plus logique pour l'implémentation. Tranche toi même le plus simple et le moins perturbant qui serve au mieux l'implémentation. » |
| 09-13 | La productivité est la mesure de l'auditeur | « Seul 35 % du temps produit le code. C'est inacceptable ! Ton rôle est de contrôler le steward et d'optimiser la productivité. » |
| 09-13 | L'auditeur est garant de l'application des règles | « Tu es le garant : assure-toi que ça marche et que c'est appliqué et respecté. Renforce si nécessaire. » |
| 09-13 | Ce qui marche s'entérine | « On entérine ce qui marche dans la méthodologie pour rendre les améliorations pérennes ! On ne s'arrête pas là, on continue les efforts ! » ; 22:3x « prends des décisions, teste-les et entérine-les si elles portent leurs fruits. » |
| 09-13 | Ce qui se généralise remonte au plugin (le texte d'une issue lui est montré avant) | « tout ce qui est prolifique et généralisable doit remonter dans le plugin. » |
| 09-13 | Le temps perdu sert de leçon | « Il faut tenir compte du temps perdu et des erreurs, elles doivent servir de leçon et plus se reproduire. » |
| 09-13 | Le modèle et l'effort se choisissent par lancement ; Sonnet et Haiku sont permis | « Sonnet autorisé, on retire ça […] l'orchestrateur choisit » ; « L'orchestrateur doit pouvoir choisir l'effort indépendamment du modèle pour optimiser. » |
| 09-14 | « bis » veut dire correction | « N était censé être le numéro de la phase dont la “bis” est une répétition pour correction. » |
| 09-15 | L'organisation de l'app se tranche avant de dessiner la suite | « Je voudrais d'abord qu'on tranche certaines questions avant de se lancer dans le dessin des futures phases et des futures surfaces de l'application. » |
| 09-27 | Tous les accès sont des droits de rôle, configurables | « tous les droits d'accès sont configurables par les ACL. Rien n'est réservé à l'opérateur […] Les ACL gèrent tout. » |
| 09-27 | La reprise des données au back-end n'est pas une migration à l'identique | « On n'est pas obligé de reprendre toutes les données telles quelles. On n'est pas encore en production » ; « on pourrait […] réimaginer des bases de données » ; « ce serait bien d'avoir une vraie staging » |
| 09-28 | Le budget n'est pas une contrainte | « ne t'inquiète pas pour le budget, j'ai ce qu'il faut, c'est pas ta préoccupation, tu enchaines ! » |
| 09-28 | Il doit toujours voir sur tm-design le travail en cours | « TM Design doit toujours me montrer le travail en cours. […] il faut que je puisse juger si le travail qui est en train d'être effectué est bon, que je puisse recadrer » |
| 09-28 | L'auditeur trouve et lève les goulots d'étranglement | « ton rôle, c'est de vérifier que tout avance bien et rapidement, de trouver les goulots d'étranglement et d'y mettre fin. » |
| 09-28 | Tout régler, sans zèle | « Je veux que tu règles tout. […] c'est ton rôle que de râler, alléger le harnais s'il faut. » ; « il ne faut pas […] faire preuve de trop de zèle au détriment […] du travail fourni. » |
| 09-28 | Desserrer, puis vérifier le desserrage | « chaque fois qu'on décide de desserrer les taux du harnais, alors il faut […] vérifier le travail fourni, que le […] desserrage de l'étau était propice, […] ne pas hésiter à remettre […] du harnais en place si nécessaire. » |
| 09-28 | Moins de contrôles, plus de bugs corrigés après coup : la question est posée | « si […] y avait moins de contrôles, il y aurait peut-être plus de bugs, mais la correction de ces bugs a […] posteriori ne serait-elle pas moins chronophage » |
| 09-28 | Un bug signalé répare sa famille | « quand je signale un bug, c'est l'occasion de mettre en place […] des tests de non-régression, mais on peut aller plus loin et vérifier que la cause qui a fait qu'on n'a pas attrapé ce bug […] ou même cette typologie de bug […] soit corrigée. » |
| 09-28 | Le squash d'une PR verte n'attend pas son feu vert | « Squash merge APR, on n'attend pas […] mon feu vert. » |
| 09-29 | Un problème se règle une fois pour toutes : la cause, et une alarme qui dit s'il revient | « Je veux qu'on résolve une fois pour toute ce problème » ; « assure toi que le problème de clef chrome ne se reproduira plus, que secd ne consomme plus de ressource du mac pour rien. » |
| 09-29 | Ce serveur n'est pas une machine de travail : les données des navigateurs y sont jetables | « si les cookies, caches, credentials sont éffacés je m'en moque j'ai rien d'important c'est une serveur pas une machine perso de travail ! » |
| 09-29 | L'auto-merge, réglé une fois pour toutes | « Encore une fois, pourquoi on attend, on est en PR auto merge, que ce passe t'il je souhaite que le problème soit réglé maintenant et une fois pour toute pour l'auto merge des PRs » |
| 09-28 | Mettre en place sans l'attendre, avec soin | « évite d'attendre après moi pour […] mettre en place des choses. Vas-y, […] fonce […]. Fais attention […] à la qualité du code et […] à l'avancement et au respect du plan » |
| 09-29 | Plus de notification à chaque version de tm-design | « C'est bon tu peux arrêter de me prévenir à chaque nouvelle version de TM design. » |
| 09-29 | Pas de rétro-compatibilité | « A, pas de gestion de rétro-compatibilité ! » (l'app n'a que deux utilisateurs, 09-26 : « l'app n'est utilisée que par 2 personnes pour l'instant. ») |
| 09-29 | Responsive partout : l'interface fonctionne sur tous les appareils, pas seulement le sien | « Non tout doit être responsive, ça doit pas fonctionné que sur mon téléphone, mais sur tous ! » |
| 09-29 | Chaque cas se voit dans la maquette | « Comment tester tout les cas, si j'ai pas un exemple de chaque cas ? » ; « seule une maquette montrant tout les cas possibles est utile. » |
| 09-29 | Design et ergonomie d'application mobile native, le design système réutilisé au maximum | « Le design doit être le plus cohérent possible on réutilise au maximum le design système existant et les actions et l'ergonomie existante. On oublie surtout pas le maitre mot, design et ergonomie d'application mobile natif. » |
| 09-29 | Le respect du design système est surveillé et corrigé | « Le respect du design système est un critère important qu'il faut surveillé (et corriger !) » |
| 09-29 | La cohérence partout | « design, ergonomie, geste, composant, design system, je veux de la cohérence partout ! » |
| 09-29 | Un composant est réutilisé, jamais recopié | « les composants sont réutiliser, si un jour je change un composant ça change partout, c'est le design système ! » |
| 09-29 | Deux mécanismes semblables se comportent pareil ; on adapte l'existant au lieu d'en créer | « 2 mécanismes similaires de l'application devrait avoir le même comportement, on crée pas de nouveau composant on adapte » |
| 09-29 | L'existant validé d'abord, et c'est le nouveau qui s'y conforme | « là où on en as besoin c'est d'abord l'existant ! » ; « c'est tracker qui doit ressembler aux autres systèmes d'onglet, l'existant est ce qui est validé. » |

## 2. Les règles de méthode en vigueur

« Mesure N » = une des mesures de l'opérateur (12 et 13/09) ; « ordre N » = un ordre d'audit (le texte intégral et son sort,
jusqu'à 82, sont dans l'archive). Une règle qui meurt sort de cette table le jour même ; son histoire reste dans l'archive.

| Id | Règle | Raison (la mesure qui la fonde) | Mesure de retour |
| --- | --- | --- | --- |
| mesure 1 | Aucune garde, aucun bras, aucune vague d'outillage sans un défaut qui l'a atteint ; les outils qui rendent du temps sans retirer une porte sont permis (son mot 09-13 19:2x) | 09-12 : l'appareil grossissait plus vite que le produit | un défaut revenu faute d'une garde refusée |
| mesure 2 | Un tour de lecture par lot, aucun par micro-vague ; les mineurs d'instruments sont filés | 09-12 | un majeur trouvé après la fusion, qu'un tour aurait vu |
| mesure 3 | Le geste post-fusion est un script de l'orchestrateur, sans agent | 09-12 | — |
| mesure 4 | Une PR docs de l'office par lot, en fin de lot | 09-12 | l'état lu par une session fraîche en retard d'un lot |
| mesure 5 | Un train de correctifs par jour, pas une micro-vague par bug | 09-12 | — |
| mesure 6 (amendée 09-29) | Trois agents au plus, dont un seul sur le harnais (le verrou) ; les deux autres sans harnais (dessin, lecture, documents) ; retour à deux si la charge dépasse 8 ou si la mémoire récupérable passe sous 2 Go | ordre 68 : L22b 1,27 phase/h seul contre 0,81–0,87 à côté d'un autre agent du harnais | la cadence du lot et les minutes d'attente du verrou |
| mesure 8 | Porte de contexte à 80 % pour les trois rôles (agent, steward, auditeur) ; une phase démarre si jauge + coût mesuré de la dernière phase ≤ 80 ; jamais de rotation en milieu de phase | 13 rotations à 60 % sur L13a | une phase coupée par la porte |
| mesure 9 | Un sous-lot démarre empilé sur la tête finale du précédent, pendant son tour de lecture ; rebase après le squash | b·1 commité avant la fusion de L13a | — |
| mesure 10 | Démarrage à froid au régime : état ≤ 40 lignes + journal en ajout seul ; rulings dans un fichier numéroté ; lecture requise = brief + état + phase + rulings | 26 → 14 min au premier commit | temps du lancement au premier commit |
| mesure 11 | Budget de contexte ≤ 15 points par phase (journaux lus à la ligne de verdict, corps de commit ≤ 12 lignes, grep avant lecture entière) | 25–33 points par phase sur L13a | points par phase |
| mesure 12 | Les instruments lisent vrai (`heavy.sh` compte la mémoire récupérable ; `mutate.sh` lit le code de sortie ; `run.sh` construit une fois) | 9 + 20 min de verrou pour rien ; un vert faux depuis le 29/08 | une porte qui mesure faux |
| ordre 17 | La copie du lecteur est épinglée à la tête de la dernière porte, re-pointée à la PR prête | 35 min PR prête → lecteur | — |
| ordre 19 | Hook pre-push : chemin « docs seuls » (≤ 1 min) | ~80 min de suites sur des poussées de prose | — |
| ordres 21, 23 | Diète d'écriture : message ≤ 3 lignes sauf décision (deux lectures + coût) ; journal aux frontières ; brief de succession = état ≤ 40 lignes + pointeurs | triple écriture, 4 successions du steward un même jour | une perte de qualité due à la diète |
| ordres 22, 29 | Le steward route modèle ET effort par lancement (`orchestrator:model-routing`, règle de la fausse économie) | son mot 09-13 | un second tour causé par un palier trop bas |
| ordres 24, 58 | La porte de phase : gardes statiques → oracle seul → règles nommées des surfaces touchées, en une invocation ; le tier contrats toutes les 5 phases, à mi-suite, à la clôture et en CI | contrats ~290 s sur une porte médiane de 340 s ; 0 capture produit propre en 14 jours | ≥ 2 défauts de phase vus seulement par un contrat dans un lot → contrats à chaque phase |
| ordre 25 | Tier contrats à 3 règles en parallèle | 19 règles à 2 ≈ 3–4 min ; ~400 Mo par règle | swap en hausse → retour à 2 |
| ordre 26 | Pas de `make check` local avant la PR d'une vague maquette : le job `test` de la CI est l'autorité | 15 min sous le verrou, 3e exécution de la même suite | — |
| ordre 27 | Délai de 10 min par invocation de règle ou de mutation (« TIMED OUT » = chute de l'instrument) ; un verrou ne se brise que si son tenant est parti | mutation pendue 47 min ; verrou brisé sous un tenant vivant | — |
| ordre 31 | Pas de chiffres de baseline dans les corps de commit (le diff du JSON est le registre) | corps de 40 lignes | un lecteur qui a manqué un nombre |
| ordre 32 | Une PR de conversion ne cite pas les §§ de la constitution ; une PR de comportement ou de surface les cite (entériné par son mot, 09-14) | — | — |
| ordre 33 | Frontière calme avant le redémarrage du lundi 05:00 : tout poussé à 04:30, aucun lancement après 04:15 | reboot hebdomadaire | le journal de relance du lundi |
| ordre 34 | Les journaux de porte vivent hors de `/private/tmp` | le reboot a effacé deux dossiers de journaux | — |
| ordre 35 | `core.hooksPath` relatif, pour que chaque worktree exécute les hooks de sa branche | trois chutes pre-push à preuve jetée | — |
| ordre 36 | Un run long s'attend dans l'appel d'outil, jamais en arrière-plan en fin de tour | pertes répétées de runs | — |
| ordre 37 | Un agent bloqué reçoit une sonde toutes les 15 min (réponse attendue en 60 s) ; l'écran n'est qu'un complément | deux agents à l'arrêt des heures | — |
| ordre 38 | « N-bis » = correction de la phase N seulement ; une phase insérée prend un numéro et décale les suivantes | son mot 09-14 | — |
| ordre 42 | Chaque fichier de phase porte sa mesure d'ouverture ; les coupes se font en un commit docs | L13r coupée cinq fois | STOP D de taille par lot |
| règle 09-16 | Un chemin parti de l'arbre se cite `path@<dernier commit de main qui le porte>`, jamais à un commit de branche | un squash rend un commit de branche irrésoluble | — |
| ordres 46, 47, 72 | Le second créneau ne reste jamais vide : dessins en avance (jamais entre deux lots), puis ce qu'aucun lot ne possède | « je trouve ça encore lent » | un lot qui attend son dessin |
| ordres 48, 65 | Une chute écartée comme « charge » se prouve par comparaison répétée contre main (5 tirages d'abord pour une règle instable connue ; 10 contre 10 si ≥ 1/5), jamais par une relance verte | — | — |
| ordre 49 | La porte ne se relance pas pour un mouvement attendu : oracle seul d'abord, mouvements déclarés par nom avec leur cause ; pas de porte « final » après une acceptation prouvée | L22b : 28 portes en échec sur 66, ~2 h par lot | portes en échec par lot |
| ordres 50, 51 | tm-design sert automatiquement la tête du lot en vol (main entre deux lots), vérifié servi = disque | tm-design resté un jour sur une fusion ancienne | tm-design en retard sur la tête |
| ordre 52 | Harnais ajouté ≤ 0,6 × produit ajouté par lot ; au-delà, une phase de consolidation avant READY, prouvée comme une conversion | ratio ~1,5 sur L22b | L16 : 0,60, porte ses fruits |
| ordre 53 | Une phase de plan ≤ 60 lignes (portée, contrats, tests, fait = quoi, pointeurs) | L16 : 91 lignes par phase | — |
| ordre 54 | Un horizon de gel de l'interface dans `IMPLEMENTATION.md` : phases restantes ÷ cadence mesurée, mis à jour à chaque clôture, avec les pages encore sans dessin | aucune date écrite | — |
| ordre 55 | Lecture permanente de l'audit : `bash review-archive/audit-health.sh` toutes les 2 h (`--alerts`), recréée à chaque relance d'audit | — | une ALERT vraie que le cycle n'a pas vue |
| ordre 56 (amendé 09-29 ~19:10, son mot) | Dès qu'une PR est ouverte et son diff vérifié sur l'artefact, le steward arme `gh pr merge <n> --auto --squash --match-head-commit <sha>` (réarmé si la tête bouge) ; jamais attendre la CI pour fusionner à la main ; `allow_auto_merge` activé sur le dépôt ; écrit en tête de chaque brief de steward | trois fois dite (09-13, 09-28, 09-29) : « pourquoi on attend, on est en PR auto merge » — le réglage du dépôt était à `false` | une PR verte non fusionnée faute d'armement |
| ordre 57 | Chaque bug signalé par l'opérateur : test vu rouge, et dans BUGS.md « échappé de », « pourquoi », « famille réparée par » | son principe du 09-28 | un bug de la même famille qui revient |
| ordre 59 | entry et pwa (hôte déployé) se contrôlent après déploiement, hors de la porte | 8 chutes sur 8 = délais du réseau | — |
| ordre 85 (remplace l'ordre 60, sur son mot du 09-29) | L'interface tient à TOUTES les largeurs : une règle « responsive » passe chaque état nommé à 320, 360, 369, 390, 412, 768 et 1280 px et refuse tout débordement ou coupure (bordure, tableau, texte, bouton hors de l'écran) ; à mi-lot, à la clôture et en CI, et à chaque phase sur les états des surfaces touchées ; les autres règles gardent leur largeur | 6 défauts de largeur échappés, dont B-557 et le tableau des exécutions coupé à droite (09-29 17:04) | un défaut de largeur signalé par lui, à n'importe quelle largeur |
| ordre 61 | Le tour de lecture marche au doigt, à 369 px sur tm-design, les surfaces du lot (à froid, depuis l'état précédent, et les voisins des correctifs) | 22 des 33 échappés dans des familles qu'aucune porte ne lit | défauts qu'il signale par lot |
| ordre 62 | Pas de fusion avec un majeur produit connu visible à 369 px sans son mot | B-557 | — |
| ordre 63 | Les familles récidivistes (tirer-pour-rafraîchir, défilement après retour, éclair) ont chacune une règle de famille | — | une récidive |
| ordre 64 | Consolidation du harnais dans le second créneau, prouvée par comptes de tenues égaux et mutations par nom ; rien retiré pour « jamais tombé » | — | — |
| ordre 66 | Le lecteur rejoue 10 mutations revendiquées tirées au hasard, puis fait les siennes | 272 sur 281 tombent | une revendiquée qui ne tombe pas |
| ordre 67 | Documents vrais et allégés : `IMPLEMENTATION.md` réécrit à chaque squash ; registre trié ; un office unique des invariants de brief ; lecture d'audit réduite (en-tête seul) | 342 Ko de mémoire relus à chaque relance | — |
| ordre 69 | Le périmètre d'un lot se fige à son ouverture : un ruling arrivé en cours va au lot suivant, sauf s'il change une surface en construction ou débloque un STOP | L22b : 23 unités sur 38 nées en cours de lot | un défaut qu'il signale à cause d'un ruling différé → le ruling entre dans le lot |
| ordre 70 | `run.sh --rules` sur quelques règles et le build de tm-design prennent la classe `rule` (plafond 10) | trois runs bloqués 9–14 min derrière le verrou | compresseur ou swap en hausse, ou charge > 12 → classe browser |
| ordre 71 | `heavy.sh` attend la place avant de prendre le verrou | — | deux runs lourds simultanés |
| ordre 73 | Un rouge chronique « d'infrastructure » (3 fois de suite) ouvre une ligne de registre avec son mécanisme, nommé avant la PR prête | — | — |
| ordres 74, 83 | Le harnais ne crée plus de clés dans le groupe « unexportable-keys » de Chrome : la voie retenue est celle dont la sonde de 20 lancements sur les vraies pages du harnais mesure un delta nul, avec sa garde — `--use-mock-keychain` (#636) n'y suffit pas, Playwright le passait déjà ; `audit-health.sh` alerte si le groupe dépasse 200 lignes ou secd 50 % de CPU | 71 443 lignes purgées le 29/09 à 21:02 (secd 60–180 %, démarrages bloqués jusqu'à 3 min ; trousseau 360 → 21 Mo) | l'ALERT du cycle de 2 h |
| ordres 76, 77 | Chaque cas de chaque surface touchée devient un état nommé du catalogue que l'opérateur ouvre sur tm-design ; lentille « exhaustivité des cas » au tour de lecture ; inventaire des cas manquants des surfaces livrées ; le gel exige le catalogue complet | « En cours » vide à froid sur tm-design | un cas découvert à l'accrochage absent du catalogue |
| ordre 79 | Lentille « cohérence du design système » au tour de lecture ; chaque élément nouveau se rattache à un composant de `design/src/ui/` (table élément → composant du DESIGN), ou sa nouveauté est justifiée ; redessiner l'existant est un défaut | Trackers de L16 hors design système | un écart au design système qu'il signale |
| ordre 80 | Revue de conformité au design système de toutes les surfaces livrées, puis un train qui remet chaque écart à l'existant ; composant d'onglets unique avec garde statique obligatoire | trois écarts signalés le 29/09 | — |
| ordre 81 | Revue de tous les chemins de navigation contre § 16, marchés au doigt ; chaque écart filé comme défaut | Système → Réglages → Retour ramenait à Acquisition | — |
| ordre 82 | La relance après redémarrage lance le steward avec l'identifiant explicite du modèle | — | le journal de relance du lundi |

## 3. Les décisions par surface

Une ligne par décision, la plus récente l'emporte. Le texte intégral : l'archive (jusqu'au 2026-09-29) ou le § 8 du rapport
d'audit en cours.

### Organisation générale et navigation

- 09-15 · ruling 1 : une arrivée crée une acquisition PONCTUELLE (film, épisode, saison), jamais un suivi ; suivre reste un acte, sur la fiche.
- 09-15 · ruling 2 : les arrivées deviennent des cartes d'acquisition (un torrent média terminé et trié → carte à l'état « arrivé »).
- 09-15 · ruling 3 : un film arrivé et confirmé dans la médiathèque peut disparaître du suivi (pas une série).
- 09-15 · ruling 4 : une seule échelle d'étapes sur la carte d'acquisition, du souhait à Plex ; 09-26 Rd 5 Q4 = B : « trié · enrichi · rangé » fusionnent en « rangé », huit crans.
- 09-15 · ruling 5 : la carte existe sans identité, avec un verbe pour la recaser (ni film ni série).
- 09-15 · ruling 6 : une carte reste à trier ; rangée à la main ailleurs, elle disparaît.
- 09-15 · ruling 7 : « À traiter » = ce que seule sa main débloque (à résoudre, match Plex à confirmer, erreur du tunnel…).
- 09-15 · ruling 8 révisé = B : après une résolution, on revient à la liste ; 09-26 Rd 5 Q7 : « n sur m en attente » meurt avec « Suivant ».
- 09-15 · ruling 9 : un ajout direct dans qBittorrent porte le propriétaire du serveur Plex comme demandeur, réaffectable.
- 09-26 · Rd 4 Q6 (ruling 15) : Système sort de la barre du bas ; il s'atteint par le menu de gauche, à son droit, et le bouton du menu porte son badge.
- 09-26 · Rd 5 Q2 : la barre du bas s'adapte au nombre de boutons présents, chacun à la même part (2 → 50/50, 3 → tiers…).
- 09-26 · Rd 6 : § 17 point 4 de la constitution, la place de barre non occupée n'est pas un défaut (phrase amendée).
- 09-27 · Rd 8 Q15 : un compte qui n'a qu'une page n'a pas de barre du bas.
- 09-27 · Rd 10 Q7 : la page d'entrée (Retour, garde de sortie) est la première page de la barre du compte.
- 09-26 · Rd 5 Q5 : `/arrivals` devient une adresse inconnue (page « introuvable »).
- 09-29 · Rd Q8 (L24 OPEN 4) : `/medias`, `/systeme`, `/controle` répondent « introuvable » à la bascule, sans redirection.
- 09-29 · amendement du § 16 règle 2 (son « oui vas-y ») : les pages du menu latéral empilent et Retour refait le chemin d'arrivée ; les pages de la barre du bas remplacent, Retour → page d'entrée.
- 09-29 · Rd Q10 (L24 OPEN 6) : le grand écran reste mobile d'abord, avec une phase finale « bureau » au plan.
- 09-12 · A6 : « × » veut dire « vu » partout ; la sortie est « Annuler », visible et distincte.

### Acquisition

- 09-26 · Rd 4 Q1 (ruling 10) : « À traiter » est un onglet d'Acquisition, avec son compteur.
- 09-26 · Rd 5 Q1 puis 09-27 Rd 8 Q20 : onglets « Suivis · En cours · À traiter » (Découvrir est parti dans la barre).
- 09-26 · Rd 7 Q4 : l'onglet par défaut est « Suivis », puis le dernier ouvert (mémoire locale).
- 09-26 · Rd 5 Q3 : « Suivis » ne liste que des suivis ; une carte d'arrivée vit dans « En cours » ou « À traiter », même pour un épisode d'une série suivie.
- 09-26 · Rd 7 Q5 : « À récupérer » quitte « En cours » ; « Récupérer maintenant » reste sur la fiche du suivi.
- 09-26 · Rd 7 Q6 : « Rangé aujourd'hui » et « Cherché, rien trouvé » quittent « En cours », qui ne garde que « En vol ».
- 09-26 · Rd 5 Q6 : « Lancer » / « Arrêter » une passe meurent avec la barre d'Arrivées.
- 09-26 · Rd 5 Q9 : la carte « match Plex à confirmer » propose « Confirmer » et « Corriger » sur le match lui-même.
- 09-26 · Rd 5 Q10 : « Abandonner » une erreur du tunnel met le dossier en quarantaine, après confirmation.
- 09-26 · Rd 5 Q11 : L22 dessine la ligne « ajouté par … » ; le geste de réaffecter naît avec L18.
- 09-26 · Rd 7 Q7 : la roue du tirer-pour-recharger tourne dès que le geste est armé, un tour minimal visible, disparaît à la fin.
- 09-27 · ruling 16 et Rd 8 Q16 : « Mis de côté » replié en fin d'« À traiter » ; « Supprimer » y est une vraie suppression du dossier, confirmée.
- 09-27 · Rd 8 Q17 : les suivis en pause forment une section repliée en fin de « Suivis ».
- 09-27 · Rd 10 Q1 : une arrivée ajoutée à la main qui correspond à un élément suivi s'y rattache.
- 09-27 · Rd 10 Q2 : prendre une saison d'une série possédée non suivie crée une acquisition ponctuelle, avec « Suivre » sur la carte.
- 09-27 · Rd 9 Q13 : voir « À traiter » est un droit ; par défaut un compte ne voit et ne compte que ses cartes.
- 09-27 · Rd 9 Q16 : un suivi peut avoir plusieurs demandeurs.
- 09-27 · Rd 10 Q6 : chaque demandeur a ses réglages ; la qualité la plus haute gagne ; régler la qualité est un droit.
- 09-27/28 · ruling 19 (tranché par l'auditeur puis le steward, sur texte) : un ajout direct devient une carte une fois terminé et trié, à « arrivé » ; tant qu'il télécharge, il se lit dans l'onglet Torrents de Trackers, jamais invisible.
- 09-29 · Rd Q5 (L24 OPEN 1) = C, sa proposition : la décision d'identification vit sur la carte du média d'acquisition.
- 09-29 · Rd 2 Q1 (L24 OPEN 7) : un seul geste, « Corriger », sur le bloc de décision.
- 09-29 · Rd Q7 (L24 OPEN 3) : pas de compteur global de l'identification ; elle se lit sur chaque carte.
- 09-29 · la récupération d'une saison entière se VOIT (lancée, en cours) et aucun épisode de cette saison ne part en parallèle (règle du moteur, demandée au back-end).
- 09-14 · Rd Q1 : la carte candidate de résolution porte une pastille « Choisir » (44 px), aucune coche avant le choix.
- 09-15 · Rd Q4 : après le choix d'un candidat, l'écran de résolution se ferme ; « Identifié comme … · Annuler ».
- 09-15 · Rd Q2 : le dialogue de suppression multiple garde le repli « et N autres ».
- 09-12 · Rd 4/4 Q3 : les étapes du pipeline se lisent par média, sur la carte.

### Médiathèque et fiche

- 09-29 · Rd 2 Q2 (L24 OPEN 8) : « Corriger » est aussi sur la fiche Médiathèque d'un média rangé.
- 09-29 · Rd 2 Q3 (L24 OPEN 9) : `/media?decision=<id>` ouvre la Médiathèque, l'identifiant ignoré (pas de rétro-compatibilité).
- 09-29 · Rd Q9 (L24 OPEN 5) = B : sur la feuille de parcours, « enrichi » se déplie en sous-étapes (métadonnées, affiches, bande-annonce).
- 09-27 · Rd 8 Q1 : le bloc « cross-seed » de la fiche, réservé à l'administrateur, attend L18.

### Découvrir

- 09-27 · Rd 8 Q20 : Découvrir est une page de la barre du bas, à la quatrième place.
- 09-29 · Rd 3 Q8 : le message de tête dit « n séries et m films à découvrir », à côté des boutons de vue.

### Trackers, ratio, cross-seed, upload

- 09-26 · Rd 4 Q2 (ruling 11) : la place libérée dans la barre va à la gestion des trackers (ratio, cross-seed), pour qui y a droit.
- 09-26 · Rd 4 Q3 (ruling 12) : chaque chose parle là où elle vit, et l'onglet de la barre qui la porte prend un badge.
- 09-26 · Rd 7 Q1 : Trackers entre dans la barre dès L16, avec le ratio seul.
- 09-26 · Rd 7 Q2 : aucun droit déclaré en L16 ; la preuve « caché aux autres comptes » vient avec L18.
- 09-26 · Rd 7 Q3 et 09-27 Rd 9 Q2 : le badge de Trackers compte les trackers sous leur seuil d'alerte (réglé par tracker) et les obligations en infraction.
- 09-27 · Rd 9 Q1 : un identifiant de tracker refusé se dit sur la page Trackers et compte au badge.
- 09-29 · Rd 3 Q6 : un tracker coupé par panne compte pour un au badge.
- 09-27 · Rd 9 Q3, Q4 : la page d'un tracker montre une ligne par torrent en cours, avec ses marques (obligation en cours ou terminée, cross-seed, ratio).
- 09-27 · Rd 9 Q6 : la page Torrents montre tous les torrents, avec un filtre par tracker ; les sous-onglets par tracker sont sur la page Trackers.
- 09-27 · Rd 9 Q7 : retirer un torrent dont les fichiers sont partagés avertit de la fin du cross-seed sur le fichier.
- 09-27 · Rd 9 Q5, Q8 : on coupe le cross-seed d'un tracker depuis le torrent ; couper retire l'entrée de qBittorrent sans ses fichiers.
- 09-27 · Rd 9 Q9 : les « non » de la configuration d'exemple ne sont pas son choix.
- 09-27 · Rd 9 Q10 : « cross-seed » partout (section, marque, interrupteur, bouton « Chercher un cross-seed »).
- 09-27 · Rd 9 Q11 = C : chaque coupure est mémorisée et exclut le titre des passages suivants.
- 09-27 · Rd 10 Q3 : « Libérer » n'est plus un geste à part (on retire le torrent, ou on coupe le cross-seed).
- 09-27 · Rd 10 Q4 : une obligation rompue d'un torrent parti se lit sur l'entrée de son tracker ; dépliable et effaçable.
- 09-27 · Rd 8 Q2 à Q7 et Rd 10 Q5 : interrupteur par tracker aussi sur Trackers ; recherche bornée par torrent ; chaque ligne montre son dernier état ; mots d'état « sans correspondance », « stoppé », « pas encore cherché » ; moteur coupé dit tel.
- 09-27 · Rd 8 Q8 : l'échec d'upload ou de création du torrent sur le tracker se voit sur la ligne.
- 09-27 · Rd 8 Q18 : l'upload sur tracker est un lot à part après L18 (L23).
- 09-27 · Rd 11 Q1 à Q5 (L23) : seulement un torrent actif et complet ; un interrupteur « accepte les uploads » par tracker ; le back-end applique les règles du tracker ; un échec laisse la ligne avec sa raison, comptée au badge ; une troisième valeur de marque d'origine.
- 09-29 · retours sur Trackers : Torrents en premier onglet ; sélecteur de tracker en tête de liste ; légende des couleurs ; la carte torrent au style et aux gestes d'une carte média, nom entier.
- 09-29 · Rd 3 Q1 : volumes reçus et envoyés par défaut ; une barre avec le débit pendant un téléchargement, le débit seul pendant un envoi.
- 09-29 · Rd 3 Q2 : un torrent sans média lié porte l'icône « dossier » ; un toucher ouvre le panneau du bas.
- 09-29 · Rd 3 Q3 : la ligne d'un tracker ouvre un panneau du bas ; l'interrupteur d'activation reste sur la ligne.
- 09-29 · Rd 3 Q5 : la légende est le composant de légende des saisons, réutilisé tel quel.
- 09-29 · Rd 3 Q9 : pas de glissé « cross-seed » avant L17.
- 09-29 · la liste des trackers accueillera d'autres trackers au back-end (v3x.club, draupnirr.xyz, …).

### Système, Maintenance, Réglages

- 09-12 · Q1 = B (L20) : les leviers globaux dans une section « Pipeline » de Système ; l'historique reste à Système.
- 09-26 · Rd 4 Q4 (ruling 13) : Système garde l'état de la machine et les leviers ; Maintenance est une page à part, atteinte depuis Système, aux mêmes droits.
- 09-26 · Rd 5 Q8 = B : le badge de Système compte les faits de maintenance ET les pannes.
- 09-29 · Rd Q6 (L24 OPEN 2) : un disque bientôt plein et une anomalie de l'index comptent au badge du menu.
- 09-29 · Système devient une page d'index comme les réglages d'un téléphone (une ligne par section, avec son badge ; Maintenance en est une ligne) ; le découpage lui revient en OPEN.
- 09-29 · Rd Q4 (C1) : la barre d'enregistrement sur toutes les pages de Réglages ; quitter Réglages ou Trackers avec des changements demande une confirmation à trois choix.
- 09-29 · Système au design système : puce « actif / inactif » en fin de ligne, pas « coupé » ; le tableau des exécutions ne se coupe pas à droite sur mobile.

### Comptes, rôles, droits (L18)

- 09-26 · Rd 4 Q5 (ruling 14) et 09-27 Rd 8 Q9 = B : « Comptes » est une page de premier niveau du menu (groupe configuration, à côté de Réglages), réservée à l'Opérateur par droit d'ACL ; Profil = le compte connecté et ses préférences.
- 09-27 · Rd 8 Q10 : la connexion propose d'abord « Se connecter avec Plex » ; le mot de passe est derrière « Utiliser un mot de passe ».
- 09-27 · Rd 8 Q11 : une page sans droit reste dans le menu, marquée ; ouverte, elle dit ce qu'elle est.
- 09-27 · Rd 8 Q12 : tous les accès sont des droits d'ACL ; « réservé à l'Opérateur » n'est qu'un raccourci.
- 09-27 · Rd 8 Q13 : « Réaffecter… » est un acte du panneau de la carte, au droit d'ACL de réaffecter.
- 09-27 · Rd 8 Q14 : la demande d'un invité est le même geste que pour tous : « Suivre » une série (jusqu'au retrait), « Ajouter » un film (jusqu'à sa confirmation dans Plex) ; les droits font la différence.
- 09-27 · Rd 9 Q12 (ruling 17) : les droits se donnent à des rôles, jamais à un utilisateur ; ruling 20 : un compte a un seul rôle.
- 09-27 · Rd 9 Q14 : pas d'escalade — un compte n'attribue qu'un rôle dont les droits sont inclus dans les siens ; les droits et les rôles livrés sont définis en amont, modifiables par l'interface.
- 09-27 · Rd 9 Q15 (ruling 22) : deux rôles système indélébiles — le rôle par défaut (tout nouveau compte, modifiable) et le rôle Admin (sans droits : un contournement des ACL, ni restreint ni modifiable).
- 09-27 · ruling 22, précision : un rôle qui ne donne aucune page envoie sur une page dédiée.

### Environnements et back-end

- 09-27 · Rd 9 Q17 (ruling 23) : la future « preprod » a ses propres jeux de données et range dans la médiathèque de la prod ; « staging » reste le nom de l'espace du pipeline.
- 09-27 · orientation : reprise des données automatisée par l'API, bases de staging et de suivi ré-imaginables, une vraie staging séparée du back-end de prod.

### Design système et composants

- 09-27 · Rd 8 Q19 : `--color-waiting-text` déclaré dans `theme.css` comme les quatre autres tons.
- 09-29 · un seul composant d'onglets, adaptable, pour toutes les pages à onglets, avec une garde statique ; sa référence est l'existant validé (Acquisition en tête), Trackers s'y conforme (Rd 3 Q7).
- 09-29 · Rd 3 Q4 : le chevron des saisons est la seule flèche de pliage de l'application.

### Documents et carte d'intention

- 09-28 · (b) : à la mort d'Arrivées, la carte d'intention change les lignes qui nomment `features/arrivals`.
- 09-29 · Rd Q11 : les moitiés dues de DOIT-1, 5, 7, 9, 11, NE-DOIT-PAS-1 et 6 ont L24 pour propriétaire.

### La machine et l'outillage

- 09-14 · Rd Q2 : le redémarrage du lundi 05:00 est gardé, avec l'outil de reprise.
- 09-28 · Rd Q1 : un mode rapide du harnais ne lance que les règles nommées.
- 09-29 · Rd Q2 : Spotlight désactivé entièrement sur IznoServer ; Rd Q3 = B : rien à changer au Wi-Fi de tm-design.
- 09-29 · le trousseau de Chrome est purgé sur son ordre (« J'ORDONE QU'ON SUPPRIME MAINTENANT ET IMMEDIATEMENT CES CLEFS !!! », puis « oui », « go ») : suppression directe des 71 443 lignes locales du groupe (sync=0, sans référence), après une sauvegarde `sqlite3 .backup` en 600 dans `~/keychain-backup-20260929/` ; la voie de Chrome (44–80 s par clé) et la réinitialisation du trousseau (mots de passe Apple, iCloud, HomeKit) écartées. Remplace Rd 2 Q4 (« attendre et mesurer »).
