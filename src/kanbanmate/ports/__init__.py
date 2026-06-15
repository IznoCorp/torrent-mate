"""Ports: the Protocol interfaces the application depends on.

This layer declares the abstract boundaries (``BoardReader``/``BoardWriter``,
``Workspace``/``Sessions``, ``StateStore``, ``Clock``) that adapters implement.
Ports may reference ``core`` types but must not import ``adapters``, ``app``,
``daemon``, ``cli``, or ``bin`` (DESIGN §3.2 downward-only import rule).
"""
