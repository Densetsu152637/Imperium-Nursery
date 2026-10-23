# Image generation for pet art

This skill never assumes a particular image generator. It describes what to ask for and what to save; any tool that can produce an image can fill the contract.

## Choosing a source

1. **Discover what the session offers.** Look for, in this order of convenience:
   - image-generation MCP tools or plugins (check the available tool list; names vary);
   - a model that can output images directly in the conversation or through a local script;
   - a local diffusion setup the user runs (a UI or CLI on their machine);
   - images the user supplies or commissions (concept art, a mascot, existing sprites).
2. **Ask the user which to use**, listing only what you actually found, plus "supply your own art" and "hand-drawn pixel art by script". If the user already named one, use it without asking.
3. If the chosen tool needs credentials, billing or a download the user has not approved, ask first. Never enter credentials yourself.

Record the choice and the settings that worked (aspect ratio, prompt prefix) in `WORK/notes.md` so later rows use the same.

## Hand-off contract (per job)

One job produces one strip for one animation. Give the image tool, or the user, all of this:

| Field | Value |
| --- | --- |
| Subject | The pet, described once and identically in every job (name, species/shape, colours, markings, props, expression style). |
| Reference | The approved canonical base sprite (attach it; condition on it as an image reference, or as an init/edit image). Add the previous approved rows if the tool takes several references. |
| Poses | The animation's pose beats from [animation-guide.md](animation-guide.md), numbered left to right, exactly the frame count from the spec table. |
| Layout | One horizontal row of N poses, evenly spaced, each pose complete and separated by clear empty gap, none touching or overlapping, same scale and same baseline. |
| Canvas | Wide: width about N times height (for example 6 poses: 6:1 or the nearest the tool supports; 4:1 for 4 poses). If the tool only offers fixed ratios, use the widest, leave extra space at the edges, and let `extract_strip_frames.py` find the poses. |
| Background | One flat chroma colour, no gradient, no shadow, no floor, no texture. Default `#00FF00` pure green. Use magenta `#FF00FF` if the pet is green. The pet must not contain the key colour. |
| Style | Pixel art, limited palette, crisp hard edges, no anti-aliasing, no gradients, no blur, no glow, no outlines that change between poses. Same palette as the base. |
| Forbidden | Text, logos, watermarks, borders, grid lines, labels, extra characters, scenery, drop shadows. |
| Save as | `WORK/strips-src/<animation>.png` (PNG, as large as the tool outputs; do not downscale). |

Do not ask for a specific final pixel size. Image models rarely draw exact pixel grids; generate large and let the tools reduce to the cell. `extract_strip_frames.py` undoes an integer upscale if the art happens to be on a grid and otherwise box-downscales.

## Prompt template

```text
Pixel art sprite strip of <PET DESCRIPTION>, <STYLE CUES>.
Animation: <animation name>, <N> poses in one horizontal row, left to right:
1. <pose 1>
2. <pose 2>
...
Same character as the reference image: identical proportions, face, colours and palette in every pose.
Each pose fully separated by empty space, same size and same ground line, nothing overlapping.
Flat solid <#RRGGBB> background, no shadow, no floor, no gradient, no text.
Crisp pixel art with hard edges, limited palette, no anti-aliasing.
```

Style cue examples: "16-bit game sprite, chunky pixels, 1 px dark outline", "NES style, 4 colours plus outline", "clean modern pixel art, soft palette". Pick one and keep it for every job.

## Per-animation prompt notes

Use the template and insert the poses from the animation guide. Extra notes by animation:

| Animation | Add to the prompt |
| --- | --- |
| `idle` | "Subtle: the poses differ by 1 pixel of body movement and one blink. Pose 1 is the neutral reference pose." |
| `walk-right` | "Character faces right in every pose; legs alternate; body bobs." Check whether `walk-left` can be a mirror before generating it. |
| `walk-left` | "Same as walk-right but facing left," or mirror by script when symmetric. |
| `failed`, `confused` | "Effects (sweat drop, question mark) are small, same palette, inside the pose's own space." |
| `sleeping` | "Eyes closed in every pose; small z glyph rising." |
| `pop-out` | "The last pose is identical to the neutral idle pose. Pose 1 shows only a small part of the character." |
| `duck-in` | "Pose 1 is identical to the neutral idle pose. The last pose shows almost nothing, or empty space." |
| `look` | "16 poses of the same character looking in 16 clockwise directions starting at straight up. Only eyes and head turn; body stays still. None looks straight at the viewer." Often two jobs of 8 (see the animation guide). |
| `petted` | "Small hearts or sparkles allowed." |

## Consistency across rows

- Always attach the approved base sprite as the reference. Add one or two approved rows when the tool accepts several images.
- Re-state the full character description each time; do not rely on the tool remembering earlier jobs.
- Generate one row per job. Do not ask for a whole sheet in one image: poses drift, and one bad pose spoils the sheet.
- Review each strip before extracting: right pose count, right order, same character, key colour clean, nothing touching. Regenerate rather than patch.
- If the tool returns several candidates, pick one; do not mix poses from different candidates in one row.

## Fallbacks

- **No image tool available.** Say so, then offer: (a) the user supplies art (concept art for the base; full strips if they have them); (b) hand-drawn pixel art by script: write a small Python/Pillow script that draws each pose as a pixel grid, as `tools/make_sample_pet.py` does for the sample pet (read it for the approach), dump `frames/<animation>/NN.png` at the cell size and continue at the compose step. Keep palettes tiny (under 16 colours) and cell size 32 for scripted pets.
- **User-supplied single image of the character.** Use it as the base. For other rows, either generate with a tool or build simple variations by script (shifted or bobbed copies for idle, mirrored copies for walk-left) and say plainly which rows are placeholders.
- **A source that produces anti-aliased or non-pixel art.** That is fine; `extract_strip_frames.py` and `pixelate.py` convert it to compliant pixel art. Quality is better when the source is already stylised as pixel art.
- **Background removal fails** (key colour in the character, soft shadows): set `--key #RRGGBB` explicitly, raise `--tolerance`, or regenerate on a different key colour.
