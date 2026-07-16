"""Unit tests for the declarative :data:`STEP_SPECS` driver (solidify P1.5).

Covers spec/registry/contract/catalog agreement, ordering, adapter mapping and
the import-time :func:`_validate_step_specs` guard. The spec list is the single
declarative source ``Pipeline.run()`` iterates; these tests pin the invariants
that keep "adding a step" a three-seam change (adapter + spec + reports
dataclass) and prevent silent drift between the four registries.
"""

from __future__ import annotations

import pytest

from personalscraper.pipeline_steps import (
    DEFAULT_STEPS,
    STEP_SPECS,
    StepSkip,
    StepSpec,
    StepSpecError,
    _validate_step_specs,
)
from personalscraper.reports import (
    STEP_REPORT_CONTRACT,
    IngestDetails,
    SortDetails,
)


class TestStepSpecOrdering:
    """The spec list mirrors the step registry order exactly."""

    def test_step_spec_names_equal_default_steps_order(self) -> None:
        """``[s.name for s in STEP_SPECS]`` equals ``list(DEFAULT_STEPS)``."""
        assert [spec.name for spec in STEP_SPECS] == list(DEFAULT_STEPS)

    def test_step_spec_has_nine_entries(self) -> None:
        """The pipeline is nine steps; the spec list carries exactly nine."""
        assert len(STEP_SPECS) == 9


class TestStepSpecKeySetAgreement:
    """DEFAULT_STEPS / STEP_SPECS / STEP_REPORT_CONTRACT key-sets agree."""

    def test_step_spec_registry_contract_key_sets_agree(self) -> None:
        """The three engine registries expose the same step names (P1.5 item 4)."""
        spec_names = {spec.name for spec in STEP_SPECS}
        assert spec_names == set(DEFAULT_STEPS) == set(STEP_REPORT_CONTRACT)

    def test_step_spec_payload_type_matches_contract(self) -> None:
        """Every spec's ``payload_type`` is the contract's declared dataclass."""
        for spec in STEP_SPECS:
            assert spec.payload_type is STEP_REPORT_CONTRACT[spec.name]

    def test_step_spec_adapter_is_registry_adapter(self) -> None:
        """Every spec's ``adapter`` is the identical ``DEFAULT_STEPS`` instance."""
        for spec in STEP_SPECS:
            assert spec.adapter is DEFAULT_STEPS[spec.name]


class TestStepSpecStageCatalogAgreement:
    """Every spec name is a key of the web stage catalog (the SoT)."""

    def test_every_step_spec_name_in_stage_catalog(self) -> None:
        """``STEP_SPECS`` names are all present in ``STEP_TO_STAGE`` (unaltered SoT)."""
        from personalscraper.web.staging.stages import STEP_TO_STAGE

        spec_names = {spec.name for spec in STEP_SPECS}
        assert spec_names <= set(STEP_TO_STAGE)
        # The catalog carries exactly the nine engine steps — no more, no less.
        assert spec_names == set(STEP_TO_STAGE)


class TestStepSpecFlags:
    """Per-step flags encode the pipeline's abort / extras / skip policy."""

    def test_only_ingest_and_sort_are_critical(self) -> None:
        """Critical steps (abort-on-crash) are exactly ingest and sort."""
        critical = {spec.name for spec in STEP_SPECS if spec.critical}
        assert critical == {"ingest", "sort"}

    def test_only_verify_exposes_an_extras_key(self) -> None:
        """``verify`` is the only step that publishes an extra (its verified list)."""
        keyed = {spec.name: spec.extras_key for spec in STEP_SPECS if spec.extras_key is not None}
        assert keyed == {"verify": "verified"}

    def test_only_dispatch_declares_a_skip_predicate(self) -> None:
        """Dispatch is the only spec with a ``skip_when`` predicate."""
        skippable = {spec.name for spec in STEP_SPECS if spec.skip_when is not None}
        assert skippable == {"dispatch"}


