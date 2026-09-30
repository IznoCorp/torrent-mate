# Rulings coherence round — 2026-09-27 (auditor, workflow wf_ac59a104-6e8, read-only)

## Résumé

Les douze incohérences vérifiées entre tes décisions se répartissent en neuf conséquences mécaniques et sept questions. Les neuf conséquences se déduisent de décisions déjà prises et sont à consigner sans choix de ta part : cinq constats entiers, plus une part de quatre autres. Deux questions pressent, parce que L22b construit en ce moment la carte d'arrivée et son « Suivre » : l'épisode ajouté à la main qu'un suivi attend déjà, et la saison prise dans l'application qui commence un suivi. Viennent ensuite deux questions pour L16 (le sens de « Libérer », l'obligation rompue qu'aucune ligne ne montre), une pour L17 (le mot d'un torrent pas encore cherché) et deux pour L18 (plusieurs demandeurs sur un même tunnel, la page d'entrée d'un compte sans Acquisition). Côté constitution, l'amendement prévu du § 17 s'élargit au minimum de la barre, et selon tes réponses le § 16.2, le § 18 et la liste des mots d'état du § 19 prennent chacun une phrase.

## Conséquences mécaniques (à consigner, aucun choix de l'opérateur)

### M1 — « Abandonner » sur la carte d'un suivi : écarter cette release et en chercher une autre

Ta décision du 26/09 (« le dossier part en quarantaine ; la carte quitte « À traiter » ») ne disait pas ce que devient l'élément voulu quand la carte appartient à un suivi. Or ce suivi continue : ta décision du 15/09 dit « le suivi d'une série ne se termine jamais seul ». La constitution tranche : « récupéré ? non → changement de release » (§ 14.1), et « récupéré » n'est pas un état de repos (§ 14.3). Marquer l'élément « abandonné » ferait une anomalie pour sa garde (la forme House of the Dragon). À consigner dans la demande au back-end sur la quarantaine :
- sur la carte d'un suivi, la release rejoint la liste des releases déjà essayées pour cet élément (le moteur a déjà cette liste), et l'élément revient à « cherché » ;
- sur une carte d'arrivée ponctuelle, la carte se ferme ;
- la confirmation dit la suite (« une autre release sera cherchée »).
Lot : L22b.

### M2 — « Supprimer » un mis de côté : la confirmation lit qBittorrent au moment du geste

Ton choix du 27/09 tient tel quel : une vraie suppression, dont la confirmation dit « le torrent garde ses fichiers dans qBittorrent » ou « c'est le seul exemplaire ». Seule change la source de cette phrase. La ligne d'ingest fige l'état du jour de l'arrivée, et le torrent a pu quitter qBittorrent depuis : par « Retirer de qBittorrent », ou à la main, ce que le § 18 appelle un « cas géré ». La phrase mentirait alors juste avant une suppression définitive. Trois textes s'y opposent : le § 13 (« aucun état affiché n'est une constante »), l'interdit de mentir, et ta phrase « l'interface reflète toujours ce qui est actif dans qBittorrent ». Conséquence : la ligne d'ingest ne donne que la provenance, et l'opération neuve déjà demandée au back-end lit qBittorrent au moment de la confirmation :
- arrivée copiée, torrent présent avec ses fichiers : « garde ses fichiers » ;
- torrent absent, ou arrivée déplacée : « seul exemplaire » ;
- qBittorrent muet : « inconnu », et le dossier est traité comme le seul exemplaire.
Lot : L22b (phase 15b).

### M3 — Le badge du bouton du menu compte selon les droits (côté droits à L18)

