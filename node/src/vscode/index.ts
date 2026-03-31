/**
 * brain.ctx VS Code Extension Helper
 * ====================================
 * Utilities for VS Code extensions and IDE integrations.
 *
 * Provides:
 *   - Auto-detection of brain.ctx in workspace
 *   - Context injection for AI features
 *   - Status bar AI Score display
 *   - Violation detection and inline warnings
 *
 * Usage in a VS Code extension:
 *
 *   import { BrainCtxVsCode } from "brain-ctx/vscode"
 *
 *   export function activate(context: vscode.ExtensionContext) {
 *     const brainCtx = new BrainCtxVsCode()
 *     brainCtx.activate(context)
 *   }
 */

import path from "path"
import * as fs from "fs"

import { BrainCtx }                          from "../core.js"
import { findBrainCtxFile }                  from "../parser/index.js"
import { validateBrainCtx }                  from "../validator/index.js"
import type { BrainCtxFile, ContextBuildOptions } from "../types/index.js"


// ── Workspace detection ─────────────────────────────────────────

/**
 * Detect brain.ctx in a workspace root.
 * Returns the BrainCtx instance if found.
 *
 * @example
 * const ctx = detectWorkspaceBrainCtx("/path/to/workspace")
 */
export function detectWorkspaceBrainCtx(
  workspaceRoot: string
): BrainCtx | null {
  const result = findBrainCtxFile(workspaceRoot)
  if (!result) return null
  return new BrainCtx(result.data)
}

/**
 * Watch a workspace for brain.ctx changes.
 * Calls the callback whenever brain.ctx is created, modified, or deleted.
 *
 * @example
 * const watcher = watchBrainCtx("/workspace", (ctx) => {
 *   injectIntoAiContext(ctx)
 * })
 * // Later: watcher.close()
 */
export function watchBrainCtx(
  workspaceRoot: string,
  onChange: (ctx: BrainCtx | null) => void
): { close: () => void } {
  const ctxPath = path.join(workspaceRoot, "brain.ctx")

  const notify = () => {
    if (fs.existsSync(ctxPath)) {
      try {
        onChange(BrainCtx.load(ctxPath))
      } catch {
        onChange(null)
      }
    } else {
      onChange(null)
    }
  }

  const watcher = fs.watch(workspaceRoot, { persistent: false }, (event, filename) => {
    if (filename === "brain.ctx") notify()
  })

  return { close: () => watcher.close() }
}


// ── Context injection ───────────────────────────────────────────

/**
 * Build a context string for injection into VS Code AI features.
 * Returns null if no brain.ctx is found.
 *
 * @example
 * const context = buildWorkspaceContext("/workspace", { model: "claude" })
 * // Inject into Copilot / Continue / other AI extension
 */
export function buildWorkspaceContext(
  workspaceRoot: string,
  options: ContextBuildOptions = {}
): string | null {
  const ctx = detectWorkspaceBrainCtx(workspaceRoot)
  if (!ctx) return null
  return ctx.buildContext(options)
}


// ── AI Score status bar ─────────────────────────────────────────

/**
 * Get the AI Score text for a VS Code status bar item.
 *
 * @example
 * // In extension activate():
 * const statusBar = vscode.window.createStatusBarItem()
 * statusBar.text = getStatusBarText(workspaceRoot) ?? "$(circle-slash) No brain.ctx"
 * statusBar.show()
 */
export function getStatusBarText(workspaceRoot: string): string | null {
  const ctx = detectWorkspaceBrainCtx(workspaceRoot)
  if (!ctx) return null
  const score = ctx.aiScore()
  return `$(brain) ${score.projectName} | ${score.invariants} rules | ${score.signed ? "✓" : "⚠"}`
}

/**
 * Get tooltip text for the status bar item.
 */
export function getStatusBarTooltip(workspaceRoot: string): string | null {
  const ctx = detectWorkspaceBrainCtx(workspaceRoot)
  if (!ctx) return null
  return ctx.aiScore().raw
}


// ── Violation detection ─────────────────────────────────────────

export interface Violation {
  rule:     string
  severity: "error" | "warning"
  message:  string
  file?:    string
  line?:    number
}

/**
 * Check if a proposed file write would violate any brain.ctx rules.
 * Returns list of violations (empty = OK to proceed).
 *
 * @example
 * const violations = checkWriteViolations(ctx, "src/wal.rs", "implementor")
 * if (violations.length > 0) showWarning(violations[0].message)
 */
