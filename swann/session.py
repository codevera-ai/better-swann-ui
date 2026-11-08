"""One shared login to the recorder, kept alive in the background.

The recorder's login is per user, and a second login may push the first one out.
So the whole app shares one session rather than logging in per request. All calls
go through a lock, because the recorder's own web interface sends one at a time.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, TypeVar

from . import config as cfg
from .cgi import CgiClient
from .errors import RecorderError, RecorderUnreachable, SessionLost

log = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class WriteOutcome:
    """What one setting write did, with the old value so it can be put back."""

    name: str
    channel: int | None
    ret: int | None
    before: Any
    had_before: bool

    @property
    def saved(self) -> bool:
        return self.ret in cfg.RET_WRITE_OK_CODES

    @property
    def needs_reboot(self) -> bool:
        return self.ret == cfg.RET_NEED_REBOOT

    @property
    def message(self) -> str:
        if not self.saved:
            return "The recorder refused the change."
        if self.needs_reboot:
            return "Saved. The recorder needs a restart before it takes effect."
        return "Saved."


class RecorderSession:
    """Owns the one CGI login and the keepalive loop."""

    def __init__(self, client: CgiClient | None = None) -> None:
        self.client = client or CgiClient()
        self._lock = asyncio.Lock()
        self._keepalive_task: asyncio.Task[None] | None = None
        self.last_error: str | None = None
        self.connected = False
        self.boot_time: str | None = None
        self._boot_time_checked_at: float | None = None

    # -- lifecycle ---------------------------------------------------------
    async def start(self) -> None:
        """Log in and start the keepalive. Never raises, so the app still boots."""
        try:
            await self._login_locked()
        except (RecorderError, RecorderUnreachable) as exc:
            self.last_error = str(exc)
            log.warning("could not log in at startup: %s", exc)
        if self._keepalive_task is None:
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def stop(self) -> None:
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None
        async with self._lock:
            await self.client.logout()
            await self.client.close()
            self.connected = False

    async def _login_locked(self) -> None:
        async with self._lock:
            await self._login_now()

    async def _login_now(self) -> None:
        """Log in. The caller must already hold the lock.

        The recorder only keeps one login per user, and a second login
        pushes the first one out. So the check and the login must happen
        together, or two jobs starting at once log in twice and fight.
        """
        await self.client.login()
        self.connected = True
        self.last_error = None

    async def _keepalive_loop(self) -> None:
        """Ping often enough that the recorder never times the session out."""
        while True:
            await asyncio.sleep(cfg.KEEPALIVE_SECONDS)
            try:
                async with self._lock:
                    if self.client.logged_in:
                        await self.client.keep_alive()
                    else:
                        await self._login_now()
                self.connected = True
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except SessionLost:
                log.info("session expired, logging in again")
                try:
                    await self._login_locked()
                except (RecorderError, RecorderUnreachable) as exc:
                    self.connected = False
                    self.last_error = str(exc)
            except (RecorderError, RecorderUnreachable) as exc:
                self.connected = False
                self.last_error = str(exc)
                log.warning("keepalive failed: %s", exc)

    # -- calling through ---------------------------------------------------
    async def run(self, work: Callable[[CgiClient], Awaitable[T]]) -> T:
        """Run one piece of recorder work under the lock.

        On an expired session this logs in again and retries once. A second
        failure is passed up to the caller.
        """
        for attempt in range(cfg.LOGIN_RETRY_LIMIT + 1):
            try:
                async with self._lock:
                    if not self.client.logged_in:
                        await self._login_now()
                    result = await work(self.client)
                self.connected = True
                self.last_error = None
                return result
            except SessionLost as exc:
                if attempt >= cfg.LOGIN_RETRY_LIMIT:
                    self.connected = False
                    self.last_error = str(exc)
                    raise
                log.info("session expired mid call, logging in again")
                await self._login_locked()
            except (RecorderError, RecorderUnreachable) as exc:
                self.last_error = str(exc)
                raise
        raise AssertionError("unreachable")

    async def read_info(self, name: str) -> Any:
        return await self.run(lambda c: c.get_info(name))

    async def read_ability(self, name: str) -> Any:
        return await self.run(lambda c: c.get_ability(name))

    async def read_channel_ability(self, name: str) -> Any:
        return await self.run(lambda c: c.get_channel_ability(name))

    async def read_config(self, name: str, channel: int | None = None) -> Any:
        return await self.run(lambda c: c.get_config(name, channel))

    async def recorder_time(self) -> str:
        return await self.run(lambda c: c.recorder_time())

    async def read_log(
        self,
        log_type: str = cfg.LOG_TYPE_DEFAULT,
        begin: str = "",
        end: str = "",
        position: int = 0,
    ) -> list[Any]:
        return await self.run(lambda c: c.get_log(log_type, begin, end, position))

    async def read_log_pages(
        self,
        log_type: str = cfg.LOG_TYPE_DEFAULT,
        begin: str = "",
        end: str = "",
        max_pages: int = cfg.LOG_MAX_PAGES,
    ) -> list[Any]:
        """Every log row in a window, by walking the recorder's pages.

        The recorder answers at most LOG_PAGE_SIZE rows at a time and marks each
        row with a Position, so the next page starts past the highest one seen.
        """
        rows: list[Any] = []
        position = 0
        for _ in range(max_pages):
            page = await self.read_log(log_type, begin, end, position)
            if not page:
                break
            rows.extend(page)
            highest = max(
                (row.get(cfg.LOG_KEY_POSITION, 0) for row in page), default=position
            )
            if highest + 1 <= position:
                break
            position = highest + 1
        return rows

    async def read_boot_time(self) -> str | None:
        """When the recorder last started, from the newest Reboot row.

        Cached, because it only changes when the recorder restarts. Returns None
        when the log does not reach back far enough, which is normal: this
        recorder's log holds about 4096 rows, roughly two and a half days.
        """
        now = time.monotonic()
        if (
            self._boot_time_checked_at is not None
            and now - self._boot_time_checked_at < cfg.BOOT_CACHE_SECONDS
        ):
            return self.boot_time

        end = datetime.now()
        begin = end - timedelta(days=cfg.BOOT_LOOKBACK_DAYS)
        try:
            rows = await self.read_log_pages(
                cfg.LOG_TYPE_SYSTEM,
                begin.strftime(cfg.RECORDER_DATE_FORMAT),
                end.strftime(cfg.RECORDER_DATE_FORMAT),
            )
        except (RecorderError, RecorderUnreachable) as exc:
            log.debug("could not read the boot time: %s", exc)
            return self.boot_time

        reboots = [
            row.get(cfg.LOG_KEY_TIME)
            for row in rows
            if row.get(cfg.LOG_KEY_TYPE) == cfg.LOG_TYPE_REBOOT
        ]
        self._boot_time_checked_at = now
        self.boot_time = max(reboots) if reboots else None
        return self.boot_time

    async def read_users(self) -> Any:
        return await self.run(lambda c: c.get_users())

    async def read_upgrade_status(self) -> Any:
        return await self.run(lambda c: c.upgrade_status())

    # -- writes ------------------------------------------------------------
    async def write_config(
        self,
        name: str,
        value: Any,
        channel: int | None = None,
    ) -> WriteOutcome:
        """Write one setting, keeping the old value so it can be put back.

        The read and the write go through the same lock, so nothing else can
        change the setting in between.
        """
        before: Any = None
        had_before = False
        try:
            before = await self.read_config(name, channel)
            had_before = True
        except (RecorderError, RecorderUnreachable) as exc:
            log.warning("could not read %s before writing it: %s", name, exc)

        ret = await self.run(lambda c: c.set_config(name, value, channel))
        return WriteOutcome(
            name=name,
            channel=channel,
            ret=ret,
            before=before,
            had_before=had_before,
        )

    async def control(
        self,
        name: str,
        payload: Any = None,
        timeout: float | None = None,
    ) -> Any:
        return await self.run(lambda c: c.op_control(name, payload, timeout))

    async def manage_user(self, name: str, payload: Any = None) -> Any:
        return await self.run(lambda c: c.user_manage(name, payload))

    async def device_op(self, name: str, payload: Any = None) -> Any:
        return await self.run(lambda c: c.op_dev(name, payload))

    async def restart_recorder(self) -> Any:
        """Restart the recorder. It takes a minute or two to come back."""
        return await self.run(lambda c: c.reboot())

    async def reset_to_factory(self, areas: dict[str, bool]) -> Any:
        """Put chosen areas of the settings back to factory."""
        return await self.run(lambda c: c.factory_reset(areas))
