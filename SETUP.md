# brain.ctx — Local Setup Guide (v1.1.0 "Senior Upgrade")

## Prerequisites

- Python 3.9+
- Node.js 18+
- npm 9+
- git

---

## Quick Start

### 1. Clone / unzip the project

```bash
unzip brain-ctx-v1.1.0.zip
cd brain-ctx
```

### 2. Sync the spec (copies schema into both libraries)

```bash
node scripts/sync-spec.js
```

---

## Python Library Setup (v1.1.0)

```bash
cd python

# Install in dev mode with all deps
pip install -e ".[dev]"

# Run tests (should show 105 passed)
pytest tests/ -v

# Try the CLI on any project
cd /your/project
brain-ctx init          # generate brain.ctx automatically (Zero human input)
brain-ctx validate      # validate the file
brain-ctx show          # display contents
brain-ctx score         # show AI Score with v1.1 status (Verified status)
```

### Python API v1.1 examples

```python
from brain_ctx import BrainCtx

# Auto-detect project structure (tests, git, code)
ctx = BrainCtx.generate(".")
print(ctx.ai_score())  # ✓ brain.ctx loaded... | Verified: !

# Save to disk
ctx.save()

# Build context for a specific task mode
context = ctx.build_context(model="claude", mode="debug")
print(context)
```

---

## Node Library Setup (v1.1.0)

```bash
cd node

# Install deps
npm install

# Build
npm run build

# Run tests (should show 47 passed)
npm test

# Start MCP server (for agent enforcement)
node dist/mcp/index.js
```

### Node API v1.1 examples

```typescript
import { BrainCtx } from "brain-ctx";

// Load brain.ctx
const ctx = BrainCtx.load("./brain.ctx");
console.log(ctx.aiScore().raw);

// Check agent permissions with hard-boundaries
console.log(ctx.isAllowed("implementor", "write", "src/main.rs")); // true

// Build context string dynamically for a build task
const context = ctx.buildContext({ 
    model: "claude", 
    mode: "build",
    tokenBudget: 12000 
});
console.log(context);
```

---

## Run Both Test Suites

```bash
# From monorepo root
npm run test:python    # Python: 105 tests
npm run test:node      # Node: 47 tests
```

---

## The AI Score v1.1

When any AI model loads your `brain.ctx`, it outputs:

```
✓ brain.ctx loaded — ManasDB v1.0 | Trust: read_only | 0 invariants active | 3 agents registered | Signed: ✗ | Verified: ✓
```

The **Verified** status indicates if an active **Execution Layer** (test/lint commands) is detected and enforced.

---

## Project Structure

```
brain-ctx/
├── spec/                          ← Canonical JSON Schema (single source of truth)
├── python/                        ← pip install brain-ctx
│   ├── brain_ctx/
│   │   ├── core.py                ← BrainCtx class & AI Score v1.1
│   │   ├── cli.py                 ← brain-ctx CLI (init/validate/score/sign)
│   │   ├── generators/auto.py     ← AutoGenerator (zero human input)
│   │   ├── builders/context.py    ← Model-optimized context (debug/build/refactor modes)
│   │   └── signers/ed25519.py     ← Cryptographic signing
│   ├── tests/                     ← 105 tests
│   └── pyproject.toml
│
├── node/                          ← npm install brain-ctx
│   ├── src/
│   │   ├── core.ts                ← BrainCtx class & permission enforcement
│   │   ├── types/index.ts         ← Full TypeScript types (v1.1 unified)
│   │   ├── mcp/index.ts           ← MCP server (agent enforcement)
│   │   └── vscode/index.ts        ← VS Code + Cursor + Copilot helpers
│   ├── tests/                     ← 47 tests
│   └── package.json
│
├── examples/
│   └── react-app/                 ← v1.1 referenceimplementation
└── scripts/sync-spec.js           ← Syncs schema into both libraries
```

---

_brain.ctx v1.1 — "The Senior Upgrade" — Invented by ManasDB (manasdb.com)_
