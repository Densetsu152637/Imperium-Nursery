import type { On } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'

import { TINY_PET_JSON, TINY_STRIPS } from './fixtures/tiny'

const PLUGIN = 'clawd-pets'
const NOW = Date.parse('2026-10-23T12:00:00Z')
const pane = { title: '', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} } as const

type World = { clock: ReturnType<typeof mock.clock>; opened: { id: string; title?: string }[]; closed: string[]; logs: string[]; stored: Record<string, unknown> }

// The engine resolves a path like /pets to the current drive; the fake folder ignores the drive and the slashes.
const norm = (p: string) => p.replace(/^[A-Za-z]:/, '').split(String.fromCharCode(92)).join('/')

const bytesOf = (b64: string) => Math.floor((b64.length * 3) / 4)

// The engine beneath the mod: a pets folder at /pets holding the tiny pet, in memory.
type Opts = {
  strips?: Record<string, string>
  sizes?: Record<string, number>
  withPet?: boolean
  stored?: Record<string, unknown>
  /** What the engine answers a tool call with. */
  tool?: (e: { command?: string }) => unknown | Promise<unknown>
  /** What the engine answers a compaction with. */
  compact?: () => Promise<unknown>
}

const world = (on: On, o: Opts = {}): World => {
  const clock = mock.clock(on, { now: NOW })
  mock.env(on, { CLAUDE_PETS_DIR: '/pets' })
  const strips = o.strips ?? TINY_STRIPS
  const w: World = { clock, opened: [], closed: [], logs: [], stored: { ...o.stored } }
  on('store.get', (_$, e) => ({ value: w.stored[e.key] }) as never)
  on('store.set', (_$, e) => {
    w.stored[e.key] = e.value
    return { value: undefined } as never
  })
  const withPet = o.withPet !== false
  on('fs.stat', (_$, e) => (withPet && norm(e.path) === '/pets/tiny/pet.json' ? { value: { kind: 'file', size: 100, mtimeMs: 5, isLink: false } } : { deny: 'ENOENT' }) as never)
  on('fs.read', (_$, e) => {
    const path = norm(e.path)
    if (path === '/pets/tiny/pet.json') return { value: TINY_PET_JSON } as never
    const m = /^\/pets\/tiny\/strips\/(.+)\.png$/.exec(path)
    const b64 = m ? strips[m[1]!] : undefined
    return (b64 ? { value: { base64: b64 } } : { deny: 'ENOENT' }) as never
  })
  on('fs.list', (_$, e) => {
    const path = norm(e.path)
    if (path === '/pets') return { value: [{ name: 'tiny', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }] } as never
    if (path === '/pets/tiny/strips' && withPet)
      return {
        value: Object.entries(strips).map(([n, b64]) => ({ name: `${n}.png`, kind: 'file', size: o.sizes?.[n] ?? bytesOf(b64), mtimeMs: 7, isLink: false })),
      } as never
    return { deny: 'ENOENT' } as never
  })
  on('command.register', (_$, e) => ({ value: { command: e.name } }))
  on('ui.open', (_$, e) => {
    w.opened.push({ id: e.id, title: e.title })
    return { value: { isPlaced: true } }
  })
  on('ui.close', (_$, e) => {
    w.closed.push(e.id)
    return { value: {} } as never
  })
  on('ui.panes', () => ({ value: w.opened.map(p => ({ id: p.id })) }) as never)
  on('ui.log', (_$, e) => {
    w.logs.push(String((e as { text?: string }).text ?? ''))
    return { value: {} } as never
  })
  on('session.start', async () => ({ cwd: '/repo' }) as never)
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }) as never)
  on('agent.spawn', (_$, e) => ({ model: 'claude-opus-5-5', agentId: `a-${e.tool_use_id}` }))
  if (o.tool) on('tool.call', (_$, e) => o.tool!(e as { command?: string }) as never)
  if (o.compact) on('session.compact', () => o.compact!() as never)
  return w
}

const start = async ($: Engine) => {
  await $.session.start({ source: 'startup', cwd: '/repo', surface: 'desktop', isInteractive: true } as never)
}

const draw = ($: Engine, surface: 'desktop' | 'terminal' | 'vscode' | 'mobile' = 'desktop') =>
  $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: 'pet', props: pane })

// The animation the desktop pane shows now, read off the class of the drawn fragment.
const shown = async ($: Engine): Promise<string> => {
  const ui = await draw($)
  const source = String((await ui.find({ type: 'Svg' }))?.props.source ?? '')
  await ui.unmount()
  return /<g class="pet-tiny-([a-z-]+?)(?:-\d+)?"/.exec(source)?.[1] ?? 'none'
}

const run = ($: Engine, args: string) =>
  $.command.run({ command: 'pet', args, origin: { kind: 'composer' }, presentation: { isFullscreen: true, columns: 80 } } as never)

const endTurn = ($: Engine, reason: 'answer' | 'error' | 'aborted' = 'answer') =>
  $.turn.complete({ turnId: 'm1', reason, answer: 'ok', durationMs: 1, isAborted: reason === 'aborted' } as never)

