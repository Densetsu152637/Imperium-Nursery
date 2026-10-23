# Pixel Pets

Pixel Pets is a pixel-art, animated pet for Claude Code. It sits in its own pane beside your chat and reacts to what the session is doing: it works while a turn runs, waits when Claude needs you, celebrates a commit, flinches at a failure, falls asleep when you leave. It also ships the tools and skills to make your own pet or bring one over from OpenAI Codex.

The pet format extends the Codex `hatch-pet` format (v2: 9 states and 16 look directions) to a v3 format with 22 animations and behaviour priorities. See [docs/pet-format-v3.md](docs/pet-format-v3.md).

## Features

- 22 animations: idle, walking, waving, jumping, failure, waiting, working, review, 16 look directions, sleeping, waking, summoning, celebrating, confused, eating, fidget, pop-out, duck-in, alert, petted.
- Behaviour priorities (P0-P6): states are loops, reactions are one-shots, and an arbiter decides what shows when several things happen at once (no flicker, coalescing, waking before reacting).
- Pixel art: cells up to 128 x 128, binary alpha, a colour budget per cell, rendered with nearest-neighbour scaling.
- Open format: a plain folder with `pet.json`, an 8 x 22 atlas PNG and per-animation strips. Missing animations fall back (a minimal pet needs only `idle`).
- Codex import: convert Codex v1 and v2 pets to v3.
- Creation tooling: Python CLIs for pixelating, cutting, composing, validating, packaging and previewing, plus Claude Code skills that drive them with any image generation tool.
- Sample pet: `pixel-clawd`, a procedurally drawn crab in [pets/pixel-clawd](pets/pixel-clawd).

## Install

This is how installation will work once the plugin is published to `Densetsu152637/Pixel-Pets`. It is not available from that marketplace yet.

```text
/plugin marketplace add Densetsu152637/Pixel-Pets
/plugin install pixel-pets@pixel-pets
```

The plugin provides the `pixel-pets` mod and the three skills below. The tools need Python 3 with [Pillow](https://pypi.org/project/pillow/).

## Using the pet

Pets are folders in `~/.claude/pets/<id>/`. The default pet is `pixel-clawd`.

| Command | Effect |
| --- | --- |
| `/pet` | Show the current pet. |
| `/pet use <id>` | Switch to the installed pet `<id>`. |
| `/pet pat` | Pat the pet (plays `petted`). |
| `/pet hide`, `/pet show` | Hide the pet (`duck-in`) or bring it back (`pop-out`). |
| `/pet open`, `/pet close` | Open or close the pet's pane. |

Options:

| Option | Default | Meaning |
| --- | --- | --- |
| `pet` | `pixel-clawd` | Pet id to load. |
| `sleepAfterMinutes` | 5 | Idle time before the pet falls asleep. |
| `fidget` | on | Occasional idle variety (stretch, yawn, scratch). |
| `openAtStart` | on | Open the pane at session start. |
| `size` | 96 | Display size in pixels. |

## Making a pet

Three skills ship in the plugin (in [skills/](skills)):

- **`hatch-pet`**: create a pet from a concept, reference images or brand cues. Works with any image generation tool you have, art you supply, or hand-drawn pixel art by script. It generates a base sprite, then one strip per animation, and assembles, validates, QA-checks and installs the package.
- **`import-codex-pet`**: convert a Codex pet to v3, then validate, preview and install it.
- **`pet-format`**: a short reference for the format.

Ask Claude, for example, "hatch a pet: a small robot with a blue visor". The tools can also be run by hand; each has `--help`:

| Tool | Purpose |
| --- | --- |
| `tools/pixelate.py` | Turn an image into compliant pixel art in one cell. |
| `tools/extract_strip_frames.py` | Cut a generated horizontal strip into frames. |
| `tools/compose_atlas.py` | Compose `frames/<animation>/NN.png` into the 8 x 22 atlas. |
| `tools/package_pet.py` | Cut `strips/`, validate, optionally install (`--install`). |
| `tools/validate_pet.py` | Check a package against the format. |
| `tools/import_codex_pet.py` | Convert a Codex v1 or v2 pet. |
| `tools/contact_sheet.py`, `tools/preview_gif.py` | Contact sheet and GIF previews for QA. |
| `tools/make_sample_pet.py` | Draw the sample pet; an example of scripted pixel art. |

## Animations

Priority: P0 highest. Full table (frame counts, durations, fallbacks) in the [format spec](docs/pet-format-v3.md#animations).

| Name | Priority | Trigger |
| --- | --- | --- |
| `petted` | P0 | You pat or click the pet. |
| `waiting` | P1 | Something is blocked on you (permission, question). |
| `alert` | P1 | Another source (a subagent) needs you while the shown one is busy. |
| `failed` | P2 | A tool failed or a turn errored. |
| `confused` | P2 | A permission was denied or a step was retried. |
| `jumping` | P3 | A turn finished cleanly. |
| `celebrating` | P3 | A commit, merged PR or passing tests. |
| `working` | P4 | A turn or subagent is running. |
| `review` | P4 | Inspecting finished output, or a reviewer subagent runs. |
| `summoning` | P4 | A subagent is dispatched. |
| `eating` | P4 | Context compaction. |
| `waving` | P5 | A session starts or you return. |
| `waking` | P5 | Plays first when anything happens while asleep. |
| `pop-out`, `duck-in` | P5 | The pet appears or hides. |
| `idle` | P6 | Default. |
| `walk-right`, `walk-left` | P6 | Idle wandering. |
| `look` | P6 | A glance toward the source of an event (16 directions). |
| `sleeping` | P6 | Idle past the sleep threshold. |
| `fidget` | P6 | Random idle variety every 20-60 s. |

## Format

[docs/pet-format-v3.md](docs/pet-format-v3.md) is the normative contract for the package layout, atlas, pixel-art rules, `pet.json`, animations, priorities and drawing. The tools, the mod and the skills all implement it.

## Limitations and future work

- **Chat-specific, in-window.** In version 3 the pet lives in a pane inside one session's window. It cannot float outside the window and does not see other chats.
- **Planned refactor: pop-out and multi-chat.** The target is a Codex-style pet that pops out of the panel and reacts to every live chat at once. The arbiter already treats events as coming from sources with priorities, so the refactor replaces the source registry (main conversation plus subagents) with one that also tracks other sessions, and replaces the pane with a floating surface. Both depend on Claude Code capabilities that do not exist yet: a cross-session event feed for mods, and a surface that can draw outside the transcript and panes.

## Licensing and credits

Apache-2.0; see [LICENSE](LICENSE). The pet format extends the pet format of OpenAI's Apache-2.0 `hatch-pet` skill for Codex; the 8-column atlas, the Codex v2 row layout for rows 0-10 and the idea of cutting frames from generated strips derive from it. The tools are original implementations. See [NOTICE](NOTICE). Pets you make or import keep their own licences, recorded in each `pet.json`.
