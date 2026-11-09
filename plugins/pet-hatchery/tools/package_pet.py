#!/usr/bin/env python3
"""Package a pet: cut strips/<animation>.png from spritesheet.png, then validate.

A strip is one horizontal PNG holding only an animation's used frames; the mod
reads strips because it cannot crop. Only animations the pet actually draws get
a strip (an all-transparent animation falls back at run time). Stale strips are
removed first.

Usage:
  python tools/package_pet.py PET_DIR [--install] [--install-dir DIR]

PET_DIR holds pet.json and spritesheet.png. --install copies the validated
package to ~/.claude/pets/<id>/ (or DIR/<id>/ with --install-dir). Exit 1 if
validation fails; nothing is installed in that case.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pet_spec  # noqa: E402
import validate_pet  # noqa: E402


def cut_strips(pet_dir: Path) -> list[str]:
    """Write strips for every drawn animation; return their names."""
    pet = pet_spec.load_pet_json(pet_dir / "pet.json")
    cw, ch = pet["cell"]["width"], pet["cell"]["height"]
    atlas = Image.open(pet_dir / pet.get("spritesheetPath", "spritesheet.png")).convert("RGBA")
    strips_dir = pet_dir / pet.get("stripsPath", "strips")
    strips_dir.mkdir(parents=True, exist_ok=True)
    for old in strips_dir.glob("*.png"):
        old.unlink()
    written = []
    anims = pet_spec.resolve_animations(pet)
    rows = atlas.height // ch
    for name, a in sorted(anims.items(), key=lambda kv: (kv[1].get("row") is None, kv[1].get("row"))):
        if not isinstance(a.get("row"), int) or not isinstance(a.get("frames"), int):
            continue
        cells = []
        for i in range(a["frames"]):
            r, c = pet_spec.frame_cell(a["row"], i)
            if r >= rows:
                break
            cells.append(atlas.crop(pet_spec.cell_box(cw, ch, r, c)))
        if len(cells) != a["frames"] or not any(cell.getchannel("A").getbbox() for cell in cells):
            continue
        strip = Image.new("RGBA", (a["frames"] * cw, ch), (0, 0, 0, 0))
        for i, cell in enumerate(cells):
            strip.paste(cell, (i * cw, 0))
        strip.save(strips_dir / f"{name}.png", optimize=True)
        written.append(name)
    return written


def install(pet_dir: Path, base: Path | None = None) -> Path:
    pet = pet_spec.load_pet_json(pet_dir / "pet.json")
    dest = (base or Path.home() / ".claude" / "pets") / pet["id"]
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(pet_dir, dest, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    return dest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Cut strips from the atlas, validate, optionally install.")
    p.add_argument("pet_dir", type=Path)
    p.add_argument("--install", action="store_true", help="copy to ~/.claude/pets/<id>/ after validation")
    p.add_argument("--install-dir", type=Path, help="install under this directory instead of ~/.claude/pets")
    a = p.parse_args(argv)
    try:
        written = cut_strips(a.pet_dir)
    except (OSError, KeyError, ValueError) as e:
        print(f"error: cannot package {a.pet_dir}: {e}", file=sys.stderr)
        return 1
    print(f"cut {len(written)} strips: {', '.join(written)}")
    rep = validate_pet.validate(a.pet_dir)
    print(validate_pet.render(rep, a.pet_dir))
    if not rep.ok:
        return 1
    if a.install or a.install_dir:
        print(f"installed to {install(a.pet_dir, a.install_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
