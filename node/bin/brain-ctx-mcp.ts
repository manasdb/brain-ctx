#!/usr/bin/env node
/**
 * brain-ctx-mcp — MCP Server entry point
 * Usage: npx brain-ctx-mcp [--ctx brain.ctx] [--enforce] [--model claude]
 */

import { startMcpServer } from "../dist/mcp/index.js"

const args = process.argv.slice(2)
const get  = (flag: string) => {
  const i = args.indexOf(flag)
  return i >= 0 ? args[i + 1] : undefined
}

startMcpServer({
  ctxPath:     get("--ctx"),
  projectRoot: get("--root") ?? process.cwd(),
  enforce:     !args.includes("--no-enforce"),
  model:       get("--model") ?? "claude",
}).catch(e => {
  console.error("[brain-ctx-mcp] Fatal error:", e)
  process.exit(1)
})
