"""Alerts, built from the recorder's own event log.

The recorder already writes down every alert: a row when one starts and a row
when it stops. It keeps about 4096 rows, which is two and a half days here. So
this machine copies them into a small file of its own every few minutes, and the
history keeps growing past what the recorder remembers.

Nothing here writes to the recorder. The log is read only.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from . import config as cfg
from .errors import RecorderError, RecorderUnreachable
from .models import parse_recorder_time
from .session import RecorderSession

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Alert:
    """One thing a camera saw, from the moment it started to the moment it stopped."""

    kind: str
    channel: int
    started_at: str
    ended_at: str | None = None
    seconds: int | None = None

    @property
    def label(self) -> str:
        return cfg.ALERT_KIND_LABELS.get(self.kind, cfg.ALERT_KIND_UNKNOWN)

    @property
    def camera(self) -> str:
        return cfg.CHANNEL_LABEL_TEMPLATE.format(number=self.channel + 1)

    @property
    def still_going(self) -> bool:
        return self.ended_at is None


def _connect() -> sqlite3.Connection:
    cfg.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cfg.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(cfg.ALERTS_SCHEMA)
    return conn


def _split_data(data: Any) -> tuple[str, int] | None:
    """Turn "MotionDetect,1" into ("MotionDetect", 0), a zero based camera."""
    if not isinstance(data, str) or cfg.ALERT_DATA_SEPARATOR not in data:
        return None
    kind, _, tail = data.partition(cfg.ALERT_DATA_SEPARATOR)
    try:
        number = int(tail.strip())
    except ValueError:
        return None
    return kind.strip(), max(number - cfg.ALERT_CHANNEL_BASE, 0)


def pair_rows(rows: Iterable[dict[str, Any]]) -> list[Alert]:
    """Match each start row to the stop row that follows it.

    An alert with no stop row is still running, or the recorder forgot to write
    the stop. Either way it is kept, with no end time.
    """
    ordered = sorted(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: (row.get(cfg.LOG_KEY_TIME, ""), row.get(cfg.LOG_KEY_POSITION, 0)),
    )
    open_alerts: dict[tuple[str, int], Alert] = {}
    done: list[Alert] = []

    for row in ordered:
        kind_channel = _split_data(row.get(cfg.LOG_KEY_DATA))
        if kind_channel is None:
            continue
        kind, channel = kind_channel
        when = row.get(cfg.LOG_KEY_TIME, "")
        row_type = row.get(cfg.LOG_KEY_TYPE)

        if row_type == cfg.LOG_EVENT_START:
            # A second start with no stop in between replaces the first.
            previous = open_alerts.get(kind_channel)
            if previous is not None:
                done.append(previous)
            open_alerts[kind_channel] = Alert(kind=kind, channel=channel, started_at=when)
        elif row_type == cfg.LOG_EVENT_STOP:
            alert = open_alerts.pop(kind_channel, None)
            if alert is None:
                continue
            alert.ended_at = when
            alert.seconds = _gap(alert.started_at, when)
            done.append(alert)

    done.extend(open_alerts.values())
    done.sort(key=lambda alert: alert.started_at, reverse=True)
    return done


def _gap(start: str, end: str) -> int | None:
    first = parse_recorder_time(start)
    last = parse_recorder_time(end)
    if first is None or last is None:
        return None
    seconds = int((last - first).total_seconds())
    return seconds if seconds >= 0 else None


def save(alerts: Iterable[Alert]) -> int:
    """Put alerts in this machine's own store. An alert already there is updated."""
    rows = [
        (alert.kind, alert.channel, alert.started_at, alert.ended_at, alert.seconds)
        for alert in alerts
    ]
    if not rows:
        return 0
    with closing(_connect()) as conn, conn:
        conn.executemany(
            "INSERT INTO alerts (kind, channel, started_at, ended_at, seconds) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (kind, channel, started_at) DO UPDATE SET "
            "  ended_at = COALESCE(excluded.ended_at, alerts.ended_at), "
            "  seconds  = COALESCE(excluded.seconds,  alerts.seconds)",
            rows,
        )
    return len(rows)


def recent(
    limit: int = cfg.ALERT_PAGE_SIZE,
    kind: str | None = None,
    channel: int | None = None,
) -> list[Alert]:
    """Alerts from this machine's store, newest first."""
    limit = max(1, min(limit, cfg.ALERT_MAX_PAGE_SIZE))
    where, args = [], []
    if kind:
        where.append("kind = ?")
        args.append(kind)
    if channel is not None:
        where.append("channel = ?")
        args.append(channel)
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    with closing(_connect()) as conn:
        rows = conn.execute(
            f"SELECT kind, channel, started_at, ended_at, seconds FROM alerts"
            f"{clause} ORDER BY started_at DESC LIMIT ?",
            (*args, limit),
        ).fetchall()
    return [Alert(**dict(row)) for row in rows]


def summary() -> dict[str, Any]:
    """Counts for the top of the alerts page."""
    with closing(_connect()) as conn:
        total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        oldest = conn.execute("SELECT MIN(started_at) FROM alerts").fetchone()[0]
        newest = conn.execute("SELECT MAX(started_at) FROM alerts").fetchone()[0]
        by_kind = conn.execute(
            "SELECT kind, COUNT(*) AS n FROM alerts GROUP BY kind ORDER BY n DESC"
        ).fetchall()
        by_camera = conn.execute(
            "SELECT channel, COUNT(*) AS n FROM alerts GROUP BY channel ORDER BY channel"
        ).fetchall()
    return {
        "total": total,
        "oldest": oldest,
        "newest": newest,
        "kinds": [
            {
                "kind": row["kind"],
                "label": cfg.ALERT_KIND_LABELS.get(row["kind"], cfg.ALERT_KIND_UNKNOWN),
                "count": row["n"],
            }
            for row in by_kind
        ],
        "cameras": [
            {
                "channel": row["channel"],
                "label": cfg.CHANNEL_LABEL_TEMPLATE.format(number=row["channel"] + 1),
                "count": row["n"],
            }
            for row in by_camera
        ],
    }


async def sync(session: RecorderSession, days: int = cfg.ALERT_SYNC_DAYS) -> int:
    """Copy the recorder's alert log into this machine's store. Returns how many."""
    end = datetime.now()
    begin = end - timedelta(days=max(1, days))
    try:
        rows = await session.read_log_pages(
            cfg.LOG_TYPE_ALARM,
            begin.strftime(cfg.RECORDER_DATE_FORMAT),
            end.strftime(cfg.RECORDER_DATE_FORMAT),
        )
    except (RecorderError, RecorderUnreachable) as exc:
        log.warning("alert sync could not read the log: %s", exc)
        return 0
    found = pair_rows(rows)
    saved = save(found)
    log.info("alert sync: %s rows read, %s alerts stored", len(rows), saved)
    return saved


async def sync_loop(session: RecorderSession) -> None:
    """Keep copying the log in the background, so history outlives the recorder's."""
    await asyncio.sleep(cfg.ALERT_FIRST_SYNC_DELAY_SECONDS)
    while True:
        try:
            await sync(session)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001  the loop must never die
            log.exception("alert sync failed, will try again")
        await asyncio.sleep(cfg.ALERT_SYNC_SECONDS)


def payload(alert: Alert) -> dict[str, Any]:
    return {
        "kind": alert.kind,
        "label": alert.label,
        "channel": alert.channel,
        "camera": alert.camera,
        "startedAt": alert.started_at,
        "endedAt": alert.ended_at,
        "seconds": alert.seconds,
        "stillGoing": alert.still_going,
    }
