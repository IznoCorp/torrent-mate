"""The ``notifications`` tag's bodies: the account's in-app notices."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from personalscraper.app.accounts.notices import NoticeView
from personalscraper.http_v1.contract import ContractModel


class NoticeModel(ContractModel):
    """The contract's ``Notice``: one in-app notice of the signed-in account.

    Attributes:
        id: Its key.
        code: What it tells, as a code the interface words (``NoticeCode``).
        params: The code's parameters — facts, never words.
        created_at: When it was raised (epoch seconds).
        read_at: When the account marked it read (epoch seconds); absent while unread.
    """

    id: int
    code: Literal["account.sign_in.device", "account.sign_in.unknown_device"]
    params: dict[str, str]
    created_at: float
    read_at: float | None = None

    @classmethod
    def from_view(cls, view: NoticeView) -> NoticeModel:
        """Map a notice view.

        Args:
            view: The service's view.

        Returns:
            The body.
        """
        params = {name: str(value) for name, value in view.params.items()}
        return cls(id=view.id, code=view.code, params=params, created_at=view.created_at, read_at=view.read_at)  # type: ignore[arg-type]


class NoticesModel(ContractModel):
    """``readNotices``'s answer: the account's notices, the newest first.

    Attributes:
        notices: The notices.
    """

    notices: list[NoticeModel]


class MarkNoticesReadBody(ContractModel):
    """``markNoticesRead``'s body.

    Attributes:
        up_to: The highest notice id marked read; the notices raised after it stay unread.
    """

    up_to: int = Field(ge=0)


class NoticesMarkedRead(ContractModel):
    """``markNoticesRead``'s answer.

    Attributes:
        marked: How many notices it newly marked read (zero when it repeats itself).
    """

    marked: int
