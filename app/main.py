"""The web server.

Serves the pages and a small JSON API on top of one shared recorder session.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from dataclasses import asdict
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from swann import config as cfg
from swann import settings as settings_engine
from swann.errors import RecorderError, RecorderUnreachable
from swann import alerts as alerts_store
from swann import live as live_video
from swann import names as camera_names
from swann import playback
from swann import users
from swann.backup import take_backup
from swann.health import read_health
from swann.models import Health
from swann.session import RecorderSession

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

PAGE_HEALTH = "health.html"
PAGE_SETTINGS = "settings.html"
PAGE_ALERTS = "alerts.html"
PAGE_LIVE = "live.html"
PAGE_CLIPS = "clips.html"
ROUTE_HOME = "/"
ROUTE_HEALTH = "/health"
ROUTE_SETTINGS = "/settings"
API_HEALTH = "/api/health"
API_STATUS = "/api/status"
API_SETTINGS = "/api/settings"
API_SETTINGS_SCREEN = "/api/settings/{key}"
API_LOG = "/api/log"
API_USERS = "/api/users"
API_USER_ONE = "/api/users/{name}"
API_BACKUP = "/api/backup"
API_RESTART = "/api/restart"
API_RESET = "/api/reset"
ROUTE_ALERTS = "/alerts"
API_ALERTS = "/api/alerts"
API_ALERTS_SYNC = "/api/alerts/sync"
ROUTE_LIVE = "/live"
API_CAMERAS = "/api/cameras"
API_CAMERA_NAME = "/api/cameras/{channel}/name"
API_PICTURES = "/api/live/{channel}/pictures"
API_SNAPSHOT = cfg.API_SNAPSHOT_TEMPLATE
API_VIDEO_PLAYLIST = "/api/live/{channel}/video/" + cfg.HLS_PLAYLIST
API_VIDEO_SEGMENT = "/api/live/{channel}/video/{name}"
ROUTE_CLIPS = "/clips"
API_CLIPS = "/api/clips"
API_CLIP_FILE = "/api/clips/{channel}/clip" + cfg.CLIP_SUFFIX
CLIP_PARAM_ALERT = "alert"
CLIP_PARAM_SAVE = "save"
CLIP_DISPOSITION = 'attachment; filename="{name}"'
NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate"}
STATUS_UNREACHABLE = 503
STATUS_BAD_REQUEST = 400
STATUS_NOT_FOUND = 404
STATUS_READ_ONLY = 403

session = RecorderSession()
cameras = live_video.LiveVideo()
clips = playback.ClipMaker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """One login for the life of the server, plus the alert copier."""
    cfg.ensure_dirs()
    for gap in cfg.missing_setup():
        log.error("setup: %s", gap)
    await session.start()
    syncer = asyncio.create_task(alerts_store.sync_loop(session))
    await cameras.start()
    try:
        yield
    finally:
        syncer.cancel()
        with suppress(asyncio.CancelledError):
            await syncer
        await cameras.stop()
        await session.stop()


app = FastAPI(title=cfg.APP_TITLE, lifespan=lifespan)
app.mount(cfg.STATIC_MOUNT, StaticFiles(directory=cfg.WEB_DIR), name="static")


def _page(name: str) -> FileResponse:
    path = cfg.WEB_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} is not built yet")
    return FileResponse(path)


def _health_payload(health: Health) -> dict[str, Any]:
    """Flatten a Health into something the page can read without guessing."""
    disk = health.main_disk
    partition = disk.video_partition if disk else None
    return {
        "reachable": health.reachable,
        "checkedAt": health.checked_at,
        "error": health.error,
        "device": {
            **asdict(health.device),
            "uptimeText": health.device.uptime_text,
            "totalRunText": health.device.total_run_text,
        },
        "disk": None
        if disk is None
        else {
            "model": disk.model,
            "state": disk.state,
            "healthy": disk.healthy,
            "serial": disk.serial,
            "spaceText": disk.space_text,
            "keptTimeText": disk.kept_time_text,
            "oldestVideo": disk.oldest_video,
            "newestVideo": disk.newest_video,
            "totalGb": None if partition is None else round(partition.total_gb, 2),
            "usedGb": None if partition is None else round(partition.used_gb, 2),
            "freeGb": None if partition is None else round(partition.free_gb, 2),
            "percentUsed": None if partition is None else partition.percent_used,
            "isFull": bool(partition and partition.is_full),
        },
        "channels": [
            {
                "index": c.index,
                "label": c.label,
                "inUse": c.in_use,
                "bitrateKbps": c.bitrate_kbps,
                "recording": c.recording,
                "resolution": c.resolution,
            }
            for c in health.channels
        ],
        "camerasInUse": health.cameras_in_use,
        "channelCount": health.device.channel_count or cfg.CHANNEL_COUNT,
        "overwriteOldest": health.overwrite_oldest,
        "recordingScheduled": health.recording_scheduled,
    }


@app.get(ROUTE_HOME, include_in_schema=False)
async def home() -> RedirectResponse:
    return RedirectResponse(ROUTE_LIVE)


@app.get(ROUTE_HEALTH, include_in_schema=False)
async def health_page() -> FileResponse:
    return _page(PAGE_HEALTH)


@app.get(API_STATUS)
async def status() -> dict[str, Any]:
    """Cheap check that does not talk to the recorder."""
    return {
        "connected": session.connected,
        "lastError": session.last_error,
        "host": cfg.RECORDER_HOST,
    }


@app.get(API_HEALTH)
async def health_api() -> JSONResponse:
    try:
        health = await read_health(session)
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse(
            {"reachable": False, "error": str(exc)}, status_code=STATUS_UNREACHABLE
        )
    payload = _health_payload(health)
    code = 200 if health.reachable else STATUS_UNREACHABLE
    return JSONResponse(payload, status_code=code)


# -- settings ------------------------------------------------------------
@app.get(ROUTE_SETTINGS, include_in_schema=False)
async def settings_page() -> FileResponse:
    return _page(PAGE_SETTINGS)


@app.get(API_SETTINGS)
async def settings_menu() -> dict[str, Any]:
    """The settings menu. Does not talk to the recorder."""
    return {"groups": settings_engine.groups(), "menuLabel": cfg.SETTINGS_MENU_LABEL}


@app.get(API_SETTINGS_SCREEN)
async def settings_screen(key: str) -> JSONResponse:
    """Every live value one settings screen shows."""
    try:
        screen = await settings_engine.read_screen(session, key)
    except KeyError:
        raise HTTPException(status_code=STATUS_NOT_FOUND, detail=f"no screen called {key}")
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse(
            {"key": key, "error": str(exc)}, status_code=STATUS_UNREACHABLE
        )
    return JSONResponse(settings_engine.payload(screen))


@app.post(API_SETTINGS_SCREEN)
async def settings_save(key: str, body: dict[str, Any] = Body(...)) -> JSONResponse:
    """Change fields on one settings screen, then read them back."""
    changes = body.get("changes")
    if not isinstance(changes, list) or not changes:
        raise HTTPException(status_code=STATUS_BAD_REQUEST, detail="nothing to change")
    try:
        results = await settings_engine.write_screen(session, key, changes)
    except KeyError:
        raise HTTPException(status_code=STATUS_NOT_FOUND, detail=f"no screen called {key}")
    except PermissionError as exc:
        raise HTTPException(status_code=STATUS_READ_ONLY, detail=str(exc))
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse({"error": str(exc)}, status_code=STATUS_UNREACHABLE)

    return JSONResponse(
        {
            "saved": all(r.saved and r.took_effect for r in results),
            "results": [
                {
                    "name": r.name,
                    "channel": r.channel,
                    "saved": r.saved,
                    "tookEffect": r.took_effect,
                    "ret": r.ret,
                    "message": r.message,
                }
                for r in results
            ],
        }
    )


@app.get(API_LOG)
async def log_api(
    type: str = cfg.LOG_TYPE_DEFAULT,
    days: int = cfg.LOG_DEFAULT_DAYS,
) -> JSONResponse:
    """The recorder's own event log, newest first."""
    if type not in cfg.LOG_TYPES:
        raise HTTPException(status_code=STATUS_BAD_REQUEST, detail=f"no log type {type}")
    end = datetime.now()
    begin = end - timedelta(days=max(1, min(days, cfg.LOG_MAX_DAYS)))
    try:
        rows = await session.read_log_pages(
            type,
            begin.strftime(cfg.RECORDER_DATE_FORMAT),
            end.strftime(cfg.RECORDER_DATE_FORMAT),
        )
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse({"error": str(exc)}, status_code=STATUS_UNREACHABLE)
    rows.sort(key=lambda r: r.get(cfg.LOG_KEY_TIME, ""), reverse=True)
    return JSONResponse({"type": type, "days": days, "rows": rows})


