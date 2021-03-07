"""Define a simple Model data type."""

from typing import List

from db_wrapper.model import ModelData


class SimpleData(ModelData):
    """An example Item."""

    # PENDS python 3.9 support in pylint,
    # ModelData inherits from TypedDict
    # pylint: disable=too-few-public-methods

    string: str
    integer: int
    array: List[str]
