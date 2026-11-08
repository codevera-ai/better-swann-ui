"""Save every recorder setting to a file. Read only, nothing is written back.

Run it with: make backup
"""
from __future__ import annotations

import asyncio
import sys

from swann.backup import take_backup
from swann.errors import RecorderError, RecorderUnreachable
from swann.session import RecorderSession

TICK = "ok"
CROSS = "no"


async def main() -> int:
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
        result = await take_backup(session)
    finally:
        await session.stop()

    if result.error:
        print(f"{CROSS}: {result.error}")
        return 1

    print(f"{TICK}: {result.summary}")
    print(f"  Saved to  {result.path}")
    if result.expected_missing:
        print("  Not on this recorder, which is expected:")
        for name in result.expected_missing:
            print(f"    {name}")
    if result.empty_sockets:
        print(f"  Skipped {len(result.empty_sockets)} settings on empty camera sockets.")
    if result.failed:
        print("  Failed, worth a look:")
        for name, why in result.failed.items():
            print(f"    {name}: {why}")
        return 1
    print("  The file holds real passwords. It is in data/, which is git ignored.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
