# brain.ctx — AI Constitution Standard

> **The self-maintaining project intelligence layer that gives every AI model, agent, and tool instant understanding of your codebase — automatically.**

Invented by [ManasDB](https://manasdb.com)

---

## ⚡ The pitch

`brain.ctx` is the `package.json` for AI. It lives at your repo root, reads your codebase in real-time, and provides every AI tool with the right context, rules, and architecture—without you writing or maintaining anything.

```bash
pip install brain-ctx
brain-ctx init        # scan project, generate brain.ctx in 30 seconds
```

---

## 🛠️ What problem it solves

| Pain               | Without brain.ctx                     | With brain.ctx                  |
| ------------------ | ------------------------------------- | ------------------------------- |
| Context amnesia    | Re-explain architecture every session | Zero re-explaining, ever        |
| Stale instructions | Manual updates when code changes      | Auto-inferred from live code    |
| Model switching    | Different prompts per tool            | One file, works with all models |
| Agent permissions  | No control over what agents can do    | Enforced permission layer       |
| Compliance         | No audit trail                        | Full observability log          |

---

## 🧠 The "Senior" Upgrade (v1.1.0)

Version 1.1.0 introduces the **Execution Layer**. Your constitution no longer just "tells" the AI what to do—it requires the AI to **prove** it.

- **Automated Verification**: Hook into your test, lint, and build suites. AI agents must verify code before proposing edits.
- **Cognitive Modes**: Dynamic context prioritization for `debug`, `build`, and `refactor` tasks.
- **AI Score v1.1**: Real-time project health and verification status in a single handshake line.

---

## 🔋 Why it never goes stale

`brain.ctx` does not store static facts. It stores **pointers to where truth lives**:

```yaml
truth_sources:
  api_surface:
    infer_from: src/lib.rs
    pattern: "pub fn"
  invariants:
    infer_from: tests/
    pattern: test_invariant_*
```

Your API changes → `brain.ctx` knows. Tests change → invariants update. New commit → conventions evolve.

---

## 📦 Monorepo Overview

- **python/**: The heavy lifter. CLI, automated generation, and cryptographic signing. (`pip install brain-ctx`)
- **node/**: The bridge. MCP server for agent enforcement and TypeScript API. (`npm install brain-ctx`)
- **spec/**: The single source of truth for the language-agnostic AI Constitution schema.

---

## Power User Features: Manual Overrides

Re-introduce advanced context manually if not automatically detected:

- **Adding Hard Rules**: Add a `hard_rules:` section for "ALWAYS/NEVER" directives.
- **Architectural Context**: Add a `timeline:` section to track major decisions and trigger `architecture` focus in the cognitive optimizer.

---

## 🔗 Links

- **Spec**: `spec/brain-ctx.schema.json`
- **MCP Server**: `node/src/mcp/`
- **Registry**: [mesh.brainctx.dev](https://mesh.brainctx.dev)

_Powered by ManasDB. Apache-2.0._
