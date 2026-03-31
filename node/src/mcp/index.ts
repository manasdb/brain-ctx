/**
 * brain.ctx MCP Server
 * ====================
 * Sits between AI agents and the filesystem.
 * Reads brain.ctx on session start.
 * Enforces permissions before every agent action.
 * Logs all actions to the observability layer.
 *
 * Usage:
 *   npx brain-ctx-mcp              # auto-detects brain.ctx
 *   npx brain-ctx-mcp --ctx ./brain.ctx --enforce
 *
 * Requires: npm install @modelcontextprotocol/sdk
 */

import { BrainCtx }     from "../core.js"
import type { McpServerOptions, AgentSession, AgentAction } from "../types/index.js"
import { randomUUID }   from "crypto"
import * as fs          from "fs"

// Active sessions map
const activeSessions = new Map<string, AgentSession>()

// ── Permission check (pure — no MCP SDK needed) ─────────────────
export function checkPermission(
  ctx:      BrainCtx,
  role:     string,
  action:   string,
  filePath?: string,
): { allowed: boolean; reason?: string } {
  const allowed = ctx.isAllowed(role, action, filePath)
  return {
    allowed,
    reason: allowed
      ? undefined
      : `brain.ctx: Role '${role}' is not permitted to '${action}'${filePath ? ` on '${filePath}'` : ""}`,
  }
}

// ── Session management ──────────────────────────────────────────
export function createSession(
  ctx:   BrainCtx,
  model: string,
  role:  string,
): { sessionId: string; aiScore: string } {
  const sessionId = randomUUID()
  activeSessions.set(sessionId, {
    sessionId,
    model,
    role,
    trustLevel: ctx.trust,
    startedAt:  new Date(),
    actions:    [],
  })
  return { sessionId, aiScore: ctx.aiScore().raw }
}

export function getSession(sessionId: string): AgentSession | undefined {
  return activeSessions.get(sessionId)
}

// ── Observability ───────────────────────────────────────────────
export function logAction(
  logFile: string,
  entry:   Record<string, unknown>,
): void {
  try {
    const line = JSON.stringify({ ...entry, ts: new Date().toISOString() }) + "\n"
    fs.appendFileSync(logFile, line, "utf-8")
  } catch {
    // Non-fatal — observability failures never block agent work
  }
}

// ── MCP Server (requires @modelcontextprotocol/sdk at runtime) ──
export async function startMcpServer(options: McpServerOptions = {}): Promise<void> {
  const {
    ctxPath     = "brain.ctx",
    projectRoot = process.cwd(),
    enforce     = true,
  } = options

  let ctx: BrainCtx
  try {
    ctx = BrainCtx.find(projectRoot) ?? BrainCtx.load(ctxPath)
  } catch {
    console.error("[brain-ctx] No brain.ctx found. Run: brain-ctx init")
    process.exit(1)
  }

  // Dynamic import of MCP SDK — optional peer dependency
  let Server: unknown, StdioServerTransport: unknown
  try {
    const sdk     = await import("@modelcontextprotocol/sdk/server/index.js" as string)
    const sdkStdio = await import("@modelcontextprotocol/sdk/server/stdio.js" as string)
    Server              = (sdk as Record<string, unknown>).Server
    StdioServerTransport = (sdkStdio as Record<string, unknown>).StdioServerTransport
  } catch {
    console.error(
      "[brain-ctx] @modelcontextprotocol/sdk not found.\n" +
      "Install with: npm install @modelcontextprotocol/sdk"
    )
    process.exit(1)
  }

  // Cast for usage
  const McpServer    = Server    as new (info: object, caps: object) => Record<string, Function>
  const McpTransport = StdioServerTransport as new () => object

  const server = new McpServer(
    { name: "brain-ctx", version: "1.0.0" },
    { capabilities: { tools: {} } },
  )

  // List tools
  server.setRequestHandler({ method: "tools/list" }, async () => ({
    tools: [
      {
        name: "brain_ctx_load",
        description: "Load the project's AI Constitution. Call at session start.",
        inputSchema: {
          type: "object",
          properties: {
            model: { type: "string" },
            role:  { type: "string" },
          },
          required: ["model"],
        },
      },
      {
        name: "brain_ctx_check",
        description: "Check if you are permitted to perform an action. Call BEFORE any write/delete.",
        inputSchema: {
          type: "object",
          properties: {
            session_id: { type: "string" },
            action:     { type: "string", enum: ["read","write","delete","propose"] },
            path:       { type: "string" },
          },
          required: ["session_id", "action"],
        },
      },
      {
        name: "brain_ctx_context",
        description: "Get full project context optimized for your model.",
        inputSchema: {
          type: "object",
          properties: {
            session_id:   { type: "string" },
            token_budget: { type: "number" },
          },
          required: ["session_id"],
        },
      },
      {
        name: "brain_ctx_log",
        description: "Log an action you performed. Call after every write/delete.",
        inputSchema: {
          type: "object",
          properties: {
            session_id: { type: "string" },
            action:     { type: "string" },
            path:       { type: "string" },
            summary:    { type: "string" },
          },
          required: ["session_id", "action"],
        },
      },
    ],
  }))

  // Handle tool calls
  server.setRequestHandler({ method: "tools/call" }, async (req: Record<string, unknown>) => {
    const params = req.params as Record<string, unknown>
    const name   = params.name as string
    const args   = (params.arguments ?? {}) as Record<string, unknown>

    switch (name) {
      case "brain_ctx_load": {
        const model     = (args.model as string) || "unknown"
        const role      = (args.role  as string) || "implementor"
        const { sessionId, aiScore } = createSession(ctx, model, role)
        return { content: [{ type: "text", text: JSON.stringify({
          session_id: sessionId, ai_score: aiScore,
          name: ctx.name, trust: ctx.trust, hard_rules: ctx.rules,
          your_role: role,
        }, null, 2)}]}
      }

      case "brain_ctx_check": {
        const sessionId = args.session_id as string
        const action    = args.action     as string
        const filePath  = args.path       as string | undefined
        const session   = getSession(sessionId)
        const role      = session?.role || "implementor"
        const result    = checkPermission(ctx, role, action, filePath)
        if (ctx.raw.observability?.enabled) {
          logAction(ctx.raw.observability.log_file ?? ".brain-ctx.log", {
            session_id: sessionId, role, action, path: filePath, ...result,
          })
        }
        if (!result.allowed && enforce) {
          return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], isError: true }
        }
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] }
      }

      case "brain_ctx_context": {
        const sessionId   = args.session_id  as string
        const tokenBudget = args.token_budget as number | undefined
        const session     = getSession(sessionId)
        const model       = session?.model || "claude"
        return { content: [{ type: "text", text: ctx.buildContext({ model, tokenBudget }) }] }
      }

      case "brain_ctx_log": {
        const entry = {
          session_id: args.session_id,
          action: args.action, path: args.path, summary: args.summary,
        }
        if (ctx.raw.observability?.enabled) {
          logAction(ctx.raw.observability.log_file ?? ".brain-ctx.log", entry)
        }
        return { content: [{ type: "text", text: JSON.stringify({ logged: true }) }] }
      }

      default:
        throw new Error(`Unknown tool: ${name}`)
    }
  })

  const transport = new McpTransport()
  await (server.connect as Function)(transport)
  console.error(`[brain-ctx] MCP server started — ${ctx.aiScore().raw}`)
}
