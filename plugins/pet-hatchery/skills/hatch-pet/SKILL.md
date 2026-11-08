---
name: hatch-pet
description: Create a Pixel Pet, a v3 pixel-art animated pet for the imperium-nursery mod, from a concept, reference images or brand cues. Use when the user wants to make, design, draw or hatch a new pet, mascot or sprite for Claude Code, or to add or redo animation rows of an existing pet. Works with any image generation tool, user-supplied art, or hand-drawn pixel art.
---

# Hatch Pet

Build a Pixel Pets v3 package: `pet.json`, an 8 x 22 `spritesheet.png` atlas and per-animation `strips/`. The contract is [pet-format-v3.md](../../docs/pet-format-v3.md); the `pet-format` skill summarises it. Do not restate it from memory; read the animation table when you need frame counts.

Tool paths below use `${CLAUDE_PLUGIN_ROOT}` (the installed plugin directory; Claude Code substitutes it in plugin skills). Run them with `python`; they need Pillow.

The pet lives in a working folder (call it `WORK`, for example `./pets-work/<id>/`), never directly in `~/.claude/pets/`. Install is the last step.

## Workflow

1. **Gather inputs.** Ask only for what is missing: a concept or character description, reference images, brand cues (colours, mascot, product), a name. Infer a short `id` (lowercase letters, digits, hyphens), a display name and a one-sentence description if the user gives none. Ask for an author and a licence (for pets derived from someone's brand or art, the user must have the right to use it).
2. **Pick a cell size.** Pixel art, at most 128 x 128 per cell; recommend 32, 48, 64 or 96. Smaller reads as pixel art and keeps strips well under the 96 KiB limit; 64 suits detailed characters. Choose a colour budget (default 64 per cell).
3. **Choose an image source** (see [image-generation.md](references/image-generation.md#choosing-a-source)): discover what the session offers, ask the user which to use, or use the one they named. Never assume a vendor. Fall back to user-supplied art or a drawing script if nothing is available.
4. **Make the canonical base sprite** (the `idle` frame, front/neutral pose) first. Show it to the user and get approval before generating anything else. Every later job conditions on this image. Optionally run it through `pixelate.py` to check it survives the cell size:
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/pixelate.py" base.png -o base-cell.png --cell 64 --max-colors 64
   ```
5. **Generate each animation as one horizontal strip** on a flat chroma background, one job per animation, using the per-animation prompts in [image-generation.md](references/image-generation.md) and the pose beats in [animation-guide.md](references/animation-guide.md). Save as `WORK/strips-src/<animation>.png`. Recommended order (stop when the user is happy; unmade rows fall back per the spec):
   1. `idle` (required)
   2. `working`, `waiting`, `jumping`, `failed` (the states people see most)
   3. `waving`, `petted`, `sleeping`, `waking`
   4. `walk-right`, `walk-left`, `fidget`, `review`
   5. `celebrating`, `confused`, `summoning`, `eating`, `alert`
   6. `pop-out`, `duck-in`, `look` (look is 16 directions; do last)

   A minimal pet needs only `idle`. Tell the user which rows will fall back and to what.
6. **Cut frames** per strip. The tool removes the chroma key, undoes any upscale, pixelates to a shared palette and writes `frames/<animation>/NN.png`:
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/extract_strip_frames.py" WORK/strips-src/idle.png --animation idle --cell 64 --out WORK/frames
   ```
   Use `--frames N` if the strip has a different pose count, `--slice equal` or `--slice gaps` when auto slicing picks the wrong cuts, `--key #RRGGBB` when the background is not auto-detected. Check the printed pose count against the spec. For `look`, which has 16 frames, use `--animation look`. For `walk-left` when the art is symmetric you may mirror frames instead of generating (see the animation guide).
7. **Write `WORK/pet.json`** (template in [pet-format SKILL](../pet-format/SKILL.md#petjson)) with `spriteVersionNumber: 3` and the chosen `cell`.
8. **Compose the atlas** into the pet folder:
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/compose_atlas.py" WORK/frames --out WORK/spritesheet.png --pet-json WORK/pet.json
   ```
   Animations without a frames directory stay transparent and fall back.
9. **Package** (cuts `strips/` and validates):
   ```text
   python "${CLAUDE_PLUGIN_ROOT}/tools/package_pet.py" WORK
   ```
   The folder name of `WORK` must equal the `id`.
10. **Validate** and fix:
    ```text
    python "${CLAUDE_PLUGIN_ROOT}/tools/validate_pet.py" WORK
    ```
    On errors, use [pixel-art-rules.md](references/pixel-art-rules.md) to find the fix, regenerate or re-extract the affected rows, and repeat steps 6-10. Do not hand-edit the atlas to silence a validator.
11. **QA.** Render a contact sheet and GIF previews, look at them, and judge them against [qa-rubric.md](references/qa-rubric.md):
    ```text
    python "${CLAUDE_PLUGIN_ROOT}/tools/contact_sheet.py" WORK --out WORK/qa/sheet.png
    python "${CLAUDE_PLUGIN_ROOT}/tools/preview_gif.py" WORK --out WORK/qa --animation idle --animation working --animation pop-out
    ```
    Redo any failing row from step 5. Repair whole rows; never splice a single regenerated frame next to frames from another generation.
12. **Install, only after the user confirms** (show the id, the rows drawn and the rows falling back):
    ```text
    python "${CLAUDE_PLUGIN_ROOT}/tools/package_pet.py" WORK --install
    ```
    This copies the package to `~/.claude/pets/<id>/`. Add `--install-dir DIR` to install elsewhere.
13. **Select it** with `/pet use <id>` (requires the `imperium-nursery` plugin, installed separately).

## Rules

- One image job per animation, always conditioned on the approved base sprite, and generated at several times the cell size on a flat chroma background; the tools do the pixelation.
- Image generation stays tool-agnostic. Hand-off contract and fallbacks are in [image-generation.md](references/image-generation.md).
- Prefer scripts for deterministic work (cutting, palette, atlas, packaging). Use judgement only for art direction and QA.
- Keep scratch files in `WORK`, and delete `strips-src/` and failed generations when the pet is installed, unless the user wants them.
- Ask before installing. Do not overwrite an existing `~/.claude/pets/<id>/` without saying so.

## References

- [image-generation.md](references/image-generation.md): sources, hand-off contract, prompt templates, fallbacks.
- [animation-guide.md](references/animation-guide.md): what each of the 22 animations shows, pose by pose.
- [pixel-art-rules.md](references/pixel-art-rules.md): validator rules and fixes.
- [qa-rubric.md](references/qa-rubric.md): the acceptance checklist.

Workflow shape (canonical base first, one job per row, shared identity, deterministic assembly, contact-sheet QA) follows OpenAI's Apache-2.0 `hatch-pet` skill; see `NOTICE`. The text here is original.
