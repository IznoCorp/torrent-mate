# Brainstorming — LLM Pipeline Assistant

> **Statut** : Idée. Item P3 de la roadmap, gardé pour la fin.
> **Document vivant** — capture l'intention et les questions ouvertes, pas l'implémentation.
> Les choix techniques (modèle, backend, format de stockage, intégrations) seront
> tranchés au moment du `/implement:feature`, quand le reste du projet aura évolué.

## Pourquoi

Beaucoup d'étapes du pipeline (surtout scraping) requièrent aujourd'hui un
arbitrage humain manuel : matches ambigus TMDB/TVDB, scores fuzzy borderline,
erreurs récurrentes qu'on corrige toujours de la même façon. En parallèle, la
médiathèque accumule du contenu qu'on ne sait plus quoi en faire (doublons,
séries abandonnées, films jamais regardés, trilogies incomplètes). L'idée :
un assistant IA appelable à la demande pour aider sur le pipeline ET sur la
gestion de la médiathèque — sans jamais agir sans validation.

## Principes directeurs

- **Simple à implémenter** — feature volontairement minimaliste. Pas
  d'architecture sophistiquée, pas de framework lourd. Briques off-the-shelf
  uniquement, on n'écrit pas d'IA sur mesure.
- **Efficace** — l'utilisateur doit sentir un vrai gain dès les premières
  utilisations.
- **À la demande seulement** — l'IA ne s'invite jamais d'elle-même. Pas
  d'intervention proactive/inline dans le pipeline, pas de cron qui balance
  des analyses non sollicitées. L'utilisateur appelle, l'IA répond.
- **Jamais autonome** — toute action proposée par l'IA reste validée par
  l'utilisateur (CLI ou Web UI).
- **RAG only, pas de fine-tuning** — l'apprentissage passe exclusivement
  par récupération de contexte (corpus médiathèque + log de corrections).
  Aucun entraînement de poids, aucun LoRA, aucune dépendance GPU.

## Vision

Un assistant qui :

- **Connaît la médiathèque** — il s'imprègne du contenu existant (ce qui est
  déjà bien rangé, les patterns de nommage, les genres récurrents, les
  langues audio par catégorie) pour comprendre "à quoi ressemble une entrée
  normale ici". Cette connaissance vit dans une base vectorielle, pas dans
  le modèle.
- **Apprend des corrections** — chaque fois que l'utilisateur accepte,
  modifie ou rejette une suggestion, ça s'ajoute au corpus. À la requête
  suivante, les corrections passées les plus similaires sont récupérées et
  injectées en few-shot dans le prompt. Au fil des semaines, les
  propositions convergent vers les choix réels de l'utilisateur — sans
  toucher au modèle.
- **Aide sans remplacer** — il intervient là où les heuristiques
  déterministes ne tranchent pas. Les scrapers classiques restent la voie
  principale, l'IA est un fallback consultatif.
- **Reste en retrait** — pas d'auto-application, pas d'intervention
  pendant l'exécution du pipeline.

## Cas d'usage visés

### Côté pipeline (à la demande)

- **Désambiguïsation de match** — plusieurs candidats TMDB/TVDB plausibles
  → l'IA classe avec son raisonnement.
- **Post-mortem par phase** — pour chaque étape du pipeline (ingest, sort,
  process, dispatch, verify, trailers), un outil dédié qui digère le
  rapport de la phase et propose un diagnostic + commande de reprise
  probable. Granulaire plutôt qu'un unique outil générique.
