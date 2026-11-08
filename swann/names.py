"""Friendly camera names, kept on this machine.

The recorder will not take a new camera name, and the names burned into the
picture belong to the cameras, not the recorder. So this app keeps its own.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from . import config as cfg


def _connect() -> sqlite3.Connection:
    cfg.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cfg.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(cfg.NAMES_SCHEMA)
    return conn


def all_names() -> dict[int, str]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT channel, name FROM camera_names").fetchall()
    return {row["channel"]: row["name"] for row in rows}


def set_name(channel: int, name: str) -> str:
    """Save a name, or clear it when the name is blank."""
    clean = name.strip()[: cfg.NAME_MAX_LENGTH]
    with closing(_connect()) as conn, conn:
        if clean:
            conn.execute(
                "INSERT INTO camera_names (channel, name) VALUES (?, ?) "
                "ON CONFLICT (channel) DO UPDATE SET name = excluded.name",
                (channel, clean),
            )
        else:
            conn.execute("DELETE FROM camera_names WHERE channel = ?", (channel,))
    return clean


def label(channel: int, fallback: str) -> str:
    return all_names().get(channel) or fallback
