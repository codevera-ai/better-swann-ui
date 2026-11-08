"""The recorder's JSON API on port 85.

Every request is a POST to /cgi-bin/<verb>.cgi with a JSON body. The session is
a cookie, and every call after login must also carry the salt in its body.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from . import config as cfg
from .errors import RecorderError, RecorderUnreachable, SessionLost
from .hashing import login_sign

log = logging.getLogger(__name__)


class CgiClient:
    """One connection to the recorder's JSON API. Not safe to share without a lock."""

    def __init__(
        self,
        host: str = cfg.RECORDER_HOST,
        port: int = cfg.CGI_PORT,
        user: str = cfg.RECORDER_USER,
        password: str = cfg.RECORDER_PASS,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._salt: str | None = None
        self._client: httpx.AsyncClient | None = None
        self.login_info: dict[str, Any] = {}

    # -- plumbing ----------------------------------------------------------
    @property
    def logged_in(self) -> bool:
        return self._salt is not None

    def _url(self, verb: str) -> str:
        return cfg.CGI_URL_TEMPLATE.format(host=self._host, port=self._port, verb=verb)

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=cfg.CGI_TIMEOUT_SECONDS,
                headers={"Content-Type": cfg.CGI_CONTENT_TYPE},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._salt = None

    async def call(
        self,
        verb: str,
        body: dict[str, Any],
        *,
        timeout: float | None = None,
        with_salt: bool = True,
        ok_codes: tuple[int, ...] = cfg.RET_OK_CODES,
    ) -> dict[str, Any]:
        """Send one request and hand back the parsed reply.

        Raises SessionLost on Ret 105 so the caller can log in again, and
        RecorderError on any other refusal. A write passes RET_WRITE_OK_CODES,
        because a write may answer 603 to mean "saved, needs a reboot".
        """
        payload = dict(body)
        if with_salt and self._salt is not None:
            payload.setdefault("Salt", self._salt)

        client = await self._http()
        try:
            response = await client.post(
                self._url(verb),
                json=payload,
                timeout=timeout or cfg.CGI_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise RecorderUnreachable(f"{verb} could not reach the recorder") from exc

        try:
            reply = response.json()
        except ValueError as exc:
            raise RecorderError(verb, None, response.text[:200]) from exc

        action = f"{verb} {body.get('Name', '')}".strip()
        ret = reply.get("Ret")
        if ret == cfg.RET_SESSION_LOST:
            raise SessionLost(action, ret, reply)
        if ret not in ok_codes:
            raise RecorderError(action, ret, reply)
        return reply

    # -- session -----------------------------------------------------------
    async def login(self) -> dict[str, Any]:
        """Two steps: ask for a salt, then sign the password with it."""
        salt_reply = await self.call(
            cfg.VERB_LOGIN, {"Name": cfg.NAME_GET_SALT}, with_salt=False
        )
        salt = salt_reply.get("Salt")
        if not salt:
            raise RecorderError(cfg.NAME_GET_SALT, salt_reply.get("Ret"), salt_reply)

        info = await self.call(
            cfg.VERB_LOGIN,
            {
                "Name": cfg.NAME_LOGIN,
                "User": self._user,
                "Salt": salt,
                "Sign": login_sign(salt, self._password),
            },
            with_salt=False,
        )
        self._salt = salt
        self.login_info = info
        log.info(
            "recorder login ok, %s channels, alive interval %ss",
            info.get("ChannelNum"),
            info.get("AliveInterval"),
        )
        return info

    async def keep_alive(self) -> None:
        await self.call(cfg.VERB_LOGIN, {"Name": cfg.NAME_KEEP_ALIVE})

    async def logout(self) -> None:
        if not self.logged_in:
            return
        try:
            await self.call(cfg.VERB_LOGIN, {"Name": cfg.NAME_LOGOUT})
        except (RecorderError, RecorderUnreachable):
            log.debug("logout was refused, dropping the session anyway")
        finally:
            self._salt = None

    @property
    def uses_aes(self) -> bool:
        """This recorder reports false. If it ever turns true, stop writing config."""
        return bool(self.login_info.get("DataUseAES", False))

    # -- reads -------------------------------------------------------------
    async def get_info(self, name: str) -> Any:
        reply = await self.call(cfg.VERB_GET_INFO, {"Name": name})
        return reply.get(name, reply)

    async def get_ability(self, name: str) -> Any:
        reply = await self.call(cfg.VERB_GET_ABILITY, {"Name": name})
        return reply.get(name, reply)

    async def get_channel_ability(self, name: str) -> Any:
        reply = await self.call(cfg.VERB_GET_CHANNEL_ABILITY, {"Name": name})
        return reply.get(name, reply)

    async def get_config(self, name: str, channel: int | None = None) -> Any:
        full = name if channel is None else cfg.channel_config_name(name, channel)
        reply = await self.call(cfg.VERB_GET_CONFIG, {"Name": full})
        return reply.get(full, reply.get(name, reply))

    async def op_dev(self, name: str, payload: Any = None) -> Any:
        body: dict[str, Any] = {"Name": name}
        if payload is not None:
            body[name] = payload
        reply = await self.call(cfg.VERB_OP_DEV, body)
        return reply.get(name, reply)

    async def recorder_time(self) -> str:
        """The recorder's own clock, as it writes it."""
        return await self.op_dev(cfg.NAME_OP_TIME_QUERY)

    async def get_log(
        self,
        log_type: str = cfg.LOG_TYPE_DEFAULT,
        begin: str = "",
        end: str = "",
        position: int = 0,
    ) -> list[dict[str, Any]]:
        """One page of the recorder's own event log, oldest first.

        Shape taken from the recorder's Dev_log.js lines 85 to 95.
        """
        query: dict[str, Any] = {"Type": log_type, "LogPosition": position}
        if begin:
            query["BeginTime"] = begin
        if end:
            query["EndTime"] = end
        reply = await self.call(
            cfg.VERB_GET_LOG,
            {"Name": cfg.NAME_OP_LOG_QUERY, cfg.NAME_OP_LOG_QUERY: query},
        )
        entries = reply.get(cfg.NAME_OP_LOG_QUERY)
        return entries if isinstance(entries, list) else []

    async def get_users(self) -> dict[str, Any]:
        """Every account and group on the recorder. Passwords are not returned."""
        reply = await self.call(
            cfg.VERB_USER_MANAGER, {"Name": cfg.NAME_GET_ALL_USER}
        )
        return reply

    async def upgrade_status(self) -> Any:
        """Read the firmware state. This does not start an upgrade."""
        reply = await self.call(
            cfg.VERB_UPGRADE, {"Name": cfg.NAME_UPGRADE_STATUS}
        )
        return reply.get(cfg.NAME_UPGRADE_STATUS, reply)

    # -- writes ------------------------------------------------------------
    # Everything below changes the recorder. Read the old value first and keep
    # it, so a change can always be put back.

    async def set_config(
        self,
        name: str,
        value: Any,
        channel: int | None = None,
    ) -> int | None:
        """Write one setting. Returns the Ret code, which the caller may show.

        Ret 100 means saved. Ret 603 means saved but needs a reboot to take
        effect. The recorder's own interface treats both as success, see its
        main.js line 1092.
        """
        if self.uses_aes:
            raise RecorderError(
                "set_config", None, "this recorder now encrypts config, writing is unsafe"
            )
        full = name if channel is None else cfg.channel_config_name(name, channel)
        reply = await self.call(
            cfg.VERB_SET_CONFIG,
            {"Name": full, full: value},
            ok_codes=cfg.RET_WRITE_OK_CODES,
        )
        return reply.get("Ret")

    async def op_control(
        self,
        name: str,
        payload: Any = None,
        timeout: float | None = None,
    ) -> Any:
        """Send a test or a live control command, such as a camera move."""
        body: dict[str, Any] = {"Name": name}
        if payload is not None:
            body[name] = payload
        reply = await self.call(
            cfg.VERB_OP_CONTROL,
            body,
            timeout=timeout,
            ok_codes=cfg.RET_WRITE_OK_CODES,
        )
        return reply.get(name, reply)

    async def user_manage(self, name: str, fields: dict[str, Any] | None = None) -> Any:
        """Change an account.

        This verb is not like the others. Its fields sit at the top of the
        body, beside "Name", not inside a box named after it. Read off the
        recorder's own page, plugin.js line 364.
        """
        body: dict[str, Any] = {"Name": name}
        if fields:
            body.update(fields)
        reply = await self.call(
            cfg.VERB_USER_MANAGER, body, ok_codes=cfg.RET_WRITE_OK_CODES
        )
        return reply

    async def reboot(self) -> Any:
        """Restart the recorder. Cameras stop recording until it comes back."""
        return await self.op_dev(
            cfg.NAME_OP_MACHINE, {"Action": cfg.OP_MACHINE_REBOOT}
        )

    async def factory_reset(self, areas: dict[str, bool]) -> Any:
        """Put chosen areas back to factory. Every area is a true or false.

        The recorder resets one area at a time, not the whole thing at once.
        Read off its own page, rsui/cfg/syswh_mr.js line 10.
        """
        body = {key: bool(areas.get(key)) for key in cfg.RESET_AREA_KEYS}
        return await self.op_dev(cfg.NAME_OP_DEFAULT_CONFIG, body)

    async def test_email(self, settings: Any) -> Any:
        return await self.op_control(
            cfg.NAME_OP_MAIL_TEST,
            settings,
            timeout=cfg.OP_MAIL_TEST_TIMEOUT_SECONDS,
        )

    async def test_ddns(self, settings: Any) -> Any:
        return await self.op_control(
            cfg.NAME_OP_DDNS_TEST,
            settings,
            timeout=cfg.OP_DDNS_TEST_TIMEOUT_SECONDS,
        )
