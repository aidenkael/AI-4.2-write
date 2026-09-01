import { createHash } from 'node:crypto'
import { readdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const defaultUiDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const defaultAppDir = resolve(defaultUiDir, '..')
const defaultRepoDir = resolve(defaultAppDir, '..')

async function filesIn(directory, suffixes) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = await Promise.all(entries.map(async (entry) => {
    const full = resolve(directory, entry.name)
    if (entry.isDirectory()) return entry.name.startsWith('.') || entry.name === '__pycache__' ? [] : filesIn(full, suffixes)
    return suffixes.some((suffix) => entry.name.endsWith(suffix)) ? [full] : []
  }))
  return files.flat()
}

function pathKey(file, repoDir) {
  return relative(repoDir, file).split(sep).join('/').toLowerCase()
}

async function digest(files, repoDir) {
  const hash = createHash('sha256')
  const displayPath = (file) => relative(repoDir, file).split(sep).join('/')
  for (const file of [...files].sort((left, right) => {
    const a = pathKey(left, repoDir)
    const b = pathKey(right, repoDir)
    return a < b ? -1 : a > b ? 1 : 0
  })) {
    hash.update(displayPath(file))
    hash.update('\0')
    hash.update(await readFile(file))
    hash.update('\0')
  }
  return hash.digest('hex')
}

function isExcluded(file) {
  return file.split(sep).some((part) => [
    '.git', '.pytest_cache', '.mypy_cache', '.ruff_cache', '__pycache__',
    '.test-build', 'dist', 'node_modules',
  ].includes(part))
}

async function productionBackendPython(directory) {
  const files = await filesIn(directory, ['.py'])
  return files.filter((file) => {
    const name = file.split(sep).pop()
    return !isExcluded(file) && file.split(sep).includes('tests') === false
      && name !== 'conftest.py' && !name.startsWith('test_') && !name.endsWith('_test.py')
  })
}

export async function createRuntimeManifest({ uiDir = defaultUiDir, appDir = defaultAppDir, repoDir = defaultRepoDir } = {}) {
  const uiFiles = [
    ...(await filesIn(resolve(uiDir, 'src'), ['.ts', '.tsx', '.css'])).filter((file) => !isExcluded(file)),
    resolve(uiDir, 'index.html'), resolve(uiDir, 'package.json'), resolve(uiDir, 'package-lock.json'),
    resolve(uiDir, 'vite.config.ts'), resolve(uiDir, 'scripts', 'write-runtime-manifest.mjs'),
    ...(await readdir(uiDir, { withFileTypes: true })).filter((entry) => (
      entry.isFile() && /^tsconfig.*\.json$/.test(entry.name) && entry.name !== 'tsconfig.tests.json'
    ))
      .map((entry) => resolve(uiDir, entry.name)),
  ]
  const desktopFiles = (await readdir(resolve(appDir, 'desktop'), { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith('.py'))
    .filter((entry) => entry.name !== 'conftest.py' && !entry.name.startsWith('test_') && !entry.name.endsWith('_test.py'))
    .map((entry) => resolve(appDir, 'desktop', entry.name))
  const backendFiles = [
    ...(await productionBackendPython(resolve(appDir, 'backend'))),
    ...desktopFiles,
  ]
  return {
    schema_version: 'gowrite_runtime_manifest/v1',
    ui_source_sha256: await digest(uiFiles, repoDir),
    backend_source_sha256: await digest(backendFiles, repoDir),
  }
}

export async function writeRuntimeManifest(options = {}) {
  const uiDir = options.uiDir ?? defaultUiDir
  const manifest = await createRuntimeManifest(options)
  await writeFile(resolve(uiDir, 'dist', 'gowrite-runtime.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
  return manifest
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await writeRuntimeManifest()
}
