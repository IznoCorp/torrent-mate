# Product Intent — Constitution produit de TorrentMate

> **STATUT : IMMUABLE.** Ce document est la **raison d'être** de l'application, dictée par
> l'opérateur (son unique utilisateur). Il **prime sur toute autre consigne**, passée ou future :
> aucune demande ponctuelle, aucun choix technique, aucune « amélioration » ne peut le contredire.
>
> **En cas de conflit entre une implémentation existante et cette constitution, c'est
> l'implémentation qui est fausse.** Toute évolution de la web-UI doit être conforme à ce document.
> **Chaque PR touchant la web-UI cite les § qu'elle sert.**
>
> C'est le mécanisme anti-perte : les agents futurs le lisent **avant de coder**. Il existe parce
> que des correctifs locaux ont été « implémentés » à la lettre en détruisant la fonctionnalité
> qu'ils devaient améliorer — voir `§méthode` et le post-mortem associé.
>
> **Historique** : v1 — §1–§5 + §méthode (gravée `4d80c26a`) ; **v2** — §6–§10 + listes
> DOIT / NE-DOIT-PAS + « En une phrase », dictée par l'opérateur le 2026-07-15 ;
> **v3** — §4 « la chaîne va jusqu'à la visibilité Plex » + §5 « identité conservée au scraping »,
> dictée par l'opérateur le 2026-07-31 ;
> **v4** — §11 « Tout média est consultable » + DOIT-11 + NE-DOIT-PAS-9, dictée par
> l'opérateur le 2026-08-04 (feature media-sheet, DESIGN §4) ; NE-DOIT-PAS-9 ajusté
> le 2026-08-04 pour exiger un chemin atteignable, pas un lien sur la vignette.
> **Seul l'opérateur amende ce document.**

---

## Raison d'être

TorrentMate est l'interface de supervision d'un **pipeline média en boucle fermée** (moteur
`personalscraper` : ingest → sort → scrape → dispatch, plus acquisition/ratio). L'interface existe
pour donner à l'opérateur **le contrôle et la visibilité** du pipeline, et pour lui rendre la main
**interactivement** sur ce que l'automatisation ne sait pas résoudre seule. Elle n'est pas un
tableau de bord passif : c'est le poste de pilotage depuis lequel un média part du client torrent
et **termine son parcours jusqu'à la médiathèque**.

---

## §1 — Contrôle du pipeline

L'interface montre, **au même endroit**, les pipelines qui se lancent **automatiquement**
(watcher / cron) et permet de **contrôler** le pipeline : **lancer / stopper**.

## §2 — Visibilité du pipeline

L'interface montre **ce qui se passe** dans le pipeline : ce qui est **intégré, renommé, scrapé** —
métadonnées récupérées, posters récupérés, trailers récupérés, dispatchs faits. Chaque état porte
un **libellé en français clair**, compréhensible par un non-développeur. Aucun message obscur.

## §3 — Scraping interactif des éléments bloqués

Si des éléments du pipeline restent **non matchés donc non scrapés**, l'opérateur doit pouvoir
**déclencher le scrape manuellement** avec un **sélecteur interactif** :

- choisir parmi des **candidats proposés** ;
- **modifier le nom et l'année pour relancer une recherche** si les candidats ne conviennent pas.

**Invariant** : tout élément non matché accessible depuis l'UI arrive dans le sélecteur **avec des
propositions**. Zéro candidat trouvé = **état explicite + recherche manuelle pré-remplie**, jamais
un écran vide. Une file « invisible » de décisions sans candidats est une **dénaturation** du §3.

## §4 — La résolution termine le pipeline

Quand un candidat est choisi, **le scraping se lance** et le média **termine alors son pipeline** :
métadonnées, posters, trailer, vérification, **dispatch**.

**Résoudre n'est pas « écrire une NFO »** : c'est **remettre le média en route jusqu'au bout**, en
réutilisant l'**autorité de déclenchement unique** (lock pipeline / runner existant — jamais un
second mécanisme). L'UI **montre cette continuation** : le média avance sur le board, sa timeline se
complète, et il finit **dispatché en médiathèque**. Un média qui reste échoué en staging après
« résolution » est une **dénaturation** du §4.

**La chaîne va jusqu'à la visibilité (v3).** « Terminer le pipeline » ne s'arrête **pas** au fichier
sur le disque : un média dispatché **DOIT devenir visible dans le lecteur** (Plex). La chaîne
s'**enchaîne** de bout en bout — **acquisition terminée → pipeline → dispatch terminé → scan Plex** —
et le **dispatch terminé déclenche le scan Plex** du dossier écrit (fail-soft : Plex injoignable =
avertissement, **jamais** un échec du transfert ; le scan cible **le dossier dispatché**, pas toute
la bibliothèque). Un média **acquis + dispatché + indexé mais invisible dans Plex** est une
**dénaturation** du §4 : le scan n'a pas été déclenché (cause classique — le **token Plex absent de
l'environnement réel des crons**, donc le subscriber de refresh jamais câblé). Le déclencheur du scan
DOIT être **le même dans tous les points d'entrée de dispatch** (pipeline, `dispatch` autonome, run
web) et **fonctionner dans l'environnement d'exécution réel**, pas seulement en théorie.

## §5 — Acquisitions

L'écran Acquisitions contrôle l'acquisition **automatique** de films et de séries.

- **Ajout** : une recherche trouve un média (film ou série) et l'ajoute à la liste de suivi.
- **Film** : une fois récupéré et acquis (**pipeline terminé**), il est **retiré des suivis
  automatiquement**. Si le film est **déjà en médiathèque**, l'interface **demande confirmation du
  remplacement** avant l'ajout au suivi ; le pipeline le remplacera (version plus récente) puis le
  retirera des suivis.
- **Série** : l'interface montre **ce qui est déjà sorti vs ce qui est en médiathèque**, saison par
  saison, **épisode par épisode**, pour voir ce qui reste à acquérir. Une série **ne se retire pas
  automatiquement** : d'autres épisodes peuvent sortir.
