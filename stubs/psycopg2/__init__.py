# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=unused-argument
# pylint: disable=multiple-statements
# pylint: disable=super-init-not-called

from typing import Any, Optional


# pylint: disable=unsubscriptable-object
def connect(
    dsn: Optional[str] = ...,
    connection_factory: Optional[Any] = ...,
    cursor_factory: Optional[Any] = ...,
    **kwargs: Any) -> Any: ...
