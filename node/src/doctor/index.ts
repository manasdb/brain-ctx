/**
 * brain.ctx Doctor — Node.js implementation
 * Health checks for brain.ctx files.
 * Mirrors the Python DoctorRunner API.
 */

import * as fs   from "fs"
import * as path from "path"
import { BrainCtx } from "../core.js"
import type { BrainCtxFile } from "../types/index.js"

// ── Result types ───────────────────────────────────────────────

export type Severity = "OK" | "WARN" | "ERROR" | "INFO"

export interface CheckResult {
  check:    string
  severity: Severity
  message:  string
  fix?:     string
  detail?:  string
}

export interface DoctorReport {
  results:  CheckResult[]
  passed:   boolean
  errors:   CheckResult[]
  warnings: CheckResult[]
  okCount:  number
  summary:  string
}

// ── Doctor runner ──────────────────────────────────────────────

export class DoctorRunner {
  private ctx:        BrainCtx
  private projectRoot: string
  private results:    CheckResult[] = []

  constructor(ctx: BrainCtx, projectRoot: string = process.cwd()) {
    this.ctx         = ctx
    this.projectRoot = path.resolve(projectRoot)
  }

  run(): DoctorReport {
    this.results = []
    this._checkIdentity()
    this._checkHardRules()
    this._checkTruthSources()
    this._checkTrust()
    this._checkAgents()
    this._checkTokenBudget()
    this._checkInvariants()
    this._checkObservability()
    this._checkEthics()
    this._checkSignature()
    return this._buildReport()
  }

  // ── Checks ────────────────────────────────────────────────

  private _checkIdentity(): void {
    const i = this.ctx.raw.identity
    if (!i?.name) {
      this._add("identity.name", "ERROR", "Project name missing",
        "Add: identity:\n  name: YourProject")
    } else {
      this._add("identity.name", "OK", `Name: ${i.name}`)
    }

    if (!i?.vision) {
      this._add("identity.vision", "WARN", "No vision statement — AI has no project purpose",
        "Add: identity:\n  vision: 'What this project does'")
    } else if (i.vision.length < 15) {
      this._add("identity.vision", "WARN", `Vision too short (${i.vision.length} chars)`,
        "A good vision is 30-80 characters")
    } else {
      this._add("identity.vision", "OK", "Vision set")
    }
  }

  private _checkHardRules(): void {
    const rules = this.ctx.rules
    if (!rules.length) {
      this._add("hard_rules", "WARN", "No hard rules — AI has no absolute constraints",
        "Add at least 3 hard_rules covering critical invariants")
      return
    }
    if (rules.length < 3) {
      this._add("hard_rules.count", "WARN",
        `Only ${rules.length} rule(s) — consider adding more`,
        "Typical projects need 5-12 rules")
    } else {
      this._add("hard_rules.count", "OK", `${rules.length} hard rules defined`)
    }

    const vague = rules.filter(r =>
      /\b(be careful|be cautious|try to|if possible|generally|usually)\b/i.test(r)
    )
    if (vague.length) {
      this._add("hard_rules.precision", "WARN",
        `${vague.length} rule(s) contain vague language`,
        "Replace 'try to' / 'generally' with 'always' / 'never'",
        vague.map(r => r.slice(0, 60)).join("; "))
    } else {
      this._add("hard_rules.precision", "OK", "All rules use precise language")
    }
  }

  private _checkTruthSources(): void {
    const ts = this.ctx.raw.truth_sources
    if (!ts || !Object.keys(ts).length) {
      this._add("truth_sources", "WARN", "No truth_sources defined",
        "Add truth_sources with infer_from pointing to key source files")
      return
    }

    const missing: string[] = []
    const found:   string[] = []

    for (const [name, config] of Object.entries(ts)) {
      const infer = (config as Record<string, string>).infer_from || ""
      if (!infer) continue
      const paths = infer.split(",").map((p: string) => p.trim())
      const anyFound = paths.some((p: string) => {
        if (p.startsWith(".git") || p.includes("*")) return true
        return fs.existsSync(path.join(this.projectRoot, p))
      })
      if (anyFound) found.push(name)
      else missing.push(`${name} → ${infer}`)
    }

    if (missing.length) {
      this._add("truth_sources.paths", "ERROR",
        `${missing.length} truth_source(s) point to non-existent paths`,
        "Fix paths or run: brain-ctx init to regenerate",
        missing.join("\n"))
    } else {
      this._add("truth_sources.paths", "OK",
        `All ${found.length} truth_source paths valid`)
    }
  }

