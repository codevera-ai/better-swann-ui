"""Plain shapes for the things the recorder tells us about.

Everything the web pages show comes from one of these, so a page never reads a
raw recorder reply.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .config import (
    DAYS_PER_MONTH,
    DISK_FULL_FREE_MB,
    HOURS_PER_DAY,
    MB_PER_GB,
    MINUTES_PER_HOUR,
    RECORDER_DATE_FORMAT,
    SECONDS_PER_MINUTE,
)

# The recorder writes an unset date as one of these.
EMPTY_DATES = ("0000-00-00 00:00:00", "2000-00-00 00:00:00", "")
# Partition kinds. 0 holds video, 4 holds stills.
DRIVER_TYPE_VIDEO = 0
DISK_STATE_OK = "Normal"


def clean_date(value: object) -> str | None:
    """Turn the recorder's placeholder dates into nothing."""
    if not isinstance(value, str) or value.strip() in EMPTY_DATES:
        return None
    return value.strip()


def parse_recorder_time(value: str | None) -> datetime | None:
    """Read one of the recorder's date strings, or give nothing back."""
    cleaned = clean_date(value)
    if cleaned is None:
        return None
    try:
        return datetime.strptime(cleaned, RECORDER_DATE_FORMAT)
    except ValueError:
        return None


def _span_text(minutes: int) -> str:
    """A length of time in the biggest unit that still reads plainly."""
    hours, left = divmod(max(minutes, 0), MINUTES_PER_HOUR)
    if hours < 1:
        return f"{left} minutes"
    if hours < HOURS_PER_DAY:
        return f"{hours} hours, {left} minutes"
    days, hours = divmod(hours, HOURS_PER_DAY)
    if days < DAYS_PER_MONTH:
        return f"{days} days, {hours} hours"
    # Past a month the counter is not accurate enough to name a day, so round.
    return f"about {round(days / DAYS_PER_MONTH)} months"


@dataclass(slots=True)
class Partition:
    """One slice of one disk."""

    serial: str
    total_mb: int
    free_mb: int
    status: int
    driver_type: int = DRIVER_TYPE_VIDEO
    is_current: bool = False
    oldest: str | None = None
    newest: str | None = None

    @property
    def used_mb(self) -> int:
        return max(self.total_mb - self.free_mb, 0)

    @property
    def total_gb(self) -> float:
        return self.total_mb / MB_PER_GB

    @property
    def used_gb(self) -> float:
        return self.used_mb / MB_PER_GB

    @property
    def free_gb(self) -> float:
        return self.free_mb / MB_PER_GB

    @property
    def holds_video(self) -> bool:
        return self.driver_type == DRIVER_TYPE_VIDEO and self.total_mb > 0

    @property
    def is_full(self) -> bool:
        return self.free_mb <= DISK_FULL_FREE_MB

    @property
    def percent_used(self) -> float:
        if self.total_mb <= 0:
            return 0.0
        return round(self.used_mb / self.total_mb * 100, 1)


@dataclass(slots=True)
class Disk:
    """A physical disk and the slices on it."""

    model: str = ""
    state: str = ""
    firmware: str = ""
    serial: str = ""
    space_text: str = ""
    kept_time_text: str = ""
    partitions: list[Partition] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return self.state == DISK_STATE_OK

    @property
    def video_partition(self) -> Partition | None:
        """The slice the video actually lands on."""
        usable = [p for p in self.partitions if p.holds_video]
        if not usable:
            return None
        current = [p for p in usable if p.is_current]
        pool = current or usable
        return max(pool, key=lambda p: p.total_mb)

    @property
    def oldest_video(self) -> str | None:
        times = [p.oldest for p in self.partitions if p.oldest]
        return min(times) if times else None

    @property
    def newest_video(self) -> str | None:
        times = [p.newest for p in self.partitions if p.newest]
        return max(times) if times else None


@dataclass(slots=True)
class Channel:
    """One camera socket on the recorder."""

    index: int
    name: str
    in_use: bool
    bitrate_kbps: int
    recording: bool
    width: int | None = None
    height: int | None = None

    @property
    def label(self) -> str:
        return self.name or f"Channel {self.index + 1}"

    @property
    def resolution(self) -> str | None:
        if self.width and self.height:
            return f"{self.width} x {self.height}"
        return None


@dataclass(slots=True)
class Device:
    """The recorder itself."""

    firmware: str = ""
    hardware: str = ""
    build_time: str = ""
    serial: str = ""
    channel_count: int = 0
    total_run_minutes: int = 0
    recorder_clock: str = ""
    boot_time: str | None = None

    @property
    def total_run_text(self) -> str:
        """Total time this recorder has ever been running.

        `DeviceRunTime` counts up across restarts, so it is a lifetime total and
        not time since the last start. Proved by the log: the recorder restarted
        at 00:05 today, yet this counter reads about 148 days. See config.py.
        """
        return _span_text(max(self.total_run_minutes, 0))

    @property
    def uptime_text(self) -> str:
        """How long since the recorder last started, from its own log."""
        minutes = self.uptime_minutes
        if minutes is None:
            return "not known"
        return _span_text(minutes)

    @property
    def uptime_minutes(self) -> int | None:
        """Minutes since the last restart, or None when the log does not say."""
        if not self.boot_time:
            return None
        started = parse_recorder_time(self.boot_time)
        if started is None:
            return None
        seconds = (datetime.now() - started).total_seconds()
        if seconds < 0:
            return None
        return int(seconds // SECONDS_PER_MINUTE)


@dataclass(slots=True)
class Health:
    """Everything the health page shows."""

    reachable: bool
    checked_at: str
    device: Device = field(default_factory=Device)
    disks: list[Disk] = field(default_factory=list)
    channels: list[Channel] = field(default_factory=list)
    overwrite_oldest: bool = False
    recording_scheduled: bool = False
    error: str | None = None

    @property
    def cameras_in_use(self) -> int:
        return sum(1 for c in self.channels if c.in_use)

    @property
    def main_disk(self) -> Disk | None:
        real = [d for d in self.disks if d.video_partition is not None]
        if not real:
            return self.disks[0] if self.disks else None
        return max(real, key=lambda d: d.video_partition.total_mb)