- **Détection d'incohérences** — scan croisé indexer/FS pour anomalies
  subtiles que les checkers ratent (genre NFO vs. catégorie dossier,
  dérive d'année, langue audio incohérente avec l'origine d'une série).
- **Analyse de tendances** — sur les N derniers runs : provider qui échoue
  systématiquement, étape lente, tempête de retries → suggestions de
  tuning config.

### Côté médiathèque (à la demande)

- **Recommandations de nettoyage** — doublons, séries abandonnées (saison 1
  sans suite depuis X années), films jamais finalisés, versions basse
  qualité à upgrader.
- **Recommandations de complétion** — saisons manquantes, films d'une
  trilogie incomplète, suites/préquelles d'un film qu'on a, autres œuvres
  d'un réalisateur déjà bien représenté.
- **Recommandations de découverte** — basé sur les patterns de la
  médiathèque ("tu as 20 thrillers coréens, en voici 5 que tu n'as pas")
  en croisant avec le catalogue TMDB/TVDB déjà câblé.

## Stack pressenti (briques existantes, à reconfirmer au moment du design)

Aucun choix figé, mais voici la direction qui colle aux principes
"simple + briques off-the-shelf + apprend en s'imprégnant" :

| Couche                 | Brique pressentie                                                | Pourquoi                                                |
| ---------------------- | ---------------------------------------------------------------- | ------------------------------------------------------- |
| Front universel        | **MCP server** (FastMCP, SDK Python officiel)                    | Standard 2026, n'importe quel client MCP marche         |
| Front chat tout-en-un  | **Open WebUI** (déjà déployé)                                    | Gratuit, zéro UI à écrire pour démarrer                 |
| Front intégré projet   | Chat embarqué + actions contextuelles dans la Web UI custom (P2) | Expérience maison cohérente                             |
| Outils MCP             | Une fonction Python `@mcp.tool()` par cas d'usage                | Granularité fine (un outil par phase, un par reco type) |
| Base vectorielle (RAG) | **`sqlite-vec`** dans `indexer.db` existant                      | Pas de nouveau service à installer                      |
| Embeddings             | Modèle local via **Ollama** (ex. `nomic-embed-text`)             | Gratuit, local, déjà installé sur le serveur            |
| LLM                    | Modèles Ollama local + option remote via Open WebUI              | Open WebUI gère le routing                              |
| **Non retenu**         | LangChain / LlamaIndex / LiteLLM                                 | Sur-dimensionné pour ce besoin                          |
| **Non retenu**         | Chroma / Qdrant / autre service vectoriel séparé                 | sqlite-vec suffit pour cette échelle                    |
| **Non retenu**         | Fine-tuning / LoRA                                               | Principe directeur                                      |

Le travail concret se résume probablement à : un MCP server Python avec
6-8 outils, une table vectorielle dans `indexer.db`, une commande
d'indexation initiale, et des deep-links depuis la future Web UI custom
pour ouvrir Open WebUI avec un contexte pré-rempli (en attendant le chat
maison).

## Questions ouvertes

À retrancher quand le moment de l'implémentation arrivera :

- **Backend LLM** — local-only (Ollama) vs. distant (Anthropic/OpenAI) vs.
  les deux ? Probablement les deux, choix utilisateur dans `config/llm.json5`.
- **Modèle d'embeddings** — `nomic-embed-text` ou `mxbai-embed-large` via
  Ollama ? Le choix sera tranché en bench au moment du design.
- **Stockage du log de corrections** — table dédiée dans `indexer.db` ?
  fichier séparé ? Cohérence avec le RAG plaide pour `indexer.db`.
- **Indexation initiale de la médiathèque** — sur une grosse biblio ça
  peut prendre du temps. Commande `personalscraper llm reindex` avec
  barre de progression, idempotente, incrémentale. Cron de
  ré-indexation périodique optionnel.
- **Confidentialité sur backend distant** — si l'utilisateur active un LLM
  remote, on ne pousse jamais de chemins absolus ni de noms de fichiers
  bruts. Anonymisation/normalisation au passage au MCP server. Politique
  à formaliser.
- **Politique de purge du log** — combien de corrections garder ?
  rotation par âge ? par pertinence ? Probablement par âge + cap absolu.
- **Granularité des outils MCP** — un outil par phase de pipeline (clair
  mais surface plus large) vs. outil générique avec paramètre `phase`
  (plus compact mais moins découvrable côté client MCP).
- **Couplage Web UI custom** — quand la Web UI custom existera, on
  embarque un chat maison (cohérence) ou on iframe Open WebUI (gratuit) ?

## Pré-requis probables (à confirmer au moment où on s'y met)

Aujourd'hui ces dépendances semblent naturelles, mais l'archi du projet va
encore beaucoup bouger d'ici là :

- Event Bus (P1) — pour s'abonner aux événements pipeline et nourrir
  les outils MCP de tendances.
- Provider Registry (P1) — pour exposer l'IA comme provider tertiaire
  dans le scraper orchestrator (optionnel).
- Library Indexer (✅) — corpus structuré déjà disponible pour le RAG +
  hôte naturel pour `sqlite-vec`.
- Web Management UI (P2) — hôte du chat embarqué et des actions
  contextuelles. Avant qu'elle existe, Open WebUI tient le rôle de front.

Si ces pièces ont changé de forme d'ici l'implémentation, on s'adaptera.

## Non-engagements

- Aucune décision d'archi figée ici (le stack pressenti est une
  direction, pas un engagement).
- Aucune liste de commandes CLI figée.
- Aucun planning.
- Aucun fine-tuning, jamais (principe directeur).
- Pas de mode proactif/inline dans le pipeline (principe directeur).
- Pas d'intégration Plex watch history en v1 (sort du périmètre).

## Journal

- **2026-05-11** — Création du document. Idée brute capturée : assistant IA
  pour scraping/post-mortem, apprentissage par RAG de la médiathèque +
  corrections utilisateur, jamais autonome. RAG-only verrouillé, pas de
  fine-tuning. Simplicité d'implémentation érigée en principe directeur.

- **2026-05-11** — Brainstorming approfondi (5 questions).
  Décisions :
  - Mode **à la demande uniquement** (jamais proactif/inline).
  - Front : **MCP server** comme backend universel (marche avec Open WebUI,
    Claude Code, etc.) + chat embarqué dans la future Web UI custom + actions
    contextuelles. Permet de démarrer sans front custom (Open WebUI suffit)
    et d'enrichir plus tard.
  - Cas d'usage pipeline : match ambigu, **post-mortem par phase** (un
    outil MCP par étape), incohérences, tendances.
  - Cas d'usage médiathèque : recommandations **nettoyage + complétion +
    découverte**. Plex watch history écarté en v1.
  - Stack pressenti : FastMCP + sqlite-vec dans indexer.db + Ollama
    embeddings + Ollama LLM (option remote via Open WebUI). Pas de
    LangChain/LlamaIndex/LiteLLM.
  - Trois questions ouvertes ajoutées : log de corrections (stockage),
    indexation initiale (perf grosse biblio), confidentialité backend
    distant (anonymisation).