- **Watcher** : vérifie s'il y a de nouveaux épisodes → s'ils sont en médiathèque → sinon s'ils sont
  disponibles sur les trackers → si oui, les récupère. Il tourne **sur cron ET sur demande manuelle
  dans l'interface**. Le déclenchement manuel **montre le run** : lancé → en cours → **résultat
  chiffré** (« X nouveaux épisodes détectés, Y disponibles, Z récupérés », ou « rien de nouveau »,
  ou l'**erreur réelle**). Un toast de succès sur un run mort est **interdit** ; l'échec remonte
  bruyamment.
- **Identité conservée (v3)** : une récupération **via les acquisitions** (suivi) **garde l'ID du
  suivi (provider-ID) pour le scraping**. Le média scrapé est identifié par **l'ID choisi à
  l'ajout** — jamais re-deviné par correspondance de nom, qui recrée la **confusion d'identité** (un
  scrape re-matchant un TVDB différent du suivi → deux dossiers / deux items, épisodes coincés en
  acquisition). C'est l'application du §7 (contrôle d'identité par provider-ID) au **chemin
  acquisition → scrape**.
- **États visibles** :
  - pour chaque **film** — _en attente_ (pas encore récupéré), _en cours d'acquisition_ (du torrent
    repéré jusqu'au pipeline terminé), _en médiathèque_ (acquis, sur les disques) ;
  - pour chaque **série** — l'état **épisode par épisode, regroupé par saison**.

---

## §6 — Disponibilité des actions

Une action opérateur légitime ne répond **jamais « occupé »** : elle **s'exécute** ou elle
**s'enfile visiblement** (état « En file » affiché + exécution à la libération). Le **seul refus
permis est l'idempotence** — la même action, sur la même cible, déjà en cours. Un 409 /
« réessaie plus tard » opposé à une action légitime est une **dénaturation** de ce §.
(Patron de référence : la file resolve — 202 systématique, step `queue`, pastille « En file ».)

## §7 — Intégrité des médias

**Jamais de perte de fichier.** Un écrasement n'est permis qu'après **contrôle d'identité par
provider-ID** — on remplace le bon film parce que c'est **son ID**, pas parce que c'est son nom ;
mismatch d'ID ⇒ blocage explicite avec raison, jamais d'écrasement. **Aucune destruction depuis
l'interface sans confirmation explicite.** Toute opération destructrice (déplacement, suppression,
écrasement) laisse une trace dans un **journal append-only** — qui, quoi, quand, chemin, décision
(leçon Star City : des fichiers ont disparu et aucune piste d'audit n'existait pour innocenter ou
accuser quiconque).

## §8 — Rien en silence (extension du §2)

Skips, attentes, différés (ratio, espace disque), torrents en erreur, fichiers manquants : **tout
est affiché avec sa raison**, en français clair. Un « rien ne se passe » sans raison visible est un
mensonge par omission. Le **Dashboard est le poste de contrôle** ; toute vue de détail est
**adressable par URL**.

## §9 — Téléchargement suivi

Le **profil qualité est respecté** sur tout le chemin d'acquisition, la **3D exclue**. La
**complétude exécutable** (read-model croisant catalogue diffusé et possession par provider-ID)
est **LA** définition d'« acquis » — jamais des compteurs bruts.

## §10 — Méthode de livraison

Ces règles s'ajoutent au `§méthode` et s'appliquent à **toute** livraison :

1. **Clôture exhaustive** — on ne laisse rien d'ouvert : tout point découvert est traité ou
   arbitré explicitement par l'opérateur.
2. **Auto-vérification live par celui qui livre** — vérifier son propre travail en conditions
   réelles fait partie du travail (« ton travail et ton devoir »).
3. **Version bump à chaque PR** — patch par défaut, dans le même commit.
4. **Un test de régression par bug** — chaque bug détecté a un test qui le reproduit.
5. **Rapports honnêtes, incluant ses propres erreurs** — un rapport qui omet les erreurs de son
   auteur est un rapport faux.

---

## §11 — Tout média est consultable

Un média affiché dans l'interface (poster, titre, ligne de liste, résultat de recherche)
**doit** ouvrir sa fiche détail. Une fiche dit ce qu'est le média (titre, année, synopsis,
réalisateur, bande-annonce ; pour une série : saisons, épisodes, statut) **et où il en est**
chez nous (possédé ou non, complétude par saison). Une vignette qui ne mène nulle part est un
cul-de-sac : l'opérateur voit un objet sans pouvoir savoir ce que c'est.

**Exception unique** : un média **non identifié** (aucun ID provider connu) n'a pas de
fiche — la surface doit alors mener à la **résolution**, jamais à un lien mort.

---

## §12 — Mobile first

L'interface est **pensée pour le mobile d'abord**. Le téléphone n'est pas une adaptation du
poste de travail : c'est **le** poste de travail. Toute surface se conçoit à la largeur d'un
téléphone, puis se laisse respirer sur grand écran — jamais l'inverse. Le desktop doit rester
pleinement fonctionnel, mais il n'est pas le point de départ du dessin.

Ce que cela impose concrètement :

- **La largeur est la ressource rare.** Sur un téléphone, tout ce qui partage une ligne se
  dispute la même poignée de pixels. Une information essentielle (le **titre** d'un média)
  ne partage pas sa ligne avec des informations secondaires : elle prend la ligne entière,
  les qualificatifs descendent en dessous.
- **Rien d'essentiel n'est tronqué.** Un titre coupé en « A Knight of the Seven King… » n'est
  pas un titre : c'est une devinette. Si la place manque, c'est la mise en page qui change,
  pas le contenu qui disparaît.
- **Pas de redondance qui coûte de la place.** Une information déjà portée par le contexte
  (un onglet « Séries » actif) ne se répète pas sur chaque carte : elle vole de la largeur à
  ce qui compte.
- **L'ordre suit la lecture réelle.** Ce que l'opérateur cherche en premier vient en premier
  (pour un média suivi : le titre, puis l'avancement chiffré, puis l'état).
- **Au doigt, sans scroll horizontal.** Cibles tactiles atteignables, aucune surface ne
  déborde latéralement à la largeur d'un téléphone.

**Une maquette validée uniquement sur grand écran ne vaut rien.** Toute évolution d'interface
se vérifie à la largeur réelle d'un téléphone (§méthode : la preuve est un déroulé exécuté,
pas une intention).

### Composition d'une carte média (règle gravée)

Une carte de média suit **cet ordre, une information par rôle** :

1. **Ligne 1 — le titre, seul.** Il occupe toute la largeur disponible. Rien ne le partage.
2. **Ligne 2 — l'avancement chiffré d'abord** (`10/12`), **puis l'état** (`À jour`,
   `En cours d'acquisition`, …), puis le reste (échéance, compteurs, actions).
3. **Pas d'étiquette de type** (« Série » / « Film ») : l'onglet actif la porte déjà.

