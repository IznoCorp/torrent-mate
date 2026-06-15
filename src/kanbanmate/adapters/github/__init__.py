"""GitHub board adapter: a urllib GraphQL/REST client behind the board ports.

This package implements :class:`kanbanmate.ports.board.BoardReader` and
:class:`kanbanmate.ports.board.BoardWriter` over GitHub Projects v2 using only
the standard library (:mod:`urllib`). The layout mirrors the PoC it was ported
from (DESIGN §3.3, §11):

- :mod:`.types`    — small typed records for decoded API payloads.
- :mod:`.token`    — PAT loading + scope validation (``project`` + ``repo`` only).
- :mod:`._queries` — pure GraphQL query/mutation builders (no I/O).
- :mod:`._parsers` — pure JSON -> domain parsers (no I/O).
- :mod:`.client`   — :class:`~.client.GithubClient`, the single network seam with an
  injected transport and **mandatory connect + read timeouts on every request**.

The transport seam keeps the client unit-testable: production wires a real urllib
transport (with timeouts), tests inject a fake returning fixture JSON so no unit
test ever touches the network.
"""

from __future__ import annotations

from kanbanmate.adapters.github.client import GithubClient

__all__ = ["GithubClient"]
