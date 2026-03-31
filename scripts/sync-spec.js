#!/usr/bin/env node
/**
 * sync-spec.js
 * ============
 * Copies spec/brain-ctx.schema.json into both libraries.
 * Run before every build and in CI.
 *
 * Usage:  node scripts/sync-spec.js
 */

import fs   from "fs"
import path from "path"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root      = path.resolve(__dirname, "..")

const SOURCE = path.join(root, "spec", "brain-ctx.schema.json")
const TARGETS = [
  path.join(root, "python", "brain_ctx", "spec", "brain-ctx.schema.json"),
  path.join(root, "node",   "src",        "spec", "brain-ctx.schema.json"),
]

if (!fs.existsSync(SOURCE)) {
  console.error(`ERROR: Source schema not found: ${SOURCE}`)
  process.exit(1)
}

const schema = fs.readFileSync(SOURCE, "utf-8")

// Validate it's valid JSON before copying
try {
  JSON.parse(schema)
} catch(e) {
  console.error(`ERROR: Source schema is not valid JSON: ${e.message}`)
  process.exit(1)
}

let synced = 0
for (const target of TARGETS) {
  fs.mkdirSync(path.dirname(target), { recursive: true })

  // Check if already up to date
  if (fs.existsSync(target) && fs.readFileSync(target, "utf-8") === schema) {
    console.log(`  ✓ Already up to date: ${path.relative(root, target)}`)
    continue
  }

  fs.writeFileSync(target, schema, "utf-8")
  console.log(`  ✓ Synced: ${path.relative(root, target)}`)
  synced++
}

if (synced > 0) {
  console.log(`\n  Schema synced to ${synced} target(s).`)
} else {
  console.log("\n  All targets already up to date.")
}