Toute carte qui remet le titre en concurrence avec autre chose sur sa ligne est **non
conforme**.

---

## §13 — L'interface reflète l'état réel des données

L'interface **garantit** de montrer l'état réel des données — **acquisitions**, **staging**,
**médiathèque**. Elle n'a pas d'état à elle : tout ce qu'elle affiche est dérivé des données,
et cette dérivation doit être **vérifiable par les données**.

- **Aucun état affiché n'est une constante.** Un libellé qui ne peut pas changer quand la
  réalité change est un mensonge en attente. Un état qui _pointe_ vers autre chose (un épisode
  « absorbé » par une saison) doit **suivre le pointeur**, jamais le rapporter tel quel.
- **Une seule dérivation par question.** Deux surfaces qui répondent à la même question
  (« où en est cet épisode ? ») lisent le **même** code. Deux implémentations de la même règle,
  c'est la garantie qu'elles divergeront — et que l'opérateur verra deux vérités.
- **La vérification est exécutable.** « L'interface dit vrai » n'est recevable que prouvé par
  un contrôle croisé données ↔ affichage, à zéro anomalie
  (`scripts/check-acquisition-coherence.py`). Une relecture de code n'est pas une preuve.
- **Après un bug, l'état est corrigé — systématiquement.** Un correctif qui empêche le bug de
  se reproduire mais laisse les données qu'il a faussées est un travail **inachevé**. Toute
  correction se termine par : (1) le code corrigé, (2) **l'état existant réparé**, (3) le
  contrôle exécutable à zéro anomalie. Les trois, ou rien.

**Corollaire** : aucun verdict « c'est conforme » sans avoir _regardé les données_ après le
correctif.

---

## §14 — Les deux workflows (règle gravée)

Le produit n'a que **deux** enchaînements, et ils sont **contraignants**. Toute surface, tout
état affiché, tout garde-fou se lit par rapport à eux. Un état qui n'est pas une étape de ces
workflows, ou qui y stagne alors que la suite a eu lieu, est **non conforme**.

### §14.1 — Workflow d'acquisition

```
média ajouté au suivi
   → est-il déjà diffusé ?          non → on attend (état stable, légitime)
   → oui : torrent disponible ?     non → on cherche encore (état stable, légitime)
   → oui : récupération
   → récupéré ?                     non → changement de release
```

Deux états seulement sont des **états de repos** légitimes : « pas encore diffusé » et
« cherché, rien trouvé ». Tout le reste — « disponible », « récupéré » — est **transitoire** :
il doit avancer tout seul. Une release qui ne se récupère pas se remplace ; ce n'est jamais un
état où l'on s'installe.

### §14.2 — Workflow pipeline

```
torrent terminé
   → ingestion   (uniquement ce qui DOIT l'être : ni les torrents de ratio,
                  ni ceux déjà ingérés)
   → tri → nettoyage → identification → scraping → bande-annonce → vérification → dispatch
```

Le déclencheur est **le torrent terminé**, quelle que soit son origine. Une release issue d'une
acquisition n'est pas un cas particulier : **elle déclenche le workflow pipeline comme n'importe
quel torrent terminé**. Il n'existe pas deux chemins.

### §14.3 — La jonction des deux workflows est OBLIGATOIRE

Les deux workflows se rejoignent, et cette jonction est un **engagement**, pas un espoir :

- **« récupéré » n'est PAS un état de repos.** Un torrent d'acquisition terminé a déclenché le
  pipeline ; si l'acquisition affiche encore « récupéré » alors que le média est en
  médiathèque, l'interface ment (§13) et le workflow n'est pas allé au bout.
- **La fermeture suit la médiathèque, pas une horloge.** Dès que la médiathèque possède
  l'œuvre, la ligne d'acquisition se referme. Elle ne peut pas dépendre d'une **tentative
  unique** ni d'un cron lointain : une fermeture qui se joue sur une course, avec un filet à
  douze heures, est **non conforme**.
- **Un parcours n'a pas de trou.** Un média rangé est passé par l'ingestion, le tri,
  l'identification et le scraping — c'est le workflow. Si une étape n'est pas connue, l'interface
  dit **« inconnue »**, jamais « pas faite » : afficher « rangé » au-dessus d'étapes éteintes
  décrit un chemin qui n'existe pas.
- **Chaque garde-fou couvre les DEUX workflows en entier.** Une règle qui ne voit qu'un genre
  de ligne (un épisode mais pas une saison) laisse passer précisément ce qu'elle prétend
  garder.

---

## §15 — La maquette EST le produit (règle gravée)

**La maquette est le produit**, pas une illustration ni un souvenir de conception. Directive
opérateur du 2026-08-13 : ce n'est plus un habillage de l'app livrée, c'est une refonte — une
**v1 aboutie**, une version à part entière. L'app sera rebâtie dessus, et non amenée vers elle
surface par surface.

### La référence visuelle a changé de forme (L07, 2026-08-25)

**Ce paragraphe nommait `frontend/maquette/design/refonte.html`, et ce fichier ne porte plus une
seule règle de style.** Le lot L07 a converti ses 530 règles en utilitaires Tailwind derrière des
variants typés. La référence visuelle est désormais **les tokens et le catalogue de composants** :

| | |
| --- | --- |
| L'échelle et la palette | `frontend/maquette/design/src/styles/theme.css` — un bloc `@theme static` : 34 pas d'échelle (espacement, typographie, rayons, mouvement) et 38 jetons de palette, dont **30 couleurs** et 8 ombres — les ombres sont délibérément hors du namespace `--shadow-*` pour qu'aucun utilitaire ne puisse en être fabriqué |
| La couche de base | `frontend/maquette/design/src/styles/base.css` — reset, typographie, les surfaces d'accessibilité de L03, les `@keyframes`, et ce que le compositeur lit |
| Le vocabulaire | `frontend/maquette/design/src/ui/variants.ts` et les `variants.ts` de chaque surface — chaque décision de dessin y est écrite à côté de la classe qui l'applique |
| Le résidu, daté | `frontend/maquette/design/src/styles/legacy.css` — le CSS dont le moteur mourant a encore besoin ; il meurt avec lui à L13 et une garde refuse qu'il grossisse |
| L'échafaudage | `frontend/maquette/design/src/styles/harness.css` — le cadre de téléphone, importé une seule fois, et **la seule feuille qui ne sera pas livrée** |