@app.get(API_USERS)
async def users_api() -> JSONResponse:
    """Accounts on the recorder. Passwords never leave the server."""
    try:
        reply = await session.read_users()
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse({"error": str(exc)}, status_code=STATUS_UNREACHABLE)
    return JSONResponse(users.payload(reply))


@app.post(API_USER_ONE)
async def user_write_api(name: str, body: dict[str, Any]) -> JSONResponse:
    """Change what one account is allowed to do, or turn it on and off."""
    try:
        outcome = await users.write_user(
            session,
            name,
            group=body.get("group"),
            enabled=body.get("enabled"),
            rights=body.get("rights"),
        )
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse({"error": str(exc)}, status_code=STATUS_UNREACHABLE)
    try:
        after = users.payload(await session.read_users())
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse({"error": str(exc)}, status_code=STATUS_UNREACHABLE)
    return JSONResponse(
        {
            "saved": outcome.saved,
            "message": outcome.message,
            "ret": outcome.ret,
            **after,
        }
    )


@app.post(API_RESTART)
async def restart_api(body: dict[str, Any]) -> JSONResponse:
    """Restart the recorder. The word must be typed, here and in the browser."""
    if str(body.get("confirm", "")).strip().lower() != cfg.CONFIRM_RESTART_WORD:
        return JSONResponse(
            {"error": f"type {cfg.CONFIRM_RESTART_WORD} to do this"},
            status_code=STATUS_BAD_REQUEST,
        )
    try:
        await session.restart_recorder()
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse({"error": str(exc)}, status_code=STATUS_UNREACHABLE)
    return JSONResponse(
        {
            "ok": True,
            "message": "The recorder is restarting. Give it a minute or two.",
        }
    )


