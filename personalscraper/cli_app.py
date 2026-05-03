"""Shared Typer application instances for the PersonalScraper CLI."""

from __future__ import annotations

import typer

app = typer.Typer(help="PersonalScraper — Media pipeline automation.", invoke_without_command=True)
config_app = typer.Typer(help="Configuration management commands.")

__all__ = ["app", "config_app"]
