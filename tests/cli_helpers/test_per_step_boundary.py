"""Regression test for per_step_boundary close-on-exit (sub-phase 5.6)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.cli_helpers import per_step_boundary


def test_per_step_boundary_closes_registry_on_exit(test_config, mock_settings):
    """per_step_boundary calls provider_registry.close() on normal exit."""
    with patch("personalscraper.cli_helpers._build_app_context") as mock_build:
        mock_app_ctx = MagicMock()
        mock_build.return_value = mock_app_ctx

        with per_step_boundary(test_config, mock_settings) as ctx:
            assert ctx is mock_app_ctx

        mock_app_ctx.provider_registry.close.assert_called_once()


def test_per_step_boundary_closes_registry_on_exception(test_config, mock_settings):
    """per_step_boundary calls close() even when body raises."""
    with patch("personalscraper.cli_helpers._build_app_context") as mock_build:
        mock_app_ctx = MagicMock()
        mock_build.return_value = mock_app_ctx

        with pytest.raises(RuntimeError, match="body fail"):
            with per_step_boundary(test_config, mock_settings):
                raise RuntimeError("body fail")

        mock_app_ctx.provider_registry.close.assert_called_once()
