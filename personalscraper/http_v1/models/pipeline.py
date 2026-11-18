"""The ``pipeline`` tag's bodies."""

from __future__ import annotations

from typing import Literal

from personalscraper.http_v1.contract import ContractModel


class RunAnswer(ContractModel):
    """``runPipeline``'s answer (the contract's ``POST /pipeline/run`` 200).

    Attributes:
        state: The contract's ``PipelineState``: what the request answering the ask stands at.
        uid: The request's uid, which becomes the run's ``pipeline_run.run_uid`` once admitted.
    """

    state: Literal["idle", "running", "queued", "paused", "stopping"]
    uid: str
