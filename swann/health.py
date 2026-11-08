"""Build the health picture from what the recorder will tell us.

Field names here were read off the live recorder, not guessed. See
PLAN-evidence.md for the full reply shapes.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from . import config as cfg
from .errors import RecorderError, RecorderUnreachable
from .models import Channel, Device, Disk, Health, Partition, clean_date
from .session import RecorderSession

log = logging.getLogger(__name__)

# Keys in the recorder's own replies.
KEY_SOFTWARE = "SoftWareVersion"
KEY_HARDWARE = "HardWare"
KEY_BUILD_TIME = "BuildTime"
KEY_SERIAL = "SerialNo"
KEY_DIG_CHANNEL = "DigChannel"
KEY_RUN_TIME = "DeviceRunTime"
KEY_PARTITION = "Partition"
KEY_LOGIC_SERIAL = "LogicSerialNo"
KEY_TOTAL_SPACE = "TotalSpace"
KEY_REMAIN_SPACE = "RemainSpace"
KEY_STATUS = "Status"
KEY_DRIVER_TYPE = "DirverType"
KEY_IS_CURRENT = "IsCurrent"
KEY_OLD_START = "OldStartTime"
KEY_NEW_END = "NewEndTime"
KEY_MODEL_NUMBER = "ModelNumber"
KEY_DISK_STATE = "State"
KEY_DISK_FIRMWARE = "Firmware"
KEY_DISK_SERIAL = "SerialNumber"
KEY_FREE_TOTAL = "FreeTotal"
KEY_FREE_TOTAL_TIME = "FreeTotalTime"
KEY_CHANNEL_STATE = "ChannelState"
KEY_BITRATE = "Bitrate"
KEY_RECORD = "Record"
KEY_OVERWRITE = "OverWrite"
KEY_SCHEDULE_SHEET = "ScheduleSheet"

OVERWRITE_ON = "OverWrite"
SCHEDULE_ON_CHARACTER = "1"
HEX_PREFIX = "0x"


def _as_int(value: object, default: int = 0) -> int:
    """The recorder sends numbers as plain ints or as hex strings."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            if text.lower().startswith(HEX_PREFIX):
                return int(text, 16)
            return int(text)
        except ValueError:
            return default
    return default


def _parse_device(system_info: object, clock: str, boot_time: str | None) -> Device:
    info = system_info if isinstance(system_info, dict) else {}
    return Device(
        firmware=str(info.get(KEY_SOFTWARE, "")),
        hardware=str(info.get(KEY_HARDWARE, "")),
        build_time=str(info.get(KEY_BUILD_TIME, "")),
        serial=str(info.get(KEY_SERIAL, "")),
        channel_count=_as_int(info.get(KEY_DIG_CHANNEL), cfg.CHANNEL_COUNT),
        total_run_minutes=_as_int(info.get(KEY_RUN_TIME)),
        recorder_clock=clock,
        boot_time=boot_time,
    )


def _parse_disks(storage_info: object) -> list[Disk]:
    raw_disks = storage_info if isinstance(storage_info, list) else []
    out: list[Disk] = []
    for raw in raw_disks:
        if not isinstance(raw, dict):
            continue
        parts: list[Partition] = []
        for part in raw.get(KEY_PARTITION, []) or []:
            if not isinstance(part, dict):
                continue
            parts.append(
                Partition(
                    serial=str(part.get(KEY_LOGIC_SERIAL, "")),
                    total_mb=_as_int(part.get(KEY_TOTAL_SPACE)),
                    free_mb=_as_int(part.get(KEY_REMAIN_SPACE)),
                    status=_as_int(part.get(KEY_STATUS)),
                    driver_type=_as_int(part.get(KEY_DRIVER_TYPE)),
                    is_current=bool(part.get(KEY_IS_CURRENT, False)),
                    oldest=clean_date(part.get(KEY_OLD_START)),
                    newest=clean_date(part.get(KEY_NEW_END)),
                )
            )
        out.append(
            Disk(
                model=str(raw.get(KEY_MODEL_NUMBER, "")).strip(),
                state=str(raw.get(KEY_DISK_STATE, "")).strip(),
                firmware=str(raw.get(KEY_DISK_FIRMWARE, "")).strip(),
                serial=str(raw.get(KEY_DISK_SERIAL, "")).strip(),
                space_text=str(raw.get(KEY_FREE_TOTAL, "")).strip(),
                kept_time_text=str(raw.get(KEY_FREE_TOTAL_TIME, "")).strip(),
                partitions=parts,
            )
        )
    return out