@app.post(API_RESET)
async def reset_api(body: dict[str, Any]) -> JSONResponse:
    """Put chosen areas of the settings back to factory."""
    if str(body.get("confirm", "")).strip().lower() != cfg.CONFIRM_RESET_WORD:
        return JSONResponse(
            {"error": f"type {cfg.CONFIRM_RESET_WORD} to do this"},
            status_code=STATUS_BAD_REQUEST,
        )
    wanted = body.get("areas") or {}
    chosen = {key: bool(wanted.get(key)) for key in cfg.RESET_AREA_KEYS}
    if not any(chosen.values()):
        return JSONResponse(
            {"error": "pick at least one thing to put back"},
            status_code=STATUS_BAD_REQUEST,
        )
    try:
        reply = await session.reset_to_factory(chosen)
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse({"error": str(exc)}, status_code=STATUS_UNREACHABLE)
    ret = reply.get("Ret") if isinstance(reply, dict) else None
    return JSONResponse(
        {
            "ok": True,
            "ret": ret,
            "message": (
                "Put back. The recorder needs a restart for this to count."
                if ret == cfg.RET_NEED_REBOOT
                else "Put back."
            ),
        }
    )


@app.post(API_BACKUP)
async def backup_api() -> JSONResponse:
    """Save every setting to a file, using the session the app already holds."""
    result = await take_backup(session)
    return JSONResponse(
        {
            "ok": result.ok,
            "path": None if result.path is None else str(result.path),
            "takenAt": result.taken_at,
            "summary": result.summary,
            "read": len(result.read),
            "emptySockets": len(result.empty_sockets),
            "expectedMissing": result.expected_missing,
            "failed": result.failed,
            "error": result.error,
        },
        status_code=200 if result.error is None else STATUS_UNREACHABLE,
    )


