"""The ``pipeline`` tag's routes: asking a run."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.services import AppServices
from personalscraper.app.supervisor.model import RunOptions, RunTrigger
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.pipeline import RunAnswer

router = APIRouter()


@router.post(
    "/pipeline/run",
    operation_id="runPipeline",
    response_model=RunAnswer,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def run_pipeline(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> RunAnswer:
    """Ask a pipeline run: queued visibly, or joined to the equal one already waiting.

    The process starts nothing: the supervisor's lease is the only authority that admits
    a queued request, so the answer is ``queued`` (or ``running`` for a request already
    admitted), never ``idle``.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The state of the request answering the ask, and its uid.

    Raises:
        AppForbidden: ``right.missing``, ``instance.forbidden_write`` before anything is queued.
    """
    asked = app_services.runs.ask_run(signed_in, trigger=RunTrigger.WEB, options=RunOptions())
    return RunAnswer(state=asked.state, uid=asked.uid)
