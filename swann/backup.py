"""Read every setting off the recorder and save it to one file.

This is read only. It never writes to the recorder. It exists so a wrong write
can always be undone, so it must run before anything is ever written back.

The saved file holds real passwords, for email, Wi-Fi, DDNS and FTP, because a
backup you cannot restore from is not a backup. It lands in `data/`, which is
git ignored. Never print a value from it.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config as cfg
from .errors import RecorderError, RecorderUnreachable
from .health import KEY_DIG_CHANNEL, KEY_HARDWARE, KEY_SERIAL, KEY_SOFTWARE, _as_int
from .session import RecorderSession

log = logging.getLogger(__name__)

@dataclass(slots=True)
class BackupResult:
    """What one backup run found. Holds no setting values, so it is safe to log."""

    path: Path | None = None
    taken_at: str = ""
    read: list[str] = field(default_factory=list)
    expected_missing: list[str] = field(default_factory=list)
    empty_sockets: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.path is not None and not self.failed

    @property
    def summary(self) -> str:
        parts = [f"{len(self.read)} settings read"]
        if self.expected_missing:
            parts.append(f"{len(self.expected_missing)} not on this recorder, as expected")
        if self.empty_sockets:
            parts.append(f"{len(self.empty_sockets)} skipped on empty camera sockets")
        if self.failed:
            parts.append(f"{len(self.failed)} failed")
        return ", ".join(parts)


async def _read_one(
    result: BackupResult,
    store: dict[str, Any],
    name: str,
    read: Any,
    per_channel: bool = False,
) -> None:
    """Run one read, record the value on success and the reason on failure.

    A `per_channel` read of an empty camera socket answers Ret 607, because the
    setting only exists once a camera is plugged in. That is not a failure.
    """
    try:
        store[name] = await read()
        result.read.append(name)
    except RecorderError as exc:
        if exc.ret != cfg.RET_CONFIG_NOT_FOUND:
            result.failed[name] = str(exc)
        elif per_channel:
            result.empty_sockets.append(name)
        elif name in cfg.BACKUP_EXPECTED_MISSING:
            result.expected_missing.append(name)
        else:
            result.failed[name] = str(exc)
    except (RecorderUnreachable, OSError) as exc:
        result.failed[name] = str(exc)
    # A short pause keeps a 60 call run from crowding the recorder.
    await asyncio.sleep(cfg.BACKUP_PAUSE_SECONDS)


async def take_backup(
    session: RecorderSession,
    directory: Path | None = None,
) -> BackupResult:
    """Read everything and write one JSON file. Returns what happened."""
    result = BackupResult(taken_at=datetime.now().strftime(cfg.RECORDER_DATE_FORMAT))

    if not session.connected:
        result.error = session.last_error or "not logged in to the recorder"
        return result

    settings: dict[str, Any] = {}
    channel_settings: dict[str, dict[str, Any]] = {}
    info: dict[str, Any] = {}
    ability: dict[str, Any] = {}
    channel_ability: dict[str, Any] = {}

    for name in cfg.BACKUP_INFO_NAMES:
        await _read_one(result, info, name, lambda n=name: session.read_info(n))

    for name in cfg.BACKUP_ABILITY_NAMES:
        await _read_one(result, ability, name, lambda n=name: session.read_ability(n))

    for name in cfg.BACKUP_CHANNEL_ABILITY_NAMES:
        await _read_one(
            result, channel_ability, name, lambda n=name: session.read_channel_ability(n)
        )

    for name in cfg.BACKUP_CONFIG_NAMES:
        await _read_one(result, settings, name, lambda n=name: session.read_config(n))

    # Only these need asking channel by channel. The rest answer as a whole list.
    channel_count = _channel_count(info)
    for name in cfg.BACKUP_CHANNEL_CONFIG_NAMES:
        per_channel: dict[str, Any] = {}
        for channel in range(channel_count):
            label = cfg.channel_config_name(name, channel)
            await _read_one(
                result,
                per_channel,
                label,
                lambda n=name, c=channel: session.read_config(n, c),
                per_channel=True,
            )
        if per_channel:
            channel_settings[name] = per_channel

    device = info.get(cfg.NAME_SYSTEM_INFO) or {}
    payload = {
        "takenAt": result.taken_at,
        "recorder": {
            "host": cfg.RECORDER_HOST,
            "firmware": device.get(KEY_SOFTWARE, ""),
            "hardware": device.get(KEY_HARDWARE, ""),
            "serial": device.get(KEY_SERIAL, ""),
            "channelCount": channel_count,
        },
        "counts": {
            "read": len(result.read),
            "expectedMissing": len(result.expected_missing),
            "emptySockets": len(result.empty_sockets),
            "failed": len(result.failed),
        },
        "config": settings,
        "channelConfig": channel_settings,
        "info": info,
        "ability": ability,
        "channelAbility": channel_ability,
        "expectedMissing": {
            name: cfg.BACKUP_EXPECTED_MISSING[name] for name in result.expected_missing
        },
        "emptySockets": result.empty_sockets,
        "failed": result.failed,
    }

    target = directory or cfg.BACKUP_DIR
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime(cfg.BACKUP_FILE_FORMAT)
    path = target / f"{stamp}{cfg.BACKUP_FILE_SUFFIX}"
    text = json.dumps(payload, indent=cfg.BACKUP_JSON_INDENT, sort_keys=True)
    path.write_text(text, encoding="utf-8")
    (target / cfg.BACKUP_LATEST_NAME).write_text(text, encoding="utf-8")

    result.path = path
    log.info("settings backup saved, %s", result.summary)
    return result


def _channel_count(info: dict[str, Any]) -> int:
    """How many camera sockets to ask about, from the login reply or the default."""
    device = info.get(cfg.NAME_SYSTEM_INFO) or {}
    count = _as_int(device.get(KEY_DIG_CHANNEL))
    if count and count > 0:
        return min(count, cfg.CHANNEL_COUNT)
    return cfg.CHANNEL_COUNT