# -- alerts --------------------------------------------------------------
@app.get(ROUTE_ALERTS, include_in_schema=False)
async def alerts_page() -> FileResponse:
    return _page(PAGE_ALERTS)


@app.get(API_ALERTS)
async def alerts_api(
    limit: int = cfg.ALERT_PAGE_SIZE,
    kind: str | None = None,
    channel: int | None = None,
) -> dict[str, Any]:
    """Alerts this machine has stored, newest first. Does not call the recorder."""
    rows = alerts_store.recent(limit=limit, kind=kind, channel=channel)
    return {
        "alerts": [alerts_store.payload(alert) for alert in rows],
        "summary": alerts_store.summary(),
    }


@app.post(API_ALERTS_SYNC)
async def alerts_sync_api(days: int = cfg.ALERT_SYNC_DAYS) -> JSONResponse:
    """Copy the recorder's log into this machine's store right now."""
    saved = await alerts_store.sync(session, days=days)
    return JSONResponse({"stored": saved, "summary": alerts_store.summary()})


# -- live video ----------------------------------------------------------
@app.get(ROUTE_LIVE, include_in_schema=False)
async def live_page() -> FileResponse:
    return _page(PAGE_LIVE)


@app.get(API_CAMERAS)
async def cameras_api(client: str | None = None) -> JSONResponse:
    """Which cameras are plugged in, so the page knows what to show.

    The live page asks this every few seconds, so it doubles as the page
    saying it is still open. See `swann/live.py` for why that is needed.
    """
    cameras.seen(client)
    try:
        health = await read_health(session)
    except (RecorderError, RecorderUnreachable) as exc:
        return JSONResponse({"error": str(exc)}, status_code=STATUS_UNREACHABLE)
    chosen = camera_names.all_names()
    return JSONResponse(
        {
            "cameras": [
                {
                    "channel": channel.index,
                    "label": chosen.get(channel.index) or channel.label,
                    "recorderLabel": channel.label,
                    "named": channel.index in chosen,
                    "inUse": channel.in_use,
                    "recording": channel.recording,
                    "resolution": channel.resolution,
                }
                for channel in health.channels
                if channel.in_use
            ],
            "running": cameras.running(),
        }
    )


@app.post(API_CAMERA_NAME)
async def camera_name_api(channel: int, body: dict[str, Any] = Body(...)) -> JSONResponse:
    """Give a camera a name of your own. Kept on this machine, not the recorder."""
    _check_channel(channel)
    saved = camera_names.set_name(channel, str(body.get("name", "")))
    return JSONResponse({"channel": channel, "name": saved})


@app.get(API_PICTURES)
async def pictures_api(channel: int, client: str | None = None) -> StreamingResponse:
    """A stream of JPEGs for one camera. Point an <img> tag at it."""
    _check_channel(channel)
    return StreamingResponse(
        cameras.pictures(channel, client),
        media_type=cfg.MJPEG_CONTENT_TYPE,
        headers=NO_CACHE,
    )


@app.get(API_SNAPSHOT)
async def snapshot_api(channel: int, main: bool = False) -> Response:
    """One still from a camera, right now."""
    _check_channel(channel)
    try:
        image = await live_video.snapshot(channel, main=main)
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=STATUS_UNREACHABLE, detail=str(exc))
    return Response(image, media_type=cfg.SNAPSHOT_MEDIA_TYPE, headers=NO_CACHE)


@app.get(API_VIDEO_PLAYLIST)
async def video_playlist_api(channel: int) -> FileResponse:
    """Starts the video if it is not already going, then hands back the list."""
    _check_channel(channel)
    try:
        folder = await cameras.video_folder(channel)
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=STATUS_UNREACHABLE, detail=str(exc))
    return FileResponse(
        folder / cfg.HLS_PLAYLIST,
        media_type=cfg.HLS_MEDIA_TYPE,
        headers=NO_CACHE,
    )


@app.get(ROUTE_CLIPS, include_in_schema=False)
async def clips_page() -> FileResponse:
    return _page(PAGE_CLIPS)