  private _checkTrust(): void {
    const trust = this.ctx.raw.trust
    if (!trust) {
      this._add("trust", "WARN", "No trust configuration",
        "Add trust: section with default, never_touch, mutex_files")
      return
    }

    const nt       = trust.never_touch ?? []
    const required = ["*.pid", "*.sock", "*.lock"]
    const missing  = required.filter(r => !nt.includes(r))
    if (missing.length) {
      this._add("trust.never_touch", "WARN",
        "Missing critical runtime file patterns in never_touch",
        `Add to trust.never_touch: ${missing.join(", ")}`)
    } else {
      this._add("trust.never_touch", "OK",
        `never_touch has ${nt.length} pattern(s) including runtime files`)
    }

    const mutex = trust.mutex_files ?? []
    if (!mutex.length) {
      this._add("trust.mutex_files", "WARN",
        "No mutex_files — critical files have no approval gate",
        "Add sensitive source files to trust.mutex_files")
    } else {
      this._add("trust.mutex_files", "OK", `${mutex.length} mutex file(s) configured`)
    }

    if (trust.default === "read_write") {
      this._add("trust.default", "WARN",
        "Default trust is read_write — agents can write anywhere",
        "Consider read_only with explicit write grants per role")
    } else {
      this._add("trust.default", "OK", `Default trust: ${trust.default ?? "read_only"}`)
    }
  }

  private _checkAgents(): void {
    const agents = this.ctx.raw.trust?.agents ?? {}
    if (!Object.keys(agents).length) {
      this._add("trust.agents", "WARN", "No agent roles defined",
        "Add architect, implementor, reviewer roles")
      return
    }
    this._add("trust.agents.count", "OK", `${Object.keys(agents).length} agent role(s)`)

    for (const [role, perms] of Object.entries(agents)) {
      const can    = new Set((perms as any).can    ?? [])
      const cannot = new Set((perms as any).cannot ?? [])
      const overlap = [...can].filter(x => cannot.has(x))
      if (overlap.length) {
        this._add(`trust.agents.${role}`, "ERROR",
          `Role '${role}' has contradictory permissions`,
          `Remove from either can or cannot: ${overlap.join(", ")}`)
      } else {
        this._add(`trust.agents.${role}`, "OK", `Role '${role}' has no contradictions`)
      }
    }
  }

  private _checkTokenBudget(): void {
    const budget = this.ctx.raw.cognitive?.token_budget
    if (!budget) {
      this._add("cognitive.token_budget", "WARN", "No token budgets defined",
        "Add cognitive:\n  token_budget:\n    claude: 12000\n    local: 2000")
      return
    }

    const issues: string[] = []
    const local  = (budget as any).local  ?? 0
    const claude = (budget as any).claude ?? 0
    if (local && claude && local > claude) {
      issues.push(`local (${local}) > claude (${claude}) — local models have smaller windows`)
    }
    for (const [model, tokens] of Object.entries(budget as Record<string,number>)) {
      if (typeof tokens !== "number" || tokens <= 0) issues.push(`${model}: invalid`)
      else if (tokens < 500) issues.push(`${model}: ${tokens} very low — may truncate rules`)
    }

    if (issues.length) {
      this._add("cognitive.token_budget", "WARN", `${issues.length} budget issue(s)`,
        "Review token budgets", issues.join("; "))
    } else {
      this._add("cognitive.token_budget", "OK",
        `Budgets valid for: ${Object.keys(budget).join(", ")}`)
    }
  }

