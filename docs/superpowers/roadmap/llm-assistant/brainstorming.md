# Brainstorming — LLM Pipeline Assistant

> **Statut** : Idée. Item P3 de la roadmap, gardé pour la fin.
> **Document vivant** — capture l'intention et les questions ouvertes, pas l'implémentation.
> Les choix techniques (modèle, backend, format de stockage, intégrations) seront
> tranchés au moment du `/implement:feature`, quand le reste du projet aura évolué.

## Pourquoi

Beaucoup d'étapes du pipeline (surtout scraping) requièrent aujourd'hui un
arbitrage humain manuel : matches ambigus TMDB/TVDB, scores fuzzy borderline,
erreurs récurrentes qu'on corrige toujours de la même façon. L'idée : qu'une
IA observe ces décisions et finisse par les proposer elle-même — sans jamais
agir sans validation.

## Principes directeurs

- **Simple à implémenter** — feature volontairement minimaliste. Pas
  d'architecture sophistiquée, pas de framework lourd. Si une option ajoute
  une semaine de dev pour 5 % de qualité en plus, on la coupe.
- **Efficace** — l'utilisateur doit sentir un vrai gain dès les premières
  utilisations, sinon la feature ne sert à rien.
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
  déterministes ne tranchent pas (matches ambigus, post-mortem d'erreurs,
  détection d'incohérences subtiles que les checkers ratent). Les scrapers
  classiques restent la voie principale.
- **Reste en retrait** — pas d'auto-application, pas d'intervention
  pendant l'exécution du pipeline (post-step seulement).

## Cas d'usage visés

- **Désambiguïsation de match** — plusieurs candidats TMDB plausibles → l'IA
  classe avec son raisonnement.
- **Post-mortem de run** — un `personalscraper run` échoue → l'IA digère
  les rapports et événements, propose un diagnostic et la commande de
  reprise probable.
- **Détection d'incohérences** — NFO genre vs. catégorie de dossier, dérive
  d'année, langue audio incohérente avec l'origine d'une série.
- **Analyse de tendances** — sur N derniers runs : provider qui échoue
  systématiquement, étape lente, tempête de retries → suggestions de tuning
  config.

## Questions ouvertes

À retrancher quand le moment de l'implémentation arrivera :

- Backend LLM : local-only (Ollama) vs. remote (Anthropic/OpenAI) vs. les
  deux ? Dépend des modèles dispo et du coût au moment où on s'y met.
- Modèle d'embeddings pour le RAG : local (ex. `nomic-embed-text` via
  Ollama) ou hosted ? Local préféré pour la simplicité.
- Stockage de la base vectorielle : SQLite + extension vectorielle (sqlite-vec) ?
  fichier dédié ? table dans l'indexer existant ? Privilégier ce qui
  réutilise ce qui existe déjà.
- Granularité de l'intervention : on confirme post-step only. À acter au
  moment du design.
- Couplage à la Web UI vs. CLI-only en v1 ? CLI-only probablement.
- Format du correction log : à décider quand on connaîtra l'archi indexer
  du moment.
- Politique de purge : combien de corrections garder ? rotation ?
- Confidentialité : si backend distant, qu'envoie-t-on ? pas de chemins
  absolus, pas de noms de fichiers complets ?

## Pré-requis probables (à confirmer au moment où on s'y met)

Aujourd'hui ces dépendances semblent naturelles, mais l'archi du projet va
encore beaucoup bouger d'ici là :

- Event Bus (P1) — pour s'abonner aux événements pipeline.
- Provider Registry (P1) — pour brancher l'IA en provider tertiaire.
- Library Indexer (✅) — corpus structuré déjà disponible pour le RAG.

Si ces pièces ont changé de forme d'ici l'implémentation, on s'adaptera.

## Non-engagements

- Aucune décision d'archi figée ici.
- Aucune liste de commandes CLI figée ici.
- Aucun planning.
- Aucun fine-tuning, jamais (principe directeur).

## Journal

- **2026-05-11** — Création du document. Idée brute capturée : assistant IA
  pour scraping/post-mortem, apprentissage par RAG de la médiathèque +
  corrections utilisateur, jamais autonome. RAG-only verrouillé, pas de
  fine-tuning. Simplicité d'implémentation érigée en principe directeur.
