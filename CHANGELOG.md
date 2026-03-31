# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-03-31

### Added
- **Execution Layer (`verification`)**: Added a formal property block for test, lint, and build commands to prove code correctness.
- **Task-Specific Cognitive Modes**: Initial support for `debug`, `build`, and `refactor` modes in context builders to prioritize focus dynamically.
- **Authoritative Enforcement**: Strengthened the `isAllowed` and `McpServer` logic to move from advisory guidance to hard boundaries.
- **Auto-Detection for Verification**: The `brain-ctx init` CLI now automatically detects test/build stacks (pytest, npm, tsc) to populate verification hooks.
- **CLI UX Polish**: Sequenced the scanning process to finish status spinners before prompting for optional questions, preventing terminal overlapping.


### Changed
- **Operational Invariants**: Standardized `hard_rules` to use `ALWAYS`/`NEVER` patterns for more consistent AI compliance.
- **Inference Stability**: Defaulted `inference.mode` to `propose_only` with `require_validation: true` to prevent unvalidated knowledge drift.
- **AI Score v1.1**: Added a `Verified` status marker to the score handshake to signal project health at a glance.

### Fixed
- **Generator Reliability**: Eliminated "Dead References" in `cognitive` defaults by dynamically filtering missing sections (e.g., `hard_rules`, `verification`).
- **Reactive Roles**: Agent restrictions like `touch_mutex_files` are now only applied if the project actually contains mutex files.


## [1.0.0] - 2026-03-31


### Added
- **Generic AI Constitution Standard**: Initial public release of `brain.ctx` as a language-agnostic specification for project intelligence.
- **Python Library (`brain-ctx`)**: Core implementation for automated context generation, cryptographic signing, and CLI tools.
- **Node.js Library (`brain-ctx`)**: Implementation for MCP (Model Context Protocol) servers, TypeScript API, and agent permission enforcement.
- **Self-Maintaining Intelligence**: Automated scanning with `brain-ctx init` that requires zero manual input to build project context.
- **AI Score Handshake**: Standardized acknowledgment line (`✓ brain.ctx loaded...`) for AI models to confirm context absorption.
- **Granular Trust Layer**: Fine-grained safety controls with `never_touch`, `mutex_files`, and role-based permissions.
- **Cognitive Priority Tiers**: Multi-level context building (Critical > Important > Reference) with native token-budget awareness.
- **Dialect Support**: Model-specific instructions and optimization for Claude, GPT-4, Gemini, and local LLMs.
- **Cryptographic Trust**: Ed25519 signing for verified project constitutions.

### Changed
- **Branding**: Rebranded from internal ManasDB project tools to the generic `brain-ctx` AI Construction Standard.
- **Schema**: Migrated to a centralized JSON Schema (`spec/v1/schema.json`) shared across all implementations.
- **Documentation**: Overhauled README and introduced comprehensive guides for both Python and Node.js ecosystems.

### Fixed
- **Legacy Cleanup**: Removed all project-specific artifacts (e.g., `.wal`, `.manas`) from the generic codebase and test suites.
- **Node.js Tests**: Stabilized the TypeScript test suite to be environment-independent.
- **Windows Support**: Resolved file-locking and path encoding issues for cross-platform reliability.

---

[1.0.0]: https://github.com/manasdb/brain-ctx/releases/tag/v1.0.0
