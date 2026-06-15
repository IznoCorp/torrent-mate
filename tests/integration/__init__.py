"""Integration tests against external services (real GitHub Projects v2 + nightly CI).

Gated on ``KANBAN_TOKEN`` env var — skipped by default in CI and local runs.
Opt-in with ``KANBAN_TOKEN`` + ``KANBAN_TEST_PROJECT`` + auxiliary vars to run
against a dedicated test org / board.
"""
