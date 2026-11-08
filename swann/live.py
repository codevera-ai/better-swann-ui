"""Live video, by turning the cameras' H.265 into something a browser plays.

No browser plays H.265 from a camera reliably, so ffmpeg sits in the middle.
This machine's own encoder chip does the work, so two cameras cost very little.

Two ways out:

  pictures  a stream of JPEGs straight down one HTTP reply. Under a second
            behind, no sound, works in any browser with a plain <img> tag.
  video     H.264 with sound, written as small files the browser stitches
            together. About four seconds behind, because a file has to be
            finished before it can be sent.

Nothing here is started until somebody asks to watch, and it stops itself
again once nobody has asked for half a minute.

Never log a stream URL. It carries the recorder password.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from . import config as cfg

log = logging.getLogger(__name__)


def _safe(url: str) -> str:
    """A stream URL with the password taken out, for logging."""
    head, _, tail = url.partition("://")
    _, _, rest = tail.partition("@")
    return f"{head}://{rest}" if rest else url


@dataclass
class Feed:
    """One running ffmpeg, feeding one camera to the browser one way."""

    channel: int
    mode: str
    process: asyncio.subprocess.Process | None = None
    folder: Path | None = None
    last_asked: float = field(default_factory=time.monotonic)
    starting: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    def touch(self) -> None:
        self.last_asked = time.monotonic()

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_asked


@dataclass
class PictureSource:
    """One ffmpeg making pictures for one camera, shared by every viewer.

    A browser can walk away without saying so, and the web server does not
    always notice. One shared ffmpeg per camera means a forgotten viewer
    costs nothing, and the camera is only read once however many tabs are
    open.
    """

    channel: int
    process: asyncio.subprocess.Process | None = None
    pump: asyncio.Task[None] | None = None
    viewers: dict[int, asyncio.Queue[bytes | None]] = field(default_factory=dict)
    full_runs: dict[int, int] = field(default_factory=dict)
    clients: dict[int, str] = field(default_factory=dict)
    last_wanted: float = field(default_factory=time.monotonic)

    @property
    def idle_seconds(self) -> float:
        if self.viewers:
            return 0.0
        return time.monotonic() - self.last_wanted


class LiveVideo:
    """Owns every running ffmpeg and shuts down the ones nobody is watching."""

    def __init__(self) -> None:
        self._feeds: dict[tuple[int, str], Feed] = {}
        self._sources: dict[int, PictureSource] = {}
        self._starting: dict[int, asyncio.Lock] = {}
        self._next_viewer: int = 0
        self._clients: dict[str, float] = {}
        self._reaper: asyncio.Task[None] | None = None

    # -- lifecycle ---------------------------------------------------------
    async def start(self) -> None:
        cfg.LIVE_DIR.mkdir(parents=True, exist_ok=True)
        self._clear_old_folders()
        if self._reaper is None:
            self._reaper = asyncio.create_task(self._reap_loop())

    async def stop(self) -> None:
        if self._reaper is not None:
            self._reaper.cancel()
            try:
                await self._reaper
            except asyncio.CancelledError:
                pass
            self._reaper = None
        for feed in list(self._feeds.values()):
            await self._stop_feed(feed)
        for channel in list(self._sources):
            await self._stop_source(channel)
        self._clear_old_folders()

    def _clear_old_folders(self) -> None:
        """Clear out segments left behind by a server that was killed."""
        if not cfg.LIVE_DIR.exists():
            return
        for child in cfg.LIVE_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)

    async def _reap_loop(self) -> None:
        while True:
            await asyncio.sleep(cfg.LIVE_POLL_SECONDS * 4)
            for key, feed in list(self._feeds.items()):
                if feed.idle_seconds > cfg.LIVE_IDLE_STOP_SECONDS:
                    log.info("camera %s %s: nobody watching, stopping",
                             feed.channel + 1, feed.mode)
                    await self._stop_feed(feed)
                    self._feeds.pop(key, None)
            self._cut_lost_viewers()
            for channel, source in list(self._sources.items()):
                if source.idle_seconds > cfg.LIVE_IDLE_STOP_SECONDS:
                    log.info("camera %s pictures: nobody watching, stopping",
                             channel + 1)
                    await self._stop_source(channel)

    async def _stop_feed(self, feed: Feed) -> None:
        process = feed.process
        feed.process = None
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), cfg.LIVE_STOP_GRACE_SECONDS)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if feed.folder is not None:
            shutil.rmtree(feed.folder, ignore_errors=True)
            feed.folder = None

    # -- pictures ----------------------------------------------------------
    def seen(self, client: str | None) -> None:
        """One open page says it is still there."""
        if client:
            self._clients[client] = time.monotonic()

    def _client_gone(self, client: str | None) -> bool:
        if not client:
            return False
        last = self._clients.get(client)
        if last is None:
            return True
        return time.monotonic() - last > cfg.LIVE_CLIENT_QUIET_SECONDS

    async def pictures(
        self, channel: int, client: str | None = None
    ) -> AsyncIterator[bytes]:
        """A never ending stream of JPEG frames, ready for an <img> tag.

        Every viewer of one camera reads the same ffmpeg. A viewer that
        cannot keep up loses frames, and one whose page has stopped saying
        hello is cut off, so a closed tab cannot hold a stream open.
        """
        source = await self._picture_source(channel)
        self.seen(client)
        self._next_viewer += 1
        tag = self._next_viewer
        post: asyncio.Queue[bytes | None] = asyncio.Queue(cfg.MJPEG_QUEUE_SIZE)
        source.viewers[tag] = post
        source.full_runs[tag] = 0
        if client:
            source.clients[tag] = client
        log.info("camera %s pictures: viewer %s joined", channel + 1, tag)
        try:
            while True:
                chunk = await post.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            source.viewers.pop(tag, None)
            source.full_runs.pop(tag, None)
            source.clients.pop(tag, None)
            source.last_wanted = time.monotonic()
            log.info("camera %s pictures: viewer %s left", channel + 1, tag)

    def _cut_lost_viewers(self) -> None:
        """Cut off every viewer whose page has stopped saying hello."""
        for source in self._sources.values():
            for tag, client in list(source.clients.items()):
                if not self._client_gone(client):
                    continue
                post = source.viewers.pop(tag, None)
                source.full_runs.pop(tag, None)
                source.clients.pop(tag, None)
                source.last_wanted = time.monotonic()
                log.info("camera %s pictures: viewer %s page closed",
                         source.channel + 1, tag)
                if post is not None:
                    _drain(post)
                    with contextlib.suppress(asyncio.QueueFull):
                        post.put_nowait(None)
        oldest = time.monotonic() - cfg.LIVE_CLIENT_QUIET_SECONDS
        for client, last in list(self._clients.items()):
            if last < oldest:
                self._clients.pop(client, None)

    async def _picture_source(self, channel: int) -> PictureSource:
        """The shared picture maker for one camera, started if it is not on."""
        lock = self._starting.setdefault(channel, asyncio.Lock())
        async with lock:
            source = self._sources.get(channel)
            if source is not None:
                return source
            source = PictureSource(channel=channel)
            source.pump = asyncio.create_task(self._pump(source))
            self._sources[channel] = source
            return source

    async def _start_pictures(
        self, channel: int
    ) -> asyncio.subprocess.Process:
        url = cfg.rtsp_url(channel, cfg.RTSP_STREAM_EXTRA)
        args = [
            cfg.FFMPEG_BIN,
            *cfg.FFMPEG_INPUT_ARGS,
            "-i", url,
            "-an",
            "-vf", f"scale={cfg.MJPEG_WIDTH}:-2,fps={cfg.MJPEG_FPS}",
            "-q:v", str(cfg.MJPEG_QUALITY),
            "-f", "mpjpeg",
            "-boundary_tag", cfg.MJPEG_BOUNDARY,
            "pipe:1",
        ]
        log.info("camera %s pictures: starting", channel + 1)
        # ffmpeg's own messages go straight to the server log. A pipe nobody
        # reads fills up and stops ffmpeg dead, so never use one here.
        return await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,
        )

    async def _pump(self, source: PictureSource) -> None:
        """Keep one camera's pictures flowing to every viewer.

        If the camera drops, this starts it again. The viewers' pages stay
        open, so the picture comes back on its own. The recorder restarts
        itself every Sunday, so this will happen every week.
        """
        try:
            while True:
                process = await self._start_pictures(source.channel)
                source.process = process
                assert process.stdout is not None
                while True:
                    chunk = await process.stdout.read(cfg.MJPEG_READ_BYTES)
                    if not chunk:
                        break
                    self._hand_out(source, chunk)
                await _end(process)
                source.process = None
                log.info("camera %s pictures: camera dropped, trying again",
                         source.channel + 1)
                await asyncio.sleep(cfg.LIVE_RETRY_SECONDS)
        except asyncio.CancelledError:
            raise
        finally:
            if source.process is not None:
                await _end(source.process)
                source.process = None

    @staticmethod
    def _hand_out(source: PictureSource, chunk: bytes) -> None:
        for tag, post in list(source.viewers.items()):
            if post.full():
                # Behind. Drop the oldest piece to make room.
                source.full_runs[tag] = source.full_runs.get(tag, 0) + 1
                if source.full_runs[tag] > cfg.MJPEG_MAX_BEHIND:
                    log.info("camera %s pictures: viewer %s is gone",
                             source.channel + 1, tag)
                    source.viewers.pop(tag, None)
                    source.full_runs.pop(tag, None)
                    _drain(post)
                    post.put_nowait(None)
                    continue
                _drop_one(post)
            else:
                source.full_runs[tag] = 0
            post.put_nowait(chunk)

    async def _stop_source(self, channel: int) -> None:
        source = self._sources.pop(channel, None)
        if source is None:
            return
        if source.pump is not None:
            source.pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await source.pump
        for post in list(source.viewers.values()):
            _drain(post)
            with contextlib.suppress(asyncio.QueueFull):
                post.put_nowait(None)
        source.viewers.clear()
        if source.process is not None:
            await _end(source.process)
        log.info("camera %s pictures: stopped", channel + 1)

    # -- video with sound --------------------------------------------------
    async def video_folder(self, channel: int) -> Path:
        """Make sure a camera's video is being written, and say where.

        Shared: every viewer of the same camera reads the same files.
        """
        key = (channel, cfg.LIVE_MODE_VIDEO)
        feed = self._feeds.get(key)
        if feed is None:
            feed = Feed(channel=channel, mode=cfg.LIVE_MODE_VIDEO)
            self._feeds[key] = feed
        feed.touch()

        async with feed.starting:
            if feed.running and feed.folder is not None:
                return feed.folder
            await self._start_video(feed)
        assert feed.folder is not None
        return feed.folder

    async def _start_video(self, feed: Feed) -> None:
        folder = cfg.LIVE_DIR / f"{cfg.LIVE_MODE_VIDEO}-{feed.channel}"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        url = cfg.rtsp_url(feed.channel, cfg.RTSP_STREAM_EXTRA)
        args = [
            cfg.FFMPEG_BIN,
            *cfg.FFMPEG_INPUT_ARGS,
            "-i", url,
            "-c:v", cfg.HLS_VIDEO_ENCODER,
            "-b:v", cfg.HLS_VIDEO_BITRATE,
            "-force_key_frames", cfg.HLS_KEY_FRAMES,
            "-c:a", cfg.HLS_AUDIO_ENCODER,
            "-b:a", cfg.HLS_AUDIO_BITRATE,
            "-ar", cfg.HLS_AUDIO_RATE,
            "-ac", str(cfg.HLS_AUDIO_CHANNELS),
            "-af", cfg.HLS_AUDIO_FILTER,
            "-f", "hls",
            "-hls_time", str(cfg.HLS_SEGMENT_SECONDS),
            "-hls_list_size", str(cfg.HLS_SEGMENT_COUNT),
            "-hls_flags", cfg.HLS_FLAGS,
            "-hls_segment_filename", str(folder / cfg.HLS_SEGMENT_PATTERN),
            str(folder / cfg.HLS_PLAYLIST),
        ]
        log.info("camera %s video: starting, from %s",
                 feed.channel + 1, _safe(url))
        feed.process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        feed.folder = folder

        playlist = folder / cfg.HLS_PLAYLIST
        waited = 0.0
        while waited < cfg.LIVE_START_TIMEOUT_SECONDS:
            if _segments_ready(folder, playlist):
                return
            if feed.process.returncode is not None:
                why = await _read_error(feed.process)
                raise RuntimeError(f"the video could not be started. {why}")
            await asyncio.sleep(cfg.LIVE_POLL_SECONDS)
            waited += cfg.LIVE_POLL_SECONDS
        await self._stop_feed(feed)
        raise TimeoutError("the camera did not send video in time")

    def keep_alive(self, channel: int, mode: str) -> None:
        """Say somebody is still watching, so the reaper leaves it alone."""
        feed = self._feeds.get((channel, mode))
        if feed is not None:
            feed.touch()

    def running(self) -> list[dict[str, object]]:
        return [
            {
                "channel": feed.channel,
                "mode": feed.mode,
                "running": feed.running,
                "idleSeconds": round(feed.idle_seconds, 1),
            }
            for feed in self._feeds.values()
        ]


async def snapshot(channel: int, main: bool = False) -> bytes:
    """One JPEG from a camera, right now."""
    stream = cfg.RTSP_STREAM_MAIN if main else cfg.RTSP_STREAM_EXTRA
    url = cfg.rtsp_url(channel, stream)
    args = [
        cfg.FFMPEG_BIN,
        *cfg.FFMPEG_INPUT_ARGS,
        "-i", url,
        "-frames:v", "1",
        "-vf", f"scale={cfg.SNAPSHOT_WIDTH}:-2",
        "-q:v", str(cfg.SNAPSHOT_QUALITY),
        "-f", "image2",
        "pipe:1",
    ]
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(
            process.communicate(), cfg.SNAPSHOT_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError("the camera did not send a picture in time") from None
    if process.returncode != 0 or not out.startswith(cfg.JPEG_START):
        detail = err.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "the camera sent nothing")
    return out


def _drop_one(post: "asyncio.Queue[bytes | None]") -> None:
    with contextlib.suppress(asyncio.QueueEmpty):
        post.get_nowait()


def _drain(post: "asyncio.Queue[bytes | None]") -> None:
    while True:
        try:
            post.get_nowait()
        except asyncio.QueueEmpty:
            return


async def _end(process: asyncio.subprocess.Process) -> None:
    """Stop one ffmpeg, politely first, then for real."""
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(
            asyncio.shield(process.wait()), cfg.LIVE_STOP_GRACE_SECONDS
        )
    except (asyncio.TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()


def _segments_ready(folder: Path, playlist: Path) -> bool:
    """True once the list names enough finished pieces to play without a gap."""
    if not playlist.exists() or playlist.stat().st_size == 0:
        return False
    named = [
        line.strip()
        for line in playlist.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if len(named) < cfg.HLS_START_SEGMENTS:
        return False
    return all((folder / name).is_file() for name in named)


async def _read_error(process: asyncio.subprocess.Process) -> str:
    if process.stderr is None:
        return "no reason given"
    raw = await process.stderr.read()
    lines = raw.decode("utf-8", "replace").strip().splitlines()
    return lines[-1] if lines else "no reason given"
