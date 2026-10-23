---
name: import-codex-pet
description: Convert an OpenAI Codex pet (v1 or v2 spritesheet and pet.json) into a Pixel Pets v3 package, then validate, preview and install it. Use when the user has a Codex pet folder or pet.json and wants it in Claude Code, or asks to import, port or convert a Codex or hatch-pet pet.
---

# Import a Codex pet

Converts a Codex pet (v1 or v2: a `pet.json` plus a spritesheet) into a v3 package with `import_codex_pet.py`. Codex rows 0-10 keep their meaning in v3 (`idle`, `running-right` -> `walk-right`, `running-left` -> `walk-left`, `waving`, `jumping`, `failed`, `waiting`, `running` -> `working`, `review`, 16 look directions), so nothing is redrawn. The new rows 11-21 stay transparent and fall back (`sleeping` shows `idle`, `celebrating` shows `jumping`, and so on). Format: [pet-format-v3.md](../../docs/pet-format-v3.md).

Tools: `${CLAUDE_PLUGIN_ROOT}/tools/` (needs Pillow). Use `python`.

## Steps

1. **Locate the source.** Ask for the Codex pet folder (or its `pet.json`) if the user has not given a path. Codex pets usually live under `~/.codex/pets/<name>/` or come as a downloaded folder. Check that the licence of the pet permits conversion; pass `--author` and `--license` for the original's.
2. **Choose how to convert.**
   - **Recommended: `--pixelate --cell 64`.** Codex art is high resolution (cells around 192 x 208) and is usually not pixel art. Pixelating box-downscales every cell to 64 x 64 (any size 16-128; smaller gives chunkier pixels), binarises alpha and shares one palette of at most `--max-colors` (default 64). The result passes the validator and its strips fit the size limit.
   - **Without `--pixelate`:** the art is copied as is and `pet.json` gets `"pixelArt": false`. Validation then reports the pixel-art rules as warnings. But every strip must still be at most 96 KiB, and large non-pixelated Codex art (8 frames of full-colour 192 x 208 cells) usually exceeds that, so the import fails validation with `strip-too-large`. Use this only for small or already pixel-art sheets, and fall back to `--pixelate --cell 64` if it fails.
3. **Run the import** (the package is written to `OUT_DIR/<id>/`; `--id` overrides the id, which must be lowercase letters, digits and hyphens):
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/import_codex_pet.py" SRC --out-dir WORK --pixelate --cell 64 --max-colors 64 --author "Name" --license "CC-BY-4.0"
   ```
   Without pixelation:
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/import_codex_pet.py" SRC --out-dir WORK --id my-pet
   ```
   The tool writes the package, cuts strips and validates. Read the output; if it reports errors, see the hatch-pet skill's `pixel-art-rules.md` (`references/` folder) for the fix, then re-run with adjusted `--cell` or `--max-colors`. Lower `--cell` (48, 32) or `--max-colors` (32, 16) to shrink strips.
4. **Validate** again if you changed anything:
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/validate_pet.py" WORK/<id>
   ```
5. **Preview** the result and look at it; downscaling can lose fine detail (thin lines, small faces), so check the face and silhouette at the new size:
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/contact_sheet.py" WORK/<id> --out WORK/<id>-sheet.png
   python "${CLAUDE_PLUGIN_ROOT}/tools/preview_gif.py" WORK/<id> --out WORK/<id>-gifs --animation idle --animation working
   ```
   Try a larger `--cell` if detail is lost and strips still fit.
6. **Tell the user** which rows were imported (rows 0-10) and which new rows fall back, and that the `hatch-pet` skill can add `sleeping`, `pop-out`, `duck-in`, `petted`, and the rest, drawn to match.
7. **Install only after the user confirms:**
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/import_codex_pet.py" SRC --out-dir WORK --pixelate --cell 64 --install
   ```
   or, for the already-imported package, `python "${CLAUDE_PLUGIN_ROOT}/tools/package_pet.py" WORK/<id> --install`. This copies to `~/.claude/pets/<id>/` (never overwrite an existing pet without saying so).
8. **Select it** with `/pet use <id>`.

## Notes

- v1 Codex pets (8 x 9 atlas, no look rows) import with the look direction row falling back to `idle`; v2 pets (8 x 11) import fully. The importer reads the Codex manifest keys it finds; if it reports a missing or unreadable spritesheet, check the folder for the sheet file (PNG or WebP) and the manifest path.
- Keep the source folder untouched; the importer only reads it.
- The output goes to `--out-dir` (default: the current directory), so pass a work folder, not the source folder.
