from __future__ import annotations


class ApiError(Exception):
    """What a router raises: a stable code and a message safe to show."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
