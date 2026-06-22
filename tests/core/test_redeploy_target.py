"""Pure redeploy-target validator tests (bosun sub-phase 3.2)."""

from __future__ import annotations

from kanbanmate.core.redeploy_target import REDEPLOY_TARGETS, script_for_target


def test_prod_maps_to_deploy_sh() -> None:
    assert script_for_target("prod") == "scripts/deploy.sh"


def test_staging_maps_to_deploy_staging_sh() -> None:
    assert script_for_target("staging") == "scripts/deploy-staging.sh"


def test_unknown_target_none() -> None:
    assert script_for_target("nope") is None
    assert "prod" in REDEPLOY_TARGETS and "staging" in REDEPLOY_TARGETS
