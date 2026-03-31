/**
 * npm init hook — brain.ctx auto-detection
 * ==========================================
 * This script runs automatically after `npm install brain-ctx`.
 * It detects if a brain.ctx exists in the project and prints
 * a helpful message, or suggests running brain-ctx init.
 *
 * Called via package.json "postinstall" script.
 * Keeps it fast (<200ms), silent on CI, never errors.
 */

import fs   from "fs"
import path from "path"

const TIMEOUT_MS = 150  // never slow down npm install
const IS_CI      = process.env.CI || process.env.CONTINUOUS_INTEGRATION

async function run() {
  // Never run on CI — speeds up CI and avoids noise
  if (IS_CI) return

  // Find project root (where brain-ctx was installed)
  const projectRoot = findProjectRoot()
  if (!projectRoot) return

  const ctxPath = path.join(projectRoot, "brain.ctx")

  if (fs.existsSync(ctxPath)) {
    // brain.ctx already exists — validate it silently
    try {
      const { BrainCtx } = await import("../core.js")
      const ctx   = BrainCtx.load(ctxPath)
      const score = ctx.aiScore()
      console.log(`\n  🧠 brain.ctx detected — ${score.raw}\n`)
    } catch {
      // Invalid brain.ctx — suggest fixing
      console.log("\n  ⚠️  brain.ctx found but has errors. Run: npx brain-ctx validate\n")
    }
  } else {
    // No brain.ctx — suggest generating one
    console.log(
      "\n  💡 brain-ctx installed!\n" +
      "  Generate a brain.ctx for this project:\n\n" +
      "    pip install brain-ctx && brain-ctx init\n\n" +
      "  Or use the Node API:\n" +
      "    import { BrainCtx } from 'brain-ctx'\n\n"
    )
  }
}

function findProjectRoot(): string | null {
  // Walk up from node_modules/brain-ctx to the actual project root
  let current = process.cwd()
  while (true) {
    if (fs.existsSync(path.join(current, "package.json"))) {
      // Check it's not inside node_modules (that would be our own package.json)
      if (!current.includes("node_modules")) {
        return current
      }
    }
    const parent = path.dirname(current)
    if (parent === current) return null
    current = parent
  }
}

// Run with timeout guard — never slow down npm install
Promise.race([
  run(),
  new Promise(resolve => setTimeout(resolve, TIMEOUT_MS)),
]).catch(() => {
  // Silently ignore all errors — postinstall must never fail
})
