/**
 * brain-ctx Node library tests
 * Tests: parser, validator, BrainCtx class, VS Code helpers, permission checks
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest"
import fs   from "fs"
import path from "path"
import os   from "os"
import yaml from "js-yaml"

import { BrainCtx, SPEC_VERSION }                        from "../src/core.js"
import { parseBrainCtx, serializeBrainCtx, mergeBrainCtx,
         findBrainCtxFile, loadBrainCtxFile }             from "../src/parser/index.js"
import { validateBrainCtx, isBrainCtxFile }               from "../src/validator/index.js"
import { detectWorkspaceBrainCtx, checkWriteViolations,
         generateCursorRules, syncAiToolBridges,
         getStatusBarText }                               from "../src/vscode/index.js"
import type { BrainCtxFile }                              from "../src/types/index.js"


// ── Helpers ────────────────────────────────────────────────────

function tmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "brain-ctx-test-"))
}

function writeBrainCtx(dir: string, data: Partial<BrainCtxFile>): string {
  const full: BrainCtxFile = {
    version: "1.0",
    identity: { name: "TestProject" },
    ...data,
  }
  const p = path.join(dir, "brain.ctx")
  fs.writeFileSync(p, yaml.dump(full), "utf-8")
  return p
}

const MINIMAL: BrainCtxFile = {
  version:    "1.0",
  identity:   { name: "TestProject", vision: "Test vision" },
  hard_rules: ["Never delete production data", "Always write tests"],
  trust:      { default: "read_only", never_touch: ["*.db"], mutex_files: ["src/core.rs"] },
  ethics:     { never_expose: ["api_keys", "user_data"] },
}

const SECURE_CORE: BrainCtxFile = {
  version:  "1.0",
  identity: { name: "SecureCore", vision: "A secure infrastructure", domain: "example.com" },
  hard_rules: [
    "Never generate sidecar files",
    "Exactly 5 public API methods",
    "Reference implementation in Rust",
  ],
  trust: {
    default:     "read_only",
    never_touch: ["*.key", "*.pem"],
    mutex_files: ["src/security/audit.ts"],
    agents: {
      architect:   { can: ["read_all", "propose_changes"], cannot: ["write", "delete"] },
      implementor: { can: ["write_code", "run_tests"],     cannot: ["change_architecture"] },
      reviewer:    { can: ["read_all", "flag_violations"], cannot: ["write", "delete"] },
    },
  },
  ethics:    { never_expose: ["user_data", "api_keys"], data_sovereignty: "India" },
  dialects:  { claude: "Think step by step before touching security code" },
  cognitive: { token_budget: { claude: 12000, gpt4: 8000, gemini: 20000, local: 2000 } },
}


// ══════════════════════════════════════════════════════════════
// 1. PARSER
// ══════════════════════════════════════════════════════════════

describe("Parser", () => {
  let dir: string
  beforeEach(() => { dir = tmpDir() })
  afterEach(() => fs.rmSync(dir, { recursive: true, force: true }))

  it("parseBrainCtx parses valid YAML", () => {
    const data = parseBrainCtx(yaml.dump(MINIMAL))
    expect(data.identity.name).toBe("TestProject")
    expect(data.hard_rules).toHaveLength(2)
  })

  it("parseBrainCtx throws on invalid YAML", () => {
    // Tabs in YAML indentation cause a real parse error
    expect(() => parseBrainCtx("key:\n\t- bad_indent")).toThrow()
  })

  it("parseBrainCtx throws when root is not an object", () => {
    expect(() => parseBrainCtx("- just a list")).toThrow()
  })

  it("loadBrainCtxFile loads from disk", () => {
    writeBrainCtx(dir, MINIMAL)
    const data = loadBrainCtxFile(path.join(dir, "brain.ctx"))
    expect(data.identity.name).toBe("TestProject")
  })

  it("loadBrainCtxFile throws when file missing", () => {
    expect(() => loadBrainCtxFile("/nonexistent/brain.ctx")).toThrow("not found")
  })

  it("findBrainCtxFile walks up tree", () => {
    writeBrainCtx(dir, MINIMAL)
    const subdir = path.join(dir, "a", "b", "c")
    fs.mkdirSync(subdir, { recursive: true })
    const result = findBrainCtxFile(subdir)
    expect(result).not.toBeNull()
    expect(result!.data.identity.name).toBe("TestProject")
  })

  it("findBrainCtxFile returns null when not found", () => {
    const result = findBrainCtxFile(path.join(dir, "nowhere"))
    expect(result).toBeNull()
  })

  it("serializeBrainCtx produces valid YAML", () => {
    const content = serializeBrainCtx(MINIMAL)
    const parsed  = yaml.load(content) as BrainCtxFile
    expect(parsed.identity.name).toBe("TestProject")
  })

  it("serializeBrainCtx includes header when requested", () => {
    const content = serializeBrainCtx(MINIMAL, true)
    expect(content).toContain("brain.ctx")
  })

  it("serializeBrainCtx excludes header when not requested", () => {
    const content = serializeBrainCtx(MINIMAL, false)
    const firstLine = content.split("\n")[0]
    expect(firstLine).not.toMatch(/^#/)
  })

  it("mergeBrainCtx local wins over imported", () => {
    const local:    BrainCtxFile = { version: "1.0", identity: { name: "Local" } }
    const imported: BrainCtxFile = { version: "1.0", identity: { name: "Imported" } }
    const merged = mergeBrainCtx(local, imported)
    expect(merged.identity.name).toBe("Local")
  })

  it("mergeBrainCtx deduplicates hard_rules", () => {
    const local:    BrainCtxFile = { version: "1.0", identity: { name: "A" }, hard_rules: ["Rule A", "Shared"] }
    const imported: BrainCtxFile = { version: "1.0", identity: { name: "B" }, hard_rules: ["Rule B", "Shared"] }
    const merged = mergeBrainCtx(local, imported)
    const count  = merged.hard_rules?.filter(r => r === "Shared").length ?? 0
    expect(count).toBe(1)
  })
})


// ══════════════════════════════════════════════════════════════
// 2. VALIDATOR
// ══════════════════════════════════════════════════════════════

describe("Validator", () => {
  it("validates correct minimal data", () => {
    const r = validateBrainCtx({ version: "1.0", identity: { name: "X" } })
    expect(r.valid).toBe(true)
    expect(r.errors).toHaveLength(0)
  })

  it("validates full MINIMAL object", () => {
    const r = validateBrainCtx(MINIMAL)
    expect(r.valid).toBe(true)
  })

  it("validates SECURE_CORE object", () => {
    const r = validateBrainCtx(SECURE_CORE)
    expect(r.valid).toBe(true)
  })

  it("fails on missing version", () => {
    const r = validateBrainCtx({ identity: { name: "X" } })
    expect(r.valid).toBe(false)
    expect(r.errors.some(e => e.includes("version"))).toBe(true)
  })

  it("fails on missing identity", () => {
    const r = validateBrainCtx({ version: "1.0" })
    expect(r.valid).toBe(false)
  })

  it("fails on missing identity.name", () => {
    const r = validateBrainCtx({ version: "1.0", identity: { vision: "x" } })
    expect(r.valid).toBe(false)
    expect(r.errors.some(e => e.includes("name"))).toBe(true)
  })

  it("isBrainCtxFile returns true for valid object", () => {
    expect(isBrainCtxFile(MINIMAL)).toBe(true)
  })

  it("isBrainCtxFile returns false for invalid object", () => {
    expect(isBrainCtxFile({ version: "1.0" })).toBe(false)
    expect(isBrainCtxFile(null)).toBe(false)
    expect(isBrainCtxFile("string")).toBe(false)
  })
})


// ══════════════════════════════════════════════════════════════
// 3. BrainCtx CLASS
// ══════════════════════════════════════════════════════════════

describe("BrainCtx", () => {
  let dir: string
  beforeEach(() => { dir = tmpDir() })
  afterEach(() => fs.rmSync(dir, { recursive: true, force: true }))

  it("load() reads file", () => {
    writeBrainCtx(dir, MINIMAL)
    const ctx = BrainCtx.load(path.join(dir, "brain.ctx"))
    expect(ctx.name).toBe("TestProject")
  })

  it("find() walks up tree", () => {
    writeBrainCtx(dir, MINIMAL)
    const sub = path.join(dir, "src", "utils")
    fs.mkdirSync(sub, { recursive: true })
    const ctx = BrainCtx.find(sub)
    expect(ctx).not.toBeNull()
    expect(ctx!.name).toBe("TestProject")
  })

  it("find() returns null when missing", () => {
    const ctx = BrainCtx.find(path.join(dir, "nowhere"))
    expect(ctx).toBeNull()
  })

  it("create() builds minimal ctx", () => {
    const ctx = BrainCtx.create({ name: "Quick", vision: "Fast" })
    expect(ctx.name).toBe("Quick")
  })

  it("buildContext() includes project name", () => {
    const ctx  = new BrainCtx(SECURE_CORE)
    const text = ctx.buildContext({ model: "claude" })
    expect(text).toContain("SecureCore")
  })

  it("buildContext() includes hard rules", () => {
    const ctx  = new BrainCtx(SECURE_CORE)
    const text = ctx.buildContext({ model: "claude" })
    expect(text).toContain("Never generate sidecar files")
  })

  it("buildContext() includes dialect instruction", () => {
    const ctx  = new BrainCtx(SECURE_CORE)
    const text = ctx.buildContext({ model: "claude" })
    expect(text).toContain("security")
  })

  it("buildContext() respects token budget", () => {
    const ctx  = new BrainCtx(MINIMAL)
    const text = ctx.buildContext({ model: "local", tokenBudget: 50 })
    expect(text.length).toBeLessThan(50 * 4 + 300)
  })

  it("aiScore() returns correct format", () => {
    const ctx   = new BrainCtx(SECURE_CORE)
    const score = ctx.aiScore()
    expect(score.raw).toContain("✓ brain.ctx loaded")
    expect(score.raw).toContain("SecureCore")
    expect(score.raw).toContain("invariants active")
    expect(score.projectName).toBe("SecureCore")
    expect(score.invariants).toBe(3)
    expect(score.signed).toBe(false)
  })

  it("aiScore() reflects signature status", () => {
    const ctx = new BrainCtx({ ...MINIMAL, signature: { algorithm: "ed25519", value: "abc" } })
    expect(ctx.aiScore().signed).toBe(true)
  })

  it("isAllowed() permits reads for read_only default", () => {
    const ctx = new BrainCtx(SECURE_CORE)
    expect(ctx.isAllowed("architect", "read")).toBe(true)
  })

  it("isAllowed() blocks writes to never_touch", () => {
    const ctx = new BrainCtx(SECURE_CORE)
    expect(ctx.isAllowed("implementor", "write", "secret.key")).toBe(false)
  })

  it("isAllowed() blocks writes to mutex_files", () => {
    const ctx = new BrainCtx(SECURE_CORE)
    expect(ctx.isAllowed("implementor", "write", "src/security/audit.ts")).toBe(false)
  })

  it("isAllowed() blocks architect from writing", () => {
    const ctx = new BrainCtx(SECURE_CORE)
    expect(ctx.isAllowed("architect", "write")).toBe(false)
  })

  it("toYaml() is valid YAML", () => {
    const ctx  = new BrainCtx(MINIMAL)
    const text = ctx.toYaml()
    expect(() => yaml.load(text)).not.toThrow()
  })

  it("toJson() is valid JSON", () => {
    const ctx  = new BrainCtx(MINIMAL)
    const text = ctx.toJson()
    expect(() => JSON.parse(text)).not.toThrow()
  })

  it("save() writes to disk", () => {
    const ctx  = new BrainCtx(MINIMAL)
    const dest = path.join(dir, "brain.ctx")
    ctx.save(dest)
    expect(fs.existsSync(dest)).toBe(true)
  })

  it("SPEC_VERSION is '1.0'", () => {
    expect(SPEC_VERSION).toBe("1.0")
  })
})


// ══════════════════════════════════════════════════════════════
// 4. VS CODE HELPERS
// ══════════════════════════════════════════════════════════════

describe("VS Code Helpers", () => {
  let dir: string
  beforeEach(() => { dir = tmpDir() })
  afterEach(() => fs.rmSync(dir, { recursive: true, force: true }))

  it("detectWorkspaceBrainCtx returns ctx when found", () => {
    writeBrainCtx(dir, MINIMAL)
    const ctx = detectWorkspaceBrainCtx(dir)
    expect(ctx).not.toBeNull()
    expect(ctx!.name).toBe("TestProject")
  })

  it("detectWorkspaceBrainCtx returns null when missing", () => {
    const ctx = detectWorkspaceBrainCtx(dir)
    expect(ctx).toBeNull()
  })

  it("getStatusBarText returns formatted string", () => {
    writeBrainCtx(dir, MINIMAL)
    const text = getStatusBarText(dir)
    expect(text).not.toBeNull()
    expect(text).toContain("TestProject")
  })

  it("getStatusBarText returns null when no brain.ctx", () => {
    expect(getStatusBarText(dir)).toBeNull()
  })

  it("checkWriteViolations detects never_touch violation", () => {
    const ctx = new BrainCtx(SECURE_CORE)
    const v   = checkWriteViolations(ctx, "db.sqlite", "implementor")
    expect(v.length).toBeGreaterThan(0)
    expect(v[0].severity).toBe("error")
  })

  it("checkWriteViolations detects mutex_file warning", () => {
    const ctx = new BrainCtx(SECURE_CORE)
    const v   = checkWriteViolations(ctx, "src/security/audit.ts", "implementor")
    expect(v.length).toBeGreaterThan(0)
  })

  it("checkWriteViolations allows permitted action", () => {
    const ctx = new BrainCtx(SECURE_CORE)
    // reviewer can read_all — but write should be blocked
    const v   = checkWriteViolations(ctx, "src/utils.rs", "reviewer")
    expect(v.length).toBeGreaterThan(0)  // reviewer cannot write
  })

  it("generateCursorRules returns non-empty string", () => {
    const ctx   = new BrainCtx(SECURE_CORE)
    const rules = generateCursorRules(ctx)
    expect(typeof rules).toBe("string")
    expect(rules.length).toBeGreaterThan(50)
  })

  it("syncAiToolBridges creates bridge files", () => {
    writeBrainCtx(dir, MINIMAL)
    const ctx     = detectWorkspaceBrainCtx(dir)!
    const written = syncAiToolBridges(ctx, dir)
    expect(written.length).toBe(2)
    for (const p of written) {
      expect(fs.existsSync(p)).toBe(true)
    }
  })
})
