// PWA用アイコンを生成する。外部ライブラリを使わず、PNGを直接書き出す。
//   node scripts/generate-icons.mjs
import { deflateSync } from 'node:zlib'
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'public')
mkdirSync(OUT, { recursive: true })

const BG = [15, 16, 14] // ink-950
const FG = [219, 183, 101] // amber-300

function crc32(buf) {
  let c
  const table = []
  for (let n = 0; n < 256; n++) {
    c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[n] = c >>> 0
  }
  let crc = 0xffffffff
  for (const b of buf) crc = table[(crc ^ b) & 0xff] ^ (crc >>> 8)
  return (crc ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body))
  return Buffer.concat([len, body, crc])
}

function encodePng(size, pixels) {
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // RGBA
  const raw = Buffer.alloc((size * 4 + 1) * size)
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0 // filter: none
    pixels.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4)
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

/** 角を丸めた縦長の柱（＝スキットル）までの符号付き距離 */
function pinDistance(x, y, s) {
  const cx = s * 0.5
  const top = s * 0.28
  const bottom = s * 0.74
  const halfW = s * 0.085
  const r = halfW
  const dx = Math.abs(x - cx) - (halfW - r)
  const dy = Math.max(top + r - y, y - (bottom - r), 0)
  return Math.hypot(Math.max(dx, 0), dy) - r
}

function render(size) {
  const px = Buffer.alloc(size * size * 4)
  const cx = size / 2
  const cy = size / 2
  const ringR = size * 0.36
  const ringW = size * 0.022

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4
      let [r, g, b] = BG

      // 丸窓
      const d = Math.abs(Math.hypot(x + 0.5 - cx, y + 0.5 - cy) - ringR) - ringW
      const ringA = Math.min(Math.max(0.5 - d, 0), 1) * 0.55
      // スキットル
      const pd = pinDistance(x + 0.5, y + 0.5, size)
      const pinA = Math.min(Math.max(0.5 - pd, 0), 1)

      const a = Math.max(ringA, pinA)
      r = Math.round(r + (FG[0] - r) * a)
      g = Math.round(g + (FG[1] - g) * a)
      b = Math.round(b + (FG[2] - b) * a)

      px[i] = r
      px[i + 1] = g
      px[i + 2] = b
      px[i + 3] = 255
    }
  }
  return encodePng(size, px)
}

for (const [name, size] of [
  ['pwa-192x192.png', 192],
  ['pwa-512x512.png', 512],
  ['apple-touch-icon.png', 180],
]) {
  writeFileSync(join(OUT, name), render(size))
  console.log('wrote', name)
}

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#0f100e"/>
  <circle cx="256" cy="256" r="184" fill="none" stroke="#dbb765" stroke-opacity=".55" stroke-width="11"/>
  <rect x="212" y="143" width="88" height="235" rx="44" fill="#dbb765"/>
</svg>
`
writeFileSync(join(OUT, 'favicon.svg'), svg)
console.log('wrote favicon.svg')
