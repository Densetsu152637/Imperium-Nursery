#!/usr/bin/env python3
"""Convert a Codex pet (pet.json + 8 x 11 v2 or 8 x 9 v1 spritesheet) into a Pixel Pets v3 package.

Codex rows 0-10 (idle, running-right, running-left, waving, jumping, failed,
waiting, running, review, 16 look directions) keep their meaning in v3 and are
mapped through the Codex-name column of the format table; rows 11-21 stay
transparent, so their fallbacks cover them (sleeping -> idle, celebrating ->
jumping, ...). A v1 sheet (8 x 9) has no look rows, so look falls back to idle. The manifest may use
spriteVersionNumber / sprite_version, spritesheetPath / spritesheet / spritesheet_file and displayName / name;
missing keys are inferred (version from atlas size, sheet from the single spritesheet* file, id from the name
when it is opaque like pet_<hex>). Only the frames each animation uses are copied.

Without --pixelate the art is kept as is and pet.json gets "pixelArt": false;
validation then warns (and a strip over 96 KiB is still an error). With
--pixelate --cell N every cell is box-downscaled to N x N, alpha is binarised
and all cells share a palette of at most --max-colors.

Usage:
  python tools/import_codex_pet.py SRC [--out-dir DIR] [--id ID] [--pixelate --cell N]
         [--max-colors 64] [--author NAME] [--license SPDX] [--install]

SRC is a Codex pet folder (or its pet.json). The package is written to
DIR/<id>/ (DIR defaults to the current directory), then strips are cut and the
package is validated.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import package_pet  # noqa: E402
import pet_spec  # noqa: E402
import pixelate as px  # noqa: E402
import validate_pet  # noqa: E402

CODEX_ROWS = 11  # v2; v1 sheets have 9 rows and no look directions
ROWS_BY_VERSION = {1: 9, 2: 11}
VERSION_KEYS = ("spriteVersionNumber", "sprite_version", "spriteVersion")
SHEET_KEYS = ("spritesheetPath", "spritesheet", "spritesheet_file")
NAME_KEYS = ("displayName", "name")
OPAQUE_ID_RE = re.compile(r"^(pet[-_]?)?[0-9a-f]{8,}$")


def first_key(meta: dict, keys) -> object:
    for k in keys:
        if meta.get(k) not in (None, ""):
            return meta[k]
    return None


def find_sheet(src_dir: Path, meta: dict) -> Path:
    """Named sheet if present, else the single spritesheet*.png/.webp in the folder."""
    rel = first_key(meta, SHEET_KEYS)
    if rel and (src_dir / str(rel)).is_file():
        return src_dir / str(rel)
    found = sorted(p for p in src_dir.iterdir() if p.is_file() and p.stem.startswith("spritesheet") and p.suffix.lower() in (".png", ".webp"))
    if len(found) == 1:
        return found[0]
    if not found:
        raise ValueError(f"no spritesheet found next to pet.json (manifest names {rel!r})")
    raise ValueError(f"spritesheet {rel!r} not found and several candidates exist ({', '.join(p.name for p in found)}); name one in pet.json")


def infer_version(size: tuple[int, int]) -> int:
    """v1 (8 x 9) vs v2 (8 x 11) from the atlas aspect ratio (1536x1872 vs 1536x2288)."""
    ratio = size[1] / size[0]
    return min(ROWS_BY_VERSION, key=lambda v: abs(ratio - {1: 1872 / 1536, 2: 2288 / 1536}[v]))


def sprite_version(meta: dict, size: tuple[int, int]) -> int:
    declared = first_key(meta, VERSION_KEYS)
    if declared is None:
        return infer_version(size)
    try:
        v = int(declared)
    except (TypeError, ValueError):
        raise ValueError(f"unreadable sprite version {declared!r}") from None
    if v not in ROWS_BY_VERSION:
        raise ValueError(f"unsupported Codex sprite version {v} (supported: 1, 2)")
    return v


def convert_atlas(
    sheet: Image.Image,
    pixelate: bool = False,
    cell: int | None = None,
    max_colors: int = pet_spec.DEFAULT_MAX_COLORS,
    codex_rows: int = CODEX_ROWS,
) -> tuple[Image.Image, tuple[int, int]]:
    """Build the 8 x 22 v3 atlas from a Codex sheet (8 x 11, or 8 x 9 without look); returns (atlas, cell size)."""
    sheet = sheet.convert("RGBA")
    if sheet.width % pet_spec.COLUMNS or sheet.height % codex_rows:
        raise ValueError(f"atlas {sheet.width}x{sheet.height} is not an 8 x {codex_rows} grid")
    sw, sh = sheet.width // pet_spec.COLUMNS, sheet.height // codex_rows
    if pixelate:
        if not cell:
            raise ValueError("--pixelate needs --cell N")
        pet_spec.check_cell(cell, cell)
        f = min(cell / sw, cell / sh)
        tw, th = max(1, round(sw * f)), max(1, round(sh * f))
        out_w = out_h = cell
    else:
        out_w, out_h = sw, sh
    placed: list[tuple[int, int, Image.Image]] = []
    for name in pet_spec.ORDER:
        a = pet_spec.ANIMATIONS[name]
        if a["row"] > 9 or a["row"] >= codex_rows:
            continue
        for i in range(a["frames"]):
            r, c = pet_spec.frame_cell(a["row"], i)
            src = sheet.crop(pet_spec.cell_box(sw, sh, r, c))
            if pixelate:
                src = px.binarize_alpha(px.downscale(src, (tw, th)), 128)
                canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
                canvas.alpha_composite(src, ((out_w - tw) // 2, (out_h - th) // 2))
                src = canvas
            placed.append((r, c, src))
    if pixelate:
        quant = px.quantize_images([p[2] for p in placed], max_colors)
        placed = [(r, c, q) for (r, c, _), q in zip(placed, quant)]
    atlas = Image.new("RGBA", (pet_spec.COLUMNS * out_w, pet_spec.STANDARD_ROWS * out_h), (0, 0, 0, 0))
    for r, c, im in placed:
        atlas.paste(im, (c * out_w, r * out_h))
    return atlas, (out_w, out_h)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "imported-pet"


def derive_id(meta: dict, fallback: str) -> str:
    """Id from the manifest id, or from the name when the id is opaque (pet_<hex>)."""
    raw = str(meta.get("id") or "")
    name = first_key(meta, NAME_KEYS)
    if raw and not OPAQUE_ID_RE.match(raw.lower()) and slug(raw) != "imported-pet":
        return slug(raw)
    if name and slug(str(name)) != "imported-pet":
        return slug(str(name))
    return slug(raw or fallback)


def import_pet(
    src: Path,
    out_dir: Path,
    pet_id: str | None = None,
    pixelate: bool = False,
    cell: int | None = None,
    max_colors: int = pet_spec.DEFAULT_MAX_COLORS,
    author: str | None = None,
    license_id: str | None = None,
) -> Path:
    src_dir = src.parent if src.is_file() else src
    meta_path = src if src.is_file() else src / "pet.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sheet = Image.open(find_sheet(src_dir, meta))
    version = sprite_version(meta, sheet.size)
    pet_id = slug(pet_id) if pet_id else derive_id(meta, src_dir.name)
    if not pet_spec.PET_ID_RE.match(pet_id):
        raise ValueError(f"invalid id {pet_id!r}")
    atlas, (cw, ch) = convert_atlas(sheet, pixelate, cell, max_colors, ROWS_BY_VERSION[version])
    pkg = out_dir / pet_id
    pkg.mkdir(parents=True, exist_ok=True)
    atlas.save(pkg / "spritesheet.png", optimize=True)
    pet = pet_spec.default_pet_json(
        pet_id,
        (cw, ch),
        displayName=str(first_key(meta, NAME_KEYS) or pet_id),
        description=str(meta.get("description") or "Imported from a Codex pet."),
        author=author or str(meta.get("author") or "unknown"),
        license=license_id or str(meta.get("license") or "unspecified"),
        importedFrom=f"codex-v{version}",
    )
    pet["pixelArt"] = {"maxColors": max_colors} if pixelate else False
    (pkg / "pet.json").write_text(json.dumps(pet, indent=2) + "\n", encoding="utf-8")
    package_pet.cut_strips(pkg)
    return pkg


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Import a Codex v2 pet as a Pixel Pets v3 package.")
    p.add_argument("src", type=Path, help="Codex pet folder or its pet.json")
    p.add_argument("--out-dir", type=Path, default=Path("."), help="parent for the <id>/ package folder")
    p.add_argument("--id", help="pet id (default: from the Codex pet)")
    p.add_argument("--pixelate", action="store_true", help="convert the art to compliant pixel art")
    p.add_argument("--cell", type=int, help="target cell size with --pixelate (16-128)")
    p.add_argument("--max-colors", type=int, default=pet_spec.DEFAULT_MAX_COLORS)
    p.add_argument("--author")
    p.add_argument("--license", dest="license_id")
    p.add_argument("--install", action="store_true", help="copy to ~/.claude/pets/<id>/ if valid")
    a = p.parse_args(argv)
    if a.cell is not None:
        try:
            pet_spec.check_cell(a.cell, a.cell)
        except ValueError as e:
            p.error(f"--cell: {e}")
    try:
        pkg = import_pet(a.src, a.out_dir, a.id, a.pixelate, a.cell, a.max_colors, a.author, a.license_id)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"wrote package {pkg}")
    rep = validate_pet.validate(pkg)
    print(validate_pet.render(rep, pkg))
    if rep.ok and a.install:
        print(f"installed to {package_pet.install(pkg)}")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
