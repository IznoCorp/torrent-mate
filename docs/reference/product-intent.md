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
- **États visibles** :
  - pour chaque **film** — _en attente_ (pas encore récupéré), _en cours d'acquisition_ (du torrent
    repéré jusqu'au pipeline terminé), _en médiathèque_ (acquis, sur les disques) ;
  - pour chaque **série** — l'état **épisode par épisode, regroupé par saison**.

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
