# Release Notes: v1.1.0 — "The Senior Upgrade"

The `brain.ctx` standard is evolving from an advisory context file upwards to an **Enforced Intelligence Layer**. The v1.1.0 release introduces major architectural improvements to ensure AI agents operate with more authority, precision, and verifiability.

---

## Core Pillars of v1.1.0

### 🚀 The Execution Layer (`verification`)
We've added a formal property block for test, lint, and build commands. AI agents are now expected to **prove** their changes work by running these commands before proposing edits, bridging the gap between "suggested code" and "proven code."

### 🧠 Task-Specific Cognitive Modes
Context delivery is no longer static. With **Cognitive Modes**, the system dynamically shifts priorities based on the task:
- **Debug Mode**: Prioritizes logs, invariants, and hard rules.
- **Build Mode**: Focuses on API surfaces, dependencies, and trust configurations.
- **Refactor Mode**: Centers on architectural decisions and project timeline.

### 🛡️ Authoritative Enforcement
Our trust model is moving from passive guidance to hard boundaries:
- **Operational Invariants**: Encouraging the use of `ALWAYS`/`NEVER` patterns in `hard_rules` for absolute compliance.
- **Enforced MCP Layer**: Strengthened the Node.js implementation to hard-block unauthorized file access and actions.
- **Validation-First Inference**: Defaulted all inference to `propose_only` with required human/test validation to prevent knowledge drift.

---

## Technical Highlights

### 🩺 Auto-Detected Verification
The `brain-ctx init` CLI now automatically detects your tech stack (pytest, npm, ruff, tsc) and populates the `verification` block — zero manual setup required.

### 🏁 AI Score v1.1
A new `Verified` status marker has been added to the AI Score handshake, allowing teams to see at a glance if a project constitution is backed by an active execution layer.

### 🛡️ Generator Reliability
We've eliminated "Dead References" and ensured reactive agent roles. If your project doesn't have `hard_rules` or `mutex_files`, the generator now correctly omits them from the cognitive optimizer's priority list.

### ✨ CLI UX Polish
The `brain-ctx init` experience is now more fluid, with scanned intelligence gathered behind a status spinner that finishes completely before prompting for any optional human input.


---

## What's Next?
We are working on bringing these "Senior" patterns to the **vscode context explorer** and expanding the **diagnostic engine** to audit rule-compliance automatically.

---

For detailed changes, see the [CHANGELOG.md](./CHANGELOG.md).
_Powered by ManasDB. Apache-2.0._
