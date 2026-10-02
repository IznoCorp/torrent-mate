"""Static scheduler registry — the cron jobs that drive the pipeline off-schedule.

The web process is **separate** from the PM2 daemon that runs the scheduled
personalscraper jobs, and the PM2 ``ecosystem.config.js`` (in ``~/dev/``) is NOT
deployed alongside the repo. So the web layer must NOT shell out to ``pm2`` nor
read ``ecosystem.config.js`` at request time. Instead this module hard-codes a
**static mirror** of the scheduled personalscraper crons: for each job, its
display name, its human-readable cron schedule string, and — crucially — the
``pipeline_run`` command-prefix match rule used to look up its last run.

Ground truth (verified 2026-07-15 against the live ``library.db`` + the
``cli_run_row`` wiring):

- The **watcher** (``personalscraper-watch``) is a long-running daemon, not a
  cron — it is surfaced separately by the route (enabled = ¬``watcher.paused``
  sentinel; last run = ``acquire.db`` ``watch_state.last_successful_run_at``).
- The three crons here (``follow detect``, ``grab``, ``library-index --mode
  enrich``) each write a ``pipeline_run`` row via ``cli_run_row`` with
  ``kind='maintenance'`` and ``command`` set to ``'follow-detect'`` /
  ``'grab'`` / ``'library-index'``. A cron that has never fired simply has no
  row ⇒ the route surfaces ``last_run_at=None`` (fail-soft, the designed
  behaviour).

The match rule matches ``pipeline_run`` rows by ``command`` **prefix ALONE**
(kind-agnostic — see ``_cron_last_run`` in ``web/routes/maintenance.py``): a
cron's run is identified by what it ran, not by its ``kind``, and the
acquisition CLIs record ``kind='maintenance'`` rows. The prefix keeps the rule
tolerant of a sub-command suffix (``follow`` matches ``follow-detect``).
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
            job's rows (matched kind-agnostic by ``_cron_last_run``). When no
            row matches (a cron that has never fired), the route surfaces
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
