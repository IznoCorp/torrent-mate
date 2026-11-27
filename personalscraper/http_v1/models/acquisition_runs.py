"""The ``acquisition`` tag's run bodies: the passes asked, the season taken and the schedule.

Every pass asked is queued in the supervisor: an answer names the request (``runUid``), never a result.
"""

from __future__ import annotations

from pydantic import Field

from personalscraper.app.acquisition.seasons import SeasonAsked
from personalscraper.app.acquisition.triggers import AcquisitionSchedule
from personalscraper.http_v1.contract import ContractModel


class DetectionLaunched(ContractModel):
    """The contract's ``runDetection`` answer.

    Attributes:
        run_uid: The request answering the ask, whose figures are read from the run.
    """

    run_uid: str


class GrabLaunched(ContractModel):
    """The contract's ``grabForFollow`` answer.

    Attributes:
        run_uid: The request answering the ask. The contract lets ``null`` through (the maquette's mock
            holds no runner); the service always names one.
    """

    run_uid: str | None


class SearchQueued(ContractModel):
    """The contract's ``searchForFollow`` answer (O-6 B): the search is « en file ».

    What it found is read afterwards, from the follow and its releases.

    Attributes:
        queued: The search waits in the supervisor's queue.
        run_uid: The request answering the ask.
    """

    queued: bool
    run_uid: str


class GrabReleaseBody(ContractModel):
    """The contract's ``grabForFollow`` body, optional.

    Attributes:
        release_id: The chosen release, by its ``Release.id``; absent, the grab takes what the last
            search marked takeable.
    """

    release_id: str | None = None


class SeasonGrabbed(ContractModel):
    """The contract's ``grabSeasonForFollow`` answer, on its 201 and its 200.

    Attributes:
        season: The season asked.
        absorbed_count: Its aired episodes the library does not hold.
        queued: Whether a pass of its subject was asked of the supervisor.
        run_uid: That request's uid; ``None`` when none was asked (a season already being recovered
            that the ask did not turn on, or an ask the supervisor refused).
        reused: Whether the season was already being recovered (a 200); false on a 201.
    """

    season: int
    absorbed_count: int
    queued: bool
    run_uid: str | None
    reused: bool

    @classmethod
    def from_asked(cls, asked: SeasonAsked) -> SeasonGrabbed:
        """Map the service's answer.

        Args:
            asked: What the season ask answered.

        Returns:
            The body.
        """
        return cls(
            season=asked.season,
            absorbed_count=asked.absorbed_count,
            queued=asked.queued,
            run_uid=asked.run_uid,
            reused=asked.reused,
        )


class AcquisitionStatusModel(ContractModel):
    """The contract's ``readAcquisitionStatus`` answer.

    Attributes:
        cadence: The cron the grab pass runs on.
        next_search: When the next search runs, ISO 8601 with its offset; ``None`` on an instance that
            schedules none.
    """

    cadence: str = Field(description="the cron expression the scheduler runs on")
    next_search: str | None = Field(description="when the next search runs")

    @classmethod
    def from_schedule(cls, schedule: AcquisitionSchedule) -> AcquisitionStatusModel:
        """Map the service's schedule.

        Args:
            schedule: The schedule.

        Returns:
            The body.
        """
        return cls(cadence=schedule.cadence, next_search=schedule.next_search)
