/**
 * 由 scripts/icon.svg 生成 PWA 图标
 *
 *   node scripts/make-icons.mjs
 *
 * 生成 public/icon-192x192.png 与 public/icon-512x512.png。
 * 改图标只需编辑 icon.svg 后重跑这个脚本 —— 不要直接改 PNG。
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import sharp from 'sharp'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const svg = readFileSync(join(here, 'icon.svg'))

const targets = [
  { size: 192, file: 'public/icon-192x192.png' },
  { size: 512, file: 'public/icon-512x512.png' },
]

for (const { size, file } of targets) {
  const out = join(root, file)
  // 先把 SVG 渲染成 512 再降采样，小尺寸的边缘会更干净
  await sharp(svg, { density: 384 })
    .resize(size, size, { fit: 'cover' })
    .png({ compressionLevel: 9 })
    .toFile(out)

  const kb = (readFileSync(out).length / 1024).toFixed(1)
  console.log(`  ✓ ${file}  ${size}×${size}  ${kb} KB`)
}
