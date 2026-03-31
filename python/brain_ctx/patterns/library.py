"""
Language Pattern Library
========================
Curated patterns for extracting API surfaces, public methods,
and entry points from 20+ languages and frameworks.

Used by AutoGenerator to produce accurate truth_sources
without hardcoding a single language.

Each pattern set includes:
  - api_pattern:    what to scan for public API exports
  - entry_files:    where the entry point likely lives
  - test_dirs:      where tests are expected
  - mutex_keywords: file name patterns that are usually critical
  - framework_hint: how to detect this stack from package files

Usage:
    detector = StackDetector(project_root)
    stacks   = detector.detect()
    for stack in stacks:
        print(stack.name, stack.api_pattern)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class StackPattern:
    """Pattern definition for a single language/framework."""
    name:             str
    language:         str
    api_pattern:      str                      # regex for public API lines
    entry_files:      list[str]                # ordered by preference
    test_dirs:        list[str]
    mutex_keywords:   list[str]                # file stem keywords → mutex
    never_touch_exts: list[str]                # extensions → never_touch
    confidence:       float = 0.0             # set by detector
    detected_entry:   Optional[str] = None    # actual file found
    extras:           dict  = field(default_factory=dict)


# ── Pattern definitions ────────────────────────────────────────
# Ordered from most specific to most generic within each language.

PATTERNS: list[StackPattern] = [

    # ── Rust ──────────────────────────────────────────────────
    StackPattern(
        name="Rust Library",
        language="rust",
        api_pattern=r"^pub (fn|struct|enum|trait|type|const|mod) ",
        entry_files=["src/lib.rs", "src/main.rs"],
        test_dirs=["tests/", "src/"],
        mutex_keywords=["wal", "journal", "mvcc", "transaction", "container",
                        "storage", "index", "hnsw", "btree"],
        never_touch_exts=[".lock"],
        extras={"cargo_check": "Cargo.toml"},
    ),

    # ── Node.js / TypeScript ───────────────────────────────────
    StackPattern(
        name="Node.js / TypeScript",
        language="typescript",
        api_pattern=r"^export (function|class|const|let|default|type|interface)",
        entry_files=[
            "src/index.js", "src/index.ts",   # .js first — prefer compiled output
            "lib/index.js", "lib/index.ts",
            "index.js",     "index.ts",
        ],
        test_dirs=["tests/", "test/", "__tests__/", "spec/"],
        mutex_keywords=["auth", "payment", "webhook", "wal", "migration",
                        "transaction", "session", "token"],
        never_touch_exts=[".env", ".pem", ".key", ".lock"],
        extras={"package_check": "package.json"},
    ),

    # ── Express.js ────────────────────────────────────────────
    StackPattern(
        name="Express.js API",
        language="javascript",
        api_pattern=r"router\.(get|post|put|patch|delete)\(",
        entry_files=[
            "src/routes/index.ts", "src/routes/index.js",
            "routes/index.ts",     "routes/index.js",
            "src/app.ts",          "src/app.js",
        ],
        test_dirs=["tests/", "test/", "__tests__/"],
        mutex_keywords=["auth", "middleware", "payment", "webhook",
                        "session", "rate-limit"],
        never_touch_exts=[".env", ".lock"],
        extras={"detect_from": "express"},
    ),

    # ── FastAPI ───────────────────────────────────────────────
    StackPattern(
        name="FastAPI",
        language="python",
        api_pattern=r"@(app|router)\.(get|post|put|patch|delete|websocket)\(",
        entry_files=["main.py", "app/main.py", "src/main.py", "api/main.py"],
        test_dirs=["tests/", "test/"],
        mutex_keywords=["auth", "deps", "dependencies", "middleware",
                        "database", "models", "payment"],
        never_touch_exts=[".env", ".key", ".pem"],
        extras={"detect_from": "fastapi"},
    ),

    # ── Django ────────────────────────────────────────────────
    StackPattern(
        name="Django",
        language="python",
        api_pattern=r"^(class \w+View|def (get|post|put|patch|delete|list|create|retrieve))",
        entry_files=[
            "urls.py", "*/urls.py",
            "views.py", "*/views.py",
        ],
        test_dirs=["tests/", "*/tests/"],
        mutex_keywords=["models", "migrations", "settings", "urls",
                        "middleware", "auth", "payment"],
        never_touch_exts=[".env", ".key", ".sqlite3"],
        extras={"detect_from": "django", "detect_file": "manage.py"},
    ),

    # ── Flask ─────────────────────────────────────────────────
    StackPattern(
        name="Flask",
        language="python",
        api_pattern=r"@(app|blueprint)\.(route|get|post|put|patch|delete)\(",
        entry_files=["app.py", "main.py", "src/app.py", "application.py"],
        test_dirs=["tests/", "test/"],
        mutex_keywords=["auth", "models", "config", "payment", "session"],
        never_touch_exts=[".env", ".key", ".db"],
        extras={"detect_from": "flask"},
    ),

    # ── Python Library (generic) ──────────────────────────────
    StackPattern(
        name="Python Library",
        language="python",
        api_pattern=r"^(def |class )[a-zA-Z]",
        entry_files=["src/__init__.py", "__init__.py", "*/src/__init__.py"],
        test_dirs=["tests/", "test/"],
        mutex_keywords=["core", "base", "engine", "main", "api",
                        "client", "session"],
        never_touch_exts=[".env", ".key", ".pyc"],
        extras={"detect_from": "pyproject.toml"},
    ),

    # ── Go ────────────────────────────────────────────────────
    StackPattern(
        name="Go",
        language="go",
        api_pattern=r"^func [A-Z][a-zA-Z]*\(",
        entry_files=["main.go", "cmd/main.go", "cmd/*/main.go"],
        test_dirs=["", "tests/"],   # Go tests are in the same directory
        mutex_keywords=["handler", "middleware", "auth", "store",
                        "repository", "transaction", "migration"],
        never_touch_exts=[".env", ".key", ".pem"],
        extras={"detect_file": "go.mod"},
    ),

    # ── Gin (Go web framework) ────────────────────────────────
    StackPattern(
        name="Gin (Go)",
        language="go",
        api_pattern=r"\.(GET|POST|PUT|PATCH|DELETE|Any)\(",
        entry_files=["main.go", "cmd/server/main.go", "internal/router/*.go"],
        test_dirs=[""],
        mutex_keywords=["middleware", "auth", "payment", "handler"],
        never_touch_exts=[".env", ".key"],
        extras={"detect_from": "gin"},
    ),

    # ── React / Next.js ───────────────────────────────────────
    StackPattern(
        name="React / Next.js",
        language="typescript",
        api_pattern=r"^export (default function|function|const) [A-Z]",
        entry_files=[
            "src/App.tsx", "src/App.jsx",
            "pages/_app.tsx", "pages/_app.jsx",
            "app/layout.tsx", "app/page.tsx",
        ],
        test_dirs=["__tests__/", "tests/", "src/__tests__/"],
        mutex_keywords=["auth", "api", "middleware", "layout",
                        "provider", "context", "store"],
        never_touch_exts=[".env.local", ".env.production", ".key"],
        extras={"detect_from": ["react", "next"]},
    ),

    # ── NestJS ────────────────────────────────────────────────
    StackPattern(
        name="NestJS",
        language="typescript",
        api_pattern=r"@(Get|Post|Put|Patch|Delete|Controller|Injectable|Module)\(",
        entry_files=["src/main.ts", "src/app.module.ts"],
        test_dirs=["test/", "src/**/*.spec.ts"],
        mutex_keywords=["auth", "guard", "middleware", "interceptor",
                        "payment", "transaction", "database"],
        never_touch_exts=[".env", ".key", ".pem"],
        extras={"detect_from": "@nestjs/core"},
    ),

    # ── Spring Boot (Java) ────────────────────────────────────
    StackPattern(
        name="Spring Boot",
        language="java",
        api_pattern=r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping|RestController)",
        entry_files=[
            "src/main/java/**/Application.java",
            "src/main/java/**/Controller/*.java",
        ],
        test_dirs=["src/test/java/"],
        mutex_keywords=["Repository", "Service", "Controller",
                        "Config", "Security", "Migration"],
        never_touch_exts=[".env", ".key", ".jks"],
        extras={"detect_file": "pom.xml"},
    ),

    # ── Laravel (PHP) ─────────────────────────────────────────
    StackPattern(
        name="Laravel",
        language="php",
        api_pattern=r"(Route::(get|post|put|patch|delete)|public function (get|post|store|update|destroy|index|show))",
        entry_files=["routes/api.php", "routes/web.php", "app/Http/Controllers/"],
        test_dirs=["tests/"],
        mutex_keywords=["Migration", "Auth", "Payment", "Middleware",
                        "Model", "Service"],
        never_touch_exts=[".env", ".key", ".lock"],
        extras={"detect_file": "artisan"},
    ),

    # ── Ruby on Rails ─────────────────────────────────────────
    StackPattern(
        name="Ruby on Rails",
        language="ruby",
        api_pattern=r"(resources?|get|post|put|patch|delete) ['\"]",
        entry_files=["config/routes.rb", "app/controllers/application_controller.rb"],
        test_dirs=["spec/", "test/"],
        mutex_keywords=["migration", "schema", "auth", "payment",
                        "session", "middleware"],
        never_touch_exts=[".env", ".key", ".lock"],
        extras={"detect_file": "Gemfile"},
    ),

    # ── Terraform ─────────────────────────────────────────────
    StackPattern(
        name="Terraform",
        language="hcl",
        api_pattern=r"^(resource|module|variable|output|data) \"",
        entry_files=["main.tf", "variables.tf", "outputs.tf"],
        test_dirs=["tests/", "test/"],
        mutex_keywords=["main", "backend", "provider", "state",
                        "production", "prod", "secrets"],
        never_touch_exts=[".tfstate", ".tfstate.backup", ".key"],
        extras={"detect_ext": ".tf"},
    ),

    # ── Kubernetes / Helm ─────────────────────────────────────
    StackPattern(
        name="Kubernetes / Helm",
        language="yaml",
        api_pattern=r"^(kind|apiVersion|name):",
        entry_files=[
            "k8s/*.yaml", "manifests/*.yaml",
            "charts/*/templates/*.yaml",
            "helm/*/values.yaml",
        ],
        test_dirs=["tests/", "test/"],
        mutex_keywords=["secret", "configmap", "rbac", "ingress",
                        "production", "prod", "service-account"],
        never_touch_exts=[".key", ".pem", ".crt"],
        extras={"detect_file": "Chart.yaml"},
    ),

    # ── GraphQL (Apollo / Pothos) ─────────────────────────────
    StackPattern(
        name="GraphQL API",
        language="typescript",
        api_pattern=r"(type Query|type Mutation|type Subscription|builder\.(queryField|mutationField))",
        entry_files=[
            "src/schema.ts", "src/schema/index.ts",
            "graphql/schema.ts", "src/graphql/*.ts",
        ],
        test_dirs=["tests/", "__tests__/"],
        mutex_keywords=["resolver", "schema", "auth", "directive",
                        "permission", "middleware"],
        never_touch_exts=[".env", ".key"],
        extras={"detect_from": ["graphql", "apollo-server", "@pothos/core"]},
    ),

    # ── Solidity / Smart Contracts ────────────────────────────
    StackPattern(
        name="Solidity / Smart Contracts",
        language="solidity",
        api_pattern=r"^    (function|event|modifier|error) [a-zA-Z]",
        entry_files=["contracts/*.sol", "src/*.sol"],
        test_dirs=["test/", "tests/"],
        mutex_keywords=["token", "vault", "proxy", "upgrade",
                        "governance", "timelock", "multisig"],
        never_touch_exts=[".key", ".env"],
        extras={"detect_file": "hardhat.config.ts"},
    ),

    # ── ML / Python Data Science ──────────────────────────────
    StackPattern(
        name="ML / Data Science",
        language="python",
        api_pattern=r"^(def (train|predict|evaluate|fit|transform|preprocess)|class \w+Model)",
        entry_files=[
            "train.py", "predict.py",
            "src/train.py", "src/model.py",
            "notebooks/*.ipynb",
        ],
        test_dirs=["tests/", "test/"],
        mutex_keywords=["model", "checkpoint", "weights", "config",
                        "dataset", "pipeline"],
        never_touch_exts=[".ckpt", ".pth", ".h5", ".pkl", ".key"],
        extras={"detect_from": ["torch", "tensorflow", "sklearn"]},
    ),
]

# ── Detector ───────────────────────────────────────────────────

class StackDetector:
    """
    Detects what stacks/frameworks a project uses and returns
    the relevant StackPatterns, sorted by confidence.

    Example:
        detector = StackDetector(Path("."))
        stacks   = detector.detect()
        primary  = stacks[0]
        print(primary.name, primary.api_pattern)
    """

    def __init__(self, project_root: Path):
        self.root = project_root.resolve()

    def detect(self) -> list[StackPattern]:
        """
        Detect stacks used in this project.
        Returns patterns sorted by confidence (highest first).
        """
        import copy
        results: list[StackPattern] = []

        pkg_deps      = self._read_npm_deps()
        python_deps   = self._read_python_deps()
        existing_files = self._list_key_files()

        for pattern in PATTERNS:
            p = copy.deepcopy(pattern)
            confidence = self._score(p, pkg_deps, python_deps, existing_files)
            if confidence > 0:
                p.confidence       = confidence
                p.detected_entry   = self._find_entry(p)
                results.append(p)

        return sorted(results, key=lambda p: p.confidence, reverse=True)

    def detect_primary(self) -> Optional[StackPattern]:
        """Return the single best-matching stack pattern."""
        stacks = self.detect()
        return stacks[0] if stacks else None

    def _score(
        self,
        pattern:   StackPattern,
        pkg_deps:  set[str],
        py_deps:   set[str],
        files:     set[str],
    ) -> float:
        score = 0.0
        extras = pattern.extras

        # File-based detection (strongest signal)
        detect_file = extras.get("detect_file", "")
        detect_ext  = extras.get("detect_ext", "")
        if detect_file and (self.root / detect_file).exists():
            score += 0.6
        if detect_ext:
            if any(f.endswith(detect_ext) for f in files):
                score += 0.5

        # Entry file existence
        for ef in pattern.entry_files:
            if "*" in ef:
                if list(self.root.rglob(ef)):
                    score += 0.3
                    break
            elif (self.root / ef).exists():
                score += 0.4
                break

        # npm dependency detection
        detect_from = extras.get("detect_from", [])
        if isinstance(detect_from, str):
            detect_from = [detect_from]
        for dep in detect_from:
            if dep in pkg_deps:
                score += 0.5

        # pyproject / requirements detection
        cargo_check = extras.get("cargo_check", "")
        if cargo_check and (self.root / cargo_check).exists():
            score += 0.5

        # Python dep check
        if pattern.language == "python":
            dep_name = extras.get("detect_from", "")
            if isinstance(dep_name, str) and dep_name in py_deps:
                score += 0.5
            elif pattern.name == "Python Library":
                if (self.root / "pyproject.toml").exists() or (self.root / "setup.py").exists():
                    score += 0.3

        return min(score, 1.0)

    def _find_entry(self, pattern: StackPattern) -> Optional[str]:
        """Find the first existing entry file for a pattern."""
        for ef in pattern.entry_files:
            if "*" in ef:
                matches = list(self.root.rglob(ef))
                if matches:
                    return str(matches[0].relative_to(self.root))
            else:
                if (self.root / ef).exists():
                    return ef
        return None

    def _read_npm_deps(self) -> set[str]:
        pkg_path = self.root / "package.json"
        if not pkg_path.exists():
            return set()
        try:
            pkg  = json.loads(pkg_path.read_text())
            deps = set(pkg.get("dependencies",    {}).keys())
            deps |= set(pkg.get("devDependencies", {}).keys())
            return deps
        except Exception:
            return set()

    def _read_python_deps(self) -> set[str]:
        deps: set[str] = set()
        req_path = self.root / "requirements.txt"
        if req_path.exists():
            for line in req_path.read_text().splitlines():
                line = line.strip().split("==")[0].split(">=")[0].split("[")[0]
                if line and not line.startswith("#"):
                    deps.add(line.lower())
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                return deps
        pyproject = self.root / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text())
                for dep in data.get("project", {}).get("dependencies", []):
                    name = dep.split(">=")[0].split("==")[0].split("[")[0].strip().lower()
                    deps.add(name)
            except Exception:
                pass
        return deps

    def _list_key_files(self) -> set[str]:
        result: set[str] = set()
        skip = {"node_modules", ".git", "dist", "build", "target", "__pycache__"}
        try:
            for item in self.root.rglob("*"):
                if any(s in item.parts for s in skip):
                    continue
                result.add(item.name)
                result.add(str(item.relative_to(self.root)))
        except Exception:
            pass
        return result