export function checkWriteViolations(
  ctx:      BrainCtx,
  filePath: string,
  role:     string = "implementor"
): Violation[] {
  const violations: Violation[] = []

  // Check never_touch
  const trust = ctx.raw.trust
  if (trust?.never_touch) {
    for (const pattern of trust.never_touch) {
      if (matchesGlob(filePath, pattern)) {
        violations.push({
          rule:     `trust.never_touch: ${pattern}`,
          severity: "error",
          message:  `brain.ctx: File '${filePath}' matches never_touch pattern '${pattern}'. This file must never be modified.`,
          file:     filePath,
        })
      }
    }
  }

  // Check mutex_files
  if (trust?.mutex_files) {
    for (const pattern of trust.mutex_files) {
      if (matchesGlob(filePath, pattern)) {
        violations.push({
          rule:     `trust.mutex_files: ${pattern}`,
          severity: "warning",
          message:  `brain.ctx: File '${filePath}' is a mutex file. Requires human approval before modification.`,
          file:     filePath,
        })
      }
    }
  }

  // Check agent permissions
  if (!ctx.isAllowed(role, "write", filePath)) {
    violations.push({
      rule:     `trust.agents.${role}`,
      severity: "error",
      message:  `brain.ctx: Role '${role}' is not permitted to write to '${filePath}'.`,
      file:     filePath,
    })
  }

  return violations
}

/**
 * Validate a brain.ctx file and return diagnostics for VS Code.
 *
 * @example
 * const diags = getBrainCtxDiagnostics("/workspace/brain.ctx")
 * // Use with vscode.languages.createDiagnosticCollection
 */
export function getBrainCtxDiagnostics(
  ctxFilePath: string
): Array<{ line: number; message: string; severity: "error" | "warning" }> {
  if (!fs.existsSync(ctxFilePath)) return []

  try {
    const content = fs.readFileSync(ctxFilePath, "utf-8")
    const yaml    = require("js-yaml")
    const data    = yaml.load(content)
    const result  = validateBrainCtx(data)

    if (result.valid) return []

    return result.errors.map((msg, i) => ({
      line:     0,   // Schema errors don't have line numbers — show at top
      message:  msg,
      severity: "error" as const,
    }))
  } catch (e) {
    return [{ line: 0, message: `Parse error: ${(e as Error).message}`, severity: "error" }]
  }
}


// ── Cursor / Continue / other AI IDE integration ───────────────

/**
 * Generate a .cursorrules file content from brain.ctx.
 * Cursor reads .cursorrules as project-level AI instructions.
 *
 * @example
 * const rules = generateCursorRules(ctx)
 * fs.writeFileSync(".cursorrules", rules)
 */
export function generateCursorRules(ctx: BrainCtx): string {
  return ctx.buildContext({ model: "claude", tokenBudget: 4000 })
}

/**
 * Generate a GitHub Copilot instructions file from brain.ctx.
 * .github/copilot-instructions.md is the official Copilot instructions path.
 */
export function generateCopilotInstructions(ctx: BrainCtx): string {
  return ctx.buildContext({ model: "gpt4", tokenBudget: 4000 })
}

/**
 * Write bridge files for popular AI IDE tools.
 * Creates: .cursorrules, .github/copilot-instructions.md
 * These auto-update when brain.ctx changes.
 *
 * @example
 * syncAiToolBridges(ctx, "/workspace")
 */
export function syncAiToolBridges(ctx: BrainCtx, workspaceRoot: string): string[] {
  const written: string[] = []

  const cursorPath = path.join(workspaceRoot, ".cursorrules")
  fs.writeFileSync(cursorPath, generateCursorRules(ctx), "utf-8")
  written.push(cursorPath)

  const ghDir = path.join(workspaceRoot, ".github")
  if (!fs.existsSync(ghDir)) fs.mkdirSync(ghDir, { recursive: true })
  const copilotPath = path.join(ghDir, "copilot-instructions.md")
  fs.writeFileSync(copilotPath, generateCopilotInstructions(ctx), "utf-8")
  written.push(copilotPath)

  return written
}


// ── Helper ─────────────────────────────────────────────────────

function matchesGlob(filePath: string, pattern: string): boolean {
  if (pattern.startsWith("*.")) return filePath.endsWith(pattern.slice(1))
  if (pattern.endsWith("*"))   return filePath.startsWith(pattern.slice(0, -1))
  return filePath === pattern || filePath.endsWith("/" + pattern)
}
