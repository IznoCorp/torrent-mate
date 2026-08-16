# Brainstorming — LLM Pipeline Assistant

> **Status**: Idea. P3 roadmap item, kept for last.
> **Living document** — captures the intent and the open questions, not the implementation.
> Technical choices (model, backend, storage format, integrations) will be
> settled at `/implement:feature` time, once the rest of the project has evolved.

## Why

Many pipeline steps (scraping above all) currently require manual human
arbitration: ambiguous TMDB/TVDB matches, borderline fuzzy scores, recurring
errors that always get corrected the same way. In parallel, the media library
accumulates content we no longer know what to do with (duplicates, abandoned
series, movies never watched, incomplete trilogies). The idea: an AI assistant,
callable on demand, to help with the pipeline AND with library management —
without ever acting without validation.

## Guiding Principles

- **Simple to implement** — deliberately minimalist feature. No
  sophisticated architecture, no heavy framework. Off-the-shelf building
  blocks only; we do not write custom AI.
- **Effective** — the user must feel a real gain from the very first
  uses.
- **On demand only** — the AI never invites itself. No proactive/inline
  intervention in the pipeline, no cron pushing unsolicited analyses.
  The user calls, the AI answers.
- **Never autonomous** — every action the AI proposes remains validated by
  the user (CLI or Web UI).
- **RAG only, no fine-tuning** — learning happens exclusively through
  context retrieval (library corpus + correction log).
  No weight training, no LoRA, no GPU dependency.

## Vision

An assistant that:

- **Knows the library** — it soaks up the existing content (what is
  already well organized, the naming patterns, the recurring genres, the
  audio languages per category) to understand "what a normal entry looks
  like here". This knowledge lives in a vector store, not in
  the model.
- **Learns from corrections** — every time the user accepts,
  modifies or rejects a suggestion, it is added to the corpus. On the next
  query, the most similar past corrections are retrieved and
  injected few-shot into the prompt. Over the weeks, the
  proposals converge toward the user's actual choices — without
  touching the model.
- **Helps without replacing** — it steps in where deterministic
  heuristics cannot decide. The classic scrapers remain the primary
  path; the AI is a consultative fallback.
- **Stays in the background** — no auto-apply, no intervention
  during pipeline execution.

## Targeted Use Cases

### Pipeline side (on demand)

- **Match disambiguation** — several plausible TMDB/TVDB candidates
  → the AI ranks them with its reasoning.
- **Per-phase post-mortem** — for each pipeline step (ingest, sort,
  process, dispatch, verify, trailers), a dedicated tool that digests the
  phase report and proposes a diagnosis + likely recovery
  command. Granular rather than a single generic tool.