**Ce que cela ne change pas** : la maquette reste le produit, et une évolution de dessin se décide
toujours dans la maquette avant le code. Ce qui change est **où l'on regarde** — un variant nommé
plutôt qu'un sélecteur à chercher dans quatre mille lignes.

**Élargi par l'opérateur le 2026-08-19 — TOUS les écrans sont à redessiner. Tous.** La maquette
est une **nouvelle version de l'app**, pas un habillage : son objet est une expérience
utilisateur **cohérente**, et le premier objectif est de **figer cette interface**.

### La maquette n'est PAS connectée au backend tant qu'elle est une maquette (2026-08-20)

**Directive opérateur.** Les fixtures ne sont pas un retard, elles sont la condition : c'est ce
qui rend 82 états nommés atteignables et 51 règles déterministes. Une maquette câblée sur des
données vivantes mesure les données, pas le dessin. Le raccordement appartient à la **bascule**,
avec le backend adapté à ce dont l'interface figée a besoin — jamais l'inverse.

### Aucune vague ne s'ouvre sans son design et son plan (2026-08-20)

**SP5 a été commencé sans document de spec, et c'est la faute à corriger avant de le
poursuivre.** Il n'existe aucun `docs/features/sp5/DESIGN.md` : seulement des renvois épars et
une phrase du plan SP4-fin nommant son premier geste. Une vague se lance donc ainsi, et pas
autrement :

1. **Objectifs et contours écrits**, avant toute ligne de code.
2. **Les choix fonctionnels ET techniques soumis à l'opérateur** — c'est son arbitrage, pas une
   déduction de l'agent depuis des mesures.
3. **Un design, puis un plan**, selon la méthodologie `implement:*`.
4. Alors seulement la branche, les phases, la PR.

Ce qui a été livré de SP5 avant cette règle — SP5a, le vocabulaire rendu livrable — reste :
il corrigeait un défaut mesuré. **Ce qui suit ne bouge pas sans design validé.**

### La maquette REMPLACE l'app — elle n'y est ni transposée ni traduite (2026-08-20)

**Le jour de la bascule, `frontend/src` est ARCHIVÉ et la maquette prend sa place.** Elle est la
nouvelle version du frontend, pas une source dont on tirerait des morceaux. C'est pourquoi
**toutes les pages et tous les mécanismes de l'app doivent à terme être recréés dans la
maquette** — il n'y aura rien à récupérer ensuite.

**Ce que cela ANNULE, et c'est impératif.** Un modèle antérieur — le spec du 2026-08-10 §4.1 et
§7.2 — prévoyait de faire migrer l'app **surface par surface** vers la maquette : d'où une
extraction du CSS, un préfixe `.tm` pour que les deux CSS cohabitent, une liste d'autorisation
de sélecteurs, une garde de dérive et une sonde de parité. La directive du 2026-08-13 a inversé
cet ordre, mais **l'outillage est resté**. Il n'a plus d'objet : on ne fait pas cohabiter deux
feuilles quand l'une remplace l'autre, et on ne traduit pas un CSS qui devient le CSS.

**Un changement de décision mal répercuté coûte plus cher que la décision elle-même** : ces
mécanismes ont produit du travail inutile, des gardes qui protégeaient des objets morts, et des
frictions à chaque vague. La règle qui en découle : **quand une décision change, les directives
d'implémentation changent DANS LE MÊME MOUVEMENT**, et ce qui devient sans objet est retiré, pas
laissé en place « au cas où ».

- **Aucune surface n'est hors périmètre.** Un écran de production sans page dans la maquette est
  une page **due**, jamais un arbitrage de l'écarter. `/control` (« Contrôle ») et `/pipeline`
  avaient été déclarés volontairement sans page : **cet arbitrage est annulé.** Où leurs
  panneaux ATTERRISSENT reste une question d'UX ouverte (`IMPLEMENTATION.md`) ; qu'ils soient
  dessinés ne l'est plus.
- **Ce que la maquette porte déjà est VALIDÉ** par l'opérateur. On ne le rejuge pas.
- **Ce qui reste n'est pas que des pages** : l'UX, le langage d'interaction et **l'architecture**
  de la maquette doivent être terminés et consolidés avant le gel.
- **Le backend suit l'interface, jamais l'inverse.** Le moteur sera adapté aux besoins de la
  nouvelle interface, et ce travail vient **après** le gel. Une limite du backend n'est donc
  jamais une raison de dessiner moins : on la note, et on dessine ce que l'expérience exige.

Ce que cela impose :

- **La maquette doit TOUTES les pages que la production sert**, y compris celles qu'elle ignore
  encore. Une surface que la production a et que la maquette n'a pas est un trou dans la v1,
  pas une étape ultérieure.
- **L'attachement au backend est une mission séparée**, ouverte quand l'opérateur juge le design
  ET l'architecture front assez solides. Ce jugement lui appartient ; aucune quantité de règles
  vertes ne s'y substitue.
- Tant que ce jugement n'est pas passé, **on ne dérive aucun code d'app** depuis la maquette.

**Toute évolution du design part de la maquette, jamais du code.**

- **On modifie la maquette D'ABORD**, on la vérifie avec son harnais, puis on en dérive le
  code. Jamais l'inverse.
- **Une divergence entre l'app et la maquette est un défaut de l'app**, sauf si la maquette a
  été amendée explicitement au préalable, avec la raison écrite.
- **Si une région ne peut pas être construite telle que dessinée**, on amende la maquette et
  on note pourquoi. Le code ne diverge jamais « provisoirement » : c'est ainsi qu'une
  interface devient un patchwork.
- **Rien ne part en production que la maquette ne montre.** Une surface nouvelle s'y dessine
  avant d'être codée.

Cette règle vaut pour toutes les évolutions futures, pas seulement pour la refonte initiale.
Elle se lit aussi dans `frontend/maquette/README.md`, qui porte la méthode, les états nommés,
le jeu de règles vérifiées et les pièges déjà payés. L'inventaire de ce que la v1 doit encore
est dans `IMPLEMENTATION.md`, lu du routeur livré.

**Langue des sources.** Tout commentaire de la maquette et de son harnais est écrit **en
anglais** et ne fait référence ni à une session de travail, ni à une phase, ni à une décision
datée : il doit se lire dans plusieurs années, hors de tout contexte. Le texte d'interface
cité dans un commentaire reste en français, puisque c'est ce que l'écran affiche.

---

## §16 — Le chemin de navigation (règle gravée)

