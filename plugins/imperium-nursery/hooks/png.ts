// Just enough PNG to check a strip before it is drawn: the signature and the IHDR size.

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

/** Decodes the first `maxBytes` bytes of base64 text. */
export function decodeHead(b64: string, maxBytes: number): number[] {
  const out: number[] = []
  let acc = 0
  let bits = 0
  for (const ch of b64) {
    if (out.length >= maxBytes) break
    const v = B64.indexOf(ch)
    if (v < 0) continue
    acc = (acc << 6) | v
    bits += 6
    if (bits >= 8) {
      bits -= 8
      out.push((acc >> bits) & 0xff)
      acc &= (1 << bits) - 1
    }
  }
  return out
}

/** `{ width, height }` of a base64 PNG, or null when it is not one. */
export function pngSize(b64: string): { width: number; height: number } | null {
  const b = decodeHead(b64.slice(0, 48), 24)
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]
  if (b.length < 24 || sig.some((v, i) => b[i] !== v)) return null
  const u32 = (o: number): number => (((b[o] ?? 0) * 256 + (b[o + 1] ?? 0)) * 256 + (b[o + 2] ?? 0)) * 256 + (b[o + 3] ?? 0)
  return { width: u32(16), height: u32(20) }
}
