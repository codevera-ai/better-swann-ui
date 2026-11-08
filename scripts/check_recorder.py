"""Check the recorder answers, without starting the web server.

Run it with: make check
"""
from __future__ import annotations

import asyncio
import sys

from swann import config as cfg
from swann.errors import RecorderError, RecorderUnreachable
from swann.health import read_health
from swann.session import RecorderSession

TICK = "ok"
CROSS = "no"


def line(label: str, value: object) -> None:
    print(f"  {label:<18} {value}")


async def main() -> int:
    gaps = cfg.missing_setup()
    if gaps:
        print("Not set up yet:")
        for gap in gaps:
            print(f"  {CROSS}: {gap}")
        return 1

    print(f"Asking the recorder at {cfg.RECORDER_HOST}")
    session = RecorderSession()
    try:
        await session.start()
    except (RecorderError, RecorderUnreachable) as exc:
        print(f"{CROSS}: could not log in. {exc}")
        return 1

    if not session.connected:
        print(f"{CROSS}: could not log in. {session.last_error}")
        await session.stop()
        return 1

    try:
        health = await read_health(session)
    finally:
        await session.stop()

    if not health.reachable:
        print(f"{CROSS}: logged in, but the recorder would not answer. {health.error}")
        return 1

    disk = health.main_disk
    partition = disk.video_partition if disk else None
    print(f"{TICK}: the recorder answered.")
    line("Firmware", health.device.firmware)
    line("Hardware", health.device.hardware)
    line("Recorder clock", health.device.recorder_clock)
    line("On since restart", health.device.uptime_text)
    line("Last restart", health.device.boot_time or "not in the log")
    line("Total time running", health.device.total_run_text)
    line("Cameras", f"{health.cameras_in_use} of {health.device.channel_count}")
    if disk:
        line("Disk", f"{disk.model} ({disk.state})")
        line("Oldest video", disk.oldest_video or "not given")
        line("Newest video", disk.newest_video or "not given")
    if partition:
        line("Disk used", f"{partition.percent_used}%")
    line("Writes over oldest", "yes" if health.overwrite_oldest else "no")
    line("Recording set up", "yes" if health.recording_scheduled else "no")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
