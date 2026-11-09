#!/usr/bin/env python3
"""Render one animated GIF per animation using the format's frame durations.

Frames are upscaled with nearest-neighbour and composited over a solid
background (GIF transparency is unreliable in viewers). Animations the pet
does not draw are skipped.

Usage:
  python tools/preview_gif.py PET_DIR --out OUT_DIR [--animation NAME ...]
         [--scale N] [--bg #RRGGBB]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contact_sheet  # noqa: E402
import pet_spec  # noqa: E402


def render_gif(frames: list[Image.Image], durations: list[int], scale: int, bg, path: Path) -> None:
    imgs = []
    for f in frames:
        big = f.resize((f.width * scale, f.height * scale), Image.NEAREST)
        base = Image.new("RGBA", big.size, bg + (255,))
        base.alpha_composite(big)
        imgs.append(base.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=64))
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=durations, loop=0, disposal=1)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Render animated GIF previews of a pet's animations.")
    p.add_argument("pet_dir", type=Path)
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--animation", action="append", help="only this animation (repeatable)")
    p.add_argument("--scale", type=int, help="integer upscale (default: about 128 px per cell)")
    p.add_argument("--bg", default="#F2F0E8", help="background colour (default warm off-white)")
    a = p.parse_args(argv)
    pet, atlas, anims = contact_sheet.load_atlas(a.pet_dir)
    cw, ch = pet["cell"]["width"], pet["cell"]["height"]
    scale = a.scale or max(1, round(128 / max(cw, ch)))
    bg = pet_spec.parse_hex(a.bg)
    a.out.mkdir(parents=True, exist_ok=True)
    count = 0
    for name, anim in anims.items():
        if a.animation and name not in a.animation:
            continue
        if not isinstance(anim.get("row"), int):
            continue
        frames = contact_sheet.get_frames(atlas, cw, ch, anim)
        if not frames or not any(f.getchannel("A").getbbox() for f in frames):
            continue
        durations = pet_spec.expand_durations(anim["durations"], len(frames))
        render_gif(frames, durations, scale, bg, a.out / f"{name}.gif")
        count += 1
    print(f"wrote {count} gifs to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
