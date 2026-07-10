"""Static scheduler registry — the cron jobs that drive the pipeline off-schedule.

The web process is **separate** from the PM2 daemon that runs the scheduled
personalscraper jobs, and the PM2 ``ecosystem.config.js`` (in ``~/dev/``) is NOT
deployed alongside the repo. So the web layer must NOT shell out to ``pm2`` nor
read ``ecosystem.config.js`` at request time. Instead this module hard-codes a
**static mirror** of the scheduled personalscraper crons: for each job, its
display name, its human-readable cron schedule string, and — crucially — the
``pipeline_run`` match rule (``kind`` + ``command``) used to look up its last run.

Ground truth (verified 2026-07-10 against the live ``library.db`` + the
``cli_step_journal`` wiring):

- The **watcher** (``personalscraper-watch``) is a long-running daemon, not a
  cron — it is surfaced separately by the route (enabled = ¬``watcher.paused``
  sentinel; last run = ``acquire.db`` ``watch_state.last_successful_run_at``).
- The three crons here (``follow detect``, ``grab``, ``library-index --mode
  enrich``) currently write **no** ``pipeline_run`` row — only the pipeline STEP
  commands wrap ``cli_step_journal`` (``ingest``/``sort``/…), and the full
  ``run`` path writes its own row. So each cron's ``pipeline_run`` lookup returns
  nothing today ⇒ the route surfaces it with ``last_run_at=None`` (fail-soft, the
  designed behaviour). The match rule is nonetheless declared so that if a cron
  ever gains a ``pipeline_run`` row (e.g. a future ``cli_step_journal`` wrap of
  ``follow``/``grab``/``library-index``), the last-run surfaces automatically
  with no route change.

The match rule matches ``pipeline_run`` rows by ``kind`` (always ``'pipeline'``
for these CLI jobs) plus a ``command`` **prefix** — the CLI-step journal stores
``command`` as the bare step name (e.g. ``'ingest'``), and a future cron wrap
would likewise store its command name; the prefix keeps the rule tolerant of a
sub-command suffix (``follow`` matches a hypothetical ``follow-detect`` command).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CronJob:
    """A single scheduled personalscraper cron job (static definition).

    Attributes:
        name: Stable machine identifier, matching the PM2 process name
            (e.g. ``"personalscraper-follow-detect"``). Used as the row key
            in the API response — never localised.
        display_name: Human-readable French label for the Dashboard panel
            (e.g. ``"Détection de suivis"``).
        schedule: Human-readable schedule string mirroring the PM2
            ``cron_restart`` expression (e.g. ``"Tous les jours à 03:00"``).
        command_prefix: The ``pipeline_run.command`` prefix identifying this
            job's rows. Combined with ``kind='pipeline'`` to look up the last
            run. When no row matches (the current reality), the route surfaces
            ``last_run_at=None``.
    """

    name: str
    display_name: str
    schedule: str
    command_prefix: str


#: The scheduled personalscraper crons, mirroring the PM2 ``ecosystem.config.js``
#: definitions (verified against ``pm2 jlist`` 2026-07-10). Ordered by first
#: daily fire time. The ``personalscraper-watch`` daemon is intentionally absent
#: — it is a long-running process, surfaced by the route as the ``watcher`` row.
CRON_JOBS: tuple[CronJob, ...] = (
    CronJob(
        name="personalscraper-follow-detect",
        display_name="Détection de suivis",
        schedule="Tous les jours à 03:00",
        command_prefix="follow",
    ),
    CronJob(
        name="personalscraper-grab",
        display_name="Récupération (grab)",
        schedule="Tous les jours à 03:20 et 15:20",
        command_prefix="grab",
    ),
    CronJob(
        name="personalscraper-index-enrich",
        display_name="Enrichissement de l'index",
        schedule="Le dimanche à 04:30",
        command_prefix="library-index",
    ),
)