def _parse_channels(work_state: object, titles: object, limit: int) -> list[Channel]:
    """The recorder lists 64 slots whatever it has, so stop at the real count."""
    state = work_state if isinstance(work_state, dict) else {}
    rows = (state.get(KEY_CHANNEL_STATE, []) or [])[:limit]
    names = titles if isinstance(titles, list) else []
    out: list[Channel] = []
    for index, row in enumerate(rows):
        row = row if isinstance(row, dict) else {}
        bitrate = _as_int(row.get(KEY_BITRATE))
        name = str(names[index]) if index < len(names) else ""
        out.append(
            Channel(
                index=index,
                name=name,
                in_use=bitrate > 0,
                bitrate_kbps=bitrate,
                recording=bool(row.get(KEY_RECORD, False)),
            )
        )
    return out


def _overwrite_enabled(general: object) -> bool:
    data = general if isinstance(general, dict) else {}
    return str(data.get(KEY_OVERWRITE, "")) == OVERWRITE_ON


def _schedule_has_recording(record_config: object) -> bool:
    """True when any channel has any slot switched on in its record schedule."""
    channels = record_config if isinstance(record_config, list) else []
    for entry in channels:
        if not isinstance(entry, dict):
            continue
        for group in entry.get(KEY_SCHEDULE_SHEET, []) or []:
            for day in group if isinstance(group, list) else []:
                if isinstance(day, str) and SCHEDULE_ON_CHARACTER in day:
                    return True
    return False


async def read_health(session: RecorderSession) -> Health:
    """Ask the recorder everything the health page needs, in one go."""
    checked_at = datetime.now().strftime(cfg.RECORDER_DATE_FORMAT)
    try:
        clock = await session.recorder_time()
        system_info = await session.read_info(cfg.NAME_SYSTEM_INFO)
        storage_info = await session.read_info(cfg.NAME_STORAGE_INFO)
        work_state = await session.read_info(cfg.NAME_WORK_STATE)
    except (RecorderError, RecorderUnreachable) as exc:
        log.warning("health read failed: %s", exc)
        return Health(reachable=False, checked_at=checked_at, error=str(exc))

    # These are nice to have. A refusal on any one should not lose the page.
    titles = await _soft_read(session.read_config, cfg.CONFIG_CHANNEL_TITLE)
    general = await _soft_read(session.read_config, cfg.CONFIG_GENERAL)
    record = await _soft_read(session.read_config, cfg.CONFIG_RECORD)

    # When the recorder last started. Cached in the session, so this is one
    # extra call every five minutes, not one per refresh.
    boot_time = None
    try:
        boot_time = await session.read_boot_time()
    except (RecorderError, RecorderUnreachable) as exc:
        log.info("boot time read was refused: %s", exc)

    clock_text = clock if isinstance(clock, str) else ""
    device = _parse_device(system_info, clock_text, boot_time)
    socket_count = device.channel_count or cfg.CHANNEL_COUNT
    return Health(
        reachable=True,
        checked_at=checked_at,
        device=device,
        disks=_parse_disks(storage_info),
        channels=_parse_channels(work_state, titles, socket_count),
        overwrite_oldest=_overwrite_enabled(general),
        recording_scheduled=_schedule_has_recording(record),
    )


async def _soft_read(reader, name: str):
    """Read something optional. A refusal gives None instead of an error."""
    try:
        return await reader(name)
    except (RecorderError, RecorderUnreachable, asyncio.TimeoutError) as exc:
        log.info("optional read %s was refused: %s", name, exc)
        return None
