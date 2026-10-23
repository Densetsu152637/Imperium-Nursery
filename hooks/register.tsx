import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { PetsArbiter } from '../types'

import { current, dispatch, initial, lookIndex, nextWake } from './arbiter'
import type { Env, PetEvent } from './arbiter'
import { isCelebration, isReviewer, looksDenied } from './events'
import { allDrawn, fallbackChain, parsePetJson, resolveAnimation, withDrawn } from './pet'
import type { Catalog, PetDef } from './pet'
import { pngSize } from './png'
import { SVG_LIMIT, renderFragment } from './render'

// clawd-pets: a pixel pet in its own pane. It shares nothing with other mods: its state keys,
// its pane (`pet`) and its command (`/pet`) are its own, and it draws nowhere else.
//
// EVENT MAP (Claude Code event -> arbiter input -> animation)
//   session.start               first load: pop-out, then waving (a hot reload keeps the state)
//   turn.start (main)           main loop `working`
//   turn.start (subagent)       that subagent's loop `working`, only if agent.spawn did not set one
//   turn.complete (main)        loop cleared; reason answer -> `jumping`, error/refusal -> `failed`, aborted -> none
//   turn.complete (subagent)    its source ends; answer -> `jumping`, error/refusal -> `failed` (glance at it)
//   tool.call result isError    `failed`; text that says the person/rules refused -> `confused`
//   tool.call result { deny }   `confused`
//   tool.check verdict `ask`    the source holds `waiting` until its tool.call returns (a permission prompt)
//     (unless the host answers asks)
//   tool.call AskUserQuestion   the source holds `waiting` until the call returns
//   agent.spawn                 `summoning` one-shot, then the subagent's loop `working`, or `review` when its
//                               type or brief tag (`Profile: critic|validator|inspector|auditor`) names a reviewer
//   subagent `waiting`          drawn as `alert` while the main loop is P2 or lower (arbiter rule)
//   Bash/PowerShell ok          `git commit`, `gh pr merge`, a test runner (pytest, unittest, npm/pnpm/yarn
//                               test, cargo test, go test, claude plugin test) that exits 0 -> `celebrating`
//   session.compact (main)     main overlay loop `eating` while it runs
//   /pet pat, the pat button    `petted`;  /pet hide -> duck-in, hidden;  /pet show -> pop-out
//   (no events)                 idle past sleepAfterMinutes -> `sleeping`; `fidget` every 20-60 s while idle
//   any event above P6 while asleep plays `waking` first.
//
// GAPS: there is no event for "a permission prompt is open", so it is derived from the `ask`
// verdict of tool.check and cleared when the call returns; a prompt answered by the auto-mode
// classifier is not told apart from a person's. "Permission denied" is recognised by the
// wording of the error the model receives (events.ts), which is not a stable API.

const PANE = 'pet'
const COMMAND = 'pet'
/** How often a pet's files are checked again for changes. */
const RECHECK_MS = 3000
const DEFAULT_PET = 'pixel-clawd'

const arbiterAtom = atom({ plugin: 'clawd-pets', key: 'arbiter' } as const, null)
const selectionAtom = atom({ plugin: 'clawd-pets', key: 'selection' } as const, '')

// --- options and module caches (a reload starts them over) ----------------------------------

type Opts = { pet: string; sleepAfterMinutes: number; fidget: boolean; openAtStart: boolean; size: number; petsDir: string }
let opts: Opts = { pet: DEFAULT_PET, sleepAfterMinutes: 5, fidget: true, openAtStart: true, size: 96, petsDir: '' }

const readOpts = (o: Record<string, unknown>): Opts => {
  const num = (v: unknown, d: number): number => (typeof v === 'number' && Number.isFinite(v) ? v : d)
  return {
    pet: typeof o.pet === 'string' && o.pet.trim() ? o.pet.trim() : DEFAULT_PET,
    sleepAfterMinutes: Math.max(0, num(o.sleepAfterMinutes, 5)),
    fidget: o.fidget !== 'off' && o.fidget !== false,
    openAtStart: o.openAtStart !== 'off' && o.openAtStart !== false,
    size: Math.min(512, Math.max(24, Math.round(num(o.size, 96)))),
    petsDir: typeof o.petsDir === 'string' ? o.petsDir.trim() : '',
  }
}

