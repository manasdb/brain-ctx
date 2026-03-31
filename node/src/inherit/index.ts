/**
 * brain.ctx Inheritance Resolver — Node.js implementation
 * Resolves inherit: chains and produces merged BrainCtx.
 */

import * as fs   from "fs"
import * as path from "path"
import { BrainCtx }         from "../core.js"
import { loadBrainCtxFile } from "../parser/index.js"
import type { BrainCtxFile } from "../types/index.js"

// ── Resolver ───────────────────────────────────────────────────

export class InheritanceResolver {
  private ctx:      BrainCtx
  private basePath: string
  private seen:     Set<string> = new Set()
  private MAX_DEPTH = 5

  constructor(ctx: BrainCtx, basePath: string = process.cwd()) {
    this.ctx      = ctx
    this.basePath = path.resolve(basePath)
  }

  resolve(): BrainCtx {
    const inheritPath = this._getInheritPath(this.ctx.raw)
    if (!inheritPath) return this.ctx
    return this._resolveChain(this.ctx, 0)
  }

  private _resolveChain(ctx: BrainCtx, depth: number): BrainCtx {
    if (depth >= this.MAX_DEPTH) return ctx

    const inheritStr = this._getInheritPath(ctx.raw)
    if (!inheritStr) return ctx

    const parentPath = this._resolvePath(inheritStr, ctx)
    if (!parentPath || !fs.existsSync(parentPath)) {
      console.warn(`[brain-ctx] inherit path not found: ${inheritStr}`)
      return ctx
    }

    const canonical = path.resolve(parentPath)
    if (this.seen.has(canonical)) {
      console.warn(`[brain-ctx] circular inheritance at ${canonical}`)
      return ctx
    }
    this.seen.add(canonical)

    const parentData   = loadBrainCtxFile(parentPath)
    const parentCtx    = new BrainCtx(parentData)
    const resolvedParent = this._resolveChain(parentCtx, depth + 1)
    return new BrainCtx(this._merge(resolvedParent.raw, ctx.raw))
  }

  private _merge(parent: BrainCtxFile, child: BrainCtxFile): BrainCtxFile {
    const p = JSON.parse(JSON.stringify(parent)) as Record<string, unknown>
    const c = child as Record<string, unknown>
    const out = { ...p }

    // identity: child always wins
    if (c.identity) out.identity = c.identity

    // hard_rules: accumulate, deduplicate
    const pRules = (p.hard_rules as string[] ?? [])
    const cRules = (c.hard_rules as string[] ?? [])
    out.hard_rules = [...pRules, ...cRules.filter(r => !pRules.includes(r))]

    // conditional_rules: both apply
    const pCond = (p.conditional_rules as unknown[] ?? [])
    const cCond = (c.conditional_rules as unknown[] ?? [])
    out.conditional_rules = [...pCond, ...cCond]

    // ethics: deep merge, child wins per key, lists accumulate
    if (c.ethics) {
      const pe = (p.ethics as Record<string,unknown> ?? {})
      const ce = (c.ethics as Record<string,unknown>)
      const me: Record<string, unknown> = { ...pe }
      for (const [k, v] of Object.entries(ce)) {
        if ((k === "never_expose" || k === "never_delete") && Array.isArray(pe[k]) && Array.isArray(v)) {
          me[k] = [...new Set([...(pe[k] as string[]), ...(v as string[])])]
        } else {
          me[k] = v
        }
      }
      out.ethics = me
    }

    // trust: deep merge
    if (c.trust) {
      const pt = (p.trust as Record<string,unknown> ?? {})
      const ct = (c.trust as Record<string,unknown>)
      const mt: Record<string, unknown> = { ...pt }

      if (Array.isArray(ct.never_touch)) {
        mt.never_touch = [...new Set([...(pt.never_touch as string[] ?? []), ...ct.never_touch])]
      }
      if (Array.isArray(ct.mutex_files)) {
        mt.mutex_files = [...new Set([...(pt.mutex_files as string[] ?? []), ...ct.mutex_files])]
      }
      if (ct.default !== undefined) mt.default = ct.default
      if (ct.agents) {
        mt.agents = { ...(pt.agents as object ?? {}), ...(ct.agents as object) }
      }
      out.trust = mt
    }

    // truth_sources: child overrides per key
    if (c.truth_sources) {
      out.truth_sources = { ...(p.truth_sources as object ?? {}), ...(c.truth_sources as object) }
    }

    // cognitive: deep merge
    if (c.cognitive) {
      const pc = (p.cognitive as Record<string,unknown> ?? {})
      const cc = (c.cognitive as Record<string,unknown>)
      out.cognitive = {
        ...pc, ...cc,
        token_budget: { ...(pc.token_budget as object ?? {}), ...(cc.token_budget as object ?? {}) },
      }
    }

    // dialects: child overrides per model
    if (c.dialects) {
      out.dialects = { ...(p.dialects as object ?? {}), ...(c.dialects as object) }
    }

    // observability: child wins
    if (c.observability) out.observability = c.observability

    // timeline: combine
    const pt = (p as Record<string,unknown>).timeline as unknown[] ?? []
    const ct = (c as Record<string,unknown>).timeline as unknown[] ?? []
    if (pt.length || ct.length) out.timeline = [...pt, ...ct]

    // mesh: child wins
    if (c.mesh) out.mesh = c.mesh

    // Never inherit signature
    out.signature = {}

    // Remove inherit key
    delete out.inherit

    return out as unknown as BrainCtxFile
  }

  private _getInheritPath(data: Record<string, unknown>): string | null {
    return (data.inherit as string) ?? null
  }

  private _resolvePath(inheritStr: string, ctx: BrainCtx): string | null {
    if (inheritStr.startsWith("github://")) {
      console.warn("[brain-ctx] remote inherit not yet supported")
      return null
    }
    const base = ctx["sourcePath"]
      ? path.dirname(ctx["sourcePath"] as string)
      : this.basePath
    return path.resolve(base, inheritStr)
  }
}