class TestDispatchSkipPredicate:
    """The dispatch ``skip_when`` skips when verify yielded no items."""

    def _dispatch_skip(self) -> StepSkip:
        spec = next(spec for spec in STEP_SPECS if spec.name == "dispatch")
        assert isinstance(spec.skip_when, StepSkip)
        return spec.skip_when

    def test_skip_reason_is_operator_facing(self) -> None:
        """The skip reason is the load-bearing 'no verified items' phrase."""
        assert self._dispatch_skip().reason == "no verified items"

    def test_skips_when_no_verified_items(self) -> None:
        """An empty ``verified`` list makes the predicate return True."""
        ctx = _FakeCtx({"verified": []})
        assert self._dispatch_skip()(ctx) is True

    def test_skips_when_verified_absent(self) -> None:
        """A missing ``verified`` key (verify crashed) also skips."""
        ctx = _FakeCtx({})
        assert self._dispatch_skip()(ctx) is True

    def test_does_not_skip_when_items_present(self) -> None:
        """A non-empty ``verified`` list runs dispatch (predicate False)."""
        ctx = _FakeCtx({"verified": ["/library/Movie (2020)"]})
        assert self._dispatch_skip()(ctx) is False


class TestValidateStepSpecs:
    """``_validate_step_specs`` fails loud on any registry drift."""

    def test_real_spec_list_validates(self) -> None:
        """The shipped ``STEP_SPECS`` passes validation (regression anchor)."""
        _validate_step_specs(STEP_SPECS, DEFAULT_STEPS, STEP_REPORT_CONTRACT)

    def test_duplicate_name_raises(self) -> None:
        """Two specs for the same step name raise."""
        adapter = DEFAULT_STEPS["ingest"]
        specs = [
            StepSpec("ingest", adapter, payload_type=IngestDetails),
            StepSpec("ingest", adapter, payload_type=IngestDetails),
        ]
        with pytest.raises(StepSpecError, match="duplicate"):
            _validate_step_specs(specs, {"ingest": adapter}, {"ingest": IngestDetails})

    def test_order_or_set_mismatch_raises(self) -> None:
        """A reordered spec list no longer mirrors the registry and raises."""
        reordered = tuple(reversed(STEP_SPECS))
        with pytest.raises(StepSpecError, match="mirror DEFAULT_STEPS"):
            _validate_step_specs(reordered, DEFAULT_STEPS, STEP_REPORT_CONTRACT)

    def test_name_absent_from_stage_catalog_raises(self) -> None:
        """A spec name unknown to the web stage catalog raises."""
        adapter = DEFAULT_STEPS["ingest"]
        specs = [StepSpec("bogus", adapter, payload_type=IngestDetails)]
        with pytest.raises(StepSpecError, match="stage catalog"):
            _validate_step_specs(specs, {"bogus": adapter}, {"bogus": IngestDetails})

    def test_payload_type_mismatch_raises(self) -> None:
        """A payload type that disagrees with the contract raises."""
        adapter = DEFAULT_STEPS["ingest"]
        specs = [StepSpec("ingest", adapter, payload_type=SortDetails)]
        with pytest.raises(StepSpecError, match="payload_type"):
            _validate_step_specs(specs, {"ingest": adapter}, {"ingest": IngestDetails})

    def test_adapter_mismatch_raises(self) -> None:
        """A spec adapter that is not the registry's instance raises."""
        specs = [StepSpec("ingest", DEFAULT_STEPS["sort"], payload_type=IngestDetails)]
        with pytest.raises(StepSpecError, match="adapter"):
            _validate_step_specs(specs, {"ingest": DEFAULT_STEPS["ingest"]}, {"ingest": IngestDetails})


class _FakeCtx:
    """Minimal stand-in exposing only the ``extras`` mapping a predicate reads."""

    def __init__(self, extras: dict[str, object]) -> None:
        self.extras = extras
