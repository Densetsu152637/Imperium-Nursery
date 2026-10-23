import { expect, test } from 'claude-code/testing'

import { TINY_CELL, TINY_STRIPS } from './fixtures/tiny'
import { standardCatalog } from './pet'
import { pngSize } from './png'
import { classOf, fitSize, frameStops, phaseDelay, renderFragment } from './render'

const idle = standardCatalog().idle!
const base = {
  petId: 'tiny',
  animation: 'idle',
  frames: idle.frames,
  durations: idle.durations,
  loop: true,
  cell: TINY_CELL,
  size: 96,
  startedAt: 1000,
  now: 3500,
  png: TINY_STRIPS.idle!,
}

test('keyframe percentages follow the per-frame durations', () => {
  const { total, stops } = frameStops(idle.durations)
  expect(total).toBe(1100)
  // Frames start at 0, 280, 390, 500, 640, 780 of 1100 ms.
  expect(stops).toEqual([0, 25.45, 35.45, 45.45, 58.18, 70.91])
  const { svg } = renderFragment(base)
  expect(svg).toContain('@keyframes pet-tiny-idle{0%{transform:translateX(0px)}25.45%{transform:translateX(-16px)}35.45%{transform:translateX(-32px)}')
  expect(svg).toContain('70.91%{transform:translateX(-80px)}100%{transform:translateX(-80px)}}')
  expect(svg).toContain('animation:pet-tiny-idle 1100ms steps(1,end) infinite')
})

test('the negative delay is the playhead, so a redraw stays in phase', () => {
  expect(phaseDelay(2500, 1100, true)).toBe(300)
  expect(phaseDelay(-5, 1100, true)).toBe(0)
  expect(phaseDelay(5000, 1000, false)).toBe(1000)
  expect(renderFragment(base).svg).toContain('style="animation-delay:-300ms"')
  // A redraw a second later is the same animation, 1000 ms further on.
  expect(renderFragment({ ...base, now: 4500 }).svg).toContain('animation-delay:-200ms')
  // One cycle later it is in the same phase.
  expect(renderFragment({ ...base, now: 3500 + 1100 }).svg).toContain('animation-delay:-300ms')
})

test('a one-shot plays once and holds its last frame', () => {
  const j = standardCatalog().jumping!
  const once = { ...base, animation: 'jumping', frames: j.frames, durations: j.durations, loop: false, png: TINY_STRIPS.jumping! }
  const f = renderFragment({ ...once, now: 1500 })
  expect(f.svg).toContain('840ms steps(1,end) 1 forwards')
  expect(f.svg).toContain('animation-delay:-500ms')
  expect(f.svg).not.toContain('infinite')
  expect(renderFragment({ ...once, now: 99_999 }).svg).toContain('animation-delay:-840ms')
})

test('reduced motion shows the first frame', () => {
  expect(renderFragment(base).svg).toContain('@media (prefers-reduced-motion: reduce){.pet-tiny-idle{animation:none;transform:translateX(0px)}}')
})

test('the look pose shows a single direction cell with no animation', () => {
  const f = renderFragment({ ...base, animation: 'look', frames: 16, durations: [], loop: false, pose: 8, png: TINY_STRIPS.look! })
  expect(f.svg).toContain('style="transform:translateX(-128px)"')
  expect(f.svg).not.toContain('@keyframes')
  expect(f.svg).toContain('width="256"')
})

test('size fit keeps the aspect ratio inside size x size', () => {
  expect(fitSize({ width: 16, height: 16 }, 96)).toEqual({ width: 96, height: 96 })
  expect(fitSize({ width: 64, height: 32 }, 96)).toEqual({ width: 96, height: 48 })
  expect(fitSize({ width: 32, height: 64 }, 48)).toEqual({ width: 24, height: 48 })
  const f = renderFragment({ ...base, cell: { width: 32, height: 16 }, size: 64 })
  expect([f.width, f.height]).toEqual([64, 32])
  expect(f.svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg" x="0" y="0" width="64" height="32" viewBox="0 0 32 16">')).toBe(true)
})

test('the strip is embedded nearest-neighbour with a class unique to pet and animation', () => {
  const f = renderFragment(base)
  expect(f.svg).toContain(`href="data:image/png;base64,${TINY_STRIPS.idle}"`)
  expect(f.svg).toContain('image-rendering:pixelated')
  expect(f.svg).toContain('shape-rendering="crispEdges"')
  expect(f.svg).toContain('width="96" height="16"')
  expect(classOf('tiny', 'idle')).not.toBe(classOf('tiny', 'working'))
  expect(classOf('tiny', 'idle')).not.toBe(classOf('other', 'idle'))
  expect(classOf('My Pet!', 'pop-out')).toBe('pet-my-pet--pop-out')
  expect(f.svg.length).toBeLessThan(131_072)
})

test('the fixture strips are real PNGs of the right size', () => {
  expect(pngSize(TINY_STRIPS.idle!)).toEqual({ width: 96, height: 16 })
  expect(pngSize(TINY_STRIPS.look!)).toEqual({ width: 256, height: 16 })
  expect(pngSize('AAAA')).toBeNull()
})
