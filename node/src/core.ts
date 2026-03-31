/**
 * BrainCtx — Node.js / TypeScript implementation
 * The main class for reading, writing, and building context from brain.ctx files.
 */

import * as fs from "fs"
import * as path from "path"
import * as yaml from "js-yaml"

import type {
  BrainCtxFile, AiScore, ContextBuildOptions,
  TrustLevel
} from "./types/index.js"

export const FILENAME       = "brain.ctx"
export const SPEC_VERSION   = "1.0"

export class BrainCtx {
  private data: BrainCtxFile
  private sourcePath?: string

  constructor(data: Partial<BrainCtxFile> = {}) {
    this.data = {
      version:  SPEC_VERSION,
      identity: { name: "Unknown" },
      ...data,
    }
  }

  // ── Static factories ──────────────────────────────────────

  /**
   * Load a brain.ctx file from disk.
   *
   * @example
   * const ctx = BrainCtx.load("./brain.ctx")
   * console.log(ctx.name)  // "ManasDB"
   */
  static load(filePath: string = FILENAME): BrainCtx {
    if (!fs.existsSync(filePath)) {
      throw new Error(`brain.ctx not found at: ${filePath}`)
    }
    const raw  = fs.readFileSync(filePath, "utf-8")
    const data = yaml.load(raw) as BrainCtxFile
    const ctx  = new BrainCtx(data)
    ctx.sourcePath = path.resolve(filePath)
    return ctx
  }

  /**
   * Walk up directory tree to find nearest brain.ctx.
   * Works from any subdirectory — like git finding .git.
   *
   * @example
   * const ctx = BrainCtx.find()  // finds brain.ctx in any parent dir
   */
  static find(start: string = process.cwd()): BrainCtx | null {
    let current = path.resolve(start)
    while (true) {
      const candidate = path.join(current, FILENAME)
      if (fs.existsSync(candidate)) {
        return BrainCtx.load(candidate)
      }
      const parent = path.dirname(current)
      if (parent === current) return null
      current = parent
    }
  }

  /**
   * Create a minimal brain.ctx for a project.
   * For full auto-generation use the Python CLI: brain-ctx init
   *
   * @example
   * const ctx = BrainCtx.create({ name: "MyProject", vision: "Build great things" })
   */
  static create(identity: { name: string; vision?: string; domain?: string }): BrainCtx {
    return new BrainCtx({
      version:  SPEC_VERSION,
      identity,
      inference: { enabled: true, sources: ["codebase", "git", "tests", "dependencies"] },
      trust:     { default: "read_only" },
    })
  }

  // ── Accessors ──────────────────────────────────────────────

  get name():    string     { return this.data.identity.name }
  get version(): string     { return this.data.version }
  get trust():   TrustLevel { return this.data.trust?.default ?? "read_only" }
  get rules():   string[]   { return this.data.hard_rules ?? [] }
  get raw():     BrainCtxFile { return this.data }

  // ── Context building ───────────────────────────────────────

  /**
   * Build the AI context string optimized for a specific model.
   * Respects token budgets, cognitive priority tiers, and dialect instructions.
   *
   * @example
   * const context = ctx.buildContext({ model: "claude", tokenBudget: 12000 })
   * // Inject context into your AI API call
   */
  buildContext(options: ContextBuildOptions = {}): string {
    const { model = "claude", tokenBudget, mode } = options
    const budget = tokenBudget ?? this.data.cognitive?.token_budget?.[model] ?? 8000

    const sections: string[] = []

    // Always include critical sections
    sections.push(this._buildIdentitySection())
    sections.push(this._buildRulesSection())
    sections.push(this._buildTrustSection())

    // 1. Resolve Priorities by Mode
    const cog = this.data.cognitive
    let prioritizedKeys: string[] = []
    if (mode && cog?.modes?.[mode]) {
      prioritizedKeys = cog.modes[mode].prioritize
    }

    // 2. Add Verification Layer
    if (this.data.verification) {
      sections.push(this._buildVerificationSection())
    }

    // 3. Include prioritized/important sections if budget allows
    const important = cog?.important ?? []
    const keysToAdd = [...new Set([...prioritizedKeys, ...important])]

    keysToAdd.forEach(key => {
      if (budget > 4000) {
        if (key === "ethics" && this.data.ethics) sections.push(this._buildEthicsSection())
        if (key === "dialects" && this.data.dialects?.[model]) {
          sections.push(`\n## Model Instructions (${model})\n${this.data.dialects[model]}`)
        }
      }
    })

    // Include reference sections for large context models
    if (budget > 12000) {
      if (this.data.mesh) sections.push(this._buildMeshSection())
      if (cog?.reference?.includes("timeline")) sections.push(this._buildTimelineSection())
    }

    return sections.filter(Boolean).join("\n")
  }


  private _buildIdentitySection(): string {
    const { name, vision, domain } = this.data.identity
    const lines = [`## Project: ${name}`]
    if (vision) lines.push(`Vision: ${vision}`)
    if (domain) lines.push(`Domain: ${domain}`)
    return lines.join("\n")
  }

  private _buildRulesSection(): string {
    if (!this.data.hard_rules?.length) return ""
    const lines = ["\n## Hard Rules — Operational Invariants"]
    this.data.hard_rules.forEach(rule => lines.push(`- ${rule}`))
    lines.push("\nThese are absolute. Use ALWAYS/NEVER patterns. No exception. No workaround. If in doubt, stop and ask.")
    return lines.join("\n")
  }


