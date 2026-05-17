"""Public API of the metadata family.

Re-exports the concrete clients and façades so consumers import the
business-meaningful names directly from ``personalscraper.api.metadata``
without reaching into the private modules. The :class:`OMDbAdapter` is
re-exported alongside the façades so the rare caller that legitimately
needs the HTTP backend (e.g. the activation factory wiring) does not
have to import from a private module either.
"""

from personalscraper.api.metadata.imdb import IMDbClient
from personalscraper.api.metadata.omdb import OMDbAdapter
from personalscraper.api.metadata.rotten_tomatoes import RottenTomatoesClient

__all__ = ["IMDbClient", "OMDbAdapter", "RottenTomatoesClient"]
