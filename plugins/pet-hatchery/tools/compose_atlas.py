#!/usr/bin/env python3
"""Compose frames/<animation>/NN.png directories into the 8 x 22 v3 atlas.

Each animation directory is placed at its table row (more than 8 frames
continue on the next row; ``look`` fills rows 9-10). Animations without a
directory stay transparent, so their fallbacks apply at run time.

Usage:
  python tools/compose_atlas.py FRAMES_DIR --out spritesheet.png
         [--cell N | WxH] [--pet-json pet.json]

The cell size is taken from --cell, else from pet.json ``cell``, else from the
first frame. --pet-json adds custom animations (rows 22 and beyond) and
overrides. Every frame must be exactly one cell in size.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pet_spec  # noqa: E402


def list_frames(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix.lower() == ".png")


def compose(frames_dir: Path, cell: tuple[int, int] | None = None, pet: dict | None = None):
    """Return (atlas image, (cell_w, cell_h), list of drawn animation names)."""
    anims = pet_spec.resolve_animations(pet)
    dirs = {d.name: d for d in frames_dir.iterdir() if d.is_dir()}
    unknown = [n for n in dirs if n not in anims]
    if unknown:
        raise ValueError(f"no such animation (add it to pet.json animations): {', '.join(sorted(unknown))}")
    if cell is None and pet and isinstance(pet.get("cell"), dict):
        cell = (pet["cell"]["width"], pet["cell"]["height"])
    loaded: dict[str, list[Image.Image]] = {}
    for name, d in dirs.items():
        files = list_frames(d)
        if not files:
            continue
        imgs = [Image.open(f).convert("RGBA") for f in files]
        if cell is None:
            cell = imgs[0].size
        need = anims[name]["frames"]
        if len(imgs) != need:
            raise ValueError(f"{name}: expected {need} frames, found {len(imgs)} in {d}")
        for f, im in zip(files, imgs):
            if im.size != cell:
                raise ValueError(f"{f}: size {im.size} does not match cell {cell}")
        loaded[name] = imgs
    if cell is None:
        raise ValueError("no frames found and no cell size given")
    rows = pet_spec.atlas_rows({n: anims[n] for n in anims if n in loaded or not anims[n].get("custom")})
    atlas = Image.new("RGBA", (pet_spec.COLUMNS * cell[0], rows * cell[1]), (0, 0, 0, 0))
    for name, imgs in loaded.items():
        for i, im in enumerate(imgs):
            r, c = pet_spec.frame_cell(anims[name]["row"], i)
            atlas.paste(im, pet_spec.cell_box(cell[0], cell[1], r, c)[:2])
    return atlas, cell, sorted(loaded, key=lambda n: anims[n]["row"])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Compose frame directories into an 8 x 22 atlas.")
    p.add_argument("frames_dir", type=Path)
    p.add_argument("--out", type=Path, default=Path("spritesheet.png"))
    p.add_argument("--cell", help="cell size N or WxH")
    p.add_argument("--pet-json", type=Path)
    a = p.parse_args(argv)
    cell = None
    if a.cell:
        try:
            cell = tuple(int(v) for v in (a.cell.lower().split("x") * 2)[:2])
            pet_spec.check_cell(*cell)
        except ValueError as e:
            p.error(f"--cell: {e}")
    pet = pet_spec.load_pet_json(a.pet_json) if a.pet_json else None
    try:
        atlas, cell, drawn = compose(a.frames_dir, cell, pet)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(a.out)
    print(f"wrote {a.out} ({atlas.width}x{atlas.height}, cell {cell[0]}x{cell[1]}); drew: {', '.join(drawn)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
