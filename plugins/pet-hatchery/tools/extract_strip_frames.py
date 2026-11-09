#!/usr/bin/env python3
"""Cut one generated horizontal strip of N poses into pixel-art frames.

The strip may be an image-generation output: upscaled, anti-aliased, on a
chroma or transparent background. The tool removes the background, undoes an
integer upscale, finds the N poses by column gaps (merging the closest groups
when there are too many; falling back to equal slices when there are too few),
downscales all frames by one common factor, pixelates them to one shared
palette, and rests them on a common baseline in cell-sized canvases.

Usage:
  python tools/extract_strip_frames.py STRIP --animation NAME --cell 64
         [--frames N] [--out frames] [--max-colors 64] [--key auto|none|#RRGGBB]
         [--tolerance 40] [--scale auto|N] [--slice auto|gaps|equal] [--pad 1]
         [--pet-json pet.json]

Writes OUT/NAME/00.png, 01.png, ... (one cell-sized PNG per frame).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pet_spec  # noqa: E402
import pixelate as px  # noqa: E402


def column_runs(img: Image.Image) -> list[tuple[int, int]]:
    """Inclusive-exclusive (start, end) x ranges of columns that hold any opaque pixel."""
    w, h = img.size
    proj = img.getchannel("A").point(lambda v: 255 if v else 0).resize((w, 1), Image.BOX).getdata()
    runs, start = [], None
    for x, v in enumerate(proj):
        if v and start is None:
            start = x
        elif not v and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, w))
    return runs


def find_frame_ranges(img: Image.Image, n: int, mode: str = "auto") -> tuple[list[tuple[int, int]], str]:
    """Return n x ranges plus the method used ('gaps' or 'equal')."""
    box = px.content_bbox(img)
    if not box:
        raise ValueError("the strip has no visible content after background removal")
    if mode in ("auto", "gaps"):
        runs = column_runs(img)
        if len(runs) >= n:
            while len(runs) > n:  # merge the pair separated by the smallest gap
                gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
                i = gaps.index(min(gaps))
                runs[i : i + 2] = [(runs[i][0], runs[i + 1][1])]
            return runs, "gaps"
        if mode == "gaps":
            raise ValueError(f"found only {len(runs)} separated poses, expected {n}")
    x0, _, x1, _ = box
    step = (x1 - x0) / n
    return [(round(x0 + i * step), round(x0 + (i + 1) * step)) for i in range(n)], "equal"


def extract_frames(
    strip: Image.Image,
    n: int,
    cell_w: int,
    cell_h: int,
    max_colors: int = pet_spec.DEFAULT_MAX_COLORS,
    key=None,
    tolerance: int = 40,
    scale="auto",
    mode: str = "auto",
    pad: int = 1,
) -> tuple[list[Image.Image], dict]:
    clean = px.remove_background(strip, key, tolerance)
    factor_n = px.detect_upscale(clean) if scale == "auto" else int(scale)
    reduced = px.reduce_nearest(clean, factor_n)
    ranges, method = find_frame_ranges(reduced, n, mode)

    crops = []  # (image cropped to its bbox, absolute top, absolute bottom)
    for x0, x1 in ranges:
        part = reduced.crop((x0, 0, x1, reduced.height))
        box = px.content_bbox(part)
        if not box:
            crops.append(None)
            continue
        crops.append((part.crop(box), box[1], box[3]))
    live = [c for c in crops if c]
    if not live:
        raise ValueError("no frame has visible content")
    top = min(c[1] for c in live)
    bottom = max(c[2] for c in live)
    span_w = max(c[0].width for c in live)
    span_h = bottom - top
    f = min((cell_w - 2 * pad) / span_w, (cell_h - 2 * pad) / span_h, 1.0)

    placed = []
    for c in crops:
        canvas = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
        if c:
            sprite, _, sb = c
            size = (max(1, round(sprite.width * f)), max(1, round(sprite.height * f)))
            sprite = px.binarize_alpha(px.downscale(sprite, size), 128)
            x = (cell_w - sprite.width) // 2
            y = cell_h - pad - round((bottom - sb) * f) - sprite.height
            canvas.alpha_composite(sprite, (x, max(0, y)))
        placed.append(canvas)
    frames = px.quantize_images(placed, max_colors)
    return frames, {"method": method, "upscale": factor_n, "factor": f, "ranges": ranges}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Cut a generated strip into pixel-art frames.")
    p.add_argument("strip", type=Path)
    p.add_argument("--animation", required=True, help="animation name, e.g. walk-right")
    p.add_argument("--cell", default="64", help="cell size N or WxH")
    p.add_argument("--frames", type=int, help="pose count (default: from the animation table / pet.json)")
    p.add_argument("--out", type=Path, default=Path("frames"))
    p.add_argument("--max-colors", type=int, default=pet_spec.DEFAULT_MAX_COLORS)
    p.add_argument("--key", default="auto", help="auto, none, or #RRGGBB chroma key")
    p.add_argument("--tolerance", type=int, default=40)
    p.add_argument("--scale", default="auto", help="auto-detect integer upscale, or force N (1 disables)")
    p.add_argument("--slice", choices=["auto", "gaps", "equal"], default="auto")
    p.add_argument("--pad", type=int, default=1)
    p.add_argument("--pet-json", type=Path, help="pet.json for custom animations")
    a = p.parse_args(argv)

    anims = pet_spec.resolve_animations(pet_spec.load_pet_json(a.pet_json) if a.pet_json else None)
    n = a.frames or (anims.get(a.animation) or {}).get("frames")
    if not n:
        p.error(f"unknown animation {a.animation!r}; pass --frames or --pet-json")
    try:
        cw, ch = px.parse_cell(a.cell)
    except ValueError as e:
        p.error(f"--cell: {e}")
    frames, info = extract_frames(
        Image.open(a.strip), n, cw, ch, a.max_colors, px.parse_key(a.key), a.tolerance,
        a.scale if a.scale == "auto" else int(a.scale), a.slice, a.pad,
    )
    out = a.out / a.animation
    out.mkdir(parents=True, exist_ok=True)
    for i, fr in enumerate(frames):
        fr.save(out / f"{i:02d}.png")
    print(
        f"wrote {len(frames)} frames to {out} (slicing: {info['method']}, upscale undone: {info['upscale']}x, "
        f"shrink factor: {info['factor']:.3f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
