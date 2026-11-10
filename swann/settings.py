"""Read and write the recorder's settings, one screen at a time.

A screen is described in `config.SETTINGS_SCREENS`. This module reads the live
values for a screen, describes them as fields, and writes changes back. It never
guesses a value: the page always sends back a whole config, built from the one it
was given, so a field this tool has never seen is carried through untouched.

Every write reads the value back, because this recorder answers Ret 100 to a
write it then ignores. See PARITY-evidence.md section 14.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from . import config as cfg
from .errors import RecorderError, RecorderUnreachable
from .fields import coerce, describe, humanise, read_at, write_at
from .limits import encoder_limits
from .session import RecorderSession, WriteOutcome

log = logging.getLogger(__name__)

SCREENS_BY_KEY = {screen["key"]: screen for screen in cfg.SETTINGS_SCREENS}


@dataclass(slots=True)
class ConfigValue:
    """One config name as it stands on the recorder right now."""

    name: str
    value: Any = None
    channel: int | None = None
    error: str | None = None

    @property
    def key(self) -> str:
        return self.name if self.channel is None else f"{self.name}#{self.channel}"


@dataclass(slots=True)
class ScreenRead:
    """Everything one settings screen needs to draw itself."""

    key: str
    title: str
    group: str
    note: str
    read_only: bool
    action: str | None
    channels: list[int] = field(default_factory=list)
    values: list[ConfigValue] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)
    ability: dict[str, Any] = field(default_factory=dict)
    # What one camera's encoder will really accept, worked out per camera from
    # the recorder's own ability reply. Keyed by camera number.
    limits: dict[int, dict[str, Any]] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class ChangeResult:
    """What happened to one config we tried to change."""

    name: str
    channel: int | None
    saved: bool
    took_effect: bool
    ret: int | None
    message: str
    before: Any = None
    after: Any = None


def groups() -> list[dict[str, Any]]:
    """The settings menu: every group with its screens, in order."""
    out = []
    for name in cfg.SETTINGS_GROUPS:
        screens = [
            {
                "key": screen["key"],
                "title": screen["title"],
                "readOnly": bool(screen.get("read_only")),
                "action": screen.get("action"),
            }
            for screen in cfg.SETTINGS_SCREENS
            if screen["group"] == name
        ]
        if screens:
            out.append({"group": name, "screens": screens})
    return out


def screen_meta(key: str) -> dict[str, Any] | None:
    return SCREENS_BY_KEY.get(key)


async def read_screen(session: RecorderSession, key: str) -> ScreenRead:
    """Read every value one screen shows."""
    meta = SCREENS_BY_KEY.get(key)
    if meta is None:
        raise KeyError(key)

    out = ScreenRead(
        key=key,
        title=meta["title"],
        group=meta["group"],
        note=meta.get("note", ""),
        read_only=bool(meta.get("read_only")),
        action=meta.get("action"),
    )

    # Which sockets hold a camera. Used two ways: to ask a per camera config
    # once per camera, and to trim a list of 8 down to the ones in use.
    out.channels = await _channels(session)
    asked = out.channels if meta.get("per_channel") else [None]

    for name in meta.get("configs", ()):
        for channel in asked:
            out.values.append(await _read_config(session, name, channel))

    for name in meta.get("info", ()):
        try:
            out.info[name] = await session.read_info(name)
        except (RecorderError, RecorderUnreachable) as exc:
            log.info("info %s refused on screen %s: %s", name, key, exc)

    for name in meta.get("ability", ()):
        try:
            out.ability[name] = await session.read_ability(name)
        except (RecorderError, RecorderUnreachable) as exc:
            log.info("ability %s refused on screen %s: %s", name, key, exc)

    # The one screen whose limits the recorder states itself. Read per camera,
    # because two cameras on the same recorder can allow different sizes.
    if meta.get("limits") == cfg.LIMITS_ENCODER:
        for channel in out.channels:
            try:
                reply = await session.read_config(cfg.NAME_DIGITAL_ABILITY, channel)
            except (RecorderError, RecorderUnreachable) as exc:
                log.info("limits refused for camera %s: %s", channel, exc)
                continue
            found = encoder_limits(reply)
            if found:
                out.limits[channel] = found

    return out


async def write_screen(
    session: RecorderSession,
    key: str,
    changes: list[dict[str, Any]],
) -> list[ChangeResult]:
    """Apply field changes to one screen.

    Each change names a config, an optional channel, a field path and the new
    value. Changes to the same config are merged, so one config is written once.
    """
    meta = SCREENS_BY_KEY.get(key)
    if meta is None:
        raise KeyError(key)
    if meta.get("read_only"):
        raise PermissionError(f"{meta['title']} is a read only screen")

    allowed = set(meta.get("configs", ()))
    merged: dict[tuple[str, int | None], list[dict[str, Any]]] = {}
    for change in changes:
        name = change.get("name")
        if name not in allowed:
            raise PermissionError(f"{name} is not on the {meta['title']} screen")
        channel = change.get("channel")
        merged.setdefault((name, channel), []).append(change)

    results: list[ChangeResult] = []
    for (name, channel), group in merged.items():
        results.append(await _write_one(session, name, channel, group))
    return results


async def _write_one(
    session: RecorderSession,
    name: str,
    channel: int | None,
    changes: list[dict[str, Any]],
) -> ChangeResult:
    """Read a config, change only the named fields, write it, then read it back."""
    try:
        before = await session.read_config(name, channel)
    except (RecorderError, RecorderUnreachable) as exc:
        return ChangeResult(
            name=name,
            channel=channel,
            saved=False,
            took_effect=False,
            ret=None,
            message=f"Could not read the current value first, so nothing was changed. {exc}",
        )

    wanted = before
    for change in changes:
        path = change.get("path", "")
        old = read_at(before, path)
        wanted = write_at(wanted, path, coerce(old, change.get("value")))

    if wanted == before:
        return ChangeResult(
            name=name,
            channel=channel,
            saved=True,
            took_effect=True,
            ret=cfg.RET_OK,
            message="Nothing to change.",
            before=before,
            after=before,
        )

    try:
        outcome: WriteOutcome = await session.write_config(name, wanted, channel)
    except (RecorderError, RecorderUnreachable) as exc:
        return ChangeResult(
            name=name,
            channel=channel,
            saved=False,
            took_effect=False,
            ret=getattr(exc, "ret", None),
            message=f"The recorder refused the change. {exc}",
            before=before,
        )

    try:
        after = await session.read_config(name, channel)
    except (RecorderError, RecorderUnreachable):
        after = None

    took = after == wanted
    message = outcome.message
    if outcome.saved and not took:
        message = (
            "The recorder said it saved this, but reading it back shows the old "
            "value. It has quietly ignored the change."
        )
    return ChangeResult(
        name=name,
        channel=channel,
        saved=outcome.saved,
        took_effect=took,
        ret=outcome.ret,
        message=message,
        before=before,
        after=after,
    )


async def _read_config(
    session: RecorderSession,
    name: str,
    channel: int | None,
) -> ConfigValue:
    try:
        return ConfigValue(name=name, channel=channel, value=await session.read_config(name, channel))
    except RecorderError as exc:
        if exc.ret == cfg.RET_CONFIG_NOT_FOUND:
            return ConfigValue(
                name=name,
                channel=channel,
                error="This recorder does not have this setting.",
            )
        return ConfigValue(name=name, channel=channel, error=str(exc))
    except RecorderUnreachable as exc:
        return ConfigValue(name=name, channel=channel, error=str(exc))


async def _channels(session: RecorderSession) -> list[int]:
    """Which camera sockets to show on a per camera screen.

    Only sockets with a camera in them, because an empty socket has no settings
    and answers Ret 607.
    """
    try:
        status = await session.read_config("NetWork.ChnStatus")
    except (RecorderError, RecorderUnreachable):
        return list(range(cfg.CHANNEL_COUNT))
    if not isinstance(status, list):
        return list(range(cfg.CHANNEL_COUNT))
    live = [
        index
        for index, entry in enumerate(status[: cfg.CHANNEL_COUNT])
        if isinstance(entry, dict)
        and entry.get(cfg.CHN_STATUS_STATUS_KEY) == cfg.CHN_STATUS_CONNECTED
    ]
    return live or list(range(cfg.CHANNEL_COUNT))


def _config_label(value: ConfigValue) -> str:
    """What to head this config's block with on the page."""
    base = humanise(value.name.rsplit(".", 1)[-1])
    if value.channel is None:
        return base
    camera = cfg.CHANNEL_LABEL_TEMPLATE.format(number=value.channel + 1)
    return f"{base}, {camera}"