**La navigation doit être fluide, et revenir en arrière doit refaire le chemin emprunté.**
Dictée par l'opérateur les 2026-08-23 et 2026-08-24, en prolongement de DOIT-10. Trois règles,
et l'ordre compte. Toutes trois sont **livrées** (L05, phase 11, PR #484).

### 1. Retour dépile, et la pile ne contient que des arrivées délibérées

Retour ramène à l'arrivée précédente — l'endroit d'où le lecteur vient réellement. Celui qui a
ouvert une fiche depuis une recherche revient **à sa recherche**, pas à la médiathèque.

Ce qui rend cela possible est une discipline, et c'est elle la vraie règle : **ouvrir une
surface empile ; régler une surface remplace.** Ouvrir une fiche, une résolution, un panneau
est une arrivée. Changer un filtre, un onglet interne, un tri, un objectif est un réglage : la
même surface regardée autrement. Un réglage n'entre jamais dans la pile — sans quoi Retour
défait un tri là où le lecteur voulait sortir de l'écran, et c'est exactement la sensation
qu'une application web donne quand elle est mal faite.

### 2. Changer de page principale REMPLACE

Les pages principales sont des destinations de premier niveau, pas des étapes d'un parcours.
Passer d'Acquisition à la Médiathèque **n'empile rien**. Retour depuis n'importe quelle page
ramène à **Acquisition**, la page d'entrée ; Retour depuis Acquisition arme la garde de sortie.

**Aucune plateforme n'empile l'historique des onglets visités**, et c'est le geste qui trahit
le plus vite une application web : le lecteur tape Retour pour sortir et se retrouve à
rembobiner ses pages une à une. iOS donne à chaque onglet sa pile et ne permet aucun retour
entre onglets ; Android ramène à la destination de départ puis quitte. La règle ci-dessus est
la lecture Android, retenue parce que c'est un Retour système qui pilote une PWA.

**Ce que cette règle ne donne PAS, et c'est un choix, pas un oubli** : il n'y a pas de pile par
page. Quitter la Médiathèque alors qu'une fiche y est ouverte, puis y revenir, ramène à la
racine de la Médiathèque et non dans la fiche. Un natif iOS restaurerait la fiche. On commence
sans ; on ne l'ajoutera que si l'usage réel le réclame, parce qu'un écran qui se rouvre
ailleurs qu'à sa racine surprend autant qu'il rend service.

### 3. Sans pile, elle se synthétise depuis la hiérarchie

Un lien ouvert depuis l'extérieur — un message, un signet, un onglet restauré — n'a pas de pile
à dépiler. Ce qui se trouve alors sous l'écran est **la page dont il relève** : la médiathèque
sous une fiche média, les Arrivées sous une résolution. **Jamais l'accueil par défaut.**

**Et ce parent est rendu, pas seulement enregistré.** Fermer l'écran révèle une page déjà en
place ; c'est ce qui fait la fluidité. Un écran qui se ferme sur du vide a rompu le chemin même
s'il a répondu à la bonne adresse.

**Composer une adresse de panneau par-dessus ce parent ne suffit pas à tout réparer** : le
routeur cesse de reconnaître l'adresse propre de l'écran et la fiche se démonte derrière le
panneau, quel que soit le parent placé dessous. C'est un défaut distinct (§ méthode), mesuré et
corrigé séparément — nommer le bon parent retire une cause, pas toutes.

### 4. Remonter — examinée, non retenue

Un quatrième geste avait été envisagé : un contrôle dessiné qui remonterait directement au
parent, sans dépiler pas à pas. **L'opérateur l'a examiné et écarté le 2026-08-24** : la barre
du bas (`.bottombar`, `z-index: 50`) reste visible au-dessus de tout écran ouvert
(`.screen`, `z-45` ; `.sheet`, `z-47` — vérifié dans `refonte.html`, dont le propre commentaire
dit « the tab bar sits above a screen »). La médiathèque est donc déjà à un tap, à toute
profondeur, sans qu'un geste de plus soit nécessaire. Et la règle 2 ci-dessus (pas de pile par
page) fait qu'un tel bouton atterrirait exactement là où la barre atterrit déjà : Remonter et
taper l'onglet seraient la même destination sous un nom différent.

Chaque écran garde son bouton Retour dessiné (`.fback`), qui dépile une entrée — c'est la
règle 1, pas un geste séparé.

### Ce que tout cela interdit, nommément

Faire remonter **Retour** au parent déclaré alors qu'une pile existe. Ce serait expédier à la
médiathèque le lecteur venu de sa recherche. C'est l'erreur que produit la règle 3 appliquée
sans la règle 1, et c'est pour l'interdire que les quatre règles sont écrites dans cet ordre.

### Ce que cela impose à la preuve

Les cas se vérifient **séparément** : un parcours fait dans l'application dont le Retour revient
à l'origine réelle, un lien froid dont le dessous est le parent, un changement de page qui
n'empile rien, et une garde de sortie qui ne s'arme qu'en haut. Une tenue qui ne mesure que le
chargement à froid a déjà laissé passer deux défauts sur la vague L05 — c'est précisément ainsi
qu'ils sont passés sous des règles vertes.


## §17 — Comptes, droits et identité Plex (dicté par l'opérateur, 2026-08-26)

**L'application gère des utilisateurs, des profils et des droits.** Elle n'est plus un poste de
contrôle à un seul occupant : plusieurs personnes s'en servent, elles n'ont pas les mêmes
permissions, et l'interface doit le refléter partout — pas seulement à la porte d'entrée.

**Les utilisateurs Plex sont des utilisateurs de l'application, et ils s'authentifient par le SSO
Plex.** Quelqu'un qui a accès au serveur Plex du foyer n'a pas à se voir attribuer un second
mot de passe pour consulter la médiathèque : il se connecte avec son compte Plex.

### Ce que cela pose

1. **Un droit se lit sur la surface, jamais seulement à l'appel.** Une action qu'un compte n'a pas
   le droit d'exercer ne doit pas être offerte puis refusée : l'interface montre ce que CE compte
   peut faire. Un `403` reçu après un geste est un défaut d'interface, pas une sécurité qui
   fonctionne — c'est **NE-DOIT-PAS-3** appliqué aux droits, et le refus est ici légitime, donc
   c'est l'offre qui doit disparaître.
2. **Ce qu'un compte ne peut pas faire reste VISIBLE et EXPLIQUÉ**, quand le cacher tromperait sur
   l'état du système. §8 — rien en silence — ne s'annule pas parce que le lecteur a moins de
   droits : il voit que la chose existe et qu'elle ne lui est pas ouverte, il ne voit pas une
   application amputée dont il croirait qu'elle est complète.
