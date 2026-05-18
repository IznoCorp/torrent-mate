"""Public API of the metadata family.

The concrete clients and façades — :class:`IMDbClient`,
:class:`OMDbAdapter`,
:class:`RottenTomatoesClient`, :class:`TMDBClient`, :class:`TVDBClient`
— live in their own modules. They are *not* re-exported here to avoid
a circular import :  ``api._helpers`` references
``api.metadata._base.Notations`` at import time, and re-exporting the
façades from this package would cause Python to load
``api.metadata.imdb`` (which in turn imports
``api._helpers.ProviderFeatureUnavailable``) before ``_helpers`` has
finished initialising.

Consumers should import from the full module path :

.. code-block:: python

    from personalscraper.api.metadata.imdb import IMDbClient
    from personalscraper.api.metadata.omdb import OMDbAdapter
    from personalscraper.api.metadata.rotten_tomatoes import RottenTomatoesClient
"""