// A started session, its pop-out and waving over: the pet is idle.
const settled = async ($: Engine, on: On, o: Opts = {}) => {
  const w = world(on, o)
  await start($)
  await w.clock.advance(3000)
  return w
}

test('session start opens the pet pane titled with the pet, which pops out and waves', { options: { pet: 'tiny' } }, async ($, on) => {
  const w = world(on)
  await start($)
  expect(w.opened).toEqual([{ id: 'pet', title: 'Tiny' }])
  expect(await shown($)).toBe('pop-out')
  await w.clock.advance(700)
  expect(await shown($)).toBe('waving')
  await w.clock.advance(1500)
  expect(await shown($)).toBe('idle')
})

test('openAtStart off does not open the pane', { options: { pet: 'tiny', openAtStart: 'off' } }, async ($, on) => {
  const w = world(on)
  await start($)
  expect(w.opened).toEqual([])
})

test('the pane draws one Svg with the strip, reduced motion and a phase delay, on every Svg surface', { options: { pet: 'tiny', size: 64 } }, async ($, on) => {
  await settled($, on)
  for (const surface of ['desktop', 'vscode', 'mobile'] as const) {
    const ui = await draw($, surface)
    const svgs = await ui.findAll({ type: 'Svg' })
    expect(svgs).toHaveLength(1)
    const p = svgs[0]!.props
    const source = String(p.source)
    expect(source).toContain('data:image/png;base64,')
    expect(source).toContain('prefers-reduced-motion: reduce')
    expect(source).toMatch(/animation-delay:-\d+ms/)
    expect(source).toContain('width="64" height="64"')
    expect([p.width, p.height]).toEqual([64, 64])
    expect(source.length).toBeLessThan(131_072)
    await ui.unmount()
  }
})

test('the terminal draws a line of text, not an image', { options: { pet: 'tiny' } }, async ($, on) => {
  await settled($, on)
  const ui = await draw($, 'terminal')
  expect(await ui.find({ type: 'Text', text: /Tiny · idle/ })).toBeDefined()
  expect(await ui.findAll({ type: 'Image' })).toHaveLength(0)
  await ui.unmount()
})

test('a press on the pat button pets the pet; the Svg itself cannot be pressed', { options: { pet: 'tiny' } }, async ($, on) => {
  const w = await settled($, on)
  for (const surface of ['desktop', 'terminal'] as const) {
    const ui = await draw($, surface)
    await ui.press({ key: 'pat' })
    await ui.unmount()
    expect(await shown($)).toBe('petted')
    await w.clock.advance(3000)
  }
})

test('turn start works, a clean finish jumps, an error fails', { options: { pet: 'tiny' } }, async ($, on) => {
  const w = await settled($, on)
  await $.turn.start({ text: 'hi', turnId: 'm1' } as never)
  expect(await shown($)).toBe('working')
  await w.clock.advance(1000)
  await endTurn($)
  expect(await shown($)).toBe('jumping')
  await w.clock.advance(5000)
  expect(await shown($)).toBe('idle')
  await $.turn.start({ text: 'again', turnId: 'm1' } as never)
  await w.clock.advance(1000)
  await endTurn($, 'error')
  expect(await shown($)).toBe('failed')
  await w.clock.advance(5000)
  await $.turn.start({ text: 'again', turnId: 'm1' } as never)
  await w.clock.advance(1000)
  await endTurn($, 'aborted')
  await w.clock.advance(700)
  expect(await shown($)).toBe('idle')
})

test('tool results: errors fail, refusals confuse, commits and tests celebrate', { options: { pet: 'tiny' } }, async ($, on) => {
  const w = await settled($, on, {
    tool: e => {
      const cmd = e.command
      if (cmd === 'boom') return { isError: true, result: 'x', text: 'exit code 1' }
      if (cmd === 'no') return { isError: true, result: 'x', text: "The user doesn't want to proceed with this tool use." }
      if (cmd === 'deny') return { deny: 'blocked by policy' }
      if (cmd === 'bg') return { result: { stdout: '', stderr: '', interrupted: false, backgroundTaskId: 'b1' } }
      return { result: { stdout: 'ok', stderr: '', interrupted: false } }
    },
  })
  const after = async (command: string, expected: string, tool: 'Bash' | 'PowerShell' = 'Bash') => {
    await $.tool.call({ tool, command } as never)
    expect([command, await shown($)]).toEqual([command, expected])
    await w.clock.advance(5000)
  }
  await after('boom', 'failed')
  await after('no', 'confused')
  await after('deny', 'confused')
  await after('git commit -m x', 'celebrating')
  await after('gh pr merge 3', 'celebrating', 'PowerShell')
  await after('pytest -q', 'celebrating')
  await after('go test ./...', 'celebrating')
  await after('ls', 'idle')
  await after('bg', 'idle')
  await after('git status', 'idle')
})

test('AskUserQuestion holds waiting until it is answered', { options: { pet: 'tiny' } }, async ($, on) => {
  let release: () => void = () => {}
  const w = await settled($, on, {
    tool: async () => {
      await new Promise<void>(r => (release = r))
      return { result: {} }
    },
  })
  const pending = $.tool.call({ tool: 'AskUserQuestion', questions: [] } as never)
  await w.clock.settle()
  expect(await shown($)).toBe('waiting')
  release()
  await pending
  await w.clock.advance(1000)
  expect(await shown($)).toBe('idle')
})

