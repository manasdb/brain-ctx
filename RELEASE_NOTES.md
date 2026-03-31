# Release Notes: v1.0.0 — "Birth of the AI Constitution"

We are proud to announce the first major release of **brain.ctx** (v1.0.0), a language-agnostic AI Construction Standard designed to give every AI model, agent, and tool instant understanding of your codebase — automatically.

> "The `package.json` for AI." — Invented by [ManasDB](https://manasdb.com)

---

## Core Features (AI-Analyzed)

### 🧠 Self-Maintaining Intelligence
- **Zero Human Input**: Use `brain-ctx init` to scan your project, detect patterns, and generate a `brain.ctx` file in seconds.
- **Auto-Inferred Context**: Real-time resolution of truth sources from your codebase, git history, and tests.
- **Context Builders**: Multi-tier priority system (Critical > Important > Reference) with native token-budget awareness.

### 🛡️ The AI Constitution (Safety First)
- **Granular Trust Layer**: Fine-grained safety controls with `never_touch`, `mutex_files`, and role-based permissions (`can`/`cannot`).
- **Standardized Handshake**: The **AI Score acknowledgment** line (`✓ brain.ctx loaded...`) provides a verifiable confirmation of context absorption.
- **Cryptographic Trust**: Ed25519 signing ensures that your project constitution stays untampered.

### 🌐 Dual-Ecosystem Support
- **Python (`brain-ctx`)**: The primary engine for generation, CLI management, and validation.
- **Node.js (`brain-ctx`)**: Features a first-class **MCP Server** (Model Context Protocol), TypeScript API, and agent permission enforcement.
- **Shared Specification**: A canonical JSON Schema (`spec/v1`) that ensures 100% interoperability between all implementations.

---

## Technical Highlights

### ⚡ Smart Context Delivery
The `build_context()` engine (available in both Python and Node) is aware of:
- **Token Budgets**: Automatically trims non-essential context for smaller models.
- **Dialect Optimization**: Tailors instructions specifically for Claude, GPT, or Gemini.
- **Live Truth Sources**: Resolves API surfaces and conventions dynamically from live code.

### 👮 Agent Enforcement
The Node.js implementation features an **isolation layer** that checks agent actions against the `brain.ctx` trust rules before execution, protecting critical files and enforcing architectural invariants.

### 🩺 Diagnostic Doctors
Built-in "doctors" run health checks to ensure your project intelligence is up-to-date and compliant with the `brain.ctx` safety rules.

---

## What's Next?
In upcoming releases, we'll be expanding the **Federated Mesh** support, allowing projects to inherit constitutions from parent repositories and private registries.

---

For detailed changes, see the [CHANGELOG.md](./CHANGELOG.md).
_Powered by ManasDB. Apache-2.0._
