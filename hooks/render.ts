// Builds the pet's SVG fragment: a nested <svg> that shows one cell of an animation strip,
// animated by CSS keyframes (docs/pet-format-v3.md, "Drawing"). Pure: no `$`.

/** The desktop `Svg` element's source limit, in characters. */
export const SVG_LIMIT = 131_072

export type FragmentInput = {
  petId: string
  /** The animation being drawn (already resolved against the pet's fallbacks). */
  animation: string
  /** Frames in the strip; for a pose strip (look) the number of cells. */
  frames: number
  /** One duration in ms per frame; ignored for a pose. */
  durations: number[]
  /** A state (repeats) or a one-shot (plays once and holds its last frame). */
  loop: boolean
  /** Draw this single cell instead of animating (the `look` pose). */
  pose?: number
  cell: { width: number; height: number }
  /** Fit inside size x size pixels. */
  size: number
  startedAt: number
  now: number
  /** The strip PNG, base64. */
  png: string
}

export type Fragment = { svg: string; width: number; height: number }

const round2 = (n: number): number => Math.round(n * 100) / 100

/** The size the cell is drawn at: as large as fits in size x size, aspect ratio kept. */
export function fitSize(cell: { width: number; height: number }, size: number): { width: number; height: number } {
  const scale = size / Math.max(cell.width, cell.height)
  return { width: round2(cell.width * scale), height: round2(cell.height * scale) }
}

const slug = (s: string): string => s.toLowerCase().replace(/[^a-z0-9-]+/g, '-')

/** The class (and keyframes) name, unique to pet + animation (+ pose cell). */
export const classOf = (petId: string, animation: string, pose?: number): string =>
  `pet-${slug(petId)}-${slug(animation)}${pose === undefined ? '' : `-${pose}`}`

/** Keyframe stops: the percentage at which each frame starts, from cumulative durations. */
export function frameStops(durations: number[]): { total: number; stops: number[] } {
  const total = durations.reduce((a, b) => a + b, 0)
  let acc = 0
  const stops = durations.map(d => {
    const p = total > 0 ? Math.round((acc / total) * 1e4) / 1e2 : 0
    acc += d
    return p
  })
  return { total, stops }
}

/** Negative animation delay in ms: the playhead's position, so a redraw stays in phase. */
export function phaseDelay(elapsed: number, total: number, loop: boolean): number {
  const e = Math.max(0, Math.floor(elapsed))
  if (total <= 0) return 0
  return loop ? e % total : Math.min(e, total)
}

/**
 * The fragment `<svg x="0" y="0" width=".." height="..">` for one animation, or a still cell
 * for a pose. The strip is embedded as a data URI, cropped to a cell by the nested viewport,
 * nearest-neighbour, stepped (steps(1)) at the spec's per-frame durations.
 */
export function renderFragment(i: FragmentInput): Fragment {
  const { cell } = i
  const { width, height } = fitSize(cell, i.size)
  const cls = classOf(i.petId, i.animation, i.pose)
  const stripW = cell.width * i.frames
  const x = (frame: number): string => `translateX(${-frame * cell.width}px)`
  let css = `.${cls}{image-rendering:pixelated;image-rendering:crisp-edges;shape-rendering:crispEdges}`
  let style = ''
  if (i.pose !== undefined) {
    style = ` style="transform:${x(i.pose)}"`
  } else if (i.frames > 1) {
    const { total, stops } = frameStops(i.durations)
    const frames = stops.map((p, n) => `${p}%{transform:${x(n)}}`).join('')
    css +=
      `@keyframes ${cls}{${frames}100%{transform:${x(i.frames - 1)}}}` +
      `.${cls}{animation:${cls} ${total}ms steps(1,end) ${i.loop ? 'infinite' : '1 forwards'}}` +
      // Reduced motion: the first frame only.
      `@media (prefers-reduced-motion: reduce){.${cls}{animation:none;transform:translateX(0px)}}`
    style = ` style="animation-delay:-${phaseDelay(i.now - i.startedAt, total, i.loop)}ms"`
  }
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" x="0" y="0" width="${width}" height="${height}" viewBox="0 0 ${cell.width} ${cell.height}">` +
    `<style>${css}</style>` +
    `<g class="${cls}"${style}>` +
    `<image href="data:image/png;base64,${i.png}" x="0" y="0" width="${stripW}" height="${cell.height}" preserveAspectRatio="none" style="image-rendering:pixelated;image-rendering:crisp-edges" shape-rendering="crispEdges"/>` +
    `</g></svg>`
  return { svg, width, height }
}
