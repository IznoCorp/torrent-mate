# La méthode de l'opérateur — TorrentMate, refonte de l'interface

Deux parties : (1) ses principes, (3) ses décisions par surface. L'opérateur seul amende ses mots.
La méthode de développement est `docs/reference/method.md` ; l'ancien § 2 et le journal daté sont dans git :
`docs/reference/operator-method.md@5a763b90a`.

Heures lues sur l'horloge de la machine, sauf « ~ » (heure estimée par la session qui a reçu le mot).

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
| 09-30 | Ses retours ne sont pas des ajouts : ce sont des corrections de ce qui était attendu (une mauvaise compréhension au départ) ; on vise le gel, et c'est à l'audit de concentrer, réguler et contrôler le temps | « Mes retours ne sont pas des nouvelles choses qu'on ajoute. Mes retours sont des corrections sur ce qui est attendu. […] On définit ce qui est, des, devait être fait. Parce qu'il y a eu sûrement une mauvaise compréhension au départ. […] c'est ton rôle. de concentrer ça, de le gérer, réguler et de le contrôler. » (périmètre du gel = B) |
| 09-29/30 | L'auditeur vérifie (l'orchestrateur, le développement, l'avancée, la vitesse), l'orchestrateur fait ; et l'auditeur doit se rendre inutile : des process rodés, sans audit ; un mot répété renforce l'ordre en place, il ne s'écrit pas deux fois | « Ce qui revient à l'orchestrateur est fait par l'orchestrateur. Tu audites l'orchestrateur. » ; « à terme, euh, j'aimerais que l'auditeur ne soit plus utile » ; « Pas besoin de l'ajouter deux, trois, quatre, cinq fois […] On essaye d'alléger le processus. » |
| 09-29 | Rien de ce qu'il remonte n'est oublié : noté tout de suite, corrigé tout de suite ou plus tard, jamais laissé dans un fichier où personne ne repasse | « Est-ce qu'il y a un garde-fou qui s'assure que tout ce que je remonte […] soit bien noté et corrigé ? […] Il n'est pas oublié, écrit dans un fichier quelconque euh, et oublié parce que personne ne repassera dessus. » |
| 09-29 | Les comportements sont uniformes dans toute l'app, sauf exception qu'il décide | « Il faut uniformiser les comportements. Sauf exception volontaire de ma part. » (toucher l'affiche d'un candidat l'a choisi au lieu d'ouvrir sa fiche « comme pour le reste de l'app ») |
| 09-29 | L'existant validé d'abord, et c'est le nouveau qui s'y conforme | « là où on en as besoin c'est d'abord l'existant ! » ; « c'est tracker qui doit ressembler aux autres systèmes d'onglet, l'existant est ce qui est validé. » |
| 09-02 | Tout nettoyer après soi | « Toujours nettoyer l'espace disque, la ram, les serveurs. TOUT ! » |
| 09-05 | L'orchestrateur lance lui-même les agents | « c'est à toi de lancer les agents, tes skills d'orchestrateur sont faites pour ça ; ne pas le faire est une erreur critique » |
| 09-12 | Pas d'agent tmux | « tmux n'est pas une solution. Plus jamais d'agent tmux. » |
| 09-30 | L'audit allège et contrôle, il n'ajoute pas ; la plus grande part du temps sert au développement | « Qui a demandé un garde plex. Personne ! […] le travaille que je te demande est l'inverse. Alléger les garde et faire avancer le dev. » ; « Assainir par l'allègement la méthode de développement. T'assurer que la p'us grande part du temps sert au développement !!! » |

## 2. Les règles de méthode

Voir `docs/reference/method.md`.

## 3. Les décisions par surface

Une ligne par décision, qui dit ce qui est vrai aujourd'hui. Le texte intégral : l'archive (jusqu'au 2026-09-29) ou le § 8 du rapport
d'audit en cours.

### Organisation générale et navigation

- Une arrivée crée une acquisition PONCTUELLE (film, épisode, saison), jamais un suivi ; suivre reste un acte, sur la fiche.
- Les arrivées deviennent des cartes d'acquisition (un torrent média terminé et trié → carte à l'état « arrivé »).
- Un film arrivé et confirmé dans la médiathèque peut disparaître du suivi (pas une série).
- Une seule échelle d'étapes sur la carte d'acquisition, du souhait à Plex ; « trié · enrichi · rangé » fusionnent en « rangé », huit crans.
- La carte existe sans identité, avec un verbe pour la recaser (ni film ni série).
- Une carte reste à trier ; rangée à la main ailleurs, elle disparaît.
- « À traiter » = ce que seule sa main débloque (à résoudre, match Plex à confirmer, erreur du tunnel…).
- Après une résolution, on revient à la liste ; « n sur m en attente » meurt avec « Suivant ».
- Un ajout direct dans qBittorrent porte le propriétaire du serveur Plex comme demandeur, réaffectable.
- Système sort de la barre du bas ; il s'atteint par le menu de gauche, à son droit, et le bouton du menu porte son badge.
- La barre du bas s'adapte au nombre de boutons présents, chacun à la même part (2 → 50/50, 3 → tiers…).
- § 17 point 4 de la constitution, la place de barre non occupée n'est pas un défaut (phrase amendée).
- Un compte qui n'a qu'une page n'a pas de barre du bas.
- La page d'entrée (Retour, garde de sortie) est la première page de la barre du compte.
- `/arrivals` devient une adresse inconnue (page « introuvable »).
- `/medias`, `/systeme`, `/controle` répondent « introuvable » à la bascule, sans redirection.
- Amendement du § 16 règle 2 (son « oui vas-y ») : les pages du menu latéral empilent et Retour refait le chemin d'arrivée ; les pages de la barre du bas remplacent, Retour → page d'entrée.
- La règle se lit par DESTINATION — une page de la barre du bas (Acquisition, Médiathèque, Trackers, Découvrir) garde la règle de la barre même ouverte depuis le menu latéral (elle remplace, Retour → page d'entrée).
- Un lien DANS une page empile, même vers la page d'entrée (Système › « … laissés derrière → » vers Acquisition) — Retour ramène d'où l'on vient ; la garde de sortie ne s'arme que si la page d'entrée est au fond de la pile.
- Les précisions des deux lignes précédentes (par destination ; un lien interne empile, même vers la page d'entrée) sont écrites au § 16 de `product-intent.md`, à la fin du paragraphe du menu latéral, tel que proposé.
- Son mot (« B, toujours le même chemin mais on repasse pas 2 fois par la même vue. Exemple: si on fait "Acquisition => Système => Acquisition => Réglages => Système" le retour fait "Système => Réglages => Acquisition". Quand on repasse par la même page, elle remonte en haut de la pile elle est pas empilé 2 fois ») : une page revisitée REMONTE en haut du chemin, jamais empilée deux fois ; vaut aussi pour le lien interne vers Acquisition (Système › « … laissés derrière → ») ; quand rien ne reste sous une page, Retour tombe sur la page d'entrée (règle 3), à dessiner par le lot.
- Un écran qui en ouvre un autre (versions → profil de qualité, résolution → identifier à la main) EMPILE ; Retour ramène à l'écran d'où l'on vient.
- Quitter Réglages ou Maintenance par le menu avec une rubrique ouverte rend d'abord la rubrique ; Retour → la racine de la page.
- Le grand écran reste mobile d'abord, avec une phase finale « bureau » au plan.
- « × » veut dire « vu » partout ; la sortie est « Annuler », visible et distincte.
- Son mot (« B, le même menu latéral, épinglé ouvert par défaut, avec possibilité de le "fermé" version réduite (barre verticale avec icones seulement) ») : dès ≈ 1 024 px le même menu latéral est épinglé ouvert, repliable en barre verticale d'icônes (le même composant, une variante), le choix retenu par appareil (localStorage).
- Pas de deux volets ; les écrans restent des routes plein écran, dans la colonne ; § 16 inchangé.
- Un petit jeu de touches déclaré (`/` vers la recherche de la page, ↑/↓ dans une liste, Entrée ouvre, Échap ferme) et un fond au survol des lignes, cartes et vignettes ; aucune action seulement au survol ou seulement au clavier.

### Acquisition

- « À traiter » est un onglet d'Acquisition, avec son compteur.
- Onglets « Suivis · En cours · À traiter » (Découvrir est parti dans la barre).
- L'onglet par défaut est « Suivis », puis le dernier ouvert (mémoire locale).
- « Suivis » ne liste que des suivis ; une carte d'arrivée vit dans « En cours » ou « À traiter », même pour un épisode d'une série suivie.
- « À récupérer » quitte « En cours » ; « Récupérer maintenant » reste sur la fiche du suivi ; « Rangé aujourd'hui » et « Cherché, rien trouvé » quittent « En cours », qui ne garde que « En vol ».
- « Lancer » / « Arrêter » une passe meurent avec la barre d'Arrivées.
- La carte « match Plex à confirmer » propose « Confirmer » et « Corriger » sur le match lui-même ; « Abandonner » une erreur du tunnel met le dossier en quarantaine, après confirmation ; L22 dessine la ligne « ajouté par … » ; le geste de réaffecter naît avec L18.
- La roue du tirer-pour-recharger tourne dès que le geste est armé, un tour minimal visible, disparaît à la fin.
- « Mis de côté » replié en fin d'« À traiter » ; « Supprimer » y est une vraie suppression du dossier, confirmée.
- Les suivis en pause forment une section repliée en fin de « Suivis ».
- Une arrivée ajoutée à la main qui correspond à un élément suivi s'y rattache.
- Prendre une saison d'une série possédée non suivie crée une acquisition ponctuelle, avec « Suivre » sur la carte.
- Voir « À traiter » est un droit ; par défaut un compte ne voit et ne compte que ses cartes.
- Un suivi peut avoir plusieurs demandeurs.
- Chaque demandeur a ses réglages ; la qualité la plus haute gagne ; régler la qualité est un droit.
- Tranché par l'auditeur puis le steward, sur texte : un ajout direct devient une carte une fois terminé et trié, à « arrivé » ; tant qu'il télécharge, il se lit dans l'onglet Torrents de Trackers, jamais invisible.
- Sa proposition : la décision d'identification vit sur la carte du média d'acquisition.
- Un seul geste, « Corriger », sur le bloc de décision.
- Pas de compteur global de l'identification ; elle se lit sur chaque carte.
- La récupération d'une saison entière se VOIT (lancée, en cours) et aucun épisode de cette saison ne part en parallèle (règle du moteur, demandée au back-end).
- La carte candidate de résolution porte un « Choisir » primaire (44 px), aucune coche avant le choix ; ce « Choisir » est le bouton d'action STANDARD du design système en ton primaire — la gélule dessinée à part disparaît.
- Défaut signalé (« j'ai cliqué sur le poster d'un candidat en espérant en savoir plus sur ce candidat et il semble que ça l'a choisi, le comportement attendu était ouverture d'une fiche média pour en savoir plus ») : sur l'écran de résolution, toucher l'affiche ou la carte d'un candidat OUVRE SA FICHE (Retour ramène à l'écran de résolution) ; seul le bouton « Choisir » choisit. Aujourd'hui toute la carte est un seul bouton qui choisit (`resolution-cards.tsx:84`).
- Sur l'écran d'une exécution, les lignes du journal brut reviennent à la ligne dans la largeur de l'écran — plus de défilement de côté, aucune exception au § 12 ni à la règle « responsive ».
- Après le choix d'un candidat, l'écran de résolution se ferme ; « Identifié comme … · Annuler ».
- Le dialogue de suppression multiple garde le repli « et N autres ».
- Les étapes du pipeline se lisent par média, sur la carte.
- Son mot (« Liste à plat avec filtre. J'aime beaucoup le composant filtre des trackers mis sur la liste des torrents, j'aimerai qu'on utilise celui là et qu'on aille plus loin qu'on remplace les autres filtres (médiathèque et suivis: Tout, films, séries) par ce nouveau composant ! ») : « À traiter » est UNE liste à plat, sans sections (et non plus « une section dit ce qui la débloque »), filtrée par le sélecteur à une pilule de l'onglet Torrents (la pilule dit le filtre et son compte, un toucher ouvre le panneau du bas des choix) — un filtre par cause.
- La liste à plat se range par urgence, le plus récent d'abord dans chaque groupe — ce qui demande son jugement (identité, match Plex, erreur d'étape), puis les blocages extérieurs (reprise automatique), puis les clôtures ; aucun titre de section, la ligne de cause de chaque carte le dit ; « Mis de côté » à part, replié, en dernier.
- Sa demande (« oui, enregistre ») : à côté de la pilule de filtre, une pilule de TRI, le même composant (elle dit le tri en vigueur, un toucher ouvre le panneau du bas) ; « À traiter » : Urgence (par défaut, l'ordre ci-dessus), Plus récent, Plus ancien ; retenue comme le filtre.
- Son mot (« je confirme ») : pas de « × » sur une carte de clôture — un toucher sur la carte ouvre son panneau du bas avec ses actions, et « Marquer comme vu » est l'une d'elles.
- « contenu manquant » se partage selon le volume — le volume absent (démonté) est un BLOCAGE (« Différé : le disque où qBittorrent l'a téléchargé n'est pas lisible. », « Voir les disques », reprise au remontage) ; le volume présent et les fichiers partis est la clôture d'un tunnel dont le média a disparu (Environnements et back-end). Demande back-end BK3 : le moteur distingue les deux.
- Un cran arrêté par une cause extérieure prend le ton « en attente » (comme le différé aujourd'hui) ; le rouge de danger reste ce qui demande son jugement.
- La reprise automatique se dit par le message existant, seulement quand il est sur « À traiter » : « <titre> est reparti », un message par levée (« 6 acquisitions sont reparties »).
- Le pied de carte d'un blocage extérieur porte sa porte seule (« Voir les disques », « Voir le tracker ») ; « Abandonner » reste dans le panneau de la carte.

### Médiathèque et fiche

- « Corriger » est aussi sur la fiche Médiathèque d'un média rangé.
- `/media?decision=<id>` ouvre la Médiathèque, l'identifiant ignoré (pas de rétro-compatibilité).
- Sur la feuille de parcours, « enrichi » se déplie en sous-étapes (métadonnées, affiches, bande-annonce).
- Le bloc « cross-seed » de la fiche, réservé à l'administrateur, attend L18 ; chaque panneau et chaque fiche a sa variante FILM (« Il doit y avoir une personnalisation une différence entre film et série ») — aucun bloc saisons/épisodes pour un film (défaut : le panneau de « On l'appelait Robin des Bois », un film, disait « Série » et « Aucune donnée de saison »).
- Les filtres par catégorie (Tout, Films, Séries…) s'affichent aussi sur « Récents » (« Mediathèque sur l'onglet recents, on peut aussi mettre les filtres Tout/Films/séries. ») et sur « Incomplets » — même barre, même composant, même mémoire du choix que « Médias ».
- Son mot : le composant de filtre des trackers REMPLACE les filtres de la Médiathèque et de Suivis (Tout, Films, Séries) ; chacun reçoit aussi la pilule de tri, le même composant. Médiathèque : ses six tris existants.
- La pilule de tri de Suivis offre « Urgence » (l'ordre d'aujourd'hui, par défaut), « A → Z », « Z → A », « Suivi récemment » (date d'ajout du suivi), « Prochaine sortie » (date de la prochaine sortie) ; si le contrat ne sert pas ces deux dates, la maquette les porte et la demande va au back-end.
- B-475 : une saison qui tient des numéros d'épisode que le catalogue ne liste pas montre une ligne « hors catalogue (n) » sous la saison, sans jugement ; la fraction reste au plus ce qui est diffusé (B-380). Un geste de correction (une file « à vérifier » de Maintenance) pourra venir plus tard.
- Identité : « On corrige en amont aucune entrée/ aucun média de la médiathèque ne devrait existé sans au moins 1 identifiant. Si c'est le cas, on répertorie et on répare » — chaque média porte au moins un identifiant fournisseur ; la suppression se fait par identifiant fournisseur, jamais par titre ; un identifiant porté par deux lignes est refusé tant que le doublon n'est pas réglé.

### Découvrir

- Découvrir est une page de la barre du bas, à la quatrième place.
- Le message de tête dit « n séries et m films à découvrir », à côté des boutons de vue.
- Son mot (« Glissé à droite et à gauche à le même comportement que glissé une carte du mode deck de decouvrir, rejet, ou passé […] la carte disparait, notification pour annulé si rejet […] c'est un nouveau comportement propre à découvrir qu'on pourra réutiliser dans un autre cas », puis « vers gauche = passer / vers la droite = rejet ») : en liste ET en deck, glisser à GAUCHE = passer (disparaît sans notification, peut revenir plus tard), à DROITE = rejeter (disparaît, notification avec « Annuler ») ; un geste propre à Découvrir, déclaré au design système pour être réutilisé. Aujourd'hui les deux sens du deck font la même chose (« écarté »).
- Son mot (« A, elle repasse tout en bas de la pile. ») : « passer » renvoie la suggestion au bas de l'ordre unique que lisent la liste et le deck ; rien n'est envoyé au moteur.

### Trackers, ratio, cross-seed, upload

- La place libérée dans la barre va à la gestion des trackers (ratio, cross-seed), pour qui y a droit.
- Chaque chose parle là où elle vit, et l'onglet de la barre qui la porte prend un badge.
- Trackers entre dans la barre dès L16, avec le ratio seul.
- Aucun droit déclaré en L16 ; la preuve « caché aux autres comptes » vient avec L18.
- Le badge de Trackers compte les trackers sous leur seuil d'alerte (réglé par tracker) et les obligations en infraction.
- Un identifiant de tracker refusé se dit sur la page Trackers et compte au badge.
- Un tracker coupé par panne compte pour un au badge.
- La page d'un tracker montre une ligne par torrent en cours, avec ses marques (obligation en cours ou terminée, cross-seed, ratio).
- La page Torrents montre tous les torrents, avec un filtre par tracker ; les sous-onglets par tracker sont sur la page Trackers.
- Retirer un torrent dont les fichiers sont partagés avertit de la fin du cross-seed sur le fichier.
- On coupe le cross-seed d'un tracker depuis le torrent ; couper retire l'entrée de qBittorrent sans ses fichiers.
- Les « non » de la configuration d'exemple ne sont pas son choix.
- « cross-seed » partout (section, marque, interrupteur, bouton « Chercher un cross-seed »).
- Chaque coupure est mémorisée et exclut le titre des passages suivants.
- « Libérer » n'est plus un geste à part (on retire le torrent, ou on coupe le cross-seed).
- Une obligation rompue d'un torrent parti se lit sur l'entrée de son tracker ; dépliable et effaçable.
- Interrupteur par tracker aussi sur Trackers ; recherche bornée par torrent ; chaque ligne montre son dernier état ; mots d'état « sans correspondance », « stoppé », « pas encore cherché » ; moteur coupé dit tel.
- L'échec d'upload ou de création du torrent sur le tracker se voit sur la ligne.
- L'upload sur tracker est un lot à part après L18 (L23).
- L23 : seulement un torrent actif et complet ; un interrupteur « accepte les uploads » par tracker ; le back-end applique les règles du tracker ; un échec laisse la ligne avec sa raison, comptée au badge ; une troisième valeur de marque d'origine.
- Retours sur Trackers : Torrents en premier onglet ; sélecteur de tracker en tête de liste ; légende des couleurs ; la carte torrent au style et aux gestes d'une carte média, nom entier.
- Volumes reçus et envoyés par défaut ; une barre avec le débit pendant un téléchargement, le débit seul pendant un envoi.
- Un torrent sans média lié porte l'icône « dossier » ; un toucher ouvre le panneau du bas.
- La ligne d'un tracker ouvre un panneau du bas ; l'interrupteur d'activation reste sur la ligne.
- La légende est le composant de légende des saisons, réutilisé tel quel.
- Pas de glissé « cross-seed » avant L17.
- La liste des trackers accueillera d'autres trackers au back-end (v3x.club, draupnirr.xyz, …).
- Il cherche lui-même, connecté, une API de statistiques par site ; sans API, le ratio du tracker s'affiche INCONNU — jamais un chiffre calculé localement, jamais une page lue en scraping sauf s'il l'ordonne pour un tracker nommé.
- Il lance lui-même `scripts/capture-tracker-sample.py` ; aucune clé n'entre dans le contexte d'un agent.
- La configuration d'exemple livre v3x.club, draupnirr.xyz et digitalcore.club EN DERNIER dans `priority`, leur bloc `economy` en commentaire.
- Tout compte qui porte `trackers.view` reçoit l'alerte de ratio.

### Système, Maintenance, Réglages

- L20 : les leviers globaux dans une section « Pipeline » de Système ; l'historique reste à Système.
- Système garde l'état de la machine et les leviers ; Maintenance est une page à part, atteinte depuis Système, aux mêmes droits.
- Le badge de Système compte les faits de maintenance ET les pannes.
- Un disque bientôt plein et une anomalie de l'index comptent au badge du menu.
- Système devient une page d'index comme les réglages d'un téléphone (une ligne par section, avec son badge ; Maintenance en est une ligne) ; le découpage lui revient en OPEN.
- La barre d'enregistrement sur toutes les pages de Réglages ; quitter Réglages ou Trackers avec des changements demande une confirmation à trois choix.
- Système au design système : puce « actif / inactif » en fin de ligne, pas « coupé » ; le tableau des exécutions ne se coupe pas à droite sur mobile.
- L'interrupteur qui laisse chaque téléchargement terminé démarrer seul son traitement (ex-« Déclenchement automatique ») est gardé, RENOMMÉ par ce qu'il fait, sur une seule ligne du bloc des leviers (puce « actif / inactif » en fin de ligne, avec son bouton) ; la ligne des verrous disparaît ; « actif / inactif » pour les sept mécanismes marche/arrêt, « en pause » gardé pour le pipeline en pause.
- Les mots d'état de Système (« en ligne », « joignable », « à l'heure », « bientôt plein »…) quittent les données simulées — les données portent un CODE d'état, l'application prend le mot dans son dictionnaire (un mot par état, vu par la garde du vocabulaire) ; le moteur enverra des codes (demande au back-end).
- Un seul composant d'AVIS, adapté du panneau d'erreur, à trois tons — danger (l'erreur d'aujourd'hui, seule annoncée comme alerte), avertissement, information ; « TMDB déconnecté », « à identifier », lecture seule, redémarrage requis y passent.
- Le sélecteur segmenté n'a qu'une déclaration — le commutateur de vue du design système gagne une taille « texte », la version d'Acquisition (écran d'ajout, menu latéral) y est rebranchée et disparaît.
- La ligne d'une saison dont la récupération entière est lancée dit « Demandée » (fiche de la série et fiche du suivi), suivie ou non, jusqu'à l'arrivée en médiathèque ; l'avancement se lit sur la carte de la saison dans « En cours » ; une marque à la fois sur la ligne de la saison — « En file — pipeline en cours » tant que la demande attend, puis « Demandée ».
- Pendant la récupération d'une saison entière, la carte d'acquisition d'un épisode seul de cette saison (dans « En cours ») est ABSORBÉE — elle disparaît, la carte de la saison la couvre, son parcours renvoie à la saison ; le moteur refuse de lancer l'épisode à part (demande au back-end).
- Un PARCOURS par acquisition (la saison S03, l'épisode S03E07), plus par titre ; « Voir le parcours » ouvre la récupération en cours, sinon la plus récente (demande SR4) ; le renvoi d'un épisode absorbé mène à l'onglet d'Acquisition qui porte la carte de la saison, carte visible et mise en évidence.
- Le parcours de la saison liste chaque épisode absorbé avec son état (« S03E07 — téléchargement déjà en cours »), chacun menant à son parcours (demande SR2 : le sort d'un épisode déjà attrapé) ; le moteur sert le lien « absorbée par » (absorbedBy, saison, épisode) sur la carte ; l'interface le lit, elle ne compare aucun libellé (demande SR1).
- Son mot (« Il faut une distinction auto/manuelle même légère juste pour pas que je me demande qui à demandé la saison entière alors que c'était un process auto ») : une récupération lancée par le moteur s'affiche comme une manuelle, AVEC une distinction légère et visible sur la ligne ET sur la carte, prise dans un composant existant.
- La carte porte « auto » dans son sous-titre (« S03 · auto ») — un mot, pas une seconde puce.
- « joignable » est le seul mot de l'état « ça répond » dans Système.
- Son mot (« B, "en pause" ») : la ligne « Pause » de Système dit « en pause » quand la pause est enclenchée, « inactif » sinon — plus « actif » ; ton avertissement quand elle est enclenchée.
- Son mot (« orange si c'est en pause, rouge si c'est un problème technique ») : le « Traitement automatique des téléchargements » coupé par une personne est en ton avertissement (orange), coupé par une panne technique en ton danger (rouge) ; chaque cas est un état nommé de la maquette.

### Comptes, rôles, droits (L18)

- « Comptes » est une page de premier niveau du menu (groupe configuration, à côté de Réglages), réservée à l'Opérateur par droit d'ACL ; Profil = le compte connecté et ses préférences.
- La connexion propose d'abord « Se connecter avec Plex » ; le mot de passe est derrière « Utiliser un mot de passe », pour les comptes qui n'ont pas de Plex.
- Une page sans droit reste dans le menu, marquée ; ouverte, elle dit ce qu'elle est.
- Tous les accès sont des droits d'ACL ; « réservé à l'Opérateur » n'est qu'un raccourci.
- « Réaffecter… » est un acte du panneau de la carte, au droit d'ACL de réaffecter.
- La demande d'un invité est le même geste que pour tous : « Suivre » une série (jusqu'au retrait), « Ajouter » un film (jusqu'à sa confirmation dans Plex) ; les droits font la différence.
- Les droits se donnent à des rôles, jamais à un utilisateur ; un compte a un seul rôle.
- Pas d'escalade — un compte n'attribue qu'un rôle dont les droits sont inclus dans les siens ; les droits et les rôles livrés sont définis en amont, modifiables par l'interface.
- Cinq rôles livrés — Admin, Membre du foyer, Invité Plex, Demandeur, Invité ; Admin est le seul rôle système, indélébile (sans droits : un contournement des ACL, ni restreint ni modifiable), il n'y a plus de « rôle par défaut » ; un compte local démarre sur Invité, sauf si son rôle est choisi à la création ; un compte Plex démarre sur Membre du foyer (Plex Home) ou Invité Plex ; un rôle qui ne donne aucune page envoie sur une page dédiée.
- Son mot (« A surtout pas B ! ») : seuls le propriétaire du serveur Plex et les comptes avec qui il est partagé se connectent par Plex ; tout autre compte plex.tv est refusé par LE refus unique, indistinguable, que reçoit tout échec de connexion (jamais un 403 distinct : on ne doit pas pouvoir deviner quels e-mails correspondent au serveur).
- Le PIN tourne sur le serveur — `startPlexSignIn` → `{pinId, signInUrl}`, puis `signInWithPlex {pinId}` ; le jeton Plex ne quitte jamais le serveur.
- Le jeton Plex de l'utilisateur est GARDÉ, chiffré, pour une fonction future (lecture de la watchlist, partage Plex) ; K1 porte son stockage chiffré (clé, rotation, révocation), la brique reste sans état.
- Rien à construire pour les profils gérés de Plex Home ; celui qui doit entrer reçoit un compte local, avec le mot de passe provisoire que l'Admin pose dans Comptes.
- Son mot (« A l'ouverture (installation ?) de la PWA », puis « proposition à l'ouverture et aussi via profil ») : LES DEUX — une proposition « Activer les notifications sur cet appareil » à l'ouverture de la PWA installée (le toucher est le geste qu'iOS exige) ET la ligne par appareil de Profil avec ses quatre états ; dessinées d'abord dans la maquette.
- Connexion par genre de compte : tout identifiant est un e-mail ; une identité Plex qui a accès au serveur géré se connecte par le SSO Plex seulement (le propriétaire excepté : SSO, plus un mot de passe de secours posé par une commande CLI sur le serveur, jamais dans l'interface) ; sans accès, elle est refusée, « comme si le compte n'existait pas » ; un compte local dont l'e-mail n'est pas un utilisateur du serveur se connecte par mot de passe seulement, jamais rattaché, même si plex.tv connaît l'e-mail. La porte du mot de passe est le genre du compte (propriétaire | Plex | local), jamais un droit.
- Mots de passe : l'utilisateur d'un compte à mot de passe change le sien dans Profil ; l'Admin pose le mot de passe provisoire à la création d'un compte local, et SEUL l'Admin réinitialise le mot de passe d'un compte à mot de passe, dans « Comptes » (un gestionnaire non Admin ne le fait jamais).
- Rattachement : quand l'e-mail d'un compte local devient utilisateur du serveur Plex, le compte est rattaché, le SSO devient obligatoire et son rôle retombe au rôle de départ de son genre Plex (Membre du foyer ou Invité Plex) jusqu'à ce qu'un Admin le promeuve : aucun lien par e-mail ne porte jamais de droits d'Admin.
- Notifications : les interrupteurs par type sont PAR COMPTE (« tout le monde à le droit de changer les notifications de son propre compte, ça n'a pas de sens de mettre ça sous un droit ») — section « Notifications » de Profil, sans droit d'ACL.
- La langue de l'interface (français ou anglais) est un réglage du compte, choisi dans le Profil, le même sur tous les appareils.
- Une notification push est rédigée dans la langue du compte qui la reçoit.

### Environnements et back-end

- La future « preprod » a ses propres jeux de données et range dans la médiathèque de la prod ; « staging » reste le nom de l'espace du pipeline.
- Orientation : reprise des données automatisée par l'API, bases de staging et de suivi ré-imaginables, une vraie staging séparée du back-end de prod.
- Parole de l'opérateur : `/api` d'aujourd'hui est la v0, le nouveau back-end est `/api/v1` (les versions futures sans rupture) ; une route v0 est DÉPRÉCIÉE dès que sa v1 fonctionne (en-tête `Deprecation` + un registre = la liste de nettoyage une fois la v1 déployée et validée) ; git flow `feature → develop → main` : develop déployé automatiquement sur tm-design, main = tout ce qui est validé, `staging` déployé VOLONTAIREMENT, seulement quand la user story est prête au complet (« on déploie en staging que quand la user story est prête au complet »), `prod` (branche portant les tags de version, déployée automatiquement) déployée VOLONTAIREMENT après validation fonctionnelle sur staging.
- Précision (« l'env staging est bien la préprod ! ») : `staging` EST la préprod de la première ligne de cette section, avec ses propres données ; elle range dans la médiathèque de la prod. Remplace le « staging reste le nom de l'espace du pipeline » de cette même ligne, pour le nom de l'environnement.
- Trois bases par propriétaire (`library` = l'index seul, `acquire`, une nouvelle `app`), UN FICHIER PAR ENVIRONNEMENT par suffixe (`acquire-dev.db`, `acquire-staging.db`, `acquire.db`, `app-dev.db`, `app-staging.db`, `app.db`) — « Des fichiers bien séparé plus facile à gérer et à maintenir » ; pour l'index, UN SEUL `library.db` écrit par la prod seule, en lecture seule pour dev et staging (« B' tu as raison, la staging range en prod »), les disques sont scannés une fois.
- La reprise porte son intention et ses dettes (suivis attribués à Izno avec leurs profils de qualité, lignes voulues ouvertes et abandonnées avec leurs releases essayées, obligations de seed et états de ratio, historique cross-seed, journal destructif) ; l'index est RECONSTRUIT par un scan complet ; historique des exécutions, décisions réglées et parcours passés repartent vides.
- La staging/préprod fait tourner tout le moteur sur ses données (vrais grabs dans sa propre catégorie qBittorrent, son pipeline, rangement dans la médiathèque de la prod, suppression refusée, cross-seed et upload coupés par son overlay) ; l'instance :8711 en lecture seule est retirée, la préprod prend son port et son hôte.
- Un SUPERVISEUR (le démon watcher) détient l'autorité de déclenchement — jusqu'à `max_parallel` tunnels en travailleurs, les autres en file visible, des verrous internes seulement là où il faut du série (dispatch sur un disque, écriture de l'index) ; le web et la CLI mettent en file, ne lancent jamais ; `pipeline.lock` est remplacé par le bail du superviseur.
- Un tunnel par RELEASE (un torrent : celui d'un épisode ou un pack de saison).
- Parole de l'opérateur après discussion (« oui c'est ça ») : UNE liste « À traiter » porte TOUT ce qui est bloqué et demande une intervention, dans l'app ou ailleurs (disque plein, ratio trop bas, tracker injoignable — « qui fait de la place sur le disque ? » — comme identité, correspondance Plex, erreur) ; chaque carte dit sa cause, ce qui la lève et où elle se règle (Système › Disques, « Voir le tracker », ses réglages) ; le pipeline REPREND DE LUI-MÊME dès que le moteur voit la cause levée, et la carte part ; le badge d'Acquisition compte toute la liste. AMENDE la ligne « À traiter » = ce que seule sa main débloque (Organisation générale et navigation) et déplace la carte différée d'« En cours » vers « À traiter » (un changement de maquette à dessiner).
- Un tunnel dont le média a disparu (torrent retiré, fichiers absents) se ferme avec sa raison ; la carte le dit une fois dans « À traiter », écartée par « × » (= vu) ; rangé à la main ailleurs, il part simplement ; un média qui revient plus tard ouvre un nouveau tunnel.
- Sa règle après discussion (« oui, enregistre ») : rien n'est annulé ni filtré, chaque tunnel va à son terme (un épisode pris AVANT la demande de saison n'est pas couvert par « aucun téléchargement … se lance en parallèle » (la ligne sur la récupération d'une saison entière), qui n'interdit que les lancements APRÈS la demande ; cette règle tient) ; au rangement, le DERNIER CHOISI gagne — la date d'ajout/de grab de la release décide, pas son heure d'arrivée — pour TOUS les médias, films compris ; un fichier sans date de choix connue (rangé avant la bascule) compte comme plus ancien que tout ; une release choisie plus tôt qui arrive après n'est PAS rangée, son torrent continue de semer, son tunnel se ferme avec la raison « remplacé par un choix plus récent », dite une fois dans « À traiter », écartée par « × ». Son pourquoi : le pack apporte le plus souvent une version meilleure ou corrigée (codec, corruption, sous-titre ou audio manquant) et une qualité cohérente sur la saison. Exigence back-end : le moteur doit connaître, au rangement, la date de choix de la release qui a rangé le fichier en place.
- Parole de l'opérateur : FCM est le canal de l'alerte de ratio (« Telegram est pollué et je veux m'en débarrasser » — Telegram refusé, son souhait de s'en défaire noté, sa suppression NON ordonnée) ; pas pressé, mais le projet FCM peut être préparé dès maintenant : notifications et web push sur la PWA installée, Android et iOS ; seuil d'alerte par défaut à un ratio de 1,2, réglable tracker par tracker.
- Son mot (« A et des scripts à lancer au besoin que l'orchestrateur ou tout autre agent peut également appelé. ») : il dit « passe en staging », « mets en prod » à l'orchestrateur ; la promotion et chaque étape du flow lancée à la main sont des scripts de `scripts/` que n'importe quelle session appelle, l'orchestrateur ou tout autre agent, leur invocation écrite dans `method.md`.
- Le tag de version de `prod` est `v` + le `__version__` du commit promu.
- Son mot (« A, pour l'instant les "mise en prod" ne touche pas la prod (tm.iznogoudatall.xyz) donc on peut y aller, quand on fera la bascule à ce moment on attendra mon mot pour les mises en prod et staging, mais à ce moment tm design ne sera plus servi par main et pourra continué d'évolué en toute autonomie ») : jusqu'à la bascule du git flow, le flux d'aujourd'hui continue ; à partir d'elle, `staging` et `prod` avancent sur son mot seulement, et tm-design suit `develop` (plus `main`) et évolue en autonomie.
- La branche `staging` d'aujourd'hui est archivée sous le tag `archive/staging-2026-08-14`, puis déplacée à la bascule.
- Un hotfix va droit en prod (PR dans `prod`, CI sur sa PR), puis est reporté dans `develop`.
- Un seul projet Firebase pour dev, staging et prod.
- Sa question (« On refait tout ? On repart de l'existant ? Un juste milieu ? »), sa réponse (« Aller go pour D ! ») : une nouvelle couche applicative (son `app.db`) et une HTTP v1 écrite depuis `openapi.json`, sur le moteur GARDÉ (étendu, jamais réécrit) ; la CLI et le web en deviennent deux clients ; la v0 est gelée puis supprimée d'un bloc à la bascule. La reprise des données appelle les services de la couche applicative, sans routes d'import ni copie de table à table. Sa séparation préprod/prod : la préprod ne partage RIEN avec la prod sinon peut-être le client torrent — ses bases, sa config, son staging, ses « disques de préprod » (points de montage dédiés sur les disques NTFS), hors des bibliothèques Plex de la prod, FCM sur un canal à elle ; une purge quotidienne à 02:00 de ses téléchargements, seulement leurs obligations de seed remplies ; une garde par point de montage confine chacune de ses écritures et purges ; le client : « Ok, B sinon A » — un second qBittorrent dédié si CHAQUE tracker actif accepte deux clients sur un compte et une IP (à vérifier avant de construire), sinon un seul, la préprod dans sa catégorie et son chemin, ses torrents marqués `seed-pure`. REMPLACE « elle range dans la médiathèque de la prod » (la première ligne de cette section et sa précision), le `library.db` unique partagé (la ligne des trois bases) et le rangement en prod de la ligne sur le moteur de la préprod. Le superviseur SEUL d'abord (K4a, après K2 et avant K3), prouvé sur la préprod puis la prod. Un média s'identifie par son id fournisseur partout (TVDB d'abord pour les séries), le titre n'est qu'un repli de recherche. Le jeton Plex gardé est chiffré dans `app.db`, une base par environnement. Noté pour plus tard : une analyse de la charge d'E/S disque (prod et préprod).

### Design système et composants

- `--color-waiting-text` déclaré dans `theme.css` comme les quatre autres tons.
- Un seul composant d'onglets, adaptable, pour toutes les pages à onglets, avec une garde statique ; sa référence est l'existant validé (Acquisition en tête), Trackers s'y conforme.
- Le chevron des saisons est la seule flèche de pliage de l'application.
- Défauts signalés (« Sur iphone on voit pas l'icone "hamburger" qui ouvre le menu sidebar ni en clair ni en dark mode. De plus sur tout les téléphones, le menu dans la sidebar "Apparence" Système/clair/sombre ne change plus d'état de manière réactive, le theme change mais pas le selecteur. ») : le hamburger est visible sur iPhone (WebKit) en clair et en sombre ; le sélecteur « Apparence » montre l'état choisi dès le toucher.
- Un ton « à venir » est ajouté au point coloré et à la puce du design système, avec la couleur existante (`--color-upcoming`) ; les endroits qui le dessinaient à part y sont rebranchés.
- Sur bureau une colonne de lecture ≈ 760 px (dialogues ≈ 480 px) ; les galeries et le deck en pleine largeur.
- Sa précision (« latérale droit du coup le panneau sur desktop (pas gauche côté menu) ») : sur bureau le panneau s'ouvre en feuille latérale à DROITE, à l'opposé du menu, ≈ 440 px, pleine hauteur ; on la ferme en la tirant à l'horizontale ; Échap et le voile inchangés.
- Les colonnes d'une galerie suivent la largeur de la vignette (7 vers 1 100 px, 8 vers 1 300) ; la carte du deck garde une affiche 2:3, centrée.
- Le « + » et la barre de sélection sont bornés à la colonne.
- « sur ordinateur, un clic droit sur un élément qui a un panneau (carte, affiche, tuile) ouvre ce panneau, le même que l'appui long (qui reste) ; le menu natif reste refusé là, les champs de texte gardent le leur ».

### Documents et carte d'intention

- À la mort d'Arrivées, la carte d'intention change les lignes qui nomment `features/arrivals`.
- Les moitiés dues de DOIT-1, 5, 7, 9, 11, NE-DOIT-PAS-1 et 6 ont L24 pour propriétaire.

### La machine et l'outillage

- Le redémarrage du lundi 05:00 est gardé, avec l'outil de reprise.
- Un mode rapide du harnais ne lance que les règles nommées.
- Spotlight désactivé entièrement sur IznoServer ; rien à changer au Wi-Fi de tm-design.
- Le trousseau de Chrome est purgé sur son ordre (« J'ORDONE QU'ON SUPPRIME MAINTENANT ET IMMEDIATEMENT CES CLEFS !!! », puis « oui », « go ») : suppression directe des 71 443 lignes locales du groupe (sync=0, sans référence), après une sauvegarde `sqlite3 .backup` en 600 dans `~/keychain-backup-20260929/` ; la voie de Chrome (44–80 s par clé) et la réinitialisation du trousseau (mots de passe Apple, iCloud, HomeKit) écartées. Remplace « attendre et mesurer ».