3. **Le rôle en lecture seule qui existe déjà est un cas de ce §, pas une mécanique à côté.**
   `PERSONALSCRAPER_WEB_ROLE=staging` refuse aujourd'hui toute écriture par une dépendance unique
   (`require_not_staging`). Le modèle de droits qui arrive doit l'ABSORBER — un seul chemin
   d'autorisation, jamais deux —, faute de quoi c'est **NE-DOIT-PAS-7**, un second mécanisme
   parallèle.

### Ce que cela ne tranche pas, et qui reste à dicter

Écrit ici comme ouvert pour que personne ne les décide en chemin :

- **Quels rôles, et leurs droits exacts.** L'application en connaît un aujourd'hui (lecture seule),
  et « profils » suggère davantage.
- **Le SSO Plex remplace-t-il l'authentification actuelle ou s'y ajoute-t-il ?** Le compte
  opérateur d'aujourd'hui repose sur `WEB_PASSWORD_HASH` et une session signée.
- **Ce qu'il advient d'un utilisateur Plex qui n'a aucun droit ici** : refusé à la porte, ou admis
  avec le minimum.
- **Ce qu'un compte Plex voit par défaut.** Consulter la médiathèque n'est pas piloter le pipeline.

### Ce que cela impose à la preuve

Un droit se vérifie **des deux côtés et séparément** : l'action absente de la surface pour le
compte qui ne l'a pas, et l'appel refusé pour celui qui la forcerait. Une tenue qui ne mesure que
le second prouve la sécurité et pas l'interface — et c'est l'interface que ce document régit.

**Aucune de ces exigences n'est bloquée par la maquette, ni ne la bloque.** Elles se dessinent
comme tout le reste : dans la maquette d'abord, avec des états nommés et une règle qui mord.

## §18 — Le ratio est une ressource, et elle se pilote (dicté par l'opérateur, 2026-08-26)

**Sur un tracker privé, le ratio est ce qui donne le droit de continuer à télécharger.** Le perdre
n'est pas un désagrément d'affichage : c'est perdre l'outil. L'application doit donc laisser
l'opérateur **voir** où il en est, tracker par tracker, et **agir** dessus — pas seulement subir
une politique écrite dans un fichier de configuration.

**Le moteur sait déjà tout cela, et l'interface n'en montre rien.** La politique par tracker existe
(`min_ratio`, `min_seed_time` de `TrackerProviderConfig`, lue au grab et au cross-seed), les
obligations de seed sont suivies avec leur état de ratio courant
(`GET /api/acquisition/obligations` — « List seed obligations with their current ratio state »), et
les téléchargements en cours comme les grabs bloqués ont leur endpoint. **Aucun des trois n'est
appelé par la maquette** : ils figurent parmi les 24 opérations que le backend expose et que
l'interface n'utilise pas.

### Ce que cela pose

1. **Le ratio se lit PAR TRACKER, jamais en un seul chiffre.** Un ratio global moyen cache
   précisément la situation dangereuse : bien portant chez l'un, en dette chez l'autre.
2. **Une obligation de seed est un « rien » qui a sa raison** — §8, et **DOIT-2** nommait déjà
   « torrent différé (ratio, espace) ». Un torrent conservé parce qu'il doit encore semer doit dire
   qu'il l'est, jusqu'à quand ou jusqu'à quel ratio, et non ressembler à un téléchargement oublié.
3. **Agir là où l'on observe** (**DOIT-3**) vaut ici comme ailleurs : la politique d'un tracker se
   règle depuis la surface qui montre son ratio, pas dans un fichier que l'interface se contente de
   relire.
4. **Ce que l'application ne fera jamais pour améliorer un ratio** : maltraiter le tracker.
   **NE-DOIT-PAS-8** couvre déjà les rafales ; il est rappelé ici parce que c'est précisément le §
   où la tentation existe.

### Ce que cela ne tranche pas, et qui reste à dicter

- **Quelles actions** l'opérateur exerce sur un torrent au regard du ratio — forcer le seed,
  libérer une obligation, refuser un grab qui coûterait trop.
- **Ce qui est montré d'un tracker** au-delà du ratio : dette, marge, tendance, échéance.
- **Si l'interface propose une décision** (« ce grab vous met en dette ») ou se borne à l'exposer.

### Ce que cela impose à la preuve

Le ratio affiché est **celui que le tracker reconnaît**, pas une valeur calculée localement qui
diverge en silence — **NE-DOIT-PAS-1**. Une obligation affichée comme tenue et qu'un tracker
compte encore due est un mensonge, et c'est celui qui coûte le compte.

## Ce que l'interface DOIT faire (DOIT-1 … DOIT-13)

1. **DOIT-1 — Tout montrer, en français clair.** Chaque média a un état compréhensible sans être
   développeur : intégré, renommé, identifié, posters récupérés, trailer, dispatché. Un libellé
   incompris = un bug.
2. **DOIT-2 — Montrer ce qui ne se passe pas, et pourquoi.** Torrent différé (ratio, espace),
   décision en file, fichier manquant, erreur : chaque « rien » a sa raison affichée.
3. **DOIT-3 — Agir là où l'on observe.** Lancer/stopper le pipeline, relancer le watcher, résoudre
   un blocage — depuis le poste de contrôle, pas dans un terminal.
4. **DOIT-4 — Toujours accepter une action légitime.** Mauvais moment ⇒ mise en file **visible**
   (« En file — pipeline en cours »). Jamais « occupé, réessaie ».
5. **DOIT-5 — Aller au bout et le montrer.** Résoudre = remettre en route jusqu'à la médiathèque,
   progression visible jusqu'au bout. Une « réussite » dont on ne voit pas la fin n'est pas une
   réussite.
6. **DOIT-6 — Des résultats chiffrés.** Run manuel : lancé → en cours → « X détectés,
   Y disponibles, Z récupérés » (ou « rien de nouveau », ou la vraie erreur).
7. **DOIT-7 — Une porte de sortie à chaque impasse.** Non identifié → candidats ; zéro candidat →
   recherche manuelle pré-remplie. Jamais de cul-de-sac ni d'écran vide.
8. **DOIT-8 — Confirmation avant remplacement** d'un film déjà en médiathèque.
9. **DOIT-9 — Pensée pour le téléphone d'abord (§12).** Largeur réelle, au doigt, sans scroll
   horizontal — le mobile est le poste principal, pas une adaptation. Une information
   essentielle ne partage pas sa ligne ni ne se fait tronquer ; le desktop reste
   pleinement fonctionnel mais n'est pas le point de départ du dessin.
