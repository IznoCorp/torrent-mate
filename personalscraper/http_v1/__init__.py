"""The v1 HTTP interface: a FastAPI sub-application written from the contract, served under ``/api/v1``.

It imports the application layer (``app/``), ``conf/`` and ``core/``, never v0
(``web/``) and never the engine directly: a route reaches the engine only through
a service.
"""