@app.get(API_CLIPS)
async def clips_api(
    channel: int = 0,
    day: str | None = None,
    limit: int = cfg.ALERT_PAGE_SIZE,
) -> dict[str, Any]:
    """Clips you can watch, taken from the movement alerts already stored.

    The recorder keeps no clip list, so the alert times are the list. Each one
    sits inside a saved block of video, which is what the player asks for.
    """
    _check_channel(channel)
    everything = alerts_store.recent(limit=cfg.ALERT_MAX_PAGE_SIZE, channel=channel)

    days: dict[str, int] = {}
    for row in everything:
        days[row.started_at[:10]] = days.get(row.started_at[:10], 0) + 1

    rows = everything
    if day:
        rows = [row for row in rows if row.started_at.startswith(day)]
    rows = rows[:max(1, min(limit, cfg.ALERT_MAX_PAGE_SIZE))]

    chosen = camera_names.all_names()
    summary = alerts_store.summary()
    return {
        "channel": channel,
        "cameras": [
            {
                "channel": camera["channel"],
                "label": chosen.get(camera["channel"]) or camera["label"],
                "count": camera["count"],
            }
            for camera in summary["cameras"]
        ],
        "days": [{"day": key, "count": count}
                 for key, count in sorted(days.items(), reverse=True)],
        "clips": [alerts_store.payload(row) for row in rows],
        "maxSeconds": cfg.CLIP_MAX_SECONDS,
        "defaultSeconds": cfg.CLIP_DEFAULT_SECONDS,
    }


@app.get(API_CLIP_FILE)
async def clip_file_api(
    channel: int,
    start: str,
    end: str | None = None,
    alert: bool = False,
    quality: str = cfg.CLIP_QUALITY_VIEW,
    save: bool = False,
) -> Response:
    """One clip as an MP4.

    Watching streams it, so it starts in about two seconds. Saving builds the
    whole file first, because a saved file has to be seekable.
    """
    _check_channel(channel)
    if quality not in cfg.CLIP_QUALITIES:
        raise HTTPException(status_code=STATUS_BAD_REQUEST,
                            detail=f"quality must be one of {cfg.CLIP_QUALITIES}")
    try:
        if alert:
            window = playback.window_for_alert(channel, start, end)
        else:
            window = playback.window_for_times(channel, start, end or start)
    except ValueError as exc:
        raise HTTPException(status_code=STATUS_BAD_REQUEST, detail=str(exc))

    try:
        if save:
            path = await clips.clip(window, quality)
            return FileResponse(
                path,
                media_type=cfg.CLIP_MEDIA_TYPE,
                headers={
                    **NO_CACHE,
                    "Content-Disposition": CLIP_DISPOSITION.format(
                        name=window.filename(quality)
                    ),
                },
            )
        feed = await clips.stream(window, quality)
    except playback.NoVideo as exc:
        raise HTTPException(status_code=STATUS_NOT_FOUND, detail=str(exc))
    except playback.ClipFailed as exc:
        raise HTTPException(status_code=STATUS_UNREACHABLE, detail=str(exc))

    return StreamingResponse(
        feed, media_type=cfg.CLIP_MEDIA_TYPE, headers=NO_CACHE
    )


@app.get(API_VIDEO_SEGMENT)
async def video_segment_api(channel: int, name: str) -> FileResponse:
    """One piece of video. Only a file this app wrote is ever served."""
    _check_channel(channel)
    folder = cfg.LIVE_DIR / f"{cfg.LIVE_MODE_VIDEO}-{channel}"
    path = (folder / name).resolve()
    if path.parent != folder.resolve() or not path.is_file():
        raise HTTPException(status_code=STATUS_NOT_FOUND, detail="no such piece")
    cameras.keep_alive(channel, cfg.LIVE_MODE_VIDEO)
    return FileResponse(
        path, media_type=cfg.HLS_SEGMENT_MEDIA_TYPE, headers=NO_CACHE
    )


def _check_channel(channel: int) -> None:
    if not 0 <= channel < cfg.CHANNEL_COUNT:
        raise HTTPException(
            status_code=STATUS_BAD_REQUEST, detail=f"there is no camera {channel + 1}"
        )
