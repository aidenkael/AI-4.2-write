import { createHash } from 'node:crypto'
import { readdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const uiDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const appDir = resolve(uiDir, '..')
const repoDir = resolve(appDir, '..')

async function filesIn(directory, suffixes) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = await Promise.all(entries.map(async (entry) => {
    const full = resolve(directory, entry.name)
    if (entry.isDirectory()) return entry.name.startsWith('.') || entry.name === '__pycache__' ? [] : filesIn(full, suffixes)
    return suffixes.some((suffix) => entry.name.endsWith(suffix)) ? [full] : []
  }))
  return files.flat()
}

async function digest(files) {
  const hash = createHash('sha256')
  const displayPath = (file) => relative(repoDir, file).split(sep).join('/')
  for (const file of [...files].sort((left, right) => {
    const a = displayPath(left).toLowerCase()
    const b = displayPath(right).toLowerCase()
    return a < b ? -1 : a > b ? 1 : 0
  })) {
    hash.update(displayPath(file))
    hash.update('\0')
    hash.update(await readFile(file))
    hash.update('\0')
  }
  return hash.digest('hex')
}

const uiFiles = [
  ...await filesIn(resolve(uiDir, 'src'), ['.ts', '.tsx', '.css']),
  resolve(uiDir, 'index.html'), resolve(uiDir, 'package.json'), resolve(uiDir, 'vite.config.ts'),
]
const backendFiles = [
  ...await filesIn(resolve(appDir, 'backend'), ['.py']),
  resolve(appDir, 'desktop', 'main.py'),
]
const manifest = {
  schema_version: 'gowrite_runtime_manifest/v1',
  ui_source_sha256: await digest(uiFiles),
  backend_source_sha256: await digest(backendFiles),
}
await writeFile(resolve(uiDir, 'dist', 'gowrite-runtime.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
