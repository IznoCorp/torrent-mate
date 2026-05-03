"""Base model for all config models.

All models use ``extra='forbid'`` to catch typos and prevent accidental secret
placement in the config file.
"""

from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    """Base model that forbids extra fields.

    All concrete config models inherit from this to catch typos early and
    prevent secrets from being accidentally placed in config.json5.
    """

    model_config = ConfigDict(extra="forbid")
