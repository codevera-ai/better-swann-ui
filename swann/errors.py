"""Errors the recorder can hand back."""
from __future__ import annotations

from .config import (
    RET_CONFIG_NOT_FOUND,
    RET_FORMAT_ERROR,
    RET_NO_FILE_FOUND,
    RET_NO_PERMISSION,
    RET_NOT_SUPPORTED,
    RET_SESSION_LOST,
    RET_UNKNOWN_NAME,
)

# Plain words for the codes we have actually seen on this recorder.
RET_MEANINGS = {
    RET_UNKNOWN_NAME: "the recorder does not know that command",
    RET_SESSION_LOST: "the login expired",
    RET_NO_PERMISSION: "this login is not allowed to do that",
    RET_FORMAT_ERROR: "the recorder refused the shape of that request",
    RET_NO_FILE_FOUND: "no file found",
    RET_NOT_SUPPORTED: "this firmware does not support that",
    RET_CONFIG_NOT_FOUND: "there is no setting with that name",
}


class RecorderError(RuntimeError):
    """The recorder answered, but said no."""

    def __init__(self, action: str, ret: int | None, raw: object = None) -> None:
        self.action = action
        self.ret = ret
        self.raw = raw
        meaning = RET_MEANINGS.get(ret) if ret is not None else None
        detail = f"Ret {ret}" if ret is not None else "no return code"
        if meaning:
            detail = f"{detail}, {meaning}"
        super().__init__(f"{action} failed: {detail}")


class SessionLost(RecorderError):
    """The login expired and needs doing again."""


class RecorderUnreachable(RuntimeError):
    """The recorder did not answer at all."""