- **Inconsistency detection** — cross-scan of indexer/FS for subtle
  anomalies the checkers miss (NFO genre vs. folder category,
  year drift, audio language inconsistent with a series' origin).
- **Trend analysis** — over the last N runs: provider failing
  systematically, slow step, retry storm → config tuning
  suggestions.

### Library side (on demand)

- **Cleanup recommendations** — duplicates, abandoned series (season 1
  with no follow-up for X years), movies never finalized, low-quality
  versions to upgrade.
- **Completion recommendations** — missing seasons, movies from an
  incomplete trilogy, sequels/prequels to a movie we own, other works
  by a director already well represented.
- **Discovery recommendations** — based on the library's patterns
  ("you have 20 Korean thrillers, here are 5 you don't have"),
  cross-referenced with the TMDB/TVDB catalog already wired in.

## Anticipated Stack (existing building blocks, to reconfirm at design time)

No choice is set in stone, but here is the direction that fits the
"simple + off-the-shelf blocks + learns by soaking up" principles:

| Layer                  | Anticipated building block                                       | Why                                                     |
| ---------------------- | ---------------------------------------------------------------- | ------------------------------------------------------- |
| Universal front        | **MCP server** (FastMCP, official Python SDK)                    | 2026 standard, any MCP client works                     |
| All-in-one chat front  | **Open WebUI** (already deployed)                                | Free, zero UI to write to get started                   |
| Project-integrated front | Embedded chat + contextual actions in the custom Web UI (P2)   | Consistent home-grown experience                        |
| MCP tools              | One Python `@mcp.tool()` function per use case                   | Fine granularity (one tool per phase, one per reco type) |
| Vector store (RAG)     | **`sqlite-vec`** inside the existing `indexer.db`                | No new service to install                               |
| Embeddings             | Local model via **Ollama** (e.g. `nomic-embed-text`)             | Free, local, already installed on the server            |
| LLM                    | Local Ollama models + remote option via Open WebUI               | Open WebUI handles the routing                          |
| **Rejected**           | LangChain / LlamaIndex / LiteLLM                                 | Oversized for this need                                 |
| **Rejected**           | Chroma / Qdrant / other separate vector service                  | sqlite-vec is enough at this scale                      |
| **Rejected**           | Fine-tuning / LoRA                                               | Guiding principle                                       |

The concrete work probably boils down to: a Python MCP server with
6-8 tools, a vector table in `indexer.db`, an initial indexing
command, and deep links from the future custom Web UI
to open Open WebUI with pre-filled context (until the home-grown
chat exists).

## Open Questions

To be settled when implementation time comes:

- **LLM backend** — local-only (Ollama) vs. remote (Anthropic/OpenAI) vs.
  both? Probably both, user choice in `config/llm.json5`.
- **Embeddings model** — `nomic-embed-text` or `mxbai-embed-large` via
  Ollama? The choice will be settled by a benchmark at design time.
- **Correction log storage** — dedicated table in `indexer.db`?
  separate file? Consistency with the RAG argues for `indexer.db`.
- **Initial library indexing** — on a large library this can
  take a while. `personalscraper llm reindex` command with a
  progress bar, idempotent, incremental. Optional periodic
  re-indexing cron.
- **Privacy on a remote backend** — if the user enables a remote
  LLM, we never push absolute paths or raw file
  names. Anonymization/normalization on the way into the MCP server. Policy
  to be formalized.
- **Log purge policy** — how many corrections to keep?
  rotation by age? by relevance? Probably by age + absolute cap.
- **MCP tool granularity** — one tool per pipeline phase (clear
  but larger surface) vs. a generic tool with a `phase` parameter
  (more compact but less discoverable on the MCP client side).
- **Custom Web UI coupling** — once the custom Web UI exists, do we
  embed a home-grown chat (consistency) or iframe Open WebUI (free)?

## Likely Prerequisites (to confirm when we get to it)

Today these dependencies feel natural, but the project's architecture will
still move a lot between now and then:

- Event Bus (P1) — to subscribe to pipeline events and feed the
  trend MCP tools.
- Provider Registry (P1) — to expose the AI as a tertiary provider
  in the scraper orchestrator (optional).
- Library Indexer (✅) — structured corpus already available for the RAG +
  natural host for `sqlite-vec`.
- Web Management UI (P2) — host of the embedded chat and contextual
  actions. Until it exists, Open WebUI plays the front role.

If these pieces have changed shape by implementation time, we will adapt.

## Non-commitments

- No architecture decision locked in here (the anticipated stack is a
  direction, not a commitment).
- No frozen CLI command list.
- No schedule.
- No fine-tuning, ever (guiding principle).
- No proactive/inline mode in the pipeline (guiding principle).
- No Plex watch history integration in v1 (out of scope).

## Journal

- **2026-05-11** — Document created. Raw idea captured: AI assistant
  for scraping/post-mortem, learning via RAG over the library +
  user corrections, never autonomous. RAG-only locked in, no
  fine-tuning. Implementation simplicity elevated to a guiding principle.

- **2026-05-11** — In-depth brainstorming (5 questions).
  Decisions:
  - **On-demand only** mode (never proactive/inline).
  - Front: **MCP server** as the universal backend (works with Open WebUI,
    Claude Code, etc.) + embedded chat in the future custom Web UI + contextual
    actions. Allows starting without a custom front (Open WebUI is enough)
    and enriching later.
  - Pipeline use cases: ambiguous match, **per-phase post-mortem** (one
    MCP tool per step), inconsistencies, trends.
  - Library use cases: **cleanup + completion + discovery**
    recommendations. Plex watch history set aside for v1.
  - Anticipated stack: FastMCP + sqlite-vec in indexer.db + Ollama
    embeddings + Ollama LLM (remote option via Open WebUI). No
    LangChain/LlamaIndex/LiteLLM.
  - Three open questions added: correction log (storage),
    initial indexing (large-library perf), remote backend
    privacy (anonymization).
