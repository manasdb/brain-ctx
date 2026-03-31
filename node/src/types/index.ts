/**
 * brain.ctx TypeScript types
 * Full type definitions for the AI Constitution Standard v1.0
 */

export interface BrainCtxFile {
  version:        string
  identity:       Identity
  inference?:     InferenceConfig
  trust?:         TrustConfig
  hard_rules?:    string[]
  ethics?:        EthicsConfig
  truth_sources?: TruthSources
  cognitive?:     CognitiveConfig
  dialects?:      DialectConfig
  mesh?:          MeshConfig
  observability?: ObservabilityConfig
  signature?:     SignatureBlock
  inherit?:           string
  conditional_rules?: Array<string | ConditionalRule>
  timeline?:          TimelineEntry[]
}

export interface Identity {
  name:     string
  vision?:  string
  domain?:  string
  author?:  string
  license?: string
}

export interface InferenceConfig {
  enabled?:              boolean
  sources?:              InferenceSource[]
  auto_learn?:           boolean
  confidence_threshold?: number
  human_review_queue?:   string
}

export type InferenceSource =
  | "codebase" | "git" | "tests"
  | "dependencies" | "readme" | "comments"

export interface TrustConfig {
  default?:      TrustLevel
  mutex_files?:  string[]
  never_touch?:  string[]
  agents?:       Record<string, AgentRole>
}

export type TrustLevel = "read_only" | "read_write" | "no_access"

export interface AgentRole {
  can:    string[]
  cannot: string[]
}

export interface EthicsConfig {
  never_expose?:     string[]
  never_delete?:     string[]
  never_publish?:    string
  data_sovereignty?: string
}

export interface TruthSources {
  [key: string]: TruthSource
}

export interface TruthSource {
  infer_from?:   string | string[]
  pattern?:      string
  auto_extract?: boolean
  last_n?:       number
  auto_learn?:   boolean
  treat_as?:     "hard_invariant" | "soft_invariant"
}

export interface CognitiveConfig {
  critical?:     string[]
  important?:    string[]
  reference?:    string[]
  token_budget?: Record<string, number>
}

export interface DialectConfig {
  claude?:  string
  gpt4?:    string
  gemini?:  string
  local?:   string
  [model: string]: string | undefined
}

export interface MeshConfig {
  imports?:             string[]
  trust_level?:         "read_only" | "read_write"
  conflict_resolution?: "local_wins" | "imported_wins" | "merge"
}

export interface ObservabilityConfig {
  enabled?:    boolean
  log_file?:   string
  log_format?: "json" | "yaml" | "text"
  retention?:  string
  capture?:    ObservabilityEvent[]
}

export type ObservabilityEvent =
  | "reads" | "writes" | "proposals"
  | "rejections" | "violations"

export interface SignatureBlock {
  algorithm?:  "ed25519"
  public_key?: string
  value?:      string
  signed_at?:  string
}

// ── MCP types ──────────────────────────────────────────────────

export interface McpServerOptions {
  ctxPath?:    string        // path to brain.ctx — auto-detected if not set
  projectRoot?: string       // project root — defaults to cwd
  enforce?:    boolean       // hard-block unauthorized actions (default: true)
  model?:      string        // model hint for context optimization
  tokenBudget?: number       // override token budget
}

export interface AgentSession {
  sessionId:   string
  model:       string
  role:        string
  trustLevel:  TrustLevel
  startedAt:   Date
  actions:     AgentAction[]
}

export interface AgentAction {
  type:        "read" | "write" | "delete" | "propose"
  path?:       string
  timestamp:   Date
  allowed:     boolean
  reason?:     string
}

export interface AiScore {
  raw:         string
  projectName: string
  version:     string
  trust:       TrustLevel
  invariants:  number
  agents:      number
  signed:      boolean
}

export interface ContextBuildOptions {
  model?:       string
  tokenBudget?: number
  live?:        boolean  // resolve truth_sources from live code
}

export interface ConditionalRule {
  rule:      string
  when?:     RuleCondition
  severity?: "ERROR" | "WARN" | "INFO"
  reason?:   string
}

export interface RuleCondition {
  env?:          string | string[]
  branch?:       string | string[]
  role?:         string | string[]
  path_changed?: string | string[]
  tags?:         string[]
}

export interface TimelineEntry {
  date:    string
  event:   string
  lesson?: string
  hash?:   string
}

export interface DoctorCheckResult {
  check:    string
  severity: "OK" | "WARN" | "ERROR" | "INFO"
  message:  string
  fix?:     string
  detail?:  string
}

export interface DoctorReport {
  passed:   boolean
  errors:   number
  warnings: number
  ok:       number
  checks:   DoctorCheckResult[]
}

export interface DiffEntry {
  ts:         string
  session_id: string
  model:      string
  role:       string
  action:     string
  path?:      string
  allowed?:   boolean
  summary?:   string
}

export interface DiffStats {
  total:      number
  writes:     number
  blocked:    number
  proposals:  number
  sessions:   number
  models:     string[]
  roles:      string[]
  date_range: { from: string; to: string }
}