10. **DOIT-10 — Retrouvable.** Chaque détail a son URL ; Retour ferme ce qu'il doit fermer, et il **refait le chemin emprunté** (§16).
11. **DOIT-11 — Être consultable.** Tout média affiché ouvre sa fiche détail ; la fiche dit ce qu'est le média (titre, année, synopsis, réalisateur, bande-annonce ; pour une série : saisons, épisodes, statut) **et** où il en est chez nous (possédé ou non, complétude par saison). La fiche est atteignable par un lien stable (`/media/:provider/:id`).
12. **DOIT-12 — Montrer l'application de CE compte (§17).** Les actions offertes sont celles que le
    compte connecté peut exercer ; ce qu'il ne peut pas faire est visible et expliqué plutôt que
    silencieusement absent, quand le cacher tromperait sur l'état du système. Un refus reçu après
    le geste est un défaut d'interface.
13. **DOIT-13 — Montrer et piloter le ratio, tracker par tracker (§18).** Où en est chaque tracker,
    quelles obligations de seed courent et jusqu'où, et de quoi régler la politique depuis la
    surface qui l'affiche. Un ratio global unique ne satisfait pas cette clause : c'est par tracker
    que le droit de télécharger se gagne ou se perd.

## Ce que l'interface NE DOIT PAS faire (NE-DOIT-PAS-1 … NE-DOIT-PAS-9)

1. **NE-DOIT-PAS-1 — Mentir.** Pas de toast de succès sur un run mort ; pas d'état plus optimiste
   que le moteur (« Identifié » qui ne passerait pas le verify réel = mensonge).
2. **NE-DOIT-PAS-2 — File ou attente invisible** (le péché originel du post-mortem #249).
3. **NE-DOIT-PAS-3 — 409 / « occupé » face à une action légitime.** Seul refus : le doublon de la
   même action.
4. **NE-DOIT-PAS-4 — Message obscur.** Ni jargon brut, ni code d'erreur nu, ni anglais machine.
5. **NE-DOIT-PAS-5 — Échec silencieux.** Une erreur remonte bruyamment avec sa raison réelle.
6. **NE-DOIT-PAS-6 — Détruire sans consentement.** Confirmation explicite + identité par
   provider-ID.
7. **NE-DOIT-PAS-7 — Second mécanisme parallèle.** Tout passe par l'autorité de déclenchement
   unique (même lock, même runner).
8. **NE-DOIT-PAS-8 — Maltraiter les dépendances.** Pas de rafales vers qBittorrent / trackers —
   se faire bannir prive l'opérateur de son outil.
9. **NE-DOIT-PAS-9 — Afficher un média sans chemin vers sa fiche.** Un média identifié (avec
   ID provider) doit offrir un chemin vers `/media/:provider/:id` depuis la surface qui
   l'affiche — lien direct sur la vignette, ou action explicite dans le détail qu'elle
   ouvre. Ce chemin doit être visible, pas deviné. Seule exception : un média non
   identifié (aucun ID provider connu) — la surface doit alors mener à la **résolution**,
   jamais à un lien mort ni à une fiche inexistante.

## En une phrase

L'interface est un **poste de pilotage honnête** : elle montre tout (y compris ce qui attend ou
échoue), n'affirme rien qu'elle ne puisse prouver, n'oppose jamais un refus technique, et chaque
impasse a une porte de sortie.

---

## §méthode — Comment interpréter et vérifier toute évolution

Ces règles sont **gravées** : elles s'appliquent à tout agent (humain ou LLM) qui touche l'UI.

1. **L'intention prime sur la lettre.** Toute demande d'évolution s'interprète **au service de cette
   constitution**. Si une lecture littérale d'une demande la contredit, **c'est l'intention qui
   gagne** et le doute se **documente** (dans la PR et, si structurel, ici).
2. **Aucun verdict « conforme » sans déroulé exécuté.** On ne déclare une surface conforme qu'après
   un **déroulé réel en prod** (ou en dev seedé) **avec preuve datée** (capture / trace). Un verdict
   « conforme » sur données vides ou sur inspection statique seule est **interdit**.
3. **« Non vérifiable faute de données » = non conforme bloquant.** Si un flux ne peut pas être
   éprouvé parce qu'il n'y a rien à éprouver, il est **non conforme** tant qu'on n'a pas seedé un cas
   réel et prouvé le comportement. Ce n'est jamais une excuse pour valider.
4. **Rien n'est hors-scope sans arbitrage explicite de l'opérateur.** Un problème découvert se
   présente comme **point ouvert**, jamais étiqueté « non-bloquant » / « follow-up » de sa propre
   initiative.
5. **Préserver l'existant sain.** On réaligne sur la constitution, on ne rase pas les acquis.
6. **Preuve par contrôle exécutable, jamais par œil.** Un item scrapé / dispatché n'est « OK »
   qu'avec **`scripts/check-media-complete.py`** vert dessus — pas sur un cas chanceux, sur
   **tous** les items concernés (voir le garde-fou ci-dessous). Le read-model UI (« Identifié »,
   « Vérification : Fait ») est **plus laxiste** que le `verify` du pipeline (nommage
   poster/épisode) qui, lui, décide du dispatch : ne jamais s'y fier.

### Garde-fou exécutable — `scripts/check-media-complete.py`

Définition **exécutable** de « scrapé / dispatchable », qui est l'unique preuve recevable pour
tout verdict sur le scraping ou le dispatch (`§méthode` règle 6) :

- Il lance le **`verify` réel du pipeline** (le gate qui autorise le dispatch : NFO, nommage
  poster/landscape, et pour les séries le renommage des épisodes + NFO par épisode) **plus** un
  contrôle du **renommage de la vidéo** film (`Title.ext`, jamais le nom de release brut) que
  `verify` ne couvre pas.