type Loaded = {
  def: PetDef
  dir: string
  /** Strip name -> its file's size and mtime, for the strips that are loadable. */
  strips: Map<string, { size: number; mtimeMs: number }>
  catalog: Catalog
}
type PetEntry = { checkedAt: number; jsonMtime: number; stripKey: string; loaded: Loaded | null; error: string }

const pets = new Map<string, PetEntry>()
const stripData = new Map<string, { ver: string; b64: string | null }>()
const warned = new Set<string>()
let timer: { cancel: () => void } | undefined
const blockedIds = new Set<string>()

const warnOnce = ($: EngineInterface, key: string, text: string): void => {
  if (warned.has(key)) return
  warned.add(key)
  void $.ui.log(`clawd-pets: ${text}`)
}

// --- the pets folder --------------------------------------------------------------------------

const slashes = (p: string): string => p.replace(/\\/g, '/').replace(/\/+$/, '')

/** Where pet packages live: the `petsDir` option, CLAUDE_PETS_DIR, else ~/.claude/pets. */
async function petsRoot($: EngineInterface): Promise<string | null> {
  if (opts.petsDir) return slashes(opts.petsDir)
  const env = await $.env.get('CLAUDE_PETS_DIR')
  if (env) return slashes(env)
  const home = (await $.env.get('USERPROFILE')) || (await $.env.get('HOME'))
  return home ? `${slashes(home)}/.claude/pets` : null
}

const isPetId = (id: string): boolean => /^[a-z0-9-]+$/.test(id)

/** The installed pet `id`, re-read when its files change (checked at most every few seconds). */
async function getPet($: EngineInterface, id: string, now: number): Promise<PetEntry> {
  const cached = pets.get(id)
  if (cached && now - cached.checkedAt < RECHECK_MS) return cached
  const fail = (error: string): PetEntry => {
    const e: PetEntry = { checkedAt: now, jsonMtime: -1, stripKey: '', loaded: null, error }
    pets.set(id, e)
    return e
  }
  if (!isPetId(id)) return fail(`"${id}" is not a pet id (lowercase letters, digits and hyphens)`)
  const root = await petsRoot($)
  if (!root) return fail('cannot find the home folder; set the petsDir option')
  const dir = `${root}/${id}`
  let mtime: number
  try {
    mtime = (await $.fs.stat(`${dir}/pet.json`)).mtimeMs
  } catch {
    return fail(`no pet "${id}" in ${root}`)
  }
  let def = cached?.loaded?.def
  if (!def || cached?.jsonMtime !== mtime) {
    let text: string
    try {
      text = await $.fs.read(`${dir}/pet.json`)
    } catch {
      return fail(`cannot read ${dir}/pet.json`)
    }
    const parsed = parsePetJson(text, id)
    if (!parsed.ok) return fail(`${id}: ${parsed.error}`)
    def = parsed.pet
  }
  let entries: Awaited<ReturnType<EngineInterface['fs']['list']>> = []
  try {
    entries = await $.fs.list(`${dir}/${def.stripsPath}`)
  } catch {
    return fail(`${id}: no strips folder (run tools/package_pet.py)`)
  }
  const strips = new Map<string, { size: number; mtimeMs: number }>()
  for (const f of entries) {
    if (f.kind !== 'file' || !f.name.endsWith('.png')) continue
    const name = f.name.slice(0, -4)
    // A base64 strip must fit the Svg element's limit with room for the rest of the fragment.
    if (Math.ceil(f.size / 3) * 4 > SVG_LIMIT - 2000) {
      warnOnce($, `${id}/${name}`, `${id}: strip ${name}.png is too large to embed (96 KiB at most); its fallback is drawn instead`)
      continue
    }
    strips.set(name, { size: f.size, mtimeMs: f.mtimeMs })
  }
  if (!strips.has('idle')) return fail(`${id}: strips/idle.png is missing (a pet must draw idle)`)
  const stripKey = [...strips].map(([n, v]) => `${n}:${v.size}:${v.mtimeMs}`).join('|')
  if (cached?.loaded && cached.jsonMtime === mtime && cached.stripKey === stripKey) {
    cached.checkedAt = now
    return cached
  }
  const entry: PetEntry = {
    checkedAt: now,
    jsonMtime: mtime,
    stripKey,
    loaded: { def, dir, strips, catalog: withDrawn(def.catalog, new Set(strips.keys())) },
    error: '',
  }
  pets.set(id, entry)
  return entry
}

