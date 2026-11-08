"""The recorder's own password hash, used by both ports.

Xiongmai firmware calls this MD5_8, or the Sofia hash. It takes the 16 byte MD5
digest, adds the bytes in pairs, and maps each of the 8 results onto a 62
character alphabet. The result is always 8 characters.

Read off the recorder's own js/md5.js, and it matches the open source clients.
"""
from __future__ import annotations

import hashlib

from .config import MD5_8_CHARSET, MD5_8_LENGTH


def md5_8(text: str) -> str:
    """Hash a string the way the recorder does."""
    digest = hashlib.md5(text.encode("utf-8")).digest()
    pairs = zip(digest[0::2], digest[1::2])
    out = "".join(MD5_8_CHARSET[(a + b) % len(MD5_8_CHARSET)] for a, b in pairs)
    return out[:MD5_8_LENGTH]


def login_sign(salt: str, password: str) -> str:
    """The CGI login signature: MD5_8(salt + MD5_8(password))."""
    return md5_8(salt + md5_8(password))
