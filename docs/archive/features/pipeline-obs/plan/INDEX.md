# Pipeline Observer Protocol — Implementation Plan

> **For agentic workers:** Each phase = independently completable. Sub-phases execute inline.
> Sub-phase steps use checkbox (`- [ ]`) syntax for tracking.
> **NO DEFERRAL — every sub-phase is fully implemented within its phase. No step is skipped.**

**Goal:** Decouple the pipeline from `rich.Console` via a `PipelineObserver` Protocol. Extract all console output into `RichConsoleObserver`. Wire `on_progress` per-item events into all 9 pipeline steps.

**Architecture:**

1. `PipelineObserver` Protocol (6 methods) + `StepEvent` dataclass in `pipeline_observer.py`
2. `RichConsoleObserver` and `TelegramObserver` in `observers/` package
3. `StepContext.console` replaced by `observers: tuple[PipelineObserver, ...]`
4. `Pipeline.__init__` accepts `observers` (default: `[RichConsoleObserver()]`)
5. `_run_step` notifies observers; steps emit per-item `on_progress` events
6. CLI wires observers together in `commands/pipeline.py`

**Tech Stack:** Python 3.11+, rich, structlog, pytest

---

## Phases

| #   | Phase                                               | Type  | File                                                                     | Status |
| --- | --------------------------------------------------- | ----- | ------------------------------------------------------------------------ | ------ |
| 1   | Protocol foundation                                 | core  | [phase-01-protocol-foundation.md](phase-01-protocol-foundation.md)       | [ ]    |
| 2   | RichConsoleObserver                                 | core  | [phase-02-rich-console-observer.md](phase-02-rich-console-observer.md)   | [ ]    |
| 3   | TelegramObserver                                    | core  | [phase-03-telegram-observer.md](phase-03-telegram-observer.md)           | [ ]    |
| 4   | StepContext + Pipeline core refactor                | core  | [phase-04-pipeline-core.md](phase-04-pipeline-core.md)                   | [ ]    |
| 5   | CLI wiring                                          | wire  | [phase-05-cli-wiring.md](phase-05-cli-wiring.md)                         | [ ]    |
| 6   | Step integration — ingest + sort                    | steps | [phase-06-ingest-sort.md](phase-06-ingest-sort.md)                       | [ ]    |
| 7   | Step integration — process + scrape                 | steps | [phase-07-process-scrape.md](phase-07-process-scrape.md)                 | [ ]    |
| 8   | Step integration — enforce + verify                 | steps | [phase-08-enforce-verify.md](phase-08-enforce-verify.md)                 | [ ]    |
| 9   | Step integration — trailers + dispatch + final gate | steps | [phase-09-trailers-dispatch-gate.md](phase-09-trailers-dispatch-gate.md) | [ ]    |

## NO DEFERRAL

**Every phase produces complete, working code. Every test is written. Every step
is adapted. Nothing is left for "later". This mandate is repeated in every phase
file and every sub-phase report.**
