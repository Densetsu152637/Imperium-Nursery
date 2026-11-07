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

Pixel Pets installs as a plugin from its GitHub repository. In a Claude Code terminal session:

```text
/plugin marketplace add Densetsu152637/Pixel-Pets
/plugin install pixel-pets@pixel-pets
```

The plugin provides the `pixel-pets` mod (the pet pane and the `/pet` command) and the three skills below, and ships `tools/`, `docs/`, `skills/` and the sample pet in `pets/`. The tools need Python 3 with [Pillow](https://pypi.org/project/pillow/). The sample pet `pixel-clawd` is not installed automatically: run `python tools/package_pet.py pets/pixel-clawd --install` (or copy the folder to `~/.claude/pets/pixel-clawd`) so the mod finds it.

## Using the pet

Pets are folders in `<pets folder>/<id>/`. The pets folder is the `petsDir` option if set, else the `CLAUDE_PETS_DIR` environment variable, else `~/.claude/pets`. The default pet is `pixel-clawd`.

On the desktop the pet is drawn as an animated image in a pane, with a "pat" button under it. The terminal cannot crop a frame out of a strip, so it shows a text line `<name> · <animation>` and the pat button.

| Command | Effect |
| --- | --- |
| `/pet` | Status: the current pet and animation, and the installed pets. |
| `/pet use <id>` | Switch to the installed pet `<id>`; remembered for later sessions. |
| `/pet pat` | Pat the pet (plays `petted`). |
| `/pet hide` | Play `duck-in`, then hide the pet. |
| `/pet show` | Bring a hidden pet back (plays `pop-out`). |
| `/pet open`, `/pet close` | Open or close the pet's pane. |

Options:

| Option | Default | Meaning |
| --- | --- | --- |
| `pet` | `pixel-clawd` | Pet id to load. |
| `sleepAfterMinutes` | 5 | Idle minutes before the pet falls asleep; 0 never sleeps. |
| `fidget` | on | on/off. While idle, a fidget every 20-60 seconds; off, it only breathes. |
| `openAtStart` | on | on/off. Open the pane when a session starts; off, only `/pet open` opens it. |
| `size` | 96 | Display size in pixels, clamped to 24-512 (and to the pane width). |
| `petsDir` | (empty) | Absolute path of the pets folder; empty uses `CLAUDE_PETS_DIR`, then `~/.claude/pets`. |

### What the pet reacts to

| Claude Code event | Animation |
| --- | --- |
| Session starts | `pop-out`, then `waving` |
| Main turn starts / ends cleanly / errors | `working` loop / `jumping` / `failed` |
| Subagent dispatched | `summoning`, then its `working` loop (`review` for a reviewer) |
| Subagent finishes / fails | `jumping` / `failed`, with a glance toward it |
| Tool call fails | `failed`; if the error says it was refused or denied, `confused` |
| Tool call denied by a rule or hook | `confused` |
| Permission prompt or `AskUserQuestion` | `waiting` until the call returns |
| Subagent waiting while the main turn works | `alert` |
| `git commit`, `gh pr merge` or a test run that exits 0 | `celebrating` |
| Context compaction | `eating` |
| `/pet pat` or the pat button | `petted` |
| Idle past `sleepAfterMinutes` / while idle | `sleeping` / `fidget` every 20-60 s |
| Any event while asleep | `waking` first |

Known gaps: Claude Code has no event for "a permission prompt is open", so the mod infers it from a `tool.check` verdict of `ask` and clears it when the call returns (a prompt answered by the auto-mode classifier looks the same as one a person answers). "Denied" is recognised by the wording of the error the model receives, which is not a stable API.

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

MIT; see [LICENSE](LICENSE). The pet format extends the pet format of OpenAI's Apache-2.0 `hatch-pet` skill for Codex; the 8-column atlas, the Codex v2 row layout for rows 0-10 and the idea of cutting frames from generated strips derive from it. The tools are original implementations. See [NOTICE](NOTICE). Pets you make or import keep their own licences, recorded in each `pet.json`.