def payload(screen: ScreenRead) -> dict[str, Any]:
    """Flatten a screen read into what the page needs, fields and all."""
    meta = SCREENS_BY_KEY.get(screen.key, {})
    editor = meta.get("editor")
    return {
        "key": screen.key,
        "title": screen.title,
        "group": screen.group,
        "note": screen.note,
        "readOnly": screen.read_only,
        "action": screen.action,
        "error": screen.error,
        "channels": screen.channels,
        # Which drawing or painting editor this screen uses, and the sizes
        # and field names every editor needs. Both come from config.py, so
        # the browser never keeps its own copy of a recorder number. The
        # sizes go out on every screen, because the colour swatch in the
        # plain field list needs them too.
        "editor": editor,
        "visual": cfg.visual_settings(),
        "configs": [
            {
                "name": value.name,
                "channel": value.channel,
                "key": value.key,
                "label": _config_label(value),
                "error": value.error,
                "readOnly": value.name in cfg.CONFIG_REPORT_ONLY,
                "value": value.value,
                "fields": None
                if value.error
                else describe(
                    value.value,
                    "",
                    channels=screen.channels,
                    config=value.name,
                ),
            }
            for value in screen.values
        ],
        "info": screen.info,
        "ability": screen.ability,
        # What each camera's encoder really accepts. The page builds its
        # dropdowns from this, so no recorder number is written into the
        # browser. Empty on every screen but video quality.
        "limits": {str(channel): found for channel, found in screen.limits.items()},
        "limitFields": cfg.ENCODE_LIMIT_FIELDS if screen.limits else None,
        # The restart and reset screen needs to know what can be put back.
        "resetAreas": list(cfg.RESET_AREAS)
        if screen.action == cfg.ACTION_DANGER
        else None,
    }