- Il **échoue bruyamment** (code de sortie = nombre d'items incomplets) sur le moindre artefact
  manquant. Aucun « dispatché OK » n'est valide sans ce script **vert sur chaque item concerné**.
- Usage : `python scripts/check-media-complete.py` (tout le staging) ou
  `python scripts/check-media-complete.py --only "Titre*"`.

C'est la réponse durable au dérapage « resolve → jamais dispatché » : la résolution manuelle a
longtemps produit un écrit **partiel** (NFO + artwork seuls, dossier/vidéo/épisodes non renommés)
et se déclarait « fait » sans jamais éprouver le dispatch. Deux garde-fous verrouillent la
régression : ce script, et les tests `tests/scraper/test_scrape_forced.py`.

### Garde-fou exécutable — `scripts/check-acquisition-coherence.py`

Définition **exécutable** de « les acquisitions disent la vérité » (§5) : croise, pour chaque
suivi, le catalogue diffusé (cache `aired_episode`), la possession en médiathèque (fichiers
vivants, par provider-ID), la file `wanted` et le client torrent, et **échoue bruyamment**
(code de sortie = nombre d'anomalies) sur : un `grabbed` dont l'épisode est déjà en médiathèque
(fantôme), un `grabbed` dont le torrent a disparu du client, un `pending` déjà possédé, un
`abandoned` pour un épisode diffusé et manquant (la forme House of the Dragon), un doublon de
lignes `wanted`, un suivi sans aucun provider-ID.

Usage : `python scripts/check-acquisition-coherence.py` (ou `--json`). Aucun verdict « les états
d'acquisition sont conformes » n'est recevable sans ce script à **zéro anomalie** (session 3 :
14 lignes `grabbed` gelées depuis 11 jours, épisodes abandonnés à vie après UNE recherche —
aucun de ces mensonges n'était visible sans contrôle exécutable croisé).

### Post-mortem fondateur (pourquoi ce document existe)

La demande « pouvoir scraper en parallèle + avoir de la visibilité sur les scrapes en cours » a été
transformée en « **file d'attente invisible + perte du scraping interactif** ». Mécanisme de la
dérive :

- **implémentation de la lettre contre l'intention** : le scoped scrape lock (#249) a bien permis le
  parallélisme, mais la moitié « visibilité » de la demande a été omise, rendant le tout
  incompréhensible ;
- **vérification sur données vides** : des décisions créées avec `candidates_json="[]"` (aucune
  proposition) validées sans jamais dérouler une résolution réelle ;
- **verdicts « conforme » sans déroulé réel** : le scraping interactif a « disparu » sans qu'aucune
  preuve de bout-en-bout ne l'ait exercé.

Ces trois mécanismes sont exactement ce que `§méthode` interdit désormais.

### Post-mortem session 2 (reprise) — le même pattern, deux fois de plus

La reprise a confirmé la règle 6 sur un cas vivant **et** attrapé deux régressions que seul le
déroulé exécuté a révélées — la preuve statique les avait laissées passer :

- **Read-model menteur (règle 6, gravée).** L'UI affichait « Vérification : Fait » sur un signal
  plus laxiste (NFO + ids + un poster + n'importe quelle vidéo) que le `verify` réel qui décide du
  dispatch (nommage vidéo/épisodes). Un média « Identifié » restait en réalité non dispatchable
  (Top Chef). Corrigé : le read-model lance le vrai `verify` + expose un `blocked_reason` FR.
- **§4 « CONFIRMED » sur code, cassé à l'exécution.** L'audit Phase 0 avait déclaré §4 conforme sur
  inspection (`spawn_pipeline_run` câblé). Le déroulé prod a montré que la continuation
  `run --trigger-reason=scrape-resolve` **crashait** (l'enum du validateur rejetait la valeur), donc
  le média scrapé restait coincé en staging — la dénaturation §4 exacte. Le test existant _mockait
  `Popen`_ : vacuous. Leçon : **un « CONFIRMED » sur contrat runtime entre deux process ne vaut
  rien sans le run exécuté.**
- **Perte de données réelle (opérationnelle).** Un rename de dossier casse-seule (`Flow`→`FLOW`)
  sur FS insensible à la casse fusionnait le dossier dans lui-même et détruisait la vidéo ; et une
  fixture nommée comme un vrai film a écrasé « Le Robot sauvage » (dispatch = replace, contrôle
  d'absence sur le mauvais titre/catégorie). Corrigés + règle fixture gravée en mémoire.

### Les 5 tests de garde (§méthode) — chaque dérive a son test qui la reproduit

Chaque garde-fou échoue sur l'implémentation fautive et passe sur le fix :

1. **Enqueue sans candidats** → `tests/web/test_staging_media.py::test_enqueue_seeds_candidates_from_provider`
   - `::test_enqueue_other_seeds_search_with_cleaned_title` (le seed AUTRES avec le titre nettoyé,
     sinon deck vide).
2. **Item `other` sans chemin de résolution** →
   `::test_enqueue_other_without_kind_returns_400` + `::test_enqueue_other_with_kind_reclasses_to_movies_and_seeds`.
3. **Resolve qui n'aboutit pas au dispatch** → `tests/scraper/test_scrape_forced.py` (écrit complet)
   - `scripts/check-media-complete.py` + `tests/web/test_pipeline_trigger.py::test_continuation_trigger_reason_is_a_valid_run_trigger`
     (le contrat trigger-reason que le mock cachait) + `tests/web/test_decisions_routes.py::test_activity_hides_phantom_scrape`.
4. **Run manuel (grab/detect) sans état chiffré exposé** →
   `frontend/.../WatcherPanel.test.tsx` (jamais de toast succès sur le 202 ; le résultat chiffré
   n'arrive qu'à la fin du run) + `tests/commands/test_follow_detect.py` (le producteur film + la
   clôture §5) + le run observable (`pipeline_run` + `steps_json.counts`).
5. **La release-film exacte classée AUTRES** →
   `tests/sorter/test_file_type.py::test_archive_only_movie_release_is_movie` (le cas exact) +
   `::test_archive_only_non_media_pack_stays_other` (le garde-fou anti-sur-portée).

En bonus, la perte de données casse-seule est verrouillée par
`tests/scraper/test_rename_service.py::test_same_directory_is_never_merged` +
`tests/scraper/test_scrape_forced.py::test_case_only_rename_keeps_video`.

### Point attribution IA (tranché)

Certains commits de l'historique portent un trailer `Claude-Session:` (lien `claude.ai/code`).
Ce **n'est pas** de l'attribution IA au sens interdit par `hooks/block_ai_attribution.py` (qui
bloque `Co-Authored-By`, `Claude opus/sonnet/haiku`, `anthropic.com`) : c'est un lien de traçabilité
de session, autorisé par le harness et laissé passer par le hook. **Décision : on ne réécrit pas
l'historique.** Les nouveaux commits gardent ce trailer ; aucune mention d'auteur IA n'est ajoutée.
