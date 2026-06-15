"""CLI entrypoint: the ``kanban`` Typer application.

This layer exposes the user-facing commands and shells out to the engine. As
an entrypoint it sits at the top of the import hierarchy and may import lower
layers freely (DESIGN §3.2).
"""
