"""Work out what one camera's encoder will actually accept.

The video quality screen is the only screen whose limits the recorder states
itself. It answers `NetUse.DigitalAbility` per camera with packed numbers, one
bit per picture size and one bit per video format. This turns those into plain
lists the page can put in a dropdown.

Every number and name comes from `config.py`. Nothing here talks to the
recorder, so it can be checked against a saved reply.
"""
from __future__ import annotations

from typing import Any

from . import config as cfg

RESOLUTION_NAMES = tuple(row[0] for row in cfg.ENCODE_RESOLUTIONS)


def resolution_index(name: str) -> int:
    """Where a picture size sits in the recorder's own list, or -1."""
    try:
        return RESOLUTION_NAMES.index(str(name))
    except ValueError:
        return -1


def _range(low: int, high: int) -> dict[str, Any]:
    """A number range, with a list to pick from when the run is short.

    Same rule as the field guide: under `FIELD_CHOICE_LIMIT` steps a dropdown
    is easier than a box, over it a box is easier than a very long list.
    """
    out: dict[str, Any] = {"min": low, "max": high}
    if high - low + 1 <= cfg.FIELD_CHOICE_LIMIT:
        out["choices"] = [
            {"value": number, "title": str(number)}
            for number in range(low, high + 1)
        ]
    return out


def _size(index: int, pal: bool) -> dict[str, Any]:
    name, pal_w, pal_h, ntsc_w, ntsc_h = cfg.ENCODE_RESOLUTIONS[index]
    width, height = (pal_w, pal_h) if pal else (ntsc_w, ntsc_h)
    return {
        "value": name,
        "index": index,
        "width": width,
        "height": height,
        "title": cfg.ENCODE_SIZE_TITLE.format(
            name=name, width=width, height=height
        ),
    }


def _masked_sizes(mask: Any, pal: bool) -> list[dict[str, Any]]:
    return [
        _size(index, pal)
        for index in cfg.encode_mask_choices(mask, RESOLUTION_NAMES)
    ]


def _first(value: Any) -> Any:
    """The first entry of a list, or the value itself.

    The recorder wraps some ability numbers in a list of one, one per camera
    chip. These cameras have one chip each, so there is only ever one entry.
    """
    if isinstance(value, list) and value:
        return value[0]
    return value


def encoder_limits(ability: Any) -> dict[str, Any]:
    """Turn one camera's ability reply into lists the page can show.

    An empty dict comes back when the reply is missing or the wrong shape, and
    the page then falls back to plain number boxes.
    """
    if not isinstance(ability, dict):
        return {}
    inner = ability.get("ability")
    if not isinstance(inner, dict):
        return {}

    pal = ability.get("videoFormat") == cfg.ENCODE_VIDEO_FORMAT_PAL
    out: dict[str, Any] = {
        "pal": pal,
        # Every limit in here came out of the recorder's own reply, so the
        # info panel says so under each one.
        "source": cfg.SOURCE_RECORDER,
        "fps": _range(
            cfg.ENCODE_FPS_MIN,
            cfg.ENCODE_FPS_MAX_PAL if pal else cfg.ENCODE_FPS_MAX_NTSC,
        ),
        "quality": _range(cfg.ENCODE_QUALITY_MIN, cfg.ENCODE_QUALITY_MAX),
    }

    codecs = cfg.encode_mask_choices(
        inner.get("Compression"), cfg.ENCODE_COMPRESSIONS
    )
    out["codecs"] = [
        {"value": cfg.ENCODE_COMPRESSIONS[index], "title": cfg.ENCODE_COMPRESSIONS[index]}
        for index in codecs
        if cfg.ENCODE_COMPRESSIONS[index]
    ]

    # The main stream's picture sizes.
    main = _masked_sizes(_first(inner.get("ImageSizePerChannel")), pal)
    out["main"] = main

    # The second stream's list depends on which size the main stream is using.
    # Swann's own page reads the row for the main size: one list per main size.
    sub: dict[str, list[dict[str, Any]]] = {}
    rows = _first(inner.get("ExImageSizePerChannelEx"))
    if isinstance(rows, list):
        for size in main:
            index = size["index"]
            if index < len(rows):
                sub[size["value"]] = _masked_sizes(rows[index], pal)
    out["sub"] = sub

    # Every bit rate each picture size allows, main and second stream alike.
    # The table is the same for both, so one list per size covers them.
    wanted = {size["value"]: size["index"] for size in main}
    for sizes in sub.values():
        for size in sizes:
            wanted[size["value"]] = size["index"]
    # Each size gets its own list and the value Swann's own page falls back to.
    # Changing the picture size can leave the old bit rate outside the new
    # list, and the recorder's own page moves it to `usual` rather than send
    # something the recorder would refuse.
    out["bitrates"] = {
        name: {
            "values": list(cfg.encode_bitrate_choices(index)),
            "usual": cfg.ENCODE_BITRATES[index][2],
        }
        for name, index in sorted(wanted.items())
        if 0 <= index < len(cfg.ENCODE_BITRATES)
    }

    frames = ability.get("IFrameRange")
    if isinstance(frames, dict):
        gop: dict[str, Any] = {}
        for stream, low_key, high_key in (
            ("main", "main_min", "main_max"),
            ("sub", "sub_min", "sub_max"),
        ):
            low, high = frames.get(low_key), frames.get(high_key)
            if isinstance(low, int) and isinstance(high, int) and high >= low:
                # No list here, even though the range is short. The step is
                # the frames a second, which the page knows and this does not,
                # so the page builds the list itself.
                gop[stream] = {
                    "min": low,
                    "max": high,
                    "stepFps": cfg.ENCODE_GOP_STEPS_BY_FPS,
                    "extra": cfg.ENCODE_GOP_NOTE,
                }
        if gop:
            out["gop"] = gop

    top = inner.get("MaxBitrate")
    if isinstance(top, int):
        out["maxBitrate"] = top
    return out