/** A strip's PNG as base64, checked against the pet's cell size; null when unusable. */
async function stripOf($: EngineInterface, p: Loaded, name: string): Promise<string | null> {
  const info = p.strips.get(name)
  if (!info) return null
  const key = `${p.def.id}/${name}`
  const ver = `${info.mtimeMs}:${info.size}`
  const hit = stripData.get(key)
  if (hit && hit.ver === ver) return hit.b64
  let b64: string | null = null
  try {
    b64 = (await $.fs.read(`${p.dir}/${p.def.stripsPath}/${name}.png`, { as: 'bytes' })).base64
  } catch {
    b64 = null
  }
  if (b64 !== null) {
    const size = pngSize(b64)
    const frames = p.catalog[name]?.frames ?? 1
    if (!size || size.width !== frames * p.def.cell.width || size.height !== p.def.cell.height) {
      warnOnce($, `${key}:${ver}`, `${p.def.id}: strips/${name}.png is not ${frames * p.def.cell.width}x${p.def.cell.height}; ignored`)
      b64 = null
    }
  }
  stripData.set(key, { ver, b64 })
  return b64
}

// --- the arbiter, driven by the mod ------------------------------------------------------------

const arbiterEnv = (loaded: Loaded | null): Env => ({
  catalog: loaded ? loaded.catalog : allDrawn(),
  sleepAfterMs: opts.sleepAfterMinutes * 60_000,
  fidget: opts.fidget,
})
async function selected($: EngineInterface): Promise<string> {
  return (await read($, selectionAtom)) || opts.pet
}

function schedule($: EngineInterface, state: PetsArbiter, env: Env, at: number): void {
  timer?.cancel()
  timer = undefined
  const wake = nextWake(state, at, env)
  if (wake === null) return
  timer = $.clock.after(Math.max(20, wake - at + 5), () => void tick($))
}

async function tick($: EngineInterface): Promise<void> {
  const at = await $.clock.now()
  const entry = await getPet($, await selected($), at)
  const env = arbiterEnv(entry.loaded)
  const next = await update($, arbiterAtom, prev => dispatch(prev ?? initial(at), { type: 'tick' }, at, env))
  if (next) schedule($, next, env, at)
}

/** Feeds the arbiter an event (or several, applied together at one instant). */
async function act($: EngineInterface, input: PetEvent | PetEvent[]): Promise<PetsArbiter | null> {
  const events = Array.isArray(input) ? input : [input]
  try {
    const at = await $.clock.now()
    const entry = await getPet($, await selected($), at)
    const env = arbiterEnv(entry.loaded)
    const next = await update($, arbiterAtom, prev => events.reduce((s, ev) => dispatch(s, ev, at, env), prev ?? initial(at)))
    if (next) schedule($, next, env, at)
    return next
  } catch (error) {
    // The pet must never break the session it decorates.
    warnOnce($, `act:${String(error)}`, `event ${events.map(ev => ev.type).join('+')} failed: ${String(error)}`)
    return null
  }
}

// --- what the pane shows -------------------------------------------------------------------------

type Drawn = {
  petId: string
  displayName: string
  animation: string
  isHidden: boolean
  svg: string
  width: number
  height: number
}

type View = { kind: 'drawn'; drawn: Drawn } | { kind: 'missing'; reason: string }

async function viewOf($: EngineInterface, at: number, size: number): Promise<View> {
  const id = await selected($)
  const entry = await getPet($, id, at)
  const p = entry.loaded
  if (!p) return { kind: 'missing', reason: entry.error }
  const state = (await read($, arbiterAtom)) ?? initial(at)
  const cur = current(state, at, arbiterEnv(p))
  const base = { petId: p.def.id, displayName: p.def.displayName }
  if (cur.isHidden) return { kind: 'drawn', drawn: { ...base, animation: cur.name, isHidden: true, svg: '', width: 0, height: 0 } }
  const chain = cur.kind === 'look' ? ['look', 'idle'] : fallbackChain(p.catalog, cur.name)
  for (const name of chain) {
    const a = p.catalog[name]
    if (!a?.drawn) continue
    const png = await stripOf($, p, name)
    if (!png) continue
    const f = renderFragment({
      petId: p.def.id,
      animation: name,
      frames: a.frames,
      durations: a.durations,
      loop: a.loop,
      pose: name === 'look' ? lookIndex(cur.look ?? 180) : undefined,
      cell: p.def.cell,
      size,
      startedAt: cur.startedAt,
      now: at,
      png,
    })
    if (f.svg.length > SVG_LIMIT) continue
    return { kind: 'drawn', drawn: { ...base, animation: name, isHidden: false, svg: f.svg, width: f.width, height: f.height } }
  }
  return { kind: 'missing', reason: `${p.def.id}: no strip could be drawn` }
}

