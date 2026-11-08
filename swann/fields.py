"""Work out how to draw an editor for a setting, from the setting's own value.

The recorder answers with plain JSON, so the shape of the value tells us what
kind of control it needs. That way every setting gets an editor without anyone
writing out 59 schemas by hand, and a setting this firmware has but we have
never seen still appears.

Nothing here talks to the recorder. It is pure shape work.
"""
from __future__ import annotations

import re
from typing import Any

from . import config as cfg

KIND_BOOL = "bool"
KIND_INT = "int"
KIND_TEXT = "text"
KIND_HEX = "hex"
KIND_CHOICE = "choice"
KIND_GROUP = "group"
KIND_LIST = "list"
KIND_EMPTY = "empty"

_HEX = re.compile(r"^0x[0-9A-Fa-f]+$")
_SPLIT_WORDS = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=[0-9])")


def humanise(name: str) -> str:
    """Turn a recorder field name into something readable.

    `AutoLogout` becomes "Auto logout". `NetIPFilterV2` becomes "Net IP filter
    V2". A name in the override list wins over this.
    """
    override = cfg.FIELD_LABELS.get(name)
    if override:
        return override
    words = _SPLIT_WORDS.sub(" ", name).replace("_", " ").split()
    if not words:
        return name
    first, rest = words[0], words[1:]
    out = [first[:1].upper() + first[1:]]
    for word in rest:
        out.append(word if word.isupper() or any(c.isdigit() for c in word) else word.lower())
    return " ".join(out)


def kind_of(value: Any) -> str:
    """Which control this value needs."""
    if isinstance(value, bool):
        return KIND_BOOL
    if isinstance(value, int):
        return KIND_INT
    if isinstance(value, str):
        return KIND_HEX if _HEX.match(value) else KIND_TEXT
    if isinstance(value, dict):
        return KIND_GROUP
    if isinstance(value, list):
        return KIND_LIST
    return KIND_EMPTY


def describe(
    value: Any,
    name: str = "",
    path: str = "",
    channels: list[int] | None = None,
) -> dict[str, Any]:
    """Describe one value, and everything inside it, as a tree of fields.

    `channels` trims a per socket list to the sockets that hold a camera. The
    real index stays in the path, so a write still lands on the right socket.
    """
    kind = kind_of(value)
    field: dict[str, Any] = {
        "path": path,
        "name": name,
        "label": humanise(name) if name else "",
        "kind": kind,
    }

    if kind == KIND_GROUP:
        field["children"] = [
            describe(child, key, _join(path, key), channels)
            for key, child in value.items()
        ]
        return field

    if kind == KIND_LIST:
        field["length"] = len(value)
        # A long list is almost always one entry per camera socket.
        per_channel = len(value) in cfg.FIELD_CHANNEL_LENGTHS
        field["per_channel"] = per_channel
        wanted = range(len(value))
        if per_channel and channels is not None:
            wanted = [index for index in channels if index < len(value)]
            field["shown"] = list(wanted)
        field["children"] = [
            describe(
                value[index],
                cfg.CHANNEL_LABEL_TEMPLATE.format(number=index + 1)
                if per_channel
                else str(index),
                _join(path, str(index)),
                channels,
            )
            for index in wanted
        ]
        return field

    field["value"] = value
    choices = cfg.FIELD_CHOICES.get(name)
    if choices and isinstance(value, str):
        field["kind"] = KIND_CHOICE
        field["choices"] = list(choices)
    if kind == KIND_HEX:
        field["note"] = cfg.FIELD_HEX_NOTE
    hint = cfg.FIELD_NOTES.get(name)
    if hint:
        field["note"] = hint
    return field


def _join(path: str, part: str) -> str:
    return part if not path else f"{path}/{part}"


def read_at(value: Any, path: str) -> Any:
    """Follow a slash separated path into a value."""
    current = value
    for part in filter(None, path.split("/")):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def write_at(value: Any, path: str, new: Any) -> Any:
    """Return a copy of `value` with `path` set to `new`.

    The original is left alone, so the old value stays usable for an undo.
    """
    parts = [part for part in path.split("/") if part]
    if not parts:
        return new
    head, rest = parts[0], "/".join(parts[1:])

    if isinstance(value, dict):
        out = dict(value)
        out[head] = write_at(value.get(head), rest, new) if rest else new
        return out
    if isinstance(value, list):
        try:
            index = int(head)
        except ValueError:
            return value
        out = list(value)
        while len(out) <= index:
            out.append(None)
        out[index] = write_at(out[index], rest, new) if rest else new
        return out
    # The path goes deeper than the value does, so build what is missing.
    return {head: write_at(None, rest, new) if rest else new}


def coerce(old: Any, new: Any) -> Any:
    """Keep a value the same type the recorder gave us.

    The browser sends everything as text or as JSON numbers, and this firmware
    is fussy: a port sent as "554" instead of 554 is refused.
    """
    if isinstance(old, bool):
        if isinstance(new, bool):
            return new
        return str(new).strip().lower() in cfg.FIELD_TRUE_WORDS
    if isinstance(old, int) and not isinstance(old, bool):
        try:
            return int(str(new).strip(), 0) if str(new).strip().lower().startswith("0x") else int(new)
        except (TypeError, ValueError):
            return old
    if isinstance(old, str):
        return "" if new is None else str(new)
    return new
