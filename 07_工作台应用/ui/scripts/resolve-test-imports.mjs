import { access, readdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const outputRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '.test-build')

async function filesIn(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = await Promise.all(entries.map(async (entry) => {
    const full = resolve(directory, entry.name)
    return entry.isDirectory() ? filesIn(full) : (entry.name.endsWith('.js') ? [full] : [])
  }))
  return files.flat()
}

async function exists(path) {
  try { await access(path); return true } catch { return false }
}

for (const file of await filesIn(outputRoot)) {
  const source = await readFile(file, 'utf8')
  const matches = [...source.matchAll(/(from\s+['"])(\.{1,2}\/[^'"?#]+)(['"])/g)]
  let output = source
  for (const match of matches) {
    const specifier = match[2]
    if (specifier.endsWith('.js') || !(await exists(resolve(dirname(file), `${specifier}.js`)))) continue
    output = output.replace(`${match[1]}${specifier}${match[3]}`, `${match[1]}${specifier}.js${match[3]}`)
  }
  if (output !== source) await writeFile(file, output, 'utf8')
}
