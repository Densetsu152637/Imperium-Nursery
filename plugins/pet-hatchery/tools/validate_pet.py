#!/usr/bin/env python3
"""Validate a Pixel Pets package against docs/pet-format-v3.md.

Checks pet.json (schema, custom animations), the atlas (PNG, RGBA, size),
the pixel-art rules per cell (<=128 px, binary alpha, <= maxColors colours,
no pre-upscaled art), that unused cells are empty, that strips/<animation>.png
exist, match the atlas and stay within 96 KiB, that idle is drawn, and that
every fallback chain reaches a drawn animation.

Usage:
  python tools/validate_pet.py PET_DIR [--json]

Exit status 1 when there are errors. Warnings (for example an imported
non-pixel-art pet with "pixelArt": false) do not fail.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pet_spec  # noqa: E402

PRIORITY_RE = re.compile(r"^P([0-6])$")


class Report:
    def __init__(self):
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.stats: dict = {}

    def error(self, code: str, message: str):
        self.errors.append({"code": code, "message": message})

    def warn(self, code: str, message: str):
        self.warnings.append({"code": code, "message": message})

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "stats": self.stats}


def is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def normalize_priority(v):
    if is_int(v) and 0 <= v <= 6:
        return v
    if isinstance(v, str):
        m = PRIORITY_RE.match(v)
        if m:
            return int(m.group(1))
    return None


def check_animation_fields(name: str, a: dict, custom: bool, rep: Report, known: set[str]) -> bool:
    ok = True

    def bad(msg):
        nonlocal ok
        ok = False
        rep.error("animation-invalid", f"animation '{name}': {msg}")

    if custom:
        for field in ("row", "frames", "durations", "fallback"):
            if a.get(field) is None:
                bad(f"custom animation must give '{field}'")
    row, frames = a.get("row"), a.get("frames")
    if row is not None and (not is_int(row) or row < 0 or (custom and row < pet_spec.STANDARD_ROWS)):
        bad(f"row must be an integer{' >= 22 for a custom animation' if custom else ' >= 0'}")
    if frames is not None and (not is_int(frames) or not 1 <= frames <= 16):
        bad("frames must be an integer from 1 to 16")
    d = a.get("durations")
    if d is not None:
        seq = [d] if is_int(d) else d
        if not isinstance(seq, list) or not seq or not all(is_int(x) and x > 0 for x in seq):
            bad("durations must be a positive integer or a list of positive integers (ms)")
        elif is_int(frames) and len(seq) not in (1, frames) and not a.get("pose"):
            bad(f"durations has {len(seq)} values for {frames} frames (use 1 or {frames})")
    if "loop" in a and not isinstance(a["loop"], bool):
        bad("loop must be true or false")
    if "priority" in a and normalize_priority(a["priority"]) is None:
        bad("priority must be P0..P6")
    if "minMs" in a and (not is_int(a["minMs"]) or a["minMs"] < 0):
        bad("minMs must be a non-negative integer")
    for ref in ("next", "fallback"):
        if a.get(ref) is not None and (not isinstance(a[ref], str) or a[ref] not in known):
            bad(f"{ref} names unknown animation {a[ref]!r}")
    return ok


def uniform_block_size(cell: Image.Image) -> int:
    """Largest n >= 2 for which the cell's art is made of n x n blocks, else 0."""
    box = cell.getchannel("A").point(lambda v: 255 if v else 0).getbbox()
    if not box:
        return 0
    art = cell.crop(box)
    w, h = art.size
    for n in range(16, 1, -1):
        if w % n or h % n or (w // n) * (h // n) < 4:
            continue
        small = art.resize((w // n, h // n), Image.NEAREST)
        if ImageChops.difference(small.resize((w, h), Image.NEAREST), art).getbbox() is None:
            return n
    return 0


def validate(pet_dir: Path) -> Report:
    rep = Report()
    pet_dir = Path(pet_dir)
    pj = pet_dir / "pet.json"
    if not pj.is_file():
        rep.error("json-invalid", f"{pj} not found")
        return rep
    try:
        pet = json.loads(pj.read_text(encoding="utf-8"))
        if not isinstance(pet, dict):
            raise ValueError("top level must be an object")
    except (ValueError, OSError) as e:
        rep.error("json-invalid", f"pet.json is not valid JSON: {e}")
        return rep

    pid = pet.get("id")
    if not isinstance(pid, str) or not pet_spec.PET_ID_RE.match(pid):
        rep.error("id-invalid", "id must be lowercase letters, digits and hyphens")
    elif pid != pet_dir.resolve().name:
        rep.error("id-folder-mismatch", f"id '{pid}' must equal the folder name '{pet_dir.resolve().name}'")
    for field in ("displayName", "description"):
        if not isinstance(pet.get(field), str) or not pet.get(field):
            rep.error("field-missing", f"'{field}' must be a non-empty string")
    for field in ("author", "license"):
        if field not in pet:
            rep.warn("field-missing", f"'{field}' is not set")
    if pet.get("spriteVersionNumber") != pet_spec.SPRITE_VERSION:
        rep.error("sprite-version", f"spriteVersionNumber must be {pet_spec.SPRITE_VERSION}")

    cell = pet.get("cell")
    cw = ch = None
    if (
        isinstance(cell, dict)
        and all(is_int(cell.get(k)) and pet_spec.CELL_MIN <= cell[k] <= pet_spec.CELL_MAX for k in ("width", "height"))
    ):
        cw, ch = cell["width"], cell["height"]
    else:
        rep.error("cell-invalid", f"cell.width and cell.height must be integers from {pet_spec.CELL_MIN} to {pet_spec.CELL_MAX}")

    px_cfg = pet.get("pixelArt", {})
    strict = True
    max_colors = pet_spec.DEFAULT_MAX_COLORS
    if px_cfg is False:
        strict = False
        rep.warn("not-pixel-art", "pixelArt is false: the art is not pixel art and the pixel-art rules are reported as warnings")
    elif isinstance(px_cfg, dict):
        if "maxColors" in px_cfg:
            mc = px_cfg["maxColors"]
            if is_int(mc) and 1 <= mc <= pet_spec.HARD_MAX_COLORS:
                max_colors = mc
            else:
                rep.error("pixelart-config", f"pixelArt.maxColors must be an integer from 1 to {pet_spec.HARD_MAX_COLORS}")
    else:
        rep.error("pixelart-config", "pixelArt must be an object (or false for an imported non-pixel-art pet)")

    anim_in = pet.get("animations", {})
    if anim_in is None:
        anim_in = {}
    if not isinstance(anim_in, dict):
        rep.error("animation-invalid", "animations must be an object")
        anim_in = {}
        pet = {**pet, "animations": {}}
    merged = pet_spec.resolve_animations(pet)
    known = set(merged)
    valid_names = []
    for name, over in anim_in.items():
        if not isinstance(over, dict):
            rep.error("animation-invalid", f"animation '{name}' must be an object")
            continue
        unknown_fields = [k for k in over if k not in pet_spec.ANIMATION_FIELDS]
        if unknown_fields:
            rep.warn("animation-field-ignored", f"animation '{name}': ignored fields {', '.join(unknown_fields)}")
        if not pet_spec.PET_ID_RE.match(name):
            rep.error("animation-invalid", f"animation name '{name}' must be lowercase letters, digits and hyphens")
            continue
        if check_animation_fields(name, merged[name], name not in pet_spec.ANIMATIONS, rep, known):
            valid_names.append(name)
    for name in pet_spec.ANIMATIONS:
        if name not in anim_in:
            valid_names.append(name)
    layout_ok = {n for n in valid_names if is_int(merged[n].get("row")) and is_int(merged[n].get("frames"))}

    # row overlap
    owner: dict[int, str] = {}
    for n in sorted(layout_ok, key=lambda n: merged[n]["row"]):
        for r in range(merged[n]["row"], merged[n]["row"] + pet_spec.row_span(merged[n]["frames"])):
            if r in owner:
                rep.error("animation-overlap", f"animations '{owner[r]}' and '{n}' both use row {r}")
            owner[r] = n

    # atlas
    sheet_rel = pet.get("spritesheetPath", "spritesheet.png")
    sheet_path = (pet_dir / sheet_rel) if isinstance(sheet_rel, str) else None
    atlas = None
    if sheet_path is None or ".." in Path(sheet_rel).parts or not sheet_path.is_file():
        rep.error("spritesheet-missing", f"spritesheet not found at {sheet_rel!r} (relative path inside the package)")
    else:
        try:
            atlas = Image.open(sheet_path)
            atlas.load()
        except Exception as e:  # noqa: BLE001
            rep.error("spritesheet-format", f"cannot read spritesheet: {e}")
            atlas = None
    if atlas is not None:
        if atlas.format != "PNG" or atlas.mode != "RGBA":
            rep.error("spritesheet-format", f"spritesheet must be an RGBA PNG (found {atlas.format} {atlas.mode})")
            atlas = atlas.convert("RGBA")
    rows_needed = pet_spec.atlas_rows({n: merged[n] for n in layout_ok})
    if atlas is not None and cw:
        w_ok = atlas.width == pet_spec.COLUMNS * cw
        h_ok = atlas.height % ch == 0 and atlas.height // ch >= rows_needed
        if not (w_ok and h_ok):
            rep.error(
                "atlas-size",
                f"atlas is {atlas.width}x{atlas.height}; expected {pet_spec.COLUMNS * cw} x (a multiple of {ch} "
                f"with at least {rows_needed} rows = {rows_needed * ch})",
            )
            atlas = None
    atlas_rows = atlas.height // ch if atlas is not None and ch else 0

    drawn: set[str] = set()
    if atlas is not None:
        used_cells = set()
        violations = {"alpha-not-binary": [], "too-many-colors": [], "pre-upscaled": []}
        for n in layout_ok:
            a = merged[n]
            any_drawn = False
            for i in range(a["frames"]):
                r, c = pet_spec.frame_cell(a["row"], i)
                used_cells.add((r, c))
                if r >= atlas_rows:
                    continue
                cellimg = atlas.crop(pet_spec.cell_box(cw, ch, r, c))
                colors = cellimg.getcolors(maxcolors=cw * ch)
                if any(px[3] for _, px in colors):
                    any_drawn = True
                else:
                    continue
                label = f"{n}[{i}]"
                if any(px[3] not in (0, 255) for _, px in colors):
                    violations["alpha-not-binary"].append(label)
                    continue
                if len({px[:3] for _, px in colors if px[3] == 255}) > max_colors:
                    violations["too-many-colors"].append(label)
                if uniform_block_size(cellimg):
                    violations["pre-upscaled"].append(label)
            if any_drawn:
                drawn.add(n)
        msgs = {
            "alpha-not-binary": "alpha must be 0 or 255 (found partial transparency)",
            "too-many-colors": f"more than {max_colors} opaque colours",
            "pre-upscaled": "art is made of uniform n x n blocks (pre-upscaled); store it at native size",
        }
        for code, labels in violations.items():
            if labels:
                text = f"{msgs[code]} in {len(labels)} cell(s): {', '.join(labels[:6])}{' ...' if len(labels) > 6 else ''}"
                if strict:
                    rep.error(code, text)
                else:
                    rep.warn(code, text)
        # unused cells must be transparent; so must cells of unassigned rows
        stray = []
        for r in range(atlas_rows):
            for c in range(pet_spec.COLUMNS):
                if (r, c) in used_cells:
                    continue
                if atlas.crop(pet_spec.cell_box(cw, ch, r, c)).getchannel("A").getbbox():
                    stray.append(f"({r},{c})")
        if stray:
            rep.error("unused-cell-not-empty", f"cells after an animation's last frame must be transparent: {', '.join(stray[:8])}")
    rep.stats["drawn"] = sorted(drawn, key=lambda n: merged[n]["row"] if is_int(merged[n].get("row")) else 99)

    if atlas is not None and "idle" not in drawn:
        rep.error("idle-not-drawn", "idle must always be drawn (row 0 has no visible pixels)")

    # fallback chains
    if atlas is not None:
        for n in merged:
            seen, cur = [], n
            while cur not in drawn:
                if cur in seen or cur not in merged or merged[cur].get("fallback") is None:
                    rep.error("fallback-broken", f"animation '{n}' is not drawn and its fallback chain ({' -> '.join(seen + [cur])}) never reaches a drawn animation")
                    break
                seen.append(cur)
                cur = merged[cur]["fallback"]

    # strips
    strips_rel = pet.get("stripsPath", "strips")
    strips_dir = pet_dir / strips_rel if isinstance(strips_rel, str) else None
    largest = 0
    if atlas is not None and strips_dir is not None:
        if not strips_dir.is_dir():
            rep.error("strip-missing", f"strips directory {strips_rel!r} not found; run tools/package_pet.py")
        else:
            for n in sorted(drawn):
                a = merged[n]
                sp = strips_dir / f"{n}.png"
                if not sp.is_file():
                    rep.error("strip-missing", f"strips/{n}.png is missing; run tools/package_pet.py")
                    continue
                size = sp.stat().st_size
                largest = max(largest, size)
                if size > pet_spec.MAX_STRIP_BYTES:
                    rep.error("strip-too-large", f"strips/{n}.png is {size} bytes; the limit is {pet_spec.MAX_STRIP_BYTES} (reduce colours, frame size or detail)")
                try:
                    strip = Image.open(sp).convert("RGBA")
                except Exception as e:  # noqa: BLE001
                    rep.error("strip-mismatch", f"strips/{n}.png is unreadable: {e}")
                    continue
                if strip.size != (a["frames"] * cw, ch):
                    rep.error("strip-mismatch", f"strips/{n}.png is {strip.size[0]}x{strip.size[1]}; expected {a['frames'] * cw}x{ch}")
                    continue
                expect = Image.new("RGBA", strip.size, (0, 0, 0, 0))
                for i in range(a["frames"]):
                    r, c = pet_spec.frame_cell(a["row"], i)
                    expect.paste(atlas.crop(pet_spec.cell_box(cw, ch, r, c)), (i * cw, 0))
                if ImageChops.difference(expect, strip).getbbox():
                    rep.error("strip-mismatch", f"strips/{n}.png does not match the atlas; run tools/package_pet.py")
            for sp in sorted(strips_dir.glob("*.png")):
                if sp.stem not in drawn:
                    rep.warn("strip-orphan", f"strips/{sp.name} belongs to no drawn animation")
    rep.stats["largestStripBytes"] = largest
    rep.stats["cell"] = [cw, ch] if cw else None
    return rep


def render(rep: Report, pet_dir: Path) -> str:
    lines = [f"validating {pet_dir}"]
    for e in rep.errors:
        lines.append(f"  ERROR   [{e['code']}] {e['message']}")
    for w in rep.warnings:
        lines.append(f"  warning [{w['code']}] {w['message']}")
    lines.append(f"drawn animations: {len(rep.stats.get('drawn', []))}; largest strip: {rep.stats.get('largestStripBytes', 0)} bytes")
    lines.append(f"result: {'OK' if rep.ok else 'FAILED'} ({len(rep.errors)} errors, {len(rep.warnings)} warnings)")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Validate a Pixel Pets package (format v3).")
    p.add_argument("pet_dir", type=Path)
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    a = p.parse_args(argv)
    rep = validate(a.pet_dir)
    print(json.dumps(rep.to_dict(), indent=2) if a.json else render(rep, a.pet_dir))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