  private _buildTrustSection(): string {
    const trust = this.data.trust
    if (!trust) return ""
    const lines = ["\n## Trust Configuration"]
    lines.push(`Default: ${trust.default ?? "read_only"}`)
    if (trust.never_touch?.length)
      lines.push(`Never touch: ${trust.never_touch.join(", ")}`)
    if (trust.mutex_files?.length)
      lines.push(`Mutex files: ${trust.mutex_files.join(", ")}`)
    return lines.join("\n")
  }

  private _buildEthicsSection(): string {
    const e = this.data.ethics
    if (!e) return ""
    const lines = ["\n## Ethics & Data Protection"]
    if (e.never_expose?.length)
      lines.push(`Never expose: ${e.never_expose.join(", ")}`)
    if (e.data_sovereignty)
      lines.push(`Data sovereignty: ${e.data_sovereignty}`)
    return lines.join("\n")
  }

  private _buildMeshSection(): string {
    const m = this.data.mesh
    if (!m?.imports?.length) return ""
    const lines = ["\n## Federated Imports"]
    m.imports.forEach(i => lines.push(`- ${i}`))
    return lines.join("\n")
  }

  private _buildVerificationSection(): string {
    const v = this.data.verification
    if (!v) return ""
    const lines = ["\n## Verification — The Execution Layer"]
    if (v.test_command)  lines.push(`Test command:  ${v.test_command}`)
    if (v.lint_command)  lines.push(`Lint command:  ${v.lint_command}`)
    if (v.build_command) lines.push(`Build command: ${v.build_command}`)
    
    const status = v.auto_verify ? "ENABLED (Auto-run after edits)" : "MANUAL (Run before proposing)"
    lines.push(`\nMode: ${status}`)
    lines.push("You ARE expected to prove your changes work by running these commands.")
    return lines.join("\n")
  }

  private _buildTimelineSection(): string {
    if (!this.data.timeline?.length) return ""
    const lines = ["\n## Project Timeline & Decisions"]
    this.data.timeline.slice(0, 10).forEach(e => {
      lines.push(`- [${e.date}] ${e.event}`)
      if (e.lesson) lines.push(`  Lesson: ${e.lesson}`)
    })
    return lines.join("\n")
  }


  // ── AI Score ───────────────────────────────────────────────

  /**
   * Generate the AI Score acknowledgment line.
   * This is what AI models output when they successfully absorb brain.ctx.
   *
   * @example
   * console.log(ctx.aiScore().raw)
   * // "✓ brain.ctx loaded — ManasDB v1.0 | Trust: read_only | 7 invariants active"
   */
  aiScore(): AiScore {
    const invariants = this.data.hard_rules?.length ?? 0
    const agents     = Object.keys(this.data.trust?.agents ?? {}).length
    const signed     = !!this.data.signature?.value
    const verified   = this.data.verification?.auto_verify ? "✓" : (this.data.verification ? "!" : "✗")

    const parts = [
      `✓ brain.ctx loaded — ${this.name} v${this.version}`,
      `Trust: ${this.trust}`,
      `${invariants} invariants active`,
    ]
    if (agents) parts.push(`${agents} agents registered`)
    parts.push(`Signed: ${signed ? "✓" : "✗"}`)
    parts.push(`Verified: ${verified}`)

    const raw = parts.join(" | ")


    return {
      raw,
      projectName: this.name,
      version:     this.version,
      trust:       this.trust,
      invariants,
      agents,
      signed,
    }
  }

  // ── Permission checking ────────────────────────────────────

  /**
   * Check if an agent with a given role is allowed to perform an action on a path.
   *
   * @example
   * const allowed = ctx.isAllowed("implementor", "write", "src/main.rs")
   */
  isAllowed(agentRole: string, action: string, filePath?: string): boolean {
    const trust = this.data.trust

    // Check never_touch first
    if (filePath && trust?.never_touch) {
      for (const pattern of trust.never_touch) {
        if (this._matchGlob(filePath, pattern)) return false
      }
    }

    // Check mutex_files (always requires approval)
    if (filePath && trust?.mutex_files) {
      for (const pattern of trust.mutex_files) {
        if (this._matchGlob(filePath, pattern)) return false
      }
    }

    // Check agent role
    const role = trust?.agents?.[agentRole]
    if (!role) {
      // Unknown role — apply default trust
      return trust?.default === "read_write" || action === "read"
    }

    if (role.cannot.includes(action)) return false
    if (role.can.includes(action) || role.can.includes("read_all")) return true

    return false
  }

  private _matchGlob(filePath: string, pattern: string): boolean {
    // Simple glob matching for common patterns
    if (pattern.startsWith("*.")) {
      return filePath.endsWith(pattern.slice(1))
    }
    if (pattern.endsWith("*")) {
      return filePath.startsWith(pattern.slice(0, -1))
    }
    return filePath === pattern || filePath.includes(pattern)
  }

  // ── Serialization ──────────────────────────────────────────

  /**
   * Serialize to YAML string.
   */
  toYaml(): string {
    return yaml.dump(this.data, { lineWidth: 100, sortKeys: false })
  }

  /**
   * Serialize to JSON string.
   */
  toJson(indent = 2): string {
    return JSON.stringify(this.data, null, indent)
  }

  /**
   * Save brain.ctx to disk.
   */
  save(filePath: string = FILENAME): void {
    fs.writeFileSync(filePath, this.toYaml(), "utf-8")
    this.sourcePath = path.resolve(filePath)
  }

  toString(): string {
    return `BrainCtx(name=${this.name}, version=${this.version})`
  }
}
