#!/usr/bin/env python3
"""Draw the sample pet "pixel-clawd" procedurally: the Clawd crab from the
Crew-Progress agents panel (hooks/crabs.ts), fitted into 32 x 32 cells, with a
hand-designed pose for every frame of all 22 animations.

Usage:
  python tools/make_sample_pet.py [--out pets/pixel-clawd] [--frames-dir DIR]

Writes pet.json and spritesheet.png, cuts strips/ and validates the package.
--frames-dir additionally dumps frames/<animation>/NN.png (the compose_atlas
input layout). The art is drawn at native pixel size; nothing is upscaled.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import package_pet  # noqa: E402
import pet_spec  # noqa: E402
import validate_pet  # noqa: E402

CELL = 32
OX, OY = 1, 4  # crabs.ts grid (24 x 16 crab) -> cell coordinates

CLAY = (0xD9, 0x77, 0x57)
INK = (0x1F, 0x1E, 0x1D)
WHITE = (0xF4, 0xF1, 0xEA)
GREY = (0x9B, 0x98, 0x92)
YEL = (0xF2, 0xC9, 0x4C)
RED = (0xD6, 0x45, 0x50)
BLUE = (0x3C, 0x7D, 0xD9)
LBLUE = (0x8E, 0xC5, 0xF0)
GREEN = (0x5D, 0xAA, 0x68)
PINK = (0xE8, 0x6A, 0x92)
BROWN = (0xB9, 0x83, 0x3F)
CHOC = (0x5A, 0x3A, 0x22)

Q = [".##.", "#..#", "..#.", "....", "..#."]
EXCL = ["##", "##", "##", "..", "##"]
Z_BIG = ["####", "..#.", ".#..", "####"]
Z_SM = ["###", ".#.", "###"]
HEART = [".#.#.", "#####", "#####", ".###.", "..#.."]
HEART_SM = ["#.#", "###", ".#."]
PLUS5 = ["..#..", "..#..", "#####", "..#..", "..#.."]
PLUS3 = [".#.", "###", ".#."]
LENS = [".###.", "#lll#", "#lll#", "#lll#", ".###."]
COOKIE = [
    [".bbb.", "bbcbb", "bcbbb", "bbbcb", ".bbb."],
    [".bbb.", "bbcbb", "bcbbb", "bbbcb", ".bbb."],
    [".bbb.", ".bcbb", ".cbbb", ".bbcb", ".bbb."],
    ["..bb.", "..cbb", "..bbb", "..bcb", "..bb."],
    ["...b.", "...bb", "...cb", "...bb", "...b."],
    [".....", ".....", "....b", "...b.", "....."],
]


@dataclass
class Pose:
    dx: int = 0
    dy: int = 0  # body shift
    gy: int | None = None  # feet shift (defaults to dy; differs when crouching)
    grow: int = 0  # body taller (+) or squashed (-) at the top
    la: int = 0  # lift legs a / b by one pixel
    lb: int = 0
    lc: int = 0  # left / right claw vertical offset (negative = raised)
    rc: int = 0
    lcx: int = 0
    rcx: int = 0
    eyes: object = "open"  # style or (left, right)
    eyedx: int = 0
    eyedy: int = 0
    pupil: tuple | None = None  # (x, y) 0..3 inside the eye white for style "look"
    mouth: str | None = None  # "closed" | "open" | "yawn"
    grey: bool = False
    tilt: int = 0
    blush: bool = False


class Canvas:
    def __init__(self):
        self.img = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        self.pix = self.img.load()

    def rect(self, x, y, w, h, c):
        for yy in range(y + OY, y + h + OY):
            for xx in range(x + OX, x + w + OX):
                if 0 <= xx < CELL and 0 <= yy < CELL:
                    self.pix[xx, yy] = (0, 0, 0, 0) if c is None else c + (255,)

    def stamp(self, x, y, rows, colors):
        if isinstance(colors, tuple):
            colors = {"#": colors}
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch in colors:
                    self.rect(x + dx, y + dy, 1, 1, colors[ch])


def r(v: float) -> int:
    return math.floor(v + 0.5)


def draw_eye(c: Canvas, style, ex, ey, pupil):
    if style == "open":
        c.rect(ex, ey, 2, 2, INK)
    elif style == "half":
        c.rect(ex, ey + 1, 2, 1, INK)
    elif style == "closed":
        c.rect(ex - 1, ey + 1, 4, 1, INK)
    elif style == "squint":
        for px, py in ((-1, 1), (0, 0), (1, 0), (2, 1)):
            c.rect(ex + px, ey + py, 1, 1, INK)
    elif style == "wide":
        c.rect(ex - 1, ey - 1, 4, 4, WHITE)
        c.rect(ex, ey, 2, 2, INK)
    elif style == "x":
        for px, py in ((0, -1), (2, -1), (1, 0), (0, 1), (2, 1)):
            c.rect(ex + px, ey + py, 1, 1, INK)
    elif style == "look":
        c.rect(ex - 1, ey - 1, 5, 5, WHITE)
        c.rect(ex - 1 + pupil[0], ey - 1 + pupil[1], 2, 2, INK)


def draw_crab(p: Pose) -> Image.Image:
    c = Canvas()
    body = GREY if p.grey else CLAY
    gy = p.dy if p.gy is None else p.gy
    top = 10 - p.grow + p.dy
    bottom = 22 + p.dy  # exclusive
    # legs (a pair at x 7/17, b pair at x 11/21)
    for xs, lift in (((7, 17), p.la), ((11, 21), p.lb)):
        for x in xs:
            lt, lb = 22 + p.dy, 26 + gy - lift
            if lb > lt:
                c.rect(x, lt, 2, lb - lt, body)
    # body with chamfered top corners
    c.rect(7, top, 16, bottom - top, body)
    c.rect(7, top, 1, 1, None)
    c.rect(22, top, 1, 1, None)
    # claws (open pincers) with an arm when raised
    for side, off, offx in ((0, p.lc, p.lcx), (1, p.rc, p.rcx)):
        cx = (3 if side == 0 else 23) + offx
        cy = 14 + p.dy + off
        c.rect(cx, cy, 4, 4, body)
        c.rect(cx if side == 0 else cx + 3, cy + 1, 1, 2, None)
        if off < -1:
            c.rect(5 if side == 0 else 23, cy + 4, 2, 18 + p.dy - (cy + 4) - 0, body)
    # eyes
    ey = top + 2 + p.eyedy
    left, right = (p.eyes, p.eyes) if not isinstance(p.eyes, tuple) else p.eyes
    if "look" in (left, right):
        ey = top + 2
    draw_eye(c, left, 9 + p.eyedx, ey, p.pupil)
    draw_eye(c, right, 19 + p.eyedx, ey, p.pupil)
    if p.blush:
        c.rect(8, ey + 3, 2, 1, PINK)
        c.rect(20, ey + 3, 2, 1, PINK)
    my = top + 7
    if p.mouth == "closed":
        c.rect(14, my, 2, 1, INK)
    elif p.mouth == "open":
        c.rect(14, my, 2, 2, INK)
    elif p.mouth == "yawn":
        c.rect(13, my - 1, 4, 3, INK)
    img = c.img
    if p.tilt or p.dx:
        out = Image.new("RGBA", img.size, (0, 0, 0, 0))
        base = 22 + OY
        for y in range(CELL):
            shift = p.dx + (r(p.tilt * (base - y) / 12) if y < base else 0)
            out.paste(img.crop((0, y, CELL, y + 1)), (shift, y))
        img = out
    return img


def draw_props(img: Image.Image, props: list) -> Image.Image:
    c = Canvas()
    c.img, c.pix = img, img.load()
    for kind, *a in props:
        if kind == "stamp":
            c.stamp(*a)
        elif kind == "rect":
            c.rect(*a)
    return img


# ----- animations: each returns a list of (Pose, props) --------------------------------------


def idle():
    eyes = ["open", "half", "closed", "half", "open", "open"]
    grow = [0, 0, 0, 0, 1, 1]
    return [(Pose(eyes=e, grow=g), []) for e, g in zip(eyes, grow)]


def walk_right():
    out = []
    for i in range(8):
        ph = i % 4
        if i == 7:
            out.append((Pose(eyedx=2, tilt=1), []))
            continue
        out.append(
            (
                Pose(
                    dy=-1 if ph in (1, 3) else 0,
                    gy=0,
                    la=1 if ph in (0, 1) else 0,
                    lb=1 if ph in (2, 3) else 0,
                    lc=1 if ph < 2 else -1,
                    rc=-1 if ph < 2 else 1,
                    eyedx=2,
                    tilt=2,
                ),
                [],
            )
        )
    return out


def waving():
    spec = [(-6, 0, "open"), (-8, 1, "open"), (-6, 0, "open"), (-7, -1, "squint")]
    out = []
    for rc, rcx, eyes in spec:
        marks = [("rect", 28, rc + 8, 1, 2, INK)] if rcx >= 0 and rc == -8 else []
        out.append((Pose(rc=rc, rcx=rcx, eyes=eyes), marks))
    return out


def jumping():
    dust = [("rect", 2, 26, 2, 1, GREY), ("rect", 26, 26, 2, 1, GREY), ("rect", 5, 25, 1, 1, GREY)]
    return [
        (Pose(dy=1, gy=0, lc=1, rc=1, eyes="half"), []),
        (Pose(dy=-4, lc=-2, rc=-2, la=1, lb=1, grow=1), []),
        (Pose(dy=-7, lc=-5, rc=-5, la=1, lb=1, eyes="squint"), []),
        (Pose(dy=-3, lc=-3, rc=-3, la=1), []),
        (Pose(dy=2, gy=0, lc=2, rc=2, eyes="closed"), dust),
    ]


def failed():
    tear = lambda n: [("rect", 9, 17, 1, n, BLUE), ("rect", 20, 17, 1, n, BLUE)]
    return [
        (Pose(dy=-2, eyes="wide", lc=-2, rc=-2), []),
        (Pose(grey=True, eyes="x"), []),
        (Pose(grey=True, eyes="x", grow=-1, lc=1, rc=1), []),
        (Pose(grey=True, eyes="x", grow=-2, lc=2, rc=2), []),
        (Pose(grey=True, eyes="x", grow=-3, lc=3, rc=3), []),
        (Pose(grey=True, eyes="x", grow=-3, lc=3, rc=3), tear(2)),
        (Pose(grey=True, eyes="x", grow=-3, lc=3, rc=3), tear(4)),
        (Pose(grey=True, eyes="x", grow=-3, lc=3, rc=3), tear(3)),
    ]


def waiting():
    out = []
    for i in range(6):
        up = i % 2
        out.append(
            (
                Pose(rc=-3 if up else 0, lb=up, eyes="half" if i == 4 else "open", eyedx=-1),
                [("stamp", 13, 3 - up, Q, INK)],
            )
        )
    return out


def working():
    out = []
    for i in range(6):
        a = i % 2
        n = i % 3 + 1
        dots = [("rect", 12 + 3 * k, 5, 1, 1, BLUE) for k in range(n)]
        out.append((Pose(lc=-2 if a else 0, rc=0 if a else -2, dy=-a, gy=0, la=a, lb=1 - a, eyedy=1), dots))
    return out


def review():
    out = []
    for i, mx in enumerate([0, 1, 2, 1, 0, -1]):
        props = [
            ("stamp", 22 + mx, 2, LENS, {"#": INK, "l": LBLUE}),
            ("rect", 24 + mx, 7, 1, 4, INK),
        ]
        if i % 2:
            props.append(("rect", 23 + mx, 3, 1, 1, WHITE))
        out.append((Pose(rc=-3, eyes="squint", tilt=1, lb=i % 2), props))
    return out


def look():
    out = []
    for k in range(16):
        a = math.radians(k * 22.5)
        s, cs = math.sin(a), math.cos(a)
        out.append(
            (
                Pose(
                    dx=r(2 * s),
                    grow=r(1.5 * cs),
                    eyes="look",
                    pupil=(min(3, max(0, r(1.5 + 1.5 * s))), min(3, max(0, r(1.5 - 1.5 * cs)))),
                ),
                [],
            )
        )
    return out


def sleeping():
    out = []
    for i in range(6):
        z2 = (i + 3) % 6
        props = [("stamp", 22, 9 - i, Z_BIG, INK)]
        if z2:
            props.append(("stamp", 26, 9 - z2, Z_SM, GREY))
        out.append((Pose(dy=2, gy=0, la=1, lb=1, eyes="closed", grow=[0, 0, 1, 1, 0, 0][i], lc=2, rc=2), props))
    return out


def waking():
    return [
        (Pose(dy=2, gy=0, la=1, lb=1, eyes="closed", lc=2, rc=2), []),
        (Pose(dy=1, gy=0, eyes="half", lc=1, rc=1), []),
        (Pose(grow=2, lc=-5, rc=-5, eyes="closed", mouth="yawn"), []),
        (Pose(grow=2, lc=-6, rc=-6, eyes="closed", mouth="yawn", dy=-1, gy=0), []),
        (Pose(dx=-1, lc=-1, rc=-1, eyes="open"), []),
        (Pose(eyes="open"), []),
    ]


def summoning():
    dots = [("rect", 24, 2, 1, 1, YEL), ("rect", 30, 3, 1, 1, YEL), ("rect", 27, 7, 1, 1, BLUE), ("rect", 23, 5, 1, 1, BLUE)]
    spark3 = ("stamp", 26, 2, PLUS3, YEL)
    spark5 = ("stamp", 25, 1, PLUS5, YEL)
    core = ("rect", 27, 3, 1, 1, WHITE)
    props = [
        [],
        [("rect", 27, 3, 1, 1, YEL)],
        [spark3],
        [spark5, core],
        [spark5, core] + dots,
        [spark3] + dots[:2],
    ]
    eyes = ["open", "open", "open", "wide", "squint", "open"]
    return [(Pose(rc=-5, tilt=1, eyes=e), pr) for e, pr in zip(eyes, props)]


def celebrating():
    xs = [3, 8, 13, 18, 23, 27, 6, 21]
    cols = [YEL, RED, BLUE, GREEN, PINK, YEL, BLUE, RED]
    y0 = [-4, -2, -4, -3, -4, -2, 0, -1]
    dys = [0, -5, -7, -3, 0, -6, -7, 0]
    out = []
    for i in range(8):
        props = []
        if i:
            for k in range(8):
                y = y0[k] + i * 3 + (k % 3)
                if y < 24:
                    props.append(("rect", xs[k], y, 2 if k % 2 else 1, 1 if k % 2 else 2, cols[k]))
        up = dys[i] != 0 or i in (0, 4, 7)
        out.append((Pose(dy=dys[i], lc=-5 if up else -2, rc=-5 if up else -2, eyes="squint", la=1 if dys[i] else 0, lb=1 if dys[i] else 0), props))
    return out


def confused():
    tilts = [-2, 2, -2, 2, -1, 0]
    out = []
    for i, t in enumerate(tilts):
        out.append(
            (
                Pose(tilt=t, dx=-t // 2, eyes=("open", "half") if i % 2 == 0 else ("half", "open"), lc=-2, mouth="closed" if i in (1, 3) else None),
                [("stamp", 13 - t, 2 + (i % 2), Q, INK), ("rect", 25, 9 + i % 3, 1, 2, BLUE)],
            )
        )
    return out


def eating():
    out = []
    for i in range(6):
        chew = i % 2
        crumbs = [("rect", 13, 19 + chew, 1, 1, BROWN)] if i in (2, 3, 4) else []
        out.append(
            (
                Pose(rc=-3, eyes="squint" if chew else "open", mouth="open" if chew else "closed", grow=chew),
                [("stamp", 22, 6, COOKIE[i], {"b": BROWN, "c": CHOC})] + crumbs,
            )
        )
    return out


def fidget():
    out = []
    for i in range(6):
        w = i % 2
        ticks = [("rect", 9, 5, 1, 1, INK), ("rect", 12, 4, 1, 1, INK)] if w else [("rect", 10, 6, 1, 1, INK), ("rect", 13, 5, 1, 1, INK)]
        if i == 5:
            out.append((Pose(eyes="open"), []))
            continue
        out.append((Pose(lc=-6, lcx=2 * w + 1, eyes="half" if i < 4 else "closed", tilt=-1), ticks))
    return out


def pop_out():
    dys = [15, 11, 7, 3, -2, 0]
    eyes = ["open", "open", "open", "wide", "open", "open"]
    return [(Pose(dy=d, eyes=e, lc=-3 if i == 4 else 0, rc=-3 if i == 4 else 0), []) for i, (d, e) in enumerate(zip(dys, eyes))]


def duck_in():
    dys = [0, 2, 5, 9, 14, 20]
    eyes = ["wide", "wide", "closed", "closed", "closed", "closed"]
    return [(Pose(dy=d, gy=d, eyes=e, lc=-2 if i == 0 else 0, rc=-2 if i == 0 else 0), []) for i, (d, e) in enumerate(zip(dys, eyes))]


def alert():
    dys = [0, -3, 0, -1]
    dxs = [0, 1, 0, -1]
    out = []
    for i in range(4):
        ticks = [("rect", 4, 6, 2, 1, RED), ("rect", 25, 6, 2, 1, RED)] if i % 2 else [("rect", 5, 8, 2, 1, RED), ("rect", 24, 8, 2, 1, RED)]
        out.append(
            (
                Pose(dy=dys[i], gy=dys[i], dx=dxs[i], eyes="wide", lc=-3, rc=-3, la=1 if i == 1 else 0, lb=1 if i == 1 else 0),
                [("stamp", 14, 2 + dys[i], EXCL, RED)] + ticks,
            )
        )
    return out


def petted():
    grows = [-1, -2, -1, 0, 0, 0]
    hearts = [
        [],
        [("stamp", 20, 6, HEART_SM, PINK)],
        [("stamp", 19, 3, HEART, PINK)],
        [("stamp", 19, 1, HEART, PINK), ("stamp", 24, 6, HEART_SM, PINK)],
        [("stamp", 19, -1, HEART, PINK), ("stamp", 24, 3, HEART_SM, PINK)],
        [("stamp", 24, 0, HEART_SM, PINK)],
    ]
    return [
        (Pose(grow=g, eyes="squint", blush=True, lc=-1 if i in (2, 3) else 0, rc=-1 if i in (2, 3) else 0, mouth="closed" if i > 1 else None), h)
        for i, (g, h) in enumerate(zip(grows, hearts))
    ]


BUILDERS = {
    "idle": idle,
    "walk-right": walk_right,
    "waving": waving,
    "jumping": jumping,
    "failed": failed,
    "waiting": waiting,
    "working": working,
    "review": review,
    "look": look,
    "sleeping": sleeping,
    "waking": waking,
    "summoning": summoning,
    "celebrating": celebrating,
    "confused": confused,
    "eating": eating,
    "fidget": fidget,
    "pop-out": pop_out,
    "duck-in": duck_in,
    "alert": alert,
    "petted": petted,
}


def build_frames() -> dict[str, list[Image.Image]]:
    frames: dict[str, list[Image.Image]] = {}
    for name, build in BUILDERS.items():
        poses = build()
        assert len(poses) == pet_spec.ANIMATIONS[name]["frames"], name
        frames[name] = [draw_props(draw_crab(p), props) for p, props in poses]
    # The crab is left-right symmetric, so walking left is walking right mirrored.
    frames["walk-left"] = [f.transpose(Image.FLIP_LEFT_RIGHT) for f in frames["walk-right"]]
    return frames


PET = pet_spec.default_pet_json(
    "pixel-clawd",
    CELL,
    displayName="Pixel Clawd",
    description="The Clawd crab from the agents panel, drawn in 32 x 32 pixel art.",
    author="Pixel Pets",
    license="MIT",
)


def main(argv=None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description="Draw the sample pet pixel-clawd, package and validate it.")
    p.add_argument("--out", type=Path, default=root / "pets" / "pixel-clawd")
    p.add_argument("--frames-dir", type=Path, help="also dump frames/<animation>/NN.png here")
    a = p.parse_args(argv)
    frames = build_frames()
    atlas = Image.new("RGBA", (pet_spec.COLUMNS * CELL, pet_spec.STANDARD_ROWS * CELL), (0, 0, 0, 0))
    for name, imgs in frames.items():
        for i, im in enumerate(imgs):
            row, col = pet_spec.frame_cell(pet_spec.ANIMATIONS[name]["row"], i)
            atlas.paste(im, (col * CELL, row * CELL))
        if a.frames_dir:
            d = a.frames_dir / name
            d.mkdir(parents=True, exist_ok=True)
            for i, im in enumerate(imgs):
                im.save(d / f"{i:02d}.png")
    a.out.mkdir(parents=True, exist_ok=True)
    atlas.save(a.out / "spritesheet.png", optimize=True)
    (a.out / "pet.json").write_text(json.dumps(PET, indent=2) + "\n", encoding="utf-8")
    written = package_pet.cut_strips(a.out)
    print(f"drew {len(frames)} animations; cut {len(written)} strips")
    rep = validate_pet.validate(a.out)
    print(validate_pet.render(rep, a.out))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
