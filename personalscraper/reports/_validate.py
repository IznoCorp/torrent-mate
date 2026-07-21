"""STEP_REPORT_CONTRACT validation helpers.

Load-bearing CROSS-CUTTING-01 enforcement: validates that a step's
``details_payload`` matches the declared type for that step. A step that
attaches the wrong payload type fails loud rather than shipping silently.
"""

from __future__ import annotations

import dataclasses

from personalscraper.models import StepReport


class StepReportContractError(Exception):
    """Raised when a step's ``details_payload`` violates ``STEP_REPORT_CONTRACT``.

    The ``STEP_REPORT_CONTRACT`` validation is load-bearing (CROSS-CUTTING-01):
    when a step produces a ``details_payload``, it MUST be the typed dataclass
    (or its flattened ``dict``) declared for that step. A step that attaches the
    wrong payload type — a copy-paste bug wiring, e.g. ``IngestDetails`` onto the
    ``sort`` step — fails loud here rather than silently shipping a mistyped
    envelope. The message always carries the offending step name.

    A step that produces *no* payload (fast-skip, crash-synthesised, or a
    framework-synthesised skip report) is not an error — the honest empty typed
    payload is attached instead (see :func:`validate_details_payload`).
    """


def validate_details_payload(
    name: str,
    step_report: StepReport,
    step_report_contract: dict[str, type],
) -> StepReport:
    """Validate and normalise a step's ``details_payload`` against the contract.

    Load-bearing ``STEP_REPORT_CONTRACT`` enforcement (CROSS-CUTTING-01):

    * **Populated payload** — when the step produced per-step data (the 9
      ``run_*`` finalizers each build their typed ``Details`` dataclass), the
      payload's shape is checked against the declared type. A dataclass of the
      wrong class, or a ``dict`` whose keys don't match the declared
      dataclass fields, raises :class:`StepReportContractError` naming the
      step — a mistyped envelope fails loud instead of shipping silently.
    * **No payload** — a fast-skip, crash-synthesised, or framework
      skip-report leaves ``details_payload`` ``None``; the honest empty typed
      payload is attached so the field stays contract-shaped. This path is
      not an error (a crashed or no-op step has no per-item data to report).

    In every case the stored value is normalised to a JSON-safe
    ``dict[str, Any]`` via :func:`dataclasses.asdict` for envelope round-trip.

    Args:
        name: Step identifier used to look up the declared payload type.
        step_report: The step's report; its ``details_payload`` is validated
            and normalised in place.
        step_report_contract: Mapping of step name → declared payload dataclass
            type (typically ``STEP_REPORT_CONTRACT``).

    Returns:
        The same ``step_report`` with a contract-shaped ``details_payload``.

    Raises:
        StepReportContractError: If the step is under contract and produced a
            payload whose type/shape does not match the declared dataclass.
    """
    payload_type = step_report_contract.get(name)
    if payload_type is None:
        # Step not under contract — nothing to attach or validate.
        return step_report

    payload = step_report.details_payload
    if payload is None:
        # No per-step data (fast-skip / crash-synth / no-op): the honest
        # empty typed payload keeps the field contract-shaped.
        step_report.details_payload = dataclasses.asdict(payload_type())
        return step_report

    # A populated payload is LOAD-BEARING — it must match the declared type.
    if dataclasses.is_dataclass(payload) and not isinstance(payload, type):
        if not isinstance(payload, payload_type):
            raise StepReportContractError(
                f"step {name!r}: details_payload is {type(payload).__name__}, expected {payload_type.__name__}"
            )
        step_report.details_payload = dataclasses.asdict(payload)
        return step_report

    if isinstance(payload, dict):
        expected = {f.name for f in dataclasses.fields(payload_type)}
        actual = set(payload.keys())
        if actual != expected:
            raise StepReportContractError(
                f"step {name!r}: details_payload keys {sorted(actual)} do not match "
                f"{payload_type.__name__} fields {sorted(expected)}"
            )
        return step_report

    raise StepReportContractError(
        f"step {name!r}: details_payload has unsupported type {type(payload).__name__} "
        f"(expected {payload_type.__name__} or a matching dict)"
    )
