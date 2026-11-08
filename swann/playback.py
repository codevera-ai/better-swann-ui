"""Old video off the recorder.

The recorder will play back any time window over plain RTSP, on the same port
as live video. There is no clip list and no secret header. You ask for a start
and an end, and it hands back whatever it saved in between. See the playback
notes in `config.py` for how that was found and why the time is local.

What this does with that:

- Works out a sensible window around a movement alert.
- Runs one ffmpeg to turn the window into an MP4 a browser can play.
- Keeps the file, so watching the same clip twice costs nothing.
- Never lets two requests for the same clip start two ffmpegs.

Never log a playback URL. It carries the recorder password.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import config as cfg

log = logging.getLogger(__name__)

# The recorder's log writes times like "2026-11-07 23:23:05".
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_SAFE_URL = re.compile(r"//[^@]+@")


class NoVideo(Exception):
    """The recorder has nothing saved for that window."""


class ClipFailed(Exception):
    """ffmpeg could not make the clip."""


def _safe(text: str) -> str:
    """Strip the password out of anything before it reaches a log."""
    return _SAFE_URL.sub("//***:***@", text)


def parse_time(text: str) -> datetime:
    """Read a time in either the recorder's log shape or the URL shape."""
    cleaned = (text or "").strip().replace("T", " ").rstrip("Z")
    for shape in (LOG_TIME_FORMAT, "%Y-%m-%d %H:%M"):
        with contextlib.suppress(ValueError):
            return datetime.strptime(cleaned, shape)
    raise ValueError(f"not a time this app understands: {text!r}")


def format_time(when: datetime) -> str:
    """Put a time into the shape the playback URL wants."""
    return when.strftime(cfg.PLAYBACK_TIME_FORMAT)


@dataclass(frozen=True)
class Window:
    """One stretch of time to ask the recorder for."""

    channel: int
    start: datetime
    end: datetime

    @property
    def seconds(self) -> int:
        return int((self.end - self.start).total_seconds())

    @property
    def start_text(self) -> str:
        return format_time(self.start)

    @property
    def end_text(self) -> str:
        return format_time(self.end)

    def key(self, quality: str) -> str:
        return (f"{self.channel}-{self.start:%Y%m%d%H%M%S}"
                f"-{self.end:%Y%m%d%H%M%S}-{quality}")

    def filename(self, quality: str) -> str:
        return cfg.CLIP_NAME_TEMPLATE.format(
            channel=self.channel + 1,
            stamp=self.start.strftime(cfg.CLIP_STAMP_FORMAT),
            quality=quality,
        )


def window_for_alert(channel: int, started_at: str, ended_at: str | None) -> Window:
    """The window to ask for when somebody clicks a movement alert.

    Padded wide on purpose. Recording is movement triggered, so the saved
    block runs well past the alert itself, and the recorder trims the ask down
    to whatever it really has.
    """
    start = parse_time(started_at)
    end = parse_time(ended_at) if ended_at else start
    return Window(
        channel=channel,
        start=start - timedelta(seconds=cfg.CLIP_PAD_BEFORE_SECONDS),
        end=end + timedelta(seconds=cfg.CLIP_PAD_AFTER_SECONDS),
    )


def window_for_times(channel: int, start: str, end: str) -> Window:
    """The window for a time somebody typed in, with a cap on its length."""
    first = parse_time(start)
    last = parse_time(end)
    if last <= first:
        raise ValueError("the end has to be after the start")
    longest = timedelta(seconds=cfg.CLIP_MAX_SECONDS)
    if last - first > longest:
        last = first + longest
    return Window(channel=channel, start=first, end=last)