// --- the module ---------------------------------------------------------------------------------

export const register: Register = (on, options) => {
  opts = readOpts(options as Record<string, unknown>)

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({
      name: COMMAND,
      description: 'Your pet: status, use <id>, pat, hide, show, open, close',
      argumentHint: '[use <id>|pat|hide|show|open|close]',
    })
    const stored = await $.store.get('pet')
    await update($, selectionAtom, () => (typeof stored === 'string' && isPetId(stored) ? stored : opts.pet))
    const isFirst = (await read($, arbiterAtom)) === null
    // A hot reload keeps the state: only the timer is set again.
    if (isFirst) await act($, { type: 'start' })
    else {
      const at = await $.clock.now()
      const entry = await getPet($, await selected($), at)
      const state = await read($, arbiterAtom)
      if (state) schedule($, state, arbiterEnv(entry.loaded), at)
    }
    if (isFirst && opts.openAtStart) {
      const at = await $.clock.now()
      const entry = await getPet($, await selected($), at)
      await $.ui.open({ id: PANE, title: entry.loaded?.def.displayName ?? 'Pet' })
    }
    return started
  })

  // --- the main conversation and its subagents ---
  on('turn.start', async ($, e, next) => {
    const started = await next(e)
    if (e.agentId === undefined) await act($, { type: 'loop', source: 'main', name: 'working' })
    else await act($, { type: 'ensure', source: e.agentId, name: 'working' })
    return started
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    const source = e.agentId ?? 'main'
    const reaction = e.reason === 'answer' ? 'jumping' : e.reason === 'aborted' ? null : 'failed'
    const events: PetEvent[] = [{ type: 'end', source }]
    if (reaction) events.push({ type: 'shot', name: reaction, source })
    await act($, events)
    return result
  })

  on('agent.spawn', async ($, e, next) => {
    const started = await next(e)
    if (started.deny !== undefined) return started
    const id = started.agentId ?? e.tool_use_id
    await act($, [
      { type: 'shot', name: 'summoning', source: 'main' },
      { type: 'spawn', source: id, name: isReviewer(e.subagentType, e.prompt) ? 'review' : 'working' },
    ])
    return started
  })

  // --- permission prompts and questions: the source is `waiting` until the call returns ---
  on('tool.check', async ($, e, next) => {
    const verdict = await next(e)
    if (verdict.decision === 'ask' && e.approver !== 'host' && e.tool_use_id) {
      blockedIds.add(e.tool_use_id)
      await act($, { type: 'block', source: e.agentId ?? 'main', id: e.tool_use_id })
    }
    return verdict
  })

  on('tool.call', async ($, e, next) => {
    const source = e.agentId ?? 'main'
    const id = e.tool_use_id
    if (e.tool === 'AskUserQuestion') {
      blockedIds.add(id)
      await act($, { type: 'block', source, id })
    }
    let result
    try {
      result = await next(e)
    } finally {
      if (blockedIds.delete(id)) await act($, { type: 'unblock', source, id })
    }
    if (result.deny !== undefined) await act($, { type: 'shot', name: 'confused', source })
    else if (result.isError) await act($, { type: 'shot', name: looksDenied(result.text) ? 'confused' : 'failed', source })
    else if ((e.tool === 'Bash' || e.tool === 'PowerShell') && typeof e.command === 'string' && isCelebration(e.command)) {
      const out = result.result as { backgroundTaskId?: string } | undefined
      // A command moved to the background has not finished: its exit is unknown.
      if (!out?.backgroundTaskId) await act($, { type: 'shot', name: 'celebrating', source })
    }
    return result
  })

  on('session.compact', async ($, e, next) => {
    if (e.trigger === 'precompute' || e.agentId !== undefined) return next(e)
    await act($, { type: 'overlay', source: 'main', name: 'eating' })
    try {
      return await next(e)
    } finally {
      await act($, { type: 'overlay', source: 'main', name: null })
    }
  })

  // --- /pet ---
  on('command.run', { command: COMMAND }, async ($, e) => {
    const [sub = '', ...rest] = e.args.trim().split(/\s+/)
    const arg = rest.join(' ')
    const at = await $.clock.now()
    const id = await selected($)
    const entry = await getPet($, id, at)
    const name = entry.loaded?.def.displayName ?? 'Pet'
    switch (sub.toLowerCase()) {
      case '':
      case 'status': {
        const root = await petsRoot($)
        let installed: string[] = []
        try {
          installed = root ? (await $.fs.list(root)).filter(f => f.kind === 'dir' && isPetId(f.name)).map(f => f.name) : []
        } catch {
          installed = []
        }
        const state = (await read($, arbiterAtom)) ?? initial(at)
        const cur = current(state, at, arbiterEnv(entry.loaded))
        const lines = entry.loaded
          ? [`Pet: ${name} (${id}), ${cur.isHidden ? 'hidden' : `animation ${resolveAnimation(entry.loaded.catalog, cur.name)}`}`]
          : [`Pet: ${id} is not loadable: ${entry.error}`]
        lines.push(`Installed in ${root ?? 'no folder'}: ${installed.length ? installed.join(', ') : 'none'}`)
        return { text: lines.join('\n') }
      }
      case 'use': {
        const want = arg.trim()
        if (!want) return { text: 'Usage: /pet use <id>' }
        const target = await getPet($, want, at)
        if (!target.loaded) return { text: `Cannot use "${want}": ${target.error}` }
        await $.store.set('pet', want)
        await update($, selectionAtom, () => want)
        await act($, { type: 'show' })
        if ((await $.ui.panes()).some(p => p.id === PANE)) await $.ui.open({ id: PANE, title: target.loaded.def.displayName })
        return { text: `Now using ${target.loaded.def.displayName} (${want}).` }
      }
      case 'pat':
        await act($, { type: 'shot', name: 'petted', source: 'main' })
        return { text: `You pat ${name}.` }
      case 'hide':
        await act($, { type: 'hide' })
        return { text: `${name} ducks out of sight.` }
      case 'show':
        await act($, { type: 'show' })
        return { text: `${name} pops out.` }
      case 'open':
        await $.ui.open({ id: PANE, title: name })
        return { text: 'Pet pane opened.' }
      case 'close':
        await $.ui.close({ id: PANE })
        return { text: 'Pet pane closed.' }
      default:
        return { text: 'Usage: /pet [status|use <id>|pat|hide|show|open|close]' }
    }
  })

  // --- the pane ---
  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const ui = $.ui.resolve(e)
    const { Box, Text, Button } = ui
    const at = await $.clock.now()
    const columns = e.props.bodyColumns || 40
    // About 8 CSS px per column; the pet never draws wider than the pane.
    const size = Math.max(24, Math.min(opts.size, columns * 8 - 8))
    const view = await viewOf($, at, size)
    const pat = <Button key="pat" label="pat" plain onPress={() => void act($, { type: 'shot', name: 'petted', source: 'main' })} />

    if (view.kind === 'missing') {
      return (
        <Box flexDirection="column">
          <Text dimColor>{view.reason}</Text>
          <Text dimColor>Put a pet package in ~/.claude/pets/&lt;id&gt;/ and run /pet use &lt;id&gt;.</Text>
        </Box>
      )
    }
    const d = view.drawn
    if (d.isHidden) {
      return (
        <Box flexDirection="column">
          <Text dimColor>{d.displayName} is out of sight. /pet show brings it back.</Text>
        </Box>
      )
    }
    if ('Svg' in ui) {
      const { Svg } = ui
      return (
        <Box flexDirection="column" alignItems="flex-start">
          <Svg source={d.svg} alt={`${d.displayName}: ${d.animation}`} width={d.width} height={d.height} />
          <Text dimColor>
            {d.displayName} · {d.animation}
          </Text>
          {pat}
        </Box>
      )
    }
    // The terminal has an Image element, but it takes a whole PNG and the mod cannot crop a
    // frame out of a strip, so the terminal gets a line of text.
    return (
      <Box flexDirection="column">
        <Text>
          {d.displayName} · {d.animation}
        </Text>
        {pat}
      </Box>
    )
  })
}
