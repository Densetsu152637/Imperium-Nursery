# Pixel-art rules and fixing validator failures

The rules are defined in [pet-format-v3.md](../../../docs/pet-format-v3.md#pixel-art-rules) and enforced by `validate_pet.py`. Run it, read the `[code]` of each error, and use this table.

```text
python "${CLAUDE_PLUGIN_ROOT}/tools/validate_pet.py" WORK
python "${CLAUDE_PLUGIN_ROOT}/tools/validate_pet.py" WORK --json    # machine-readable
```

Exit status 1 means errors; warnings do not fail.

## Pixel-art cell rules

| Code | Meaning | Fix |
| --- | --- | --- |
| `alpha-not-binary` | A pixel has partial transparency. | Re-run `extract_strip_frames.py` (it binarises alpha), or `pixelate.py --threshold 128`. Do not add soft shadows or glows by hand. |
| `too-many-colors` | A cell has more than `pixelArt.maxColors` opaque colours (default 64). | Re-extract with a lower `--max-colors` (for example 32 or 16). The extractor quantises all frames of a row to one palette, so lower it for every row and keep it consistent. |
| `pre-upscaled` | A cell is made of uniform n x n blocks (n >= 2). | The art was stored enlarged. Re-extract with `--scale auto` (default) or force `--scale N` with the real upscale factor; or use a smaller `--cell`. Never upscale the atlas to look bigger. |
| `cell-invalid` | `cell` out of range (cells are at most 128 x 128, at least 16). | `cell.width` and `cell.height` must be integers 16-128. Use 32-96. |

## Package and file rules

| Code | Meaning | Fix |
| --- | --- | --- |
| `json-invalid` | `pet.json` missing or not JSON. | Create or fix it; see the [pet-format skill](../../pet-format/SKILL.md#petjson). |
| `id-invalid`, `id-folder-mismatch` | `id` has illegal characters or differs from the folder name. | Lowercase letters, digits, hyphens; rename the folder or the id so they match. |
| `field-missing` | A required string field is empty. | Fill the fields the validator names (`description`, `author`, `license` only warn if missing). |
| `sprite-version` | `spriteVersionNumber` is not 3. | Set it to 3. |
| `pixelart-config` | Bad `pixelArt` object. | `{"maxColors": N}` with N 1-256, or `false` only for imported non-pixel pets. |
| `animation-invalid`, `animation-overlap` | Bad override or custom animation; two animations share a row. | Check fields against the spec; custom animations need `row` >= 22, `frames`, `durations`, `fallback`; give each a unique row range. |
| `spritesheet-missing`, `spritesheet-format` | No atlas, or not an RGBA PNG. | Re-run `compose_atlas.py`. |
| atlas size error | Atlas is not 8 x cell wide and 22 (or more) x cell high. | Re-run `compose_atlas.py` with the same `--cell`; every frame must be exactly one cell. |
| `unused-cell-not-empty` | Pixels in cells after an animation's last frame, or in unassigned rows. | Remove the extra frame files, or fix `frames` counts. Re-compose. |
| `idle-not-drawn` | Row 0 is empty. | `idle` is mandatory; generate it first. |
| `fallback-broken` | A chain of fallbacks never reaches a drawn animation. | For custom animations, give a `fallback` that reaches a drawn animation. |
| `strip-missing`, `strip-mismatch` | `strips/` missing, stale or not equal to the atlas. | Run `package_pet.py WORK` (it regenerates strips) after every compose. |
| `strip-too-large` | A strip PNG is over 96 KiB (the mod embeds it as base64 in an SVG). | Reduce colours (`--max-colors`), cell size, or detail (large flat areas compress best; avoid dithering and noise). Regenerate that row with a simpler design if needed. |
| `strip-orphan` (warning) | A strip belongs to no drawn animation. | Run `package_pet.py` again. |
| `not-pixel-art` (warning) | `pixelArt` is false (imported). | Expected for imports without `--pixelate`. |

## Habits that keep the validator quiet

- Always go source strip, then `extract_strip_frames.py`, then `compose_atlas.py`, then `package_pet.py`. Do not edit the atlas PNG in an image editor that anti-aliases or changes colour mode.
- Keep the same cell size and `--max-colors` for every row.
- A hard pixel-art look in the source (flat colours, no gradients, no soft shadows) quantises cleanly and compresses small.