test('a subagent: summoning, then a glance toward it, then its loop; reviewers use review', { options: { pet: 'tiny' } }, async ($, on) => {
  const w = await settled($, on)
  const spawn = (id: string, prompt: string) =>
    $.agent.spawn({ tool_use_id: id, prompt, description: 'task', subagentType: 'general-purpose', provider: { plugin: 'engine', tier: 'core' }, parentModel: 'm', background: false, fork: false } as never)
  await spawn('t1', 'Role: leaf; Profile: implementer')
  expect(await shown($)).toBe('summoning')
  await w.clock.advance(900)
  expect(await shown($)).toBe('look')
  await w.clock.advance(700)
  expect(await shown($)).toBe('working')
  // It finishes: the loop ends and a clean finish jumps.
  await $.turn.complete({ turnId: 's1', agentId: 'a-t1', reason: 'answer', answer: 'ok', durationMs: 1, isAborted: false } as never)
  await w.clock.advance(3000)
  expect(await shown($)).toBe('idle')
  await w.clock.advance(10_000)
  await spawn('t2', 'Role: leaf; Profile: critic')
  await w.clock.advance(2300)
  expect(await shown($)).toBe('review')
})

test('compaction shows eating while it runs', { options: { pet: 'tiny' } }, async ($, on) => {
  let release: () => void = () => {}
  const w = await settled($, on, {
    compact: async () => {
      await new Promise<void>(r => (release = r))
      return { messages: [{ role: 'user', text: 'summary', toolUses: [] }] }
    },
  })
  const pending = $.session.compact({ trigger: 'manual', messages: [{ role: 'user', text: 'hi', toolUses: [], handle: 'h1' }] } as never)
  await w.clock.settle()
  await w.clock.advance(700)
  expect(await shown($)).toBe('eating')
  release()
  await pending
  await w.clock.advance(700)
  expect(await shown($)).toBe('idle')
})

test('a strip over the size limit is not drawn: its fallback is', { options: { pet: 'tiny' } }, async ($, on) => {
  const w = world(on, { sizes: { working: 120_000 } })
  await start($)
  await w.clock.advance(3000)
  await $.turn.start({ text: 'hi', turnId: 'm1' } as never)
  expect(await shown($)).toBe('idle')
  expect(w.logs.some(l => /too large/.test(l))).toBe(true)
})

test('a strip of the wrong size is ignored', { options: { pet: 'tiny' } }, async ($, on) => {
  const w = world(on, { strips: { ...TINY_STRIPS, working: TINY_STRIPS.jumping! } })
  await start($)
  await w.clock.advance(3000)
  await $.turn.start({ text: 'hi', turnId: 'm1' } as never)
  expect(await shown($)).toBe('idle')
})

test('/pet: status, pat, hide, show, open, close', { options: { pet: 'tiny' } }, async ($, on) => {
  const w = await settled($, on)
  const status = await run($, '')
  expect(status.text).toContain('Pet: Tiny (tiny), animation idle')
  expect(status.text).toContain('Installed in /pets: tiny')
  expect((await run($, 'pat')).text).toContain('pat Tiny')
  expect(await shown($)).toBe('petted')
  await w.clock.advance(3000)
  await run($, 'hide')
  expect(await shown($)).toBe('duck-in')
  await w.clock.advance(1000)
  const ui = await draw($)
  expect(await ui.find({ type: 'Text', text: /out of sight/ })).toBeDefined()
  await ui.unmount()
  expect((await run($, '')).text).toContain('hidden')
  await run($, 'show')
  expect(await shown($)).toBe('pop-out')
  await run($, 'close')
  expect(w.closed).toEqual(['pet'])
  await run($, 'open')
  expect(w.opened.at(-1)).toEqual({ id: 'pet', title: 'Tiny' })
  expect((await run($, 'frobnicate')).text).toContain('Usage')
})

test('/pet use: an installed pet is chosen and remembered; an unknown one is refused', { options: { pet: 'other' } }, async ($, on) => {
  const w = world(on)
  await start($)
  // The configured pet is not installed: the pane says so.
  const ui = await draw($)
  expect(await ui.find({ type: 'Text', text: /no pet "other"/ })).toBeDefined()
  await ui.unmount()
  expect((await run($, 'use nope')).text).toContain('Cannot use "nope"')
  expect((await run($, 'use tiny')).text).toContain('Now using Tiny (tiny)')
  await w.clock.advance(3000)
  expect(await shown($)).toBe('idle')
  expect(w.stored.pet).toBe('tiny')
  expect((await run($, 'use')).text).toContain('Usage')
})

test('the pet is chosen from the store on a later session', { options: { pet: 'other' } }, async ($, on) => {
  const w = world(on, { stored: { pet: 'tiny' } })
  await start($)
  await w.clock.advance(3000)
  expect(await shown($)).toBe('idle')
})
