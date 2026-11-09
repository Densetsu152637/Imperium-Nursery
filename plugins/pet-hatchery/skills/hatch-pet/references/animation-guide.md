# Animation guide

What each animation should show, frame by frame. Frame counts, durations, priorities and fallbacks come from the table in [pet-format-v3.md](../../../docs/pet-format-v3.md#animations); this file adds the poses. Beats are for a generic character with a face, body and limbs; adapt them to the design (a blob squashes, a bird flaps).

General rules:

- Frame 0 is the reduced-motion still, so it must read as the animation's key pose (or neutral for loops).
- Loops: the last frame must lead back into frame 0 without a pop. Do not repeat frame 0 at the end.
- Keep the character's feet on one baseline (the extractor rests frames on a common baseline) and its scale constant. Motion lives in the body, not in resizing.
- Small, readable changes beat many tiny ones. At 32-64 px, a change of 1-3 px per frame is enough.
- Intensity follows priority (see the [QA rubric](qa-rubric.md#intensity-matches-priority)): P0-P2 reactions are bold, P6 ambient is subtle.
- Effects (sparkles, zzz, sweat drops, "!") are allowed if small, drawn in the same palette, and inside the cell. No text beyond simple glyphs like `!` `?` `z`.

## Standard rows (Codex v2 layout, rows 0-10)

### idle (6 frames, loop, P6, row 0)
Calm breathing and an occasional blink. Required.
0 neutral front pose; 1 inhale (body up 1 px); 2 hold; 3 exhale (down 1 px); 4 blink (eyes closed); 5 eyes open, settle toward 0. Durations are uneven on purpose (blink is quick). Must be the base sprite in frame 0.

### walk-right (8 frames, loop, P6, row 1)
A walk cycle facing right: contact, down, pass, up, then the mirror leg. 0 right foot forward contact; 1 down; 2 passing; 3 up; 4 left foot forward contact; 5 down; 6 passing; 7 up/recover. Body bobs, limbs swing. The character faces right throughout.

### walk-left (8 frames, loop, P6, row 2)
The same cycle facing left. If the design is left-right symmetric (no asymmetric markings, held props or text), mirror the frames of `walk-right` with a script (flip each `frames/walk-right/NN.png` into `frames/walk-left/NN.png`) rather than generating. `make_sample_pet.py` does this.

### waving (4 frames, once, P5, row 3)
A greeting. 0 neutral; 1 arm/limb raised; 2 wave out; 3 wave in, held longest. End near neutral.

### jumping (5 frames, once, P3, row 4)
A happy hop for a clean finish. 0 crouch (anticipation); 1 launch, stretched; 2 apex, tucked or arms up; 3 descent; 4 landing squash, settling. Highest point clearly above the baseline but inside the cell.

### failed (8 frames, once, P2, row 5)
A tool failed or a turn errored. Dramatic but not scary. 0 neutral; 1 flinch (recoil); 2 eyes wide or `x` eyes; 3 slump begins; 4 slumped, sweat drop or dark cloud; 5 hold; 6 shake head or sigh; 7 recover toward neutral. Slumps and effects must fit the cell.

### waiting (6 frames, loop, P1, row 6)
Something is blocked on the person. Patient but attention-seeking. 0 look up and out toward the viewer; 1 tilt head; 2 small bounce or foot tap; 3 tilt other way; 4 tap; 5 blink. Must read differently from `idle` (more alert, more eye contact) and from `working`.

### working (6 frames, loop, P4, row 7)
A turn or subagent is running. Busy and focused: typing, tinkering, hammering, whatever suits the character. 0-5 a repeating motion cycle of limbs or tool with a steady rhythm (keep the 5 x 120 ms + 220 ms feel). Eyes down or on the task.

### review (6 frames, loop, P4, row 8)
Inspecting output. Distinct from `working`: a magnifier, a squint, scanning left-right, chin on hand. 0 lean in; 1 scan left; 2 scan centre; 3 scan right; 4 nod; 5 squint and return.

### look (16 poses, pose, P6, rows 9-10)
A glance toward a direction. Not an animation: 16 still poses, clockwise from up. Row 9: 000, 022.5, 045, 067.5, 090, 112.5, 135, 157.5. Row 10: 180, 202.5, 225, 247.5, 270, 292.5, 315, 337.5. `000` is straight up (12 o'clock), `090` is toward the viewer's right, `180` straight down (toward the transcript), `270` left. Move the eyes and a little head turn; keep the body in place. Neutral is not a look pose (it is `idle`), so every pose must visibly differ from neutral. Generate one strip of 16 poses and extract it with `--animation look`. If the image tool cannot hold 16 poses, generate two strips of 8, extract each with `--animation look --frames 8` into separate `--out` folders (`look-a`, `look-b`), then copy their PNGs into `frames/look/` as `00`-`07` and `08`-`15` (the two strips get separate palettes, so check the result for colour drift). Do this row last.

## New rows (11-21)

### sleeping (6 frames, loop, 400 ms each, P6, row 11)
Idle past 5 minutes. 0 eyes closed, curled or slumped; 1-5 slow breathing with a rising `z` (or similar). Slow and quiet.

### waking (6 frames, once, P5, row 12)
Plays first when something happens while asleep. 0 asleep pose; 1 twitch; 2 eyes open a crack; 3 stretch or startle; 4 shake off; 5 alert neutral, so it hands off cleanly to the next animation.

### summoning (6 frames, once, P4, row 13)
A subagent is dispatched. A call-out: 0 neutral; 1 raise limb or tool; 2 gesture forward, a small sparkle or portal appears; 3 release, a small helper or spark flies off; 4 hold; 5 return to neutral. Falls back to `waving`.

### celebrating (8 frames, once, P3, row 14)
A commit, merged PR or green tests. Bigger than `jumping`: 0 crouch; 1 leap with arms up; 2 confetti or sparkles; 3 apex spin or twirl; 4 spin continues; 5 landing; 6 pose with arms up; 7 settle. Falls back to `jumping`.

### confused (6 frames, once, P2, row 15)
A permission was denied or a step was retried. 0 neutral; 1 head tilt; 2 `?` appears; 3 scratch head or shrug; 4 tilt other way; 5 settle. Gentler than `failed`. Falls back to `failed`.

### eating (6 frames, loop, 140 ms each, P4, row 16)
Context compaction ("digesting"). A chewing loop: 0 mouth open toward a morsel or crumb; 1 bite; 2 chew; 3 chew wide; 4 chew; 5 swallow. Cheeks puff. Falls back to `working`.

### fidget (6 frames, once, P6, row 17)
Random idle variety every 20-60 s: stretch, yawn, scratch or look around. 0 neutral; 1-4 the gesture; 5 return to neutral so it hands back to `idle`. Subtle (P6).

### pop-out (6 frames, once, P5, row 18)
The pet appears. Anticipation then arrival: 0 empty or only a hint (a tiny part visible); 1 rising or emerging; 2 overshoot; 3 settle; 4 ready; 5 **the final frame is exactly the idle-ready pose (same as `idle` frame 0)**. Pop-out must end where `idle` begins so the handoff is seamless.

### duck-in (6 frames, once, P5, row 19)
The pet hides. The reverse of pop-out: 0 idle pose (same as `idle` frame 0); 1 notice, crouch; 2 sink; 3 mostly hidden; 4 only a hint left; 5 **the final frame is empty or nearly empty (a sliver, or fully transparent)**, because the pet stays hidden after it. A fully transparent last frame is allowed. Falls back to `idle`.

### alert (4 frames, loop, 120 ms each, P1, row 20)
Another source needs the person while the shown source is busy. Urgent and quick: 0 `!` appears, wide eyes; 1 bounce up; 2 `!` flash; 3 bounce down. Distinct from `waiting` (faster, more intense). Falls back to `waiting`.

### petted (6 frames, once, P0, row 21)
The person clicked or patted the pet. Happy and immediate: 0 neutral; 1 squish down, eyes closed in pleasure; 2 hearts or sparkles; 3 wiggle; 4 wiggle other way; 5 relax. P0 is top priority, so it must read instantly. Falls back to `waving`.

## Custom animations

Any other key in `pet.json` `animations` is a custom animation with its own row (22 or more), `frames`, `durations`, `fallback`. See the [pet-format skill](../../pet-format/SKILL.md#custom-animations). Custom animations default to P4 and must give a fallback that reaches a drawn animation.
