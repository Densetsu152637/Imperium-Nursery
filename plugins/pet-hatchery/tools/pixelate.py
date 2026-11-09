#!/usr/bin/env python3
"""Turn any image into compliant pixel art for a Pixel Pets cell.

Steps: remove the background (existing transparency, or a given / auto-detected
chroma key flood-filled from the border), detect and undo an integer upscale
(AI image generators and screenshots often enlarge pixel art), otherwise
box-downscale to fit the cell, binarise alpha, quantise to a shared palette of
at most --max-colors, and place the sprite in a cell-sized canvas.

Usage:
  python tools/pixelate.py INPUT -o OUTPUT --cell 64 [--max-colors 64]
         [--key auto|none|#RRGGBB] [--tolerance 40] [--scale auto|N]
         [--pad 1] [--anchor bottom|center] [--threshold 128] [--no-despill]

Other tools import the functions below (``pixelate_image``, ``quantize_images`` ...).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pet_spec  # noqa: E402


def _dist2(a, b) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def has_transparency(img: Image.Image, fraction: float = 0.02) -> bool:
    hist = img.getchannel("A").histogram()
    return sum(hist[:250]) > img.width * img.height * fraction


def detect_key(img: Image.Image, tolerance: int = 40):
    """Return the dominant border colour if the border looks like a solid background."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    border = [px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)]
    border += [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)]
    opaque = [p[:3] for p in border if p[3] >= 250]
    if len(opaque) < len(border) * 0.6:
        return None
    buckets = Counter((r // 8, g // 8, b // 8) for r, g, b in opaque)
    top, count = buckets.most_common(1)[0]
    if count < len(opaque) * 0.5:
        return None
    members = [p for p in opaque if (p[0] // 8, p[1] // 8, p[2] // 8) == top]
    return tuple(sum(c[i] for c in members) // len(members) for i in range(3))


def remove_background(img: Image.Image, key=None, tolerance: int = 40, despill: bool = True) -> Image.Image:
    """Make the background transparent.

    ``key`` None: keep existing transparency, else auto-detect a border colour.
    ``key`` False: leave the image untouched. Otherwise an (r, g, b) key.
    """
    img = img.convert("RGBA")
    if key is False or (key is None and has_transparency(img)):
        return img
    if key is None:
        key = detect_key(img, tolerance)
        if key is None:
            return img
    w, h = img.size
    data = bytearray(img.tobytes())
    tol2 = tolerance * tolerance
    seen = bytearray(w * h)

    def match(i: int) -> bool:
        o = i * 4
        return data[o + 3] < 8 or _dist2((data[o], data[o + 1], data[o + 2]), key) <= tol2

    stack = []
    for x in range(w):
        stack += [x, (h - 1) * w + x]
    for y in range(h):
        stack += [y * w, y * w + w - 1]
    while stack:
        i = stack.pop()
        if seen[i] or not match(i):
            continue
        seen[i] = 1
        x, y = i % w, i // w
        if x > 0:
            stack.append(i - 1)
        if x < w - 1:
            stack.append(i + 1)
        if y > 0:
            stack.append(i - w)
        if y < h - 1:
            stack.append(i + w)
    for i in range(w * h):
        if seen[i]:
            data[i * 4 + 3] = 0
    if despill:
        wide2 = (tolerance * 2) ** 2
        fringe = []
        for i in range(w * h):
            if seen[i]:
                continue
            x, y = i % w, i // w
            near = (
                (x > 0 and seen[i - 1])
                or (x < w - 1 and seen[i + 1])
                or (y > 0 and seen[i - w])
                or (y < h - 1 and seen[i + w])
            )
            if near:
                o = i * 4
                if _dist2((data[o], data[o + 1], data[o + 2]), key) <= wide2:
                    fringe.append(o)
        for o in fringe:
            data[o + 3] = 0
    return Image.frombytes("RGBA", (w, h), bytes(data))


def content_bbox(img: Image.Image, threshold: int = 1):
    return img.getchannel("A").point(lambda v: 255 if v >= threshold else 0).getbbox()


def _edge_profile(img: Image.Image, axis: int, tol: int) -> list[int]:
    """Strength of colour change between neighbours along ``axis`` (0 = x, 1 = y), per position."""
    w, h = img.size
    shifted = ImageChops.offset(img, 1, 0) if axis == 0 else ImageChops.offset(img, 0, 1)
    chans = ImageChops.difference(img, shifted).split()
    m = chans[0]
    for c in chans[1:]:
        m = ImageChops.lighter(m, c)
    m = m.point(lambda v: 255 if v > tol else 0)
    prof = list(m.resize((w, 1) if axis == 0 else (1, h), Image.BOX).getdata())
    prof[0] = 0
    return prof


def detect_upscale(img: Image.Image, max_n: int = 32, tol: int = 24, aligned_ratio: float = 0.95) -> int:
    """Largest integer n such that nearly all colour edges fall on multiples of n (bbox-relative)."""
    box = content_bbox(img)
    if not box:
        return 1
    crop = img.crop(box)
    w, h = crop.size
    px = _edge_profile(crop, 0, tol)
    py = _edge_profile(crop, 1, tol)
    totals = (sum(px), sum(py))
    if totals[0] == 0 and totals[1] == 0:
        return 1
    best = 1
    for n in range(2, min(max_n, max(w, h) // 4) + 1):
        ok = True
        for prof, total in ((px, totals[0]), (py, totals[1])):
            if total and sum(v for i, v in enumerate(prof) if i % n == 0) < aligned_ratio * total:
                ok = False
                break
        if ok:
            best = n
    return best


def reduce_nearest(img: Image.Image, n: int) -> Image.Image:
    """Crop to content and undo an integer upscale by centre-sampling n x n blocks."""
    box = content_bbox(img)
    if not box:
        return img
    crop = img.crop(box)
    if n <= 1:
        return crop
    nw, nh = max(1, round(crop.width / n)), max(1, round(crop.height / n))
    return crop.resize((nw, nh), Image.NEAREST)


def downscale(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Box downscale on premultiplied alpha so background never bleeds into edges."""
    size = (max(1, size[0]), max(1, size[1]))
    if size == img.size:
        return img
    return img.convert("RGBa").resize(size, Image.BOX).convert("RGBA")


def binarize_alpha(img: Image.Image, threshold: int = 128) -> Image.Image:
    img = img.convert("RGBA")
    a = img.getchannel("A").point(lambda v: 255 if v >= threshold else 0)
    out = img.copy()
    out.putalpha(a)
    clear = Image.new("RGBA", img.size, (0, 0, 0, 0))
    return Image.composite(out, clear, a)  # transparent pixels carry no colour


def quantize_images(images: list[Image.Image], max_colors: int) -> list[Image.Image]:
    """Quantise RGBA images (binary alpha) to one shared palette of at most ``max_colors``."""
    max_colors = max(1, min(max_colors, pet_spec.HARD_MAX_COLORS))
    colors = Counter()
    for im in images:
        colors.update(p[:3] for p in im.getdata() if p[3] == 255)
    if len(colors) <= max_colors:
        return [im.copy() for im in images]
    pixels = []
    for c, n in colors.items():
        pixels += [c] * min(n, 64)
    strip = Image.new("RGB", (len(pixels), 1))
    strip.putdata(pixels)
    pal = strip.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = []
    for im in images:
        rgb = im.convert("RGB").quantize(palette=pal, dither=Image.Dither.NONE).convert("RGBA")
        rgb.putalpha(im.getchannel("A"))
        out.append(binarize_alpha(rgb, 128))
    return out


def place(sprite: Image.Image, cell_w: int, cell_h: int, anchor: str = "bottom", pad: int = 1) -> Image.Image:
    """Centre horizontally; ``bottom`` rests the sprite on the cell's bottom padding."""
    canvas = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    x = (cell_w - sprite.width) // 2
    y = cell_h - pad - sprite.height if anchor == "bottom" else (cell_h - sprite.height) // 2
    canvas.alpha_composite(sprite, (x, y))
    return canvas


def fit_size(w: int, h: int, cell_w: int, cell_h: int, pad: int) -> tuple[int, int]:
    f = min((cell_w - 2 * pad) / w, (cell_h - 2 * pad) / h, 1.0)
    return max(1, int(w * f)), max(1, int(h * f))


def to_sprite(img: Image.Image, cell_w: int, cell_h: int, scale="auto", pad: int = 1, threshold: int = 128):
    """Background-free RGBA -> cropped native-size sprite with binary alpha (not yet quantised)."""
    if not content_bbox(img):
        return None, 1
    n = detect_upscale(img) if scale == "auto" else int(scale)
    sprite = reduce_nearest(img, n)
    sprite = downscale(sprite, fit_size(sprite.width, sprite.height, cell_w, cell_h, pad))
    sprite = binarize_alpha(sprite, threshold)
    box = content_bbox(sprite)
    return (sprite.crop(box) if box else None), n


def pixelate_image(
    img: Image.Image,
    cell_w: int,
    cell_h: int | None = None,
    max_colors: int = pet_spec.DEFAULT_MAX_COLORS,
    key=None,
    tolerance: int = 40,
    scale="auto",
    pad: int = 1,
    anchor: str = "bottom",
    threshold: int = 128,
    despill: bool = True,
) -> Image.Image:
    """Full pipeline for one image; returns a cell_w x cell_h RGBA pixel-art cell."""
    cell_h = cell_h or cell_w
    clean = remove_background(img, key, tolerance, despill)
    sprite, _ = to_sprite(clean, cell_w, cell_h, scale, pad, threshold)
    if sprite is None:
        return Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    sprite = quantize_images([sprite], max_colors)[0]
    return place(sprite, cell_w, cell_h, anchor, pad)


def parse_cell(text: str) -> tuple[int, int]:
    if "x" in text.lower():
        w, h = text.lower().split("x", 1)
        cw, ch = int(w), int(h)
    else:
        cw = ch = int(text)
    pet_spec.check_cell(cw, ch)
    return cw, ch


def parse_key(text: str):
    t = text.lower()
    if t == "auto":
        return None
    if t == "none":
        return False
    return pet_spec.parse_hex(text)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Convert an image to compliant pixel art in one cell.")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--out", type=Path, required=True)
    p.add_argument("--cell", default="64", help="cell size N or WxH (default 64)")
    p.add_argument("--max-colors", type=int, default=pet_spec.DEFAULT_MAX_COLORS)
    p.add_argument("--key", default="auto", help="auto, none (keep existing alpha), or #RRGGBB chroma key")
    p.add_argument("--tolerance", type=int, default=40, help="RGB distance counted as background")
    p.add_argument("--scale", default="auto", help="auto-detect integer upscale, or force N (1 disables)")
    p.add_argument("--pad", type=int, default=1)
    p.add_argument("--anchor", choices=["bottom", "center"], default="bottom")
    p.add_argument("--threshold", type=int, default=128, help="alpha >= this becomes opaque")
    p.add_argument("--no-despill", action="store_true", help="keep fringe pixels near the key colour")
    a = p.parse_args(argv)
    try:
        cw, ch = parse_cell(a.cell)
    except ValueError as e:
        p.error(f"--cell: {e}")
    out = pixelate_image(
        Image.open(a.input), cw, ch, a.max_colors, parse_key(a.key), a.tolerance,
        a.scale if a.scale == "auto" else int(a.scale), a.pad, a.anchor, a.threshold, not a.no_despill,
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(a.out)
    colors = len({px[:3] for px in out.getdata() if px[3]})
    print(f"wrote {a.out} ({cw}x{ch}, {colors} colours)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
