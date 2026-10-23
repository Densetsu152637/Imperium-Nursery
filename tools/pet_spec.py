"""Claude Pets format v3: the in-code copy of the animation table and limits.

Every tool imports this module; ``docs/pet-format-v3.md`` is the normative
contract and this file must mirror it. No command line interface.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

COLUMNS = 8
STANDARD_ROWS = 22
CELL_MIN = 16
CELL_MAX = 256
DEFAULT_MAX_COLORS = 64
HARD_MAX_COLORS = 256
MAX_STRIP_BYTES = 96 * 1024
DEFAULT_MIN_MS = 600
DEFAULT_CUSTOM_PRIORITY = 4
SPRITE_VERSION = 3
PET_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Look directions, clockwise from up (12 o'clock); 16 poses over rows 9-10.
LOOK_ANGLES = [i * 22.5 for i in range(16)]

ANIMATION_FIELDS = ("row", "frames", "durations", "loop", "priority", "minMs", "next", "fallback")


def _a(row, name, frames, durations, loop, priority, fallback, codex=None, pose=False):
    return {
        "row": row,
        "name": name,
        "frames": frames,
        "durations": durations,
        "loop": loop,
        "priority": priority,
        "minMs": DEFAULT_MIN_MS,
        "fallback": fallback,
        "codex": codex,
        "pose": pose,
    }


def _d(base, n, last):
    return [base] * (n - 1) + [last]


_TABLE = [
    _a(0, "idle", 6, [280, 110, 110, 140, 140, 320], True, 6, None, "idle"),
    _a(1, "walk-right", 8, _d(120, 8, 220), True, 6, "idle", "running-right"),
    _a(2, "walk-left", 8, _d(120, 8, 220), True, 6, "idle", "running-left"),
    _a(3, "waving", 4, _d(140, 4, 280), False, 5, "idle", "waving"),
    _a(4, "jumping", 5, _d(140, 5, 280), False, 3, "idle", "jumping"),
    _a(5, "failed", 8, _d(140, 8, 240), False, 2, "idle", "failed"),
    _a(6, "waiting", 6, _d(150, 6, 260), True, 1, "idle", "waiting"),
    _a(7, "working", 6, _d(120, 6, 220), True, 4, "idle", "running"),
    _a(8, "review", 6, _d(150, 6, 280), True, 4, "working", "review"),
    _a(9, "look", 16, [100], True, 6, "idle", None, pose=True),
    _a(11, "sleeping", 6, [400], True, 6, "idle"),
    _a(12, "waking", 6, _d(120, 6, 200), False, 5, "idle"),
    _a(13, "summoning", 6, _d(120, 6, 240), False, 4, "waving"),
    _a(14, "celebrating", 8, _d(110, 8, 300), False, 3, "jumping"),
    _a(15, "confused", 6, _d(150, 6, 300), False, 2, "failed"),
    _a(16, "eating", 6, [140], True, 4, "working"),
    _a(17, "fidget", 6, _d(160, 6, 300), False, 6, "idle"),
    _a(18, "pop-out", 6, _d(90, 6, 160), False, 5, "jumping"),
    _a(19, "duck-in", 6, _d(90, 6, 160), False, 5, "idle"),
    _a(20, "alert", 4, [120], True, 1, "waiting"),
    _a(21, "petted", 6, _d(120, 6, 260), False, 0, "waving"),
]

ANIMATIONS = {a["name"]: a for a in _TABLE}
ORDER = [a["name"] for a in _TABLE]
CODEX_NAME_TO_ANIMATION = {a["codex"]: a["name"] for a in _TABLE if a["codex"]}
CODEX_ROW_ANIMATIONS = [a["name"] for a in _TABLE if a["row"] <= 9]  # rows 0-10 (look spans 9-10)


def parse_hex(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        raise ValueError(f"invalid colour {value!r}; expected #RRGGBB")
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def row_span(frames: int) -> int:
    return max(1, math.ceil(frames / COLUMNS))


def frame_cell(row: int, index: int) -> tuple[int, int]:
    """Return (row, column) of frame ``index`` for an animation starting at ``row``."""
    return row + index // COLUMNS, index % COLUMNS


def expand_durations(durations, frames: int) -> list[int]:
    if isinstance(durations, int):
        durations = [durations]
    if not durations:
        return [100] * frames
    if len(durations) == 1:
        return list(durations) * frames
    return list(durations)


def resolve_animations(pet: dict | None) -> dict[str, dict]:
    """Merge the standard table with ``pet['animations']`` overrides and custom animations."""
    out = {name: {k: (list(v) if isinstance(v, list) else v) for k, v in a.items()} for name, a in ANIMATIONS.items()}
    for name, override in ((pet or {}).get("animations") or {}).items():
        if not isinstance(override, dict):
            continue
        if name in out:
            out[name].update({k: v for k, v in override.items() if k in ANIMATION_FIELDS})
        else:
            entry = {
                "row": None,
                "name": name,
                "frames": None,
                "durations": None,
                "loop": True,
                "priority": DEFAULT_CUSTOM_PRIORITY,
                "minMs": DEFAULT_MIN_MS,
                "fallback": None,
                "codex": None,
                "pose": False,
                "custom": True,
            }
            entry.update({k: v for k, v in override.items() if k in ANIMATION_FIELDS})
            out[name] = entry
    return out


def atlas_rows(animations: dict[str, dict]) -> int:
    rows = STANDARD_ROWS
    for a in animations.values():
        if isinstance(a.get("row"), int) and isinstance(a.get("frames"), int):
            rows = max(rows, a["row"] + row_span(a["frames"]))
    return rows


def cell_box(cell_w: int, cell_h: int, row: int, col: int) -> tuple[int, int, int, int]:
    return col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h


def load_pet_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def default_pet_json(pet_id: str, cell: int | tuple[int, int], **extra) -> dict:
    cw, ch = (cell, cell) if isinstance(cell, int) else cell
    pet = {
        "id": pet_id,
        "displayName": pet_id.replace("-", " ").title(),
        "description": "A Claude pet.",
        "author": "unknown",
        "license": "unspecified",
        "spriteVersionNumber": SPRITE_VERSION,
        "spritesheetPath": "spritesheet.png",
        "stripsPath": "strips",
        "cell": {"width": cw, "height": ch},
        "pixelArt": {"maxColors": DEFAULT_MAX_COLORS},
        "animations": {},
    }
    pet.update(extra)
    return pet