Ta règle du 26/09 (« les droits filtrent les badges avec la barre, sans règle de plus ») filtrait par la barre. Mais Système a quitté la barre pour le menu, et tout compte a le menu. Deux règles donnent la suite : la tienne du 27/09 (« un compte n'y voit, et son badge ne compte, que SES cartes ») et le § 17 (« c'est l'offre qui doit disparaître »). Chaque terme du badge ne compte donc que pour un compte dont le rôle ouvre la page où il mène :
- les pannes de la machine, sous le droit Système ;
- les faits de maintenance, sous le droit Maintenance ;
- l'Admin voit tout ;
- un compte sans page n'a pas de menu.
Un compte privé de ces droits garde son explication : une carte bloquée dit déjà sa raison dans « En cours » (ta décision du 15/09). L22b construit ce badge sans droits, puisqu'aucun droit n'existe avant L18, et l'écrit noir sur blanc. L18 écrit ensuite le côté droits et le vérifie par mutation.

### M4 — Retirer ou couper une obligation en cours : elle se clôt « libérée », toujours après confirmation

Le § 18 définit libérer comme « arrêter de semer avant l'échéance, en connaissance de cause », et fait du retrait un « cas géré ». D'où :
- un « Retirer de qBittorrent » ou un « couper le cross-seed » fait dans l'application et confirmé clôt l'obligation comme libérée, jamais comme infraction ;
- un retrait fait à la main dans qBittorrent se lit « Libérée — retrait externe », comme le prévoit déjà le dessin de L16 ;
- ta règle « confirmation dès que des fichiers sont supprimés » est un minimum : tout geste qui arrête une obligation en cours demande une confirmation qui nomme chaque tracker concerné, même avec « supprimer les fichiers » décoché. C'est l'interdit de détruire sans consentement, et « couper » confirme déjà ;
- l'option « couper aussi les cross-seeds en cours » est déjà sur la confirmation de l'interrupteur ;
- « Ne plus partager ce titre » ne coupe que les partages croisés : le torrent d'origine continue de semer, et le libellé ou la confirmation doit le dire.
Lots : L16, et L17 pour les coupures.

### M5 — Badge de Trackers : un échec est un état, et un tracker injoignable se lit sur Trackers

Ta décision du 27/09 (« chaque ligne montre son dernier état ») et les états du § 19 font d'un échec de cross-seed un état. Il sort donc du badge quand sa ligne cesse d'être en erreur, par une relance réussie ou par une coupure qui la passe à « stoppé », sans fil ni geste de plus. Un tracker injoignable se lit sur Trackers : tu as refusé d'en faire « une dépendance de Système ». La « dépendance tombée » de Système reste qBittorrent et Plex. Pour l'unité du badge, le dessin fixe qu'un tracker refusé absorbe ses propres échecs : un identifiant périmé compte 1, pas 1 plus le nombre de torrents touchés. C'est ta règle « chaque chose parle là où elle vit », puisque la cause est le refus. Lots : L16 (le badge) et L17 (les échecs).

### M6 — L'interrupteur général ne coupe rien de ce qui tourne ; « En file » n'est pas un mot de case

Ta décision du 27/09 nomme les seules façons de devenir « stoppé » : les deux gestes de coupure et le retrait du torrent. L'interrupteur général n'en fait pas partie, d'où :
- les cross-seeds en cours restent dans qBittorrent, et leurs cases disent « actif » ;
- seules la ligne du tracker et la section disent « le moteur est coupé » ;
- moteur coupé et identifiant refusé sont deux faits distincts (la cause côté cross-seed, et la santé du tracker), donc l'en-tête dit les deux ;
- « En file » est l'état d'une recherche demandée pour un torrent, pas un mot de case.
Lot : L17.

### M7 — La règle contre l'escalade vérifie aussi le compte qu'on modifie

Ta règle du 27/09 (« un compte ne crée, ne règle ni n'attribue qu'un rôle dont les droits sont inclus dans ceux de son propre rôle ») ne regarde que le rôle donné. Un gestionnaire non-Admin pourrait donc donner le rôle par défaut à un second Admin et le rétrograder, contre ta phrase « l'admin ne peut être ni restreint ». Clause à ajouter, sur le même principe d'inclusion : un gestionnaire ne change le rôle que d'un compte dont le rôle actuel est inclus dans le sien, et un non-Admin ne touche jamais un compte Admin. La mesure « A si une phase au plus, sinon B » se prend avec cette clause, qui coûte une clause et une mutation. Lot : L18.

### M8 — L'amendement prévu du § 17 doit aussi réécrire le minimum de la barre

Le § 17 dit encore « Acquisition et Médiathèque pour tous » et « Un utilisateur Plex sans aucun droit ici est admis en lecture seule, médiathèque uniquement ». Or tes décisions du 27/09 permettent un compte à une seule page (« le minimum est à 1 sans barre du bas ») et un rôle sans aucune page (« envoie sur une page/route spéciale »). L'amendement « § 17 (ACL) » déjà prévu, que tu tapes toi-même, s'élargit à trois points :
- « pour tous » devient « les pages quotidiennes que le rôle de ce compte ouvre (Acquisition, Médiathèque, Trackers, Découvrir) » ;
- une seule page, pas de barre ; aucune page, la route dédiée ;
- la phrase « médiathèque uniquement » disparaît, ou devient la valeur de départ du rôle par défaut.
« De deux à quatre » tient tel quel. Le même amendement autorise le pluriel pour les demandeurs (§ 17, « toute acquisition a un demandeur » ; § 20, « le média a un demandeur »), puisque tu as décidé qu'un suivi peut en avoir plusieurs. Lot : L18. Le texte reste de ta main.

### M9 — « Réaffecter » : l'acteur choisit le demandeur, et seuls les comptes qui voient la carte sont proposés

« Réaffecter » est un acte du panneau de la carte (ta décision du 27/09), et l'acteur y choisit lequel des demandeurs il déplace. Ta règle veut que le dessin fixe ce que l'interface fait quand un droit manque. La liste ne propose donc que des comptes dont le rôle voit Acquisition : jamais une carte que personne ne pourrait voir. Lot : L18.

## Questions pour l'opérateur (round 10)

1. Tu ajoutes à la main dans qBittorrent un épisode qu'une série suivie attend : faut-il une seule carte, celle du suivi, ou une carte d'arrivée à part ?
2. « Récupérer la saison N » sur une série que tu possèdes mais ne suis pas : ce geste doit-il commencer un suivi ?
3. Sur la ligne d'un torrent dans Trackers, que fait « Libérer », maintenant qu'il existe « Retirer de qBittorrent » et « couper le cross-seed » ?
4. Une obligation de seed rompue par le moteur, dont le torrent a quitté qBittorrent : où se lit-elle dans Trackers, et quand sort-elle du badge ?
5. Dans l'onglet « Torrents », quel mot afficher pour un torrent que le moteur n'a pas encore cherché, sur un tracker qui fait du cross-seed ?
6. Quand deux comptes suivent le même média, qui règle ce qu'ils partagent : la pause, la qualité, « Abandonner », la confirmation Plex ?
7. Pour un compte qui n'a pas Acquisition, quelle est la page d'entrée, celle où « Retour » ramène et où la garde de sortie s'arme ?
