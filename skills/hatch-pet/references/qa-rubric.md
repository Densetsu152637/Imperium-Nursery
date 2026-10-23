# QA rubric

Judge the pet from the contact sheet and GIF previews, not from the validator alone. The validator proves the package loads; this rubric checks it is good. The idea of a written QA rubric follows OpenAI's Apache-2.0 `hatch-pet` skill (see `NOTICE`); the checks are written for the v3 format.

```text
python "${CLAUDE_PLUGIN_ROOT}/tools/contact_sheet.py" WORK --out WORK/qa/sheet.png
python "${CLAUDE_PLUGIN_ROOT}/tools/preview_gif.py" WORK --out WORK/qa --animation idle --animation pop-out --animation duck-in
```

Open `sheet.png` and the GIFs. `preview_gif.py` without `--animation` renders every drawn animation; `--scale N` enlarges for small cells. Do not report a pass for rows you did not view.

## Package

- [ ] `validate_pet.py` reports 0 errors.
- [ ] Rows the pet does not draw are intentional, and the user knows their fallbacks (for example `sleeping` shows `idle`).
- [ ] Used cells are non-empty; no stray pixels in unused cells (the validator also checks).
- [ ] No leftover chroma-key fringe (green or magenta edge pixels) around any frame.

## Identity consistency

- [ ] Silhouette, proportions, face, colours, markings and props match the base sprite in every row.
- [ ] Palette is shared across rows (no row looks lighter, darker or differently saturated).
- [ ] Scale and baseline are constant: the pet does not grow, shrink or float between frames or between rows.
- [ ] No frame adds an unintended character, object, text or logo.

## Readable motion

- [ ] Each animation reads as its purpose at its real size (cell size, and 96 px display). Check the GIF at 1x and the contact sheet.
- [ ] Loops (`idle`, `walk-*`, `waiting`, `working`, `review`, `sleeping`, `eating`, `alert`) cycle without a pop from last frame to first.
- [ ] One-shots (`waving`, `jumping`, `failed`, `waking`, `summoning`, `celebrating`, `confused`, `fidget`, `petted`) end near the neutral pose, because the shown loop resumes after them.
- [ ] `idle` frame 0 works as a still (reduced motion shows each animation's first frame only).
- [ ] `walk-right` faces right and `walk-left` faces left.
- [ ] `waiting`, `working`, `review`, `alert` and `failed` look clearly different from each other and from `idle`.
- [ ] `look` poses: 16 distinct directions in clockwise order from up; up, right, down and left read unmistakably; none equals the idle pose.

## Intensity matches priority

Higher priority (lower P number) is bolder and more attention-grabbing; lower priority is quieter.

- [ ] P0 `petted`: instant, clearly happy.
- [ ] P1 `waiting`, `alert`: attention-seeking, and `alert` is more urgent than `waiting`.
- [ ] P2 `failed`, `confused`: clear bad outcome; `confused` gentler than `failed`.
- [ ] P3 `jumping`, `celebrating`: clearly positive; `celebrating` bigger than `jumping`.
- [ ] P4 `working`, `review`, `eating`, `summoning`: steady activity, not distracting over long runs.
- [ ] P5 transitions (`waving`, `waking`, `pop-out`, `duck-in`): short and smooth.
- [ ] P6 ambient (`idle`, `walk-*`, `sleeping`, `fidget`, `look`): subtle. A pet that idles with big motion becomes annoying.

## Transitions and ending frames

- [ ] `pop-out` last frame equals the `idle` ready pose (same as `idle` frame 0), and its first frame is empty or nearly empty.
- [ ] `duck-in` first frame equals the `idle` ready pose, and its last frame is empty or nearly empty (the pet stays hidden after it).
- [ ] `waking` ends in an alert neutral pose that can hand off to any following animation.
- [ ] `fidget` starts and ends on the idle pose.

## Transparency

- [ ] Background is fully transparent (alpha 0) outside the pet; alpha is binary (the validator checks).
- [ ] No transparent holes inside the body; no one-pixel halo or fringe.
- [ ] The pet fits inside its cell with the pad margin on all sides (no clipped limbs or effects).

## Repair policy

Fix the smallest unit that is not mixed with other generations: one whole animation row. Regenerate or re-extract the row (steps 5-6 of the SKILL), re-compose, package, validate and re-check the rows you touched plus the contact sheet. After three failed attempts at a row, ask the user whether to simplify the design or let the row fall back.
