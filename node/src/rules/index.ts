/**
 * brain.ctx Conditional Rules — Node.js implementation
 * Rules that activate based on environment, branch, or context.
 */

import * as os from "os"

// ── Types ──────────────────────────────────────────────────────

export interface RuleContext {
  env:           string    // production | staging | development | test | ci
  branch:        string    // git branch name
  agentRole:     string
  changedPaths:  string[]
  tags:          string[]
  user:          string
}

export interface ConditionalRuleDefinition {
  rule:      string
  when?:     {
    env?:          string | string[]
    branch?:       string | string[]
    role?:         string | string[]
    path_changed?: string | string[]
    tags?:         string[]
  }
  severity?: "ERROR" | "WARN" | "INFO"
  reason?:   string
}

export interface ActiveRule {
  rule:     string
  severity: "ERROR" | "WARN" | "INFO"
  reason:   string
  source:   "conditional_rules" | "hard_rules"
}

// ── Context builder ────────────────────────────────────────────

export function buildRuleContext(overrides: Partial<RuleContext> = {}): RuleContext {
  let env = process.env.BRAIN_CTX_ENV ?? ""

  if (!env && process.env.CI) env = "ci"
  if (!env) {
    const nodeEnv = process.env.NODE_ENV ?? ""
    if (nodeEnv.includes("prod"))  env = "production"
    else if (nodeEnv.includes("test")) env = "test"
    else env = "development"
  }

  let branch = process.env.BRAIN_CTX_BRANCH
    ?? process.env.GITHUB_REF_NAME
    ?? process.env.CI_COMMIT_BRANCH
    ?? ""

  if (!branch) {
    try {
      const { execSync } = require("child_process")
      branch = execSync("git rev-parse --abbrev-ref HEAD", {
        encoding: "utf-8", timeout: 2000
      }).trim()
    } catch { branch = "" }
  }

  return {
    env,
    branch,
    agentRole:    process.env.BRAIN_CTX_ROLE ?? "",
    changedPaths: [],
    tags:         [],
    user:         process.env.USER ?? os.userInfo().username,
    ...overrides,
  }
}

// ── Rule evaluator ─────────────────────────────────────────────

const ENV_ALIASES: Record<string, string[]> = {
  production:  ["production", "prod", "live"],
  prod:        ["production", "prod", "live"],
  development: ["development", "dev", "local"],
  dev:         ["development", "dev", "local"],
  test:        ["test", "testing", "ci", "github-actions"],
  ci:          ["ci", "test", "testing", "github-actions"],
  staging:     ["staging", "stage", "uat", "preprod"],
}

function matchesEnv(current: string, pattern: string): boolean {
  const aliases = ENV_ALIASES[pattern.toLowerCase()] ?? [pattern.toLowerCase()]
  return aliases.includes(current.toLowerCase())
}

function matchesGlob(value: string, pattern: string): boolean {
  if (!pattern.includes("*")) return value === pattern
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*")
  return new RegExp(`^${escaped}$`).test(value)
}

export function ruleAppliesTo(
  rule: ConditionalRuleDefinition,
  context: RuleContext
): boolean {
  const when = rule.when
  if (!when) return true

  if (when.env !== undefined) {
    const envList = Array.isArray(when.env) ? when.env : [when.env]
    if (!envList.some(e => matchesEnv(context.env, e))) return false
  }

  if (when.branch !== undefined) {
    const branchList = Array.isArray(when.branch) ? when.branch : [when.branch]
    if (!context.branch) return false
    if (!branchList.some(b => matchesGlob(context.branch, b))) return false
  }

  if (when.role !== undefined) {
    const roleList = Array.isArray(when.role) ? when.role : [when.role]
    if (context.agentRole && !roleList.includes(context.agentRole)) return false
  }

  if (when.path_changed !== undefined && context.changedPaths.length) {
    const patterns = Array.isArray(when.path_changed) ? when.path_changed : [when.path_changed]
    const anyMatch = context.changedPaths.some(p =>
      patterns.some(pat => matchesGlob(p, pat))
    )
    if (!anyMatch) return false
  }

  if (when.tags !== undefined) {
    const required = when.tags
    if (!required.some(t => context.tags.includes(t))) return false
  }

  return true
}

// ── Engine ─────────────────────────────────────────────────────

export class ConditionalRuleEngine {
  private conditionalRules: ConditionalRuleDefinition[]
  private hardRules:        string[]

  constructor(
    conditionalRules: ConditionalRuleDefinition[] = [],
    hardRules:        string[]                    = []
  ) {
    this.conditionalRules = conditionalRules
    this.hardRules        = hardRules
  }

  static fromBrainCtxData(data: Record<string, unknown>): ConditionalRuleEngine {
    const conditionalRules = (data.conditional_rules ?? []) as ConditionalRuleDefinition[]
    const hardRules        = (data.hard_rules        ?? []) as string[]
    return new ConditionalRuleEngine(conditionalRules, hardRules)
  }

  evaluate(context?: RuleContext): ActiveRule[] {
    const ctx = context ?? buildRuleContext()
    const active: ActiveRule[] = []

    // Conditional rules — evaluated against context
    for (const rule of this.conditionalRules) {
      if (ruleAppliesTo(rule, ctx)) {
        active.push({
          rule:     rule.rule,
          severity: rule.severity ?? "ERROR",
          reason:   rule.reason   ?? "",
          source:   "conditional_rules",
        })
      }
    }

    // Hard rules — always active
    for (const rule of this.hardRules) {
      active.push({ rule, severity: "ERROR", reason: "Unconditional", source: "hard_rules" })
    }

    return active
  }

  evaluateForEnv(env: string, branch = ""): ActiveRule[] {
    return this.evaluate(buildRuleContext({ env, branch }))
  }

  summary(context?: RuleContext): string {
    const ctx    = context ?? buildRuleContext()
    const active = this.evaluate(ctx)
    const errors = active.filter(r => r.severity === "ERROR")
    const warns  = active.filter(r => r.severity === "WARN")
    const lines  = [
      `Active rules for env=${ctx.env}, branch=${ctx.branch || "unknown"}`,
      `  ${errors.length} errors  ${warns.length} warnings  ${active.length} total`,
    ]
    errors.slice(0, 5).forEach(r => lines.push(`  ❌ ${r.rule.slice(0, 80)}`))
    warns.slice(0, 3).forEach(r  => lines.push(`  ⚠️  ${r.rule.slice(0, 80)}`))
    return lines.join("\n")
  }
}
