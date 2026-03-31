/**
 * brain.ctx Diff — Node.js implementation
 * Reads observability log and produces human-readable summaries.
 */

import * as fs   from "fs"
import * as path from "path"

// ── Data types ─────────────────────────────────────────────────

export interface LogEntry {
  ts:         Date
  sessionId:  string
  model:      string
  role:       string
  action:     string
  filePath?:  string
  allowed?:   boolean
  reason?:    string
  summary?:   string
  raw:        Record<string, unknown>
}

export interface DiffReport {
  since?:    Date
  entries:   LogEntry[]
  writes:    LogEntry[]
  blocked:   LogEntry[]
  violations: LogEntry[]
  proposals: LogEntry[]
  sessions:  Record<string, LogEntry[]>
  byRole:    Record<string, LogEntry[]>
  filesTouched: string[]
}

// ── Reader ─────────────────────────────────────────────────────

export class DiffReader {
  private logPath:     string
  private projectRoot: string

  constructor(logPath = ".brain-ctx.log", projectRoot = process.cwd()) {
    this.logPath     = logPath
    this.projectRoot = projectRoot
  }

  private _load(): LogEntry[] {
    if (!fs.existsSync(this.logPath)) return []

    const entries: LogEntry[] = []
    const lines = fs.readFileSync(this.logPath, "utf-8").split("\n")

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      try {
        const d   = JSON.parse(trimmed)
        const tsStr = (d.ts ?? d.timestamp ?? "") as string
        const ts = tsStr ? new Date(tsStr) : new Date()
        entries.push({
          ts,
          sessionId: (d.session_id ?? "") as string,
          model:     (d.model   ?? "unknown") as string,
          role:      (d.role    ?? "unknown") as string,
          action:    (d.action  ?? "") as string,
          filePath:  d.path as string | undefined,
          allowed:   d.allowed as boolean | undefined,
          reason:    d.reason  as string | undefined,
          summary:   d.summary as string | undefined,
          raw:       d,
        })
      } catch { continue }
    }
    return entries.sort((a, b) => a.ts.getTime() - b.ts.getTime())
  }

  private _buildReport(entries: LogEntry[], since?: Date): DiffReport {
    const writes     = entries.filter(e => e.action === "write" && e.allowed)
    const blocked    = entries.filter(e => e.allowed === false)
    const violations = entries.filter(e => ["write","delete"].includes(e.action) && e.allowed === false)
    const proposals  = entries.filter(e => e.action === "propose")

    const sessions: Record<string, LogEntry[]> = {}
    for (const e of entries) {
      if (!sessions[e.sessionId]) sessions[e.sessionId] = []
      sessions[e.sessionId].push(e)
    }

    const byRole: Record<string, LogEntry[]> = {}
    for (const e of entries) {
      if (!byRole[e.role]) byRole[e.role] = []
      byRole[e.role].push(e)
    }

    const seen = new Set<string>()
    const filesTouched: string[] = []
    for (const e of writes) {
      if (e.filePath && !seen.has(e.filePath)) {
        seen.add(e.filePath)
        filesTouched.push(e.filePath)
      }
    }

    return { since, entries, writes, blocked, violations, proposals,
             sessions, byRole, filesTouched }
  }

  all(): DiffReport {
    return this._buildReport(this._load())
  }

  since(when: Date): DiffReport {
    const entries = this._load().filter(e => e.ts >= when)
    return this._buildReport(entries, when)
  }

  sinceHours(hours: number): DiffReport {
    const when = new Date(Date.now() - hours * 3600 * 1000)
    return this.since(when)
  }

  sinceCommit(): DiffReport {
    try {
      const { execSync } = require("child_process")
      const out = execSync("git log -1 --format=%ci", {
        cwd: this.projectRoot, encoding: "utf-8", timeout: 3000
      }).trim()
      if (out) return this.since(new Date(out))
    } catch { /* fall through */ }
    return this.sinceHours(24)
  }

  forRole(role: string): DiffReport {
    const entries = this._load().filter(e => e.role === role)
    return this._buildReport(entries)
  }

  violationsOnly(): DiffReport {
    const entries = this._load().filter(e => e.allowed === false)
    return this._buildReport(entries)
  }

  stats(): Record<string, unknown> {
    const entries = this._load()
    if (!entries.length) return { total: 0 }
    return {
      total:     entries.length,
      writes:    entries.filter(e => e.action === "write" && e.allowed).length,
      blocked:   entries.filter(e => e.allowed === false).length,
      proposals: entries.filter(e => e.action === "propose").length,
      sessions:  new Set(entries.map(e => e.sessionId)).size,
      models:    [...new Set(entries.map(e => e.model))],
      roles:     [...new Set(entries.map(e => e.role))],
      dateRange: {
        from: entries[0].ts.toISOString(),
        to:   entries[entries.length - 1].ts.toISOString(),
      },
    }
  }

  rotate(keepDays = 30): { archived: number; archivePath: string } {
    const cutoff  = new Date(Date.now() - keepDays * 86400 * 1000)
    const entries = this._load()
    const keep    = entries.filter(e => e.ts >= cutoff)
    const archive = entries.filter(e => e.ts <  cutoff)

    if (!archive.length) return { archived: 0, archivePath: "" }

    const archivePath = this.logPath + ".archive"
    fs.appendFileSync(archivePath,
      archive.map(e => JSON.stringify(e.raw)).join("\n") + "\n", "utf-8")
    fs.writeFileSync(this.logPath,
      keep.map(e => JSON.stringify(e.raw)).join("\n") + (keep.length ? "\n" : ""), "utf-8")

    return { archived: archive.length, archivePath }
  }

  /** Format a DiffReport as a human-readable string. */
  static format(report: DiffReport): string {
    const lines: string[] = []
    const since = report.since
      ? `since ${report.since.toISOString().slice(0,16)}`
      : "all time"

    lines.push(`\n${"─".repeat(60)}`)
    lines.push(`  brain.ctx diff — ${since}`)
    lines.push("─".repeat(60))

    if (!report.entries.length) {
      lines.push("  No AI activity recorded in this period.\n")
      return lines.join("\n")
    }

    const sessions = Object.entries(report.sessions)
    lines.push(`\n  📋 Sessions: ${sessions.length}`)
    for (const [sid, ses] of sessions.slice(0, 5)) {
      const first = ses[0], last = ses[ses.length - 1]
      lines.push(`     ${sid.slice(0,8)}... | ${first.model}/${first.role} | ${ses.length} actions`)
    }

    lines.push(`\n  ✏️  Files written: ${report.filesTouched.length}`)
    for (const f of report.filesTouched.slice(0, 10)) {
      const roles = [...new Set(report.writes.filter(e => e.filePath === f).map(e => e.role))]
      lines.push(`     ${f}  [${roles.join(", ")}]`)
    }

    if (report.blocked.length) {
      lines.push(`\n  🚫 Blocked: ${report.blocked.length}`)
      for (const e of report.blocked.slice(0, 5)) {
        lines.push(`     [${e.role}] ${e.action} ${e.filePath ?? ""}`)
        if (e.reason) lines.push(`     → ${e.reason.slice(0, 80)}`)
      }
    }

    if (report.proposals.length) {
      lines.push(`\n  💡 Proposals: ${report.proposals.length}`)
      for (const e of report.proposals.slice(0, 3)) {
        if (e.summary) lines.push(`     [${e.role}] ${e.summary.slice(0, 80)}`)
      }
    }

    lines.push(`\n  👥 By role:`)
    for (const [role, roleEntries] of Object.entries(report.byRole)) {
      const w = roleEntries.filter(e => e.action === "write" && e.allowed).length
      const b = roleEntries.filter(e => e.allowed === false).length
      lines.push(`     ${role.padEnd(15)} ${roleEntries.length.toString().padStart(3)} actions  ${w.toString().padStart(3)} writes  ${b.toString().padStart(3)} blocked`)
    }

    lines.push(`\n${"─".repeat(60)}\n`)
    return lines.join("\n")
  }
}
