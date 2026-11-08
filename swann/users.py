"""Accounts on the recorder.

The recorder's own page can do two things to an account: change what it is
allowed to do, and change its password. It cannot add one and it cannot
remove one, so neither can this. Read off its own page,
`rsui/cfg/syspm_user.js`.

**Never let a password out of this file.** `GetAllUser` hands back
`Password` and `PasswordV2`. They look scrambled, but the recorder logs you
in with the scrambled form, so they are as good as the password itself.
`clean()` takes them out before anything else sees the account.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from . import config as cfg
from .errors import RecorderError

log = logging.getLogger(__name__)


@dataclass
class UserOutcome:
    """What happened to one account."""

    name: str
    ret: int | None
    before: dict[str, Any] | None

    @property
    def saved(self) -> bool:
        return self.ret in cfg.RET_WRITE_OK_CODES

    @property
    def message(self) -> str:
        if self.ret == cfg.RET_OK:
            return "Saved."
        if self.ret == cfg.RET_NEED_REBOOT:
            return "Saved. The recorder needs a restart for this to count."
        if self.ret == cfg.RET_NO_PERMISSION:
            return "This login is not allowed to change accounts."
        return f"The recorder said no. Code {self.ret}."


def clean(user: dict[str, Any]) -> dict[str, Any]:
    """One account with every password field taken out."""
    return {
        key: value
        for key, value in user.items()
        if key not in cfg.USER_SECRET_FIELDS
    }


def payload(reply: dict[str, Any]) -> dict[str, Any]:
    """What the accounts page shows, with no passwords in it."""
    users = reply.get(cfg.USER_LIST_KEY) or []
    groups = reply.get(cfg.USER_GROUP_KEY) or []
    return {
        "users": [
            {
                "name": user.get("Name"),
                "group": user.get("Group"),
                "enabled": user.get("Memo") == cfg.USER_MEMO_ON,
                "sharable": bool(user.get("Sharable")),
                "reserved": bool(user.get("Reserved")),
                "rights": list(user.get("AuthorityList") or []),
                "isAdmin": user.get("Name") == cfg.USER_ADMIN_NAME,
            }
            for user in users
        ],
        "groups": [
            {
                "name": group.get("Name"),
                "memo": group.get("Memo"),
                "rights": list(group.get("AuthorityList") or []),
            }
            for group in groups
        ],
        "allRights": sorted(
            {
                right
                for group in groups
                for right in (group.get("AuthorityList") or [])
            }
            | {
                right
                for user in users
                for right in (user.get("AuthorityList") or [])
            }
        ),
    }


def _find(reply: dict[str, Any], name: str) -> dict[str, Any]:
    for user in reply.get(cfg.USER_LIST_KEY) or []:
        if user.get("Name") == name:
            return user
    raise RecorderError("usermanager", None, f"there is no account called {name}")


async def write_user(
    session: Any,
    name: str,
    *,
    group: str | None = None,
    enabled: bool | None = None,
    rights: list[str] | None = None,
) -> UserOutcome:
    """Change one account.

    The recorder wants the whole account back, not just the bits that
    changed, so this reads it first and sends it on with the changes made.
    The password fields go back exactly as they came, untouched.
    """
    reply = await session.read_users()
    before = _find(reply, name)
    user = dict(before)

    if group is not None:
        user["Group"] = group
    if enabled is not None:
        user["Memo"] = cfg.USER_MEMO_ON if enabled else cfg.USER_MEMO_OFF
    if rights is not None:
        user["AuthorityList"] = list(rights)

    answer = await session.manage_user(
        cfg.NAME_MODIFY_USER, {"User": user, "UserName": name}
    )
    return UserOutcome(name=name, ret=answer.get("Ret"), before=clean(before))
