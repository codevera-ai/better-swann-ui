"""An MCP server for Better Swann UI, so an LLM can drive the recorder.

It talks to the local app on `http://127.0.0.1:8750`, never to the recorder.
That matters: the recorder only keeps one login per user, and a second login
pushes the first one out. The app owns that login, so everything goes through
the app.

It runs in its own virtual environment, `.venv-mcp`, because the MCP library
wants a newer Starlette than FastAPI allows.

Start the app first with `make run`, or every tool here will say the app is
not running.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

# -- settings, all in one place --------------------------------------------
APP_HOST = os.environ.get("SWANN_APP_HOST", "127.0.0.1")
APP_PORT = os.environ.get("SWANN_APP_PORT", "8750")
APP_URL = os.environ.get("SWANN_APP_URL", f"http://{APP_HOST}:{APP_PORT}")
READ_TIMEOUT = 45.0
WRITE_TIMEOUT = 90.0
SNAPSHOT_TIMEOUT = 45.0
SNAPSHOT_DIR = Path(
    os.environ.get("SWANN_SNAPSHOT_DIR", str(Path(__file__).resolve().parent.parent / "snapshots"))
)
SNAPSHOT_NAME = "camera-{channel}-{stamp}.jpg"
STAMP_FORMAT = "%Y%m%d-%H%M%S"
DEFAULT_ALERT_LIMIT = 50
DEFAULT_LOG_DAYS = 3
NOT_RUNNING = (
    "The Swann app is not running. Start it in a terminal with "
    "`cd ~/Sites/swann && make run`, then try again."
)

server = MCPServer(
    name="swann",
    version="0.1.0",
    instructions=(
        "Control a Swann or Xiongmai CCTV recorder on the local network. "
        "The Better Swann UI app must be running on this machine. Read tools are "
        "safe. Write tools change a live recorder, so say what will change "
        "before using one. restart_recorder and factory_reset stop the "
        "cameras recording, so always ask the person first."
    ),
)


# -- talking to the app ----------------------------------------------------
async def _call(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = READ_TIMEOUT,
) -> Any:
    url = f"{APP_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            reply = await client.request(method, url, params=params, json=body)
    except httpx.ConnectError:
        return {"error": NOT_RUNNING}
    except httpx.TimeoutException:
        return {"error": f"the app did not answer in {timeout:.0f} seconds"}
    try:
        data = reply.json()
    except ValueError:
        return {"error": f"the app answered {reply.status_code} with no detail"}
    if reply.status_code >= 400 and isinstance(data, dict):
        data.setdefault("error", f"the app said no, code {reply.status_code}")
    return data


async def _get(path: str, **params: Any) -> Any:
    clean = {k: v for k, v in params.items() if v is not None}
    return await _call("GET", path, params=clean)


async def _post(path: str, body: dict[str, Any] | None = None, **params: Any) -> Any:
    clean = {k: v for k, v in params.items() if v is not None}
    return await _call("POST", path, params=clean, body=body, timeout=WRITE_TIMEOUT)


# -- reading ----------------------------------------------------------------
@server.tool()
async def recorder_health() -> dict[str, Any]:
    """How the recorder is doing: disk, uptime, cameras and whether it is up.

    Safe. Changes nothing.
    """
    return await _get("/api/health")


@server.tool()
async def list_cameras() -> dict[str, Any]:
    """Which cameras are plugged in, their names and whether they are saving."""
    return await _get("/api/cameras")


@server.tool()
async def take_snapshot(channel: int, full_size: bool = False) -> dict[str, Any]:
    """Save a still from one camera, right now, and say where the file is.

    channel counts from 0, so camera 1 is channel 0.
    full_size takes the 4K picture instead of the small one. It is slower.
    """
    url = f"{APP_URL}/api/live/{channel}/snapshot"
    params = {"main": "true"} if full_size else None
    try:
        async with httpx.AsyncClient(timeout=SNAPSHOT_TIMEOUT) as client:
            reply = await client.get(url, params=params)
    except httpx.ConnectError:
        return {"error": NOT_RUNNING}
    except httpx.TimeoutException:
        return {"error": "the camera did not send a picture in time"}
    if reply.status_code >= 400:
        return {"error": reply.text[:200]}

    from datetime import datetime

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / SNAPSHOT_NAME.format(
        channel=channel + 1, stamp=datetime.now().strftime(STAMP_FORMAT)
    )
    path.write_bytes(reply.content)
    return {"path": str(path), "bytes": len(reply.content), "channel": channel}


@server.tool()
async def list_alerts(
    limit: int = DEFAULT_ALERT_LIMIT,
    kind: str | None = None,
    channel: int | None = None,
) -> dict[str, Any]:
    """Alerts this machine has stored, newest first, with totals.

    kind filters by what was seen, for example MotionDetect or HumanDetect.
    channel counts from 0. This reads this machine's own store, not the recorder,
    so it is fast and it goes back further than the recorder's own memory.
    """
    return await _get("/api/alerts", limit=limit, kind=kind, channel=channel)


@server.tool()
async def sync_alerts(days: int = 1) -> dict[str, Any]:
    """Copy the recorder's log into this machine's store right now.

    The app does this on its own every five minutes, so you rarely need it.
    """
    return await _post("/api/alerts/sync", params=None, days=days)


@server.tool()
async def read_log(type: str = "LogSystem", days: int = DEFAULT_LOG_DAYS) -> dict[str, Any]:
    """The recorder's own event log, newest first.

    The recorder only remembers about two and a half days.
    """
    return await _get("/api/log", type=type, days=days)


@server.tool()
async def list_settings_screens() -> dict[str, Any]:
    """Every settings screen, grouped, with its key. Use a key with read_settings."""
    return await _get("/api/settings")


@server.tool()
async def read_settings(key: str) -> dict[str, Any]:
    """Everything on one settings screen, with each field named and typed.

    Get the key from list_settings_screens. The reply tells you each field's
    config name, channel and path, which is what write_settings needs.
    """
    return await _get(f"/api/settings/{key}")


@server.tool()
async def list_accounts() -> dict[str, Any]:
    """Accounts on the recorder and what each is allowed to do.

    Passwords never leave the app, so they are not in this answer.
    """
    return await _get("/api/users")


# -- writing ----------------------------------------------------------------
@server.tool()
async def write_settings(key: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
    """Change fields on one settings screen, then read them back to check.

    key is the screen key. Each change is
    {"name": "<config name>", "channel": <number or null>,
     "path": "<field path from read_settings>", "value": <new value>}.

    Read the screen first and copy the name, channel and path from it. The
    answer says, per field, whether it saved and whether it really took
    effect, because this recorder sometimes says yes and ignores the write.
    """
    return await _post(f"/api/settings/{key}", {"changes": changes})


@server.tool()
async def write_account(
    name: str,
    enabled: bool | None = None,
    group: str | None = None,
    rights: list[str] | None = None,
) -> dict[str, Any]:
    """Turn an account on or off, change its group, or change what it may do.

    The admin account cannot be changed, because the app logs in as it.
    Passwords cannot be changed here. Use the recorder's own screen for that.
    """
    body: dict[str, Any] = {}
    if enabled is not None:
        body["enabled"] = enabled
    if group is not None:
        body["group"] = group
    if rights is not None:
        body["rights"] = rights
    if not body:
        return {"error": "say what to change: enabled, group or rights"}
    return await _post(f"/api/users/{name}", body)


@server.tool()
async def rename_camera(channel: int, name: str) -> dict[str, Any]:
    """Give one camera a name. The name is kept locally, not on the recorder.

    channel counts from 0. An empty name puts the recorder's own name back.
    """
    return await _post(f"/api/cameras/{channel}/name", {"name": name})


@server.tool()
async def backup_settings() -> dict[str, Any]:
    """Save every recorder setting to a file on this machine. Read only, always safe.

    Do this before any run of writes. The file holds real passwords, so
    never read it out or paste it anywhere.
    """
    return await _post("/api/backup")


@server.tool()
async def restart_recorder(confirm: str) -> dict[str, Any]:
    """Restart the recorder. Nothing is saved while it is off, about two minutes.

    Ask the person first. confirm must be the word restart, from them.
    """
    return await _post("/api/restart", {"confirm": confirm})


@server.tool()
async def factory_reset(confirm: str, areas: dict[str, bool]) -> dict[str, Any]:
    """Put chosen areas of the settings back to factory. This cannot be undone.

    Ask the person first, and back up first. confirm must be the word reset,
    from them. areas picks what to wipe, any of DisPlay, Device, Record,
    Network, Alarm, System, Advanced. Network wipes the recorder's address on
    the local network, so the app may not find it afterwards.
    """
    return await _post("/api/reset", {"confirm": confirm, "areas": areas})


def main() -> None:
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
