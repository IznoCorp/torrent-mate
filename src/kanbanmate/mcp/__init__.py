"""MCP board-surface layer — the ``kanban mcp`` stdio server (conduit / roadmap mcp).

``mcp`` sits at the TOP of the import hierarchy alongside ``cli`` / ``daemon`` / ``http`` (DESIGN
§3): it may import ``app`` / ``adapters`` / ``core`` / ``ports`` / ``cli`` but NOT the sibling
entrypoints ``daemon`` / ``bin``, so the board surface is a thin standalone front-door while ``core``
stays pure (enforced by ``tests/test_layering.py`` — the ``"mcp": ["daemon", "bin"]`` forbidden
entry). The same permitted set ``http`` enjoys.

The shell holds NO domain logic: the resource serializers and tool bodies are thin wrappers over the
already-existing ``core`` / ``app`` / port functions the ``kanban-*`` bins call — the MCP server is an
additive parallel surface that performs no direct GitHub writes and is pinned to the agent's own
issue. The SDK ``server.py`` (the only module importing ``mcp`` the SDK) is Phase 3; this phase is
SDK-free and unit-testable without it.
"""
