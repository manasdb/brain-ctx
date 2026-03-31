/**
 * brain-ctx — Node.js / TypeScript library
 *
 * @example
 * import { BrainCtx } from "brain-ctx"
 * const ctx = BrainCtx.load()
 * console.log(ctx.aiScore().raw)
 */

export { BrainCtx, FILENAME, SPEC_VERSION } from "./core.js"
export { startMcpServer }                   from "./mcp/index.js"
export { parseBrainCtx, loadBrainCtxFile,
         findBrainCtxFile, serializeBrainCtx,
         mergeBrainCtx }                    from "./parser/index.js"
export { validateBrainCtx, validateBrainCtxFile,
         isBrainCtxFile }                   from "./validator/index.js"
export { detectWorkspaceBrainCtx, watchBrainCtx,
         buildWorkspaceContext, getStatusBarText,
         checkWriteViolations, generateCursorRules,
         generateCopilotInstructions,
         syncAiToolBridges }                from "./vscode/index.js"
export { DoctorRunner }                     from "./doctor/index.js"
export { DiffReader }                       from "./diff/index.js"
export { ConditionalRuleEngine, buildRuleContext,
         ruleAppliesTo }                    from "./rules/index.js"
export { InheritanceResolver }             from "./inherit/index.js"

export type {
  BrainCtxFile, Identity, TrustConfig, TrustLevel, AgentRole,
  EthicsConfig, CognitiveConfig, DialectConfig, MeshConfig,
  ObservabilityConfig, SignatureBlock, AiScore, AgentSession,
  AgentAction, McpServerOptions, ContextBuildOptions,
} from "./types/index.js"

export type { CheckResult, DoctorReport, Severity } from "./doctor/index.js"
export type { LogEntry, DiffReport }                from "./diff/index.js"
export type { RuleContext, ConditionalRuleDefinition,
              ActiveRule }                          from "./rules/index.js"