class ClipMaker:
    """Turns a window into a playable file, once per window."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def clip(self, window: Window, quality: str) -> Path:
        """The file for this window, making it first if it is not there."""
        if quality not in cfg.CLIP_QUALITIES:
            raise ValueError(f"unknown quality: {quality}")
        cfg.CLIPS_DIR.mkdir(parents=True, exist_ok=True)
        self._clear_old_clips()

        key = window.key(quality)
        done = cfg.CLIPS_DIR / f"{key}{cfg.CLIP_SUFFIX}"

        # One ffmpeg per clip. Two viewers of the same clip wait on the first.
        async with self._lock(key):
            if done.is_file() and done.stat().st_size > 0:
                return done
            await self._make(window, quality, done)
        return done

    @staticmethod
    def _encode_args(quality: str) -> list[str]:
        """The picture and sound settings both ways out share."""
        args = [
            "-c:v", cfg.CLIP_VIDEO_ENCODER,
            "-b:v", (cfg.CLIP_VIDEO_BITRATE_VIEW
                     if quality == cfg.CLIP_QUALITY_VIEW
                     else cfg.CLIP_VIDEO_BITRATE_FULL),
            "-c:a", cfg.CLIP_AUDIO_ENCODER,
            "-b:a", cfg.CLIP_AUDIO_BITRATE,
        ]
        if quality == cfg.CLIP_QUALITY_VIEW:
            return ["-vf", cfg.CLIP_VIEW_SCALE, *args]
        return args

    async def stream(
        self, window: Window, quality: str
    ) -> AsyncIterator[bytes]:
        """Hand out the clip while it is still arriving.

        For watching in the page. The recorder sends old video at normal
        speed, so building the whole file first would mean a wait as long as
        the clip. This starts in about two seconds instead.
        """
        if quality not in cfg.CLIP_QUALITIES:
            raise ValueError(f"unknown quality: {quality}")
        url = cfg.playback_url(window.channel, window.start_text, window.end_text)
        args = [
            cfg.FFMPEG_BIN,
            *cfg.FFMPEG_INPUT_ARGS,
            "-i", url,
            *self._encode_args(quality),
            *cfg.CLIP_STREAM_FLAGS,
            "-f", cfg.CLIP_FORMAT,
            "pipe:1",
        ]
        log.info("clip stream: camera %s, %s to %s, %s",
                 window.channel + 1, window.start_text, window.end_text, quality)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdout is not None

        try:
            # Nothing at all in this long means the recorder has no video
            # there. Say so plainly instead of handing back an empty file.
            first = await asyncio.wait_for(
                process.stdout.read(cfg.CLIP_STREAM_CHUNK),
                timeout=cfg.CLIP_STREAM_FIRST_BYTES_SECONDS,
            )
        except asyncio.TimeoutError:
            await _end(process)
            raise ClipFailed("the recorder did not send that clip in time")

        if not first:
            why = _safe((await process.stderr.read()).decode("utf-8", "replace"))
            await _end(process)
            if any(marker in why for marker in cfg.CLIP_EMPTY_MARKERS):
                raise NoVideo(cfg.CLIP_EMPTY_MESSAGE)
            log.warning("clip stream failed: %s", why[:400])
            raise ClipFailed(why.splitlines()[-1] if why.strip() else "ffmpeg stopped")

        async def feed() -> AsyncIterator[bytes]:
            try:
                yield first
                while True:
                    chunk = await process.stdout.read(cfg.CLIP_STREAM_CHUNK)
                    if not chunk:
                        return
                    yield chunk
            finally:
                # The browser can walk away mid clip, so always end ffmpeg.
                await _end(process)

        return feed()

    async def _make(self, window: Window, quality: str, done: Path) -> None:
        part = done.with_suffix(done.suffix + cfg.CLIP_PART_SUFFIX)
        part.unlink(missing_ok=True)
        url = cfg.playback_url(window.channel, window.start_text, window.end_text)

        args = [
            cfg.FFMPEG_BIN,
            *cfg.FFMPEG_INPUT_ARGS,
            "-i", url,
            *self._encode_args(quality),
            *cfg.CLIP_FLAGS,
            "-f", cfg.CLIP_FORMAT,
            str(part),
        ]

        log.info("clip: camera %s, %s to %s, %s",
                 window.channel + 1, window.start_text, window.end_text, quality)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, raw = await asyncio.wait_for(
                process.communicate(), timeout=cfg.CLIP_MAKE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            part.unlink(missing_ok=True)
            raise ClipFailed("the recorder took too long to send that clip")

        why = _safe((raw or b"").decode("utf-8", "replace").strip())
        if process.returncode != 0 or not part.is_file() or part.stat().st_size == 0:
            part.unlink(missing_ok=True)
            if any(marker in why for marker in cfg.CLIP_EMPTY_MARKERS):
                raise NoVideo(cfg.CLIP_EMPTY_MESSAGE)
            log.warning("clip failed: %s", why[:400])
            raise ClipFailed(why.splitlines()[-1] if why else "ffmpeg stopped")

        # Only ever rename a finished file into place, so a second request
        # can never be handed a half written one.
        part.replace(done)
        log.info("clip: saved %s, %.1f MB",
                 done.name, done.stat().st_size / 1024 / 1024)

    def _clear_old_clips(self) -> None:
        """Drop cached clips nobody has asked for in a while."""
        cutoff = time.time() - cfg.CLIP_KEEP_SECONDS
        for path in cfg.CLIPS_DIR.glob(f"*{cfg.CLIP_SUFFIX}*"):
            with contextlib.suppress(OSError):
                if path.stat().st_mtime < cutoff:
                    path.unlink()


async def _end(process: asyncio.subprocess.Process) -> None:
    """Stop an ffmpeg and wait for it, even if the caller was cancelled."""
    if process.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        process.kill()
    with contextlib.suppress(Exception):
        await asyncio.shield(process.wait())


def payload(window: Window, quality: str) -> dict[str, object]:
    """What the page needs to show and name one clip."""
    return {
        "channel": window.channel,
        "start": window.start.strftime(LOG_TIME_FORMAT),
        "end": window.end.strftime(LOG_TIME_FORMAT),
        "seconds": window.seconds,
        "quality": quality,
        "filename": window.filename(quality),
    }
