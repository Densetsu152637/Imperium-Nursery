#!/usr/bin/env python3
"""Render a labelled contact sheet of every animation in a pet package.

One row per animation (``look`` takes two rows of eight), frames upscaled with
nearest-neighbour over a checkerboard so transparency is visible, undrawn
animations shown empty with their fallback named.

Usage:
  python tools/contact_sheet.py PET_DIR --out sheet.png [--scale N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pet_spec  # noqa: E402

LABEL_W = 150


def load_atlas(pet_dir: Path) -> tuple[dict, Image.Image, dict]:
    pet = pet_spec.load_pet_json(pet_dir / "pet.json")
    atlas = Image.open(pet_dir / pet.get("spritesheetPath", "spritesheet.png")).convert("RGBA")
    return pet, atlas, pet_spec.resolve_animations(pet)


def get_frames(atlas: Image.Image, cw: int, ch: int, a: dict) -> list[Image.Image]:
    out = []
    for i in range(a["frames"]):
        r, c = pet_spec.frame_cell(a["row"], i)
        if (r + 1) * ch > atlas.height:
            break
        out.append(atlas.crop(pet_spec.cell_box(cw, ch, r, c)))
    return out


def checker(w: int, h: int, size: int = 8) -> Image.Image:
    img = Image.new("RGB", (w, h), (214, 214, 214))
    d = ImageDraw.Draw(img)
    for y in range(0, h, size):
        for x in range(0, w, size):
            if (x // size + y // size) % 2:
                d.rectangle([x, y, x + size - 1, y + size - 1], fill=(236, 236, 236))
    return img


def render(pet_dir: Path, scale: int | None = None) -> Image.Image:
    pet, atlas, anims = load_atlas(pet_dir)
    cw, ch = pet["cell"]["width"], pet["cell"]["height"]
    s = scale or max(1, round(64 / max(cw, ch)))
    font = ImageFont.load_default(size=12)
    names = sorted((n for n in anims if isinstance(anims[n].get("row"), int)), key=lambda n: anims[n]["row"])
    layout = []
    for n in names:
        layout.append((n, anims[n], get_frames(atlas, cw, ch, anims[n])))
    total_rows = sum(pet_spec.row_span(a["frames"]) for _, a, _ in layout)
    cw_s, ch_s = cw * s, ch * s
    sheet = Image.new("RGB", (LABEL_W + pet_spec.COLUMNS * cw_s, total_rows * ch_s), (250, 250, 250))
    d = ImageDraw.Draw(sheet)
    bg = checker(cw_s, ch_s, max(4, s * 4))
    y = 0
    for n, a, frames in layout:
        drawn = any(f.getchannel("A").getbbox() for f in frames)
        label = f"{a['row']:>2} {n}"
        sub = f"{a['frames']}f {'loop' if a.get('loop') else 'once'} P{a.get('priority')}"
        d.text((6, y + 4), label, fill=(20, 20, 20) if drawn else (150, 150, 150), font=font)
        d.text((6, y + 20), sub if drawn else f"fallback: {a.get('fallback')}", fill=(90, 90, 90), font=font)
        for i in range(a["frames"]):
            r, c = divmod(i, pet_spec.COLUMNS)
            x0, y0 = LABEL_W + c * cw_s, y + r * ch_s
            sheet.paste(bg, (x0, y0))
            if i < len(frames):
                big = frames[i].resize((cw_s, ch_s), Image.NEAREST)
                sheet.paste(big, (x0, y0), big)
            d.rectangle([x0, y0, x0 + cw_s - 1, y0 + ch_s - 1], outline=(180, 180, 180))
            d.text((x0 + 2, y0 + 1), str(i), fill=(120, 120, 120), font=font)
        y += pet_spec.row_span(a["frames"]) * ch_s
    return sheet


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Render a labelled contact sheet of all animations.")
    p.add_argument("pet_dir", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--scale", type=int, help="integer upscale (default: about 64 px per cell)")
    a = p.parse_args(argv)
    sheet = render(a.pet_dir, a.scale)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out)
    print(f"wrote {a.out} ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