  private _checkInvariants(): void {
    const inv = this.ctx.raw.truth_sources?.invariants
    if (!inv) {
      this._add("invariants", "WARN", "No invariants truth_source configured",
        "Add invariants: section pointing to tests/")
      return
    }

    // Check for actual test_invariant_* files
    const testDirs = ["tests", "test", "spec", "__tests__"]
    let found = 0
    for (const dir of testDirs) {
      const testPath = path.join(this.projectRoot, dir)
      if (!fs.existsSync(testPath)) continue
      found += this._countInvariantFiles(testPath)
    }

    if (found === 0) {
      this._add("invariants.files", "WARN",
        "No test_invariant_* files found — invariants declared but not tested",
        "Create tests/test_invariant_*.py (or .ts/.rs) to activate checking")
    } else {
      this._add("invariants.files", "OK", `${found} invariant test file(s) found`)
    }
  }

  private _countInvariantFiles(dir: string): number {
    let count = 0
    try {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.isDirectory()) {
          count += this._countInvariantFiles(path.join(dir, entry.name))
        } else if (entry.name.includes("invariant")) {
          count++
        }
      }
    } catch { /* ignore */ }
    return count
  }

  private _checkObservability(): void {
    const obs = this.ctx.raw.observability
    if (!obs?.enabled) {
      this._add("observability", "WARN", "Observability disabled — no AI audit trail",
        "Add observability:\n  enabled: true\n  log_file: .brain-ctx.log")
      return
    }
    this._add("observability.enabled", "OK", "Observability enabled")

    const logFile = path.join(this.projectRoot, obs.log_file ?? ".brain-ctx.log")
    if (fs.existsSync(logFile)) {
      const sizeMb = fs.statSync(logFile).size / (1024 * 1024)
      if (sizeMb > 100) {
        this._add("observability.log_size", "WARN",
          `Log is ${sizeMb.toFixed(1)}MB — consider rotating`,
          "Run: brain-ctx diff --rotate")
      } else {
        this._add("observability.log_size", "OK", `Log size: ${sizeMb.toFixed(2)}MB`)
      }
    } else {
      this._add("observability.log_file", "INFO", "Log not yet created")
    }
  }

  private _checkEthics(): void {
    const ethics = this.ctx.raw.ethics
    if (!ethics) {
      this._add("ethics", "WARN", "No ethics section — no data protection rules",
        "Add ethics:\n  never_expose: [api_keys, user_data]")
      return
    }
    const ne = ethics.never_expose ?? []
    if (!ne.length) {
      this._add("ethics.never_expose", "WARN", "No never_expose entries",
        "Add: ethics:\n  never_expose: [api_keys, user_data]")
    } else {
      this._add("ethics.never_expose", "OK", `${ne.length} data category/categories protected`)
    }
  }

  private _checkSignature(): void {
    const sig = this.ctx.raw.signature
    if (!sig?.value) {
      this._add("signature", "INFO", "brain.ctx is unsigned — tamper detection not active",
        "Sign with: brain-ctx sign --key ~/.brain-ctx/private.key")
    } else {
      this._add("signature", "OK", "Signature present (verify with: brain-ctx verify)")
    }
  }

  // ── Helpers ───────────────────────────────────────────────

  private _add(
    check: string, severity: Severity, message: string,
    fix?: string, detail?: string
  ): void {
    this.results.push({ check, severity, message, fix, detail })
  }

  private _buildReport(): DoctorReport {
    const errors   = this.results.filter(r => r.severity === "ERROR")
    const warnings = this.results.filter(r => r.severity === "WARN")
    const okCount  = this.results.filter(r => r.severity === "OK").length
    const passed   = errors.length === 0
    const status   = passed ? "HEALTHY" : "UNHEALTHY"
    const summary  = `brain.ctx doctor — ${status}\n  ${okCount} passed  ${warnings.length} warnings  ${errors.length} errors`
    return { results: this.results, passed, errors, warnings, okCount, summary }
  }
}
