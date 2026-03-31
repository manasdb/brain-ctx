# brain.ctx — Local Setup Guide

## Prerequisites
- Python 3.9+
- Node.js 18+
- npm 9+
- git

---

## Quick Start

### 1. Clone / unzip the project
```bash
unzip brain-ctx-v1.0.zip
cd brain-ctx
```

### 2. Sync the spec (copies schema into both libraries)
```bash
node scripts/sync-spec.js
```

---

## Python Library Setup

```bash
cd python

# Install in dev mode with all deps
pip install -e ".[dev]"

# Run tests (should show 46 passed)
pytest tests/ -v

# Try the CLI on any project
cd /your/project
brain-ctx init          # generate brain.ctx automatically
brain-ctx validate      # validate the file
brain-ctx show          # display contents
brain-ctx score         # show AI Score

# Optional: install signing support
pip install brain-ctx[signing]
brain-ctx sign --key ~/.brain-ctx/private.key
```

### Python API quick test
```python
from brain_ctx import BrainCtx

# Generate for current project
ctx = BrainCtx.generate(".")
print(ctx.ai_score())
ctx.save()

# Load existing
ctx = BrainCtx.load("./brain.ctx")
print(ctx.identity)
print(ctx.hard_rules)

# Build context for AI
context = ctx.build_context(model="claude", token_budget=12000)
print(context)
```

---

## Node Library Setup

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
# OR via npx after publishing:
# npx brain-ctx-mcp
```

### Node API quick test
```typescript
import { BrainCtx } from "brain-ctx"

// Load brain.ctx
const ctx = BrainCtx.load("./brain.ctx")
console.log(ctx.aiScore().raw)

// Check agent permissions
console.log(ctx.isAllowed("implementor", "write", "src/main.rs"))  // true
console.log(ctx.isAllowed("implementor", "write", "prod.manas"))   // false

// Build context string for any AI model
const context = ctx.buildContext({ model: "claude", tokenBudget: 12000 })
console.log(context)

// VS Code integration
import { syncAiToolBridges } from "brain-ctx/vscode"
syncAiToolBridges(ctx, process.cwd())
// Creates: .cursorrules + .github/copilot-instructions.md
```

---

## Run Both Test Suites

```bash
# From monorepo root
npm run test:python    # Python: 46 tests
npm run test:node      # Node: 47 tests
```

---

## Try It On ManasDB's brain.ctx

```bash
# Validate the reference implementation
brain-ctx validate examples/manasdb/brain.ctx

# Load and inspect via Python
python3 -c "
from brain_ctx import BrainCtx
ctx = BrainCtx.load('examples/manasdb/brain.ctx')
print(ctx.ai_score())
print('Rules:', ctx.hard_rules)
print('Trust:', ctx.trust)
"

# Load and inspect via Node
node -e "
const { BrainCtx } = require('./node/dist/index.js')
const ctx = BrainCtx.load('./examples/manasdb/brain.ctx')
console.log(ctx.aiScore().raw)
console.log('Allowed to write WAL?', ctx.isAllowed('implementor', 'write', 'src/wal.rs'))
"
```

---

## Project Structure

```
brain-ctx/
├── spec/                          ← Canonical JSON Schema (single source of truth)
│   └── brain-ctx.schema.json
│
├── python/                        ← pip install brain-ctx
│   ├── brain_ctx/
│   │   ├── core.py                ← BrainCtx class
│   │   ├── cli.py                 ← brain-ctx CLI
│   │   ├── generators/auto.py     ← AutoGenerator (zero human input)
│   │   ├── generators/updater.py  ← UpdateProposer
│   │   ├── parsers/               ← loader + writer
│   │   ├── validators/schema.py   ← JSON Schema validation
│   │   ├── signers/ed25519.py     ← Cryptographic signing
│   │   └── builders/context.py    ← Model-optimized context builder
│   ├── tests/test_brain_ctx.py    ← 46 tests
│   └── pyproject.toml
│
├── node/                          ← npm install brain-ctx
│   ├── src/
│   │   ├── core.ts                ← BrainCtx class
│   │   ├── types/index.ts         ← Full TypeScript types
│   │   ├── parser/index.ts        ← YAML read/write/merge
│   │   ├── validator/index.ts     ← AJV schema validation
│   │   ├── vscode/index.ts        ← VS Code + Cursor + Copilot helpers
│   │   ├── mcp/index.ts           ← MCP server (agent enforcement)
│   │   └── postinstall.ts         ← npm install hook
│   ├── tests/brain-ctx.test.ts    ← 47 tests
│   └── package.json
│
├── examples/
│   └── manasdb/brain.ctx          ← First real-world brain.ctx (reference)
│
├── scripts/sync-spec.js           ← Syncs schema into both libraries
└── README.md
```

---

## Spec Location

The JSON Schema lives at `spec/brain-ctx.schema.json`.
It is automatically copied into:
- `python/brain_ctx/spec/brain-ctx.schema.json`
- `node/src/spec/brain-ctx.schema.json`

Run `node scripts/sync-spec.js` after any schema change.

---

*brain.ctx v1.0 — Invented by Bomberedman / ManasDB (manasdb.com)*
