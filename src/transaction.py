from __future__ import annotations
from copy import deepcopy
from typing import Optional
from uuid import UUID

from .models import TransactionData


class Transaction:
    """The object to be returned by the service."""

    _data: TransactionData

    def __init__(self, data: TransactionData) -> None:
        self._data = data

    def update_spent_from(self, new_spent_from: UUID) -> Transaction:
        """Update what Budget Item this Transaction is spent from."""
        old_data: TransactionData = deepcopy(self._data)

        return Transaction({
            # ignoring type on unpacking, see
            # https://github.com/python/mypy/issues/4122#issuecomment-336924377
            **old_data,  # type: ignore
            'spent_from_id': new_spent_from,
        })

    @property
    def spent_from_id(self) -> Optional[UUID]:
        return self._data['spent_from_id']
