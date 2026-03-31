"""
AutoGenerator — The core of brain.ctx.

Scans a project and produces a complete brain.ctx automatically.
Zero mandatory human input. One optional question maximum.

Scan order:
    1. Package files  → identity, stack
    2. README         → vision, description
    3. Git history    → hard_rules, temporal, patterns
    4. Source files   → truth_sources, api_surface
    5. Test files     → invariants
    6. .gitignore     → ethics (security patterns)
    7. LLM synthesis  → vision inference, rule formulation
    8. Optional prompt → "Anything AI must NEVER do?"
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import yaml


class AutoGenerator:
    """
    Fully automatic brain.ctx generator.
    Reads the project, infers everything, asks nothing (or one question).
    """

    def __init__(self, project_path: Path):
        self.root      = project_path.resolve()
        self.proposals: list[dict] = []    # low-confidence proposals queue
        self.confidence: dict[str, float] = {}

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def run(self, interactive: bool = True) -> "BrainCtx":
        from brain_ctx.core import BrainCtx

        ctx = BrainCtx()

        # Run all scanners
        self._scan_identity(ctx)
        self._scan_stack(ctx)
        self._scan_git(ctx)
        self._scan_sources(ctx)
        self._scan_tests(ctx)
        self._scan_ethics(ctx)
        self._build_inference_config(ctx)
        self._build_cognitive_defaults(ctx)
        self._build_observability_defaults(ctx)

        # One optional human question
        if interactive and sys.stdin.isatty():
            self._ask_one_question(ctx)

        return ctx

    # ──────────────────────────────────────────────────────────
    # Scanner 1 — Identity
    # ──────────────────────────────────────────────────────────

    def _scan_identity(self, ctx) -> None:
        """Infer project name, vision, domain, author from project files."""
        identity: dict[str, Any] = {}

        # ── Name ──────────────────────────────────────────────
        name = (
            self._from_package_json("name")
            or self._from_cargo_toml("name")
            or self._from_pyproject("name")
            or self.root.name  # fallback: folder name
        )
        identity["name"] = self._clean_package_name(name)

        # ── Author ────────────────────────────────────────────
        author = (
            self._from_package_json("author")
            or self._from_cargo_toml("authors", first=True)
            or self._from_pyproject("authors", first=True)
            or self._from_git_config("user.name")
        )
        if author:
            identity["author"] = author

        # ── Domain ────────────────────────────────────────────
        domain = (
            self._from_package_json("homepage")
            or self._from_readme_url()
            or self._from_cname_file()
        )
        if domain:
            identity["domain"] = self._clean_url(domain)

        # ── Vision ────────────────────────────────────────────
        vision = self._infer_vision(identity.get("name", ""))
        if vision:
            identity["vision"] = vision

        # ── License ───────────────────────────────────────────
        license_ = (
            self._from_package_json("license")
            or self._from_cargo_toml("license")
            or self._detect_license_file()
        )
        if license_:
            identity["license"] = license_

        ctx.identity = identity
        self.confidence["identity"] = 0.9

    def _infer_vision(self, project_name: str) -> Optional[str]:
        """
        Extract vision/tagline from README headline or package description.
        Tries multiple sources, takes the most descriptive.
        """
        candidates: list[str] = []

        # README first line / H1
        readme = self._read_readme()
        if readme:
            for line in readme.split("\n")[:20]:
                line = line.strip().lstrip("#").strip()
                if (
                    len(line) > 10
                    and len(line) < 120
                    and project_name.lower() not in line.lower()[:10]
                    and not line.startswith("!")   # skip badge lines
                    and not line.startswith("[")   # skip link lines
                ):
                    candidates.append(line)
                    break

        # Package description
        for getter in [
            lambda: self._from_package_json("description"),
            lambda: self._from_cargo_toml("description"),
            lambda: self._from_pyproject("description"),
        ]:
            val = getter()
            if val and isinstance(val, str) and len(val) > 10:
                candidates.append(val)

        if not candidates:
            return None

        # Return shortest meaningful candidate (taglines are concise)
        return min(candidates, key=lambda x: abs(len(x) - 60))

    # ──────────────────────────────────────────────────────────
    # Scanner 2 — Stack / Dependencies
    # ──────────────────────────────────────────────────────────

    def _scan_stack(self, ctx) -> None:
        """
        Detect tech stack using the pattern library.
        Supports 20+ languages and frameworks automatically.
        """
        from brain_ctx.patterns.library import StackDetector

        detector = StackDetector(self.root)
        stacks   = detector.detect()

        truth_sources: dict[str, Any] = {}

        if stacks:
            primary = stacks[0]
            # Use the pattern library's detected entry file
            infer_from = primary.detected_entry or (
                primary.entry_files[0] if primary.entry_files else "src/index.ts"
            )
            truth_sources["api_surface"] = {
                "infer_from":   infer_from,
                "pattern":      primary.api_pattern,
                "auto_extract": True,
                "stack":        primary.name,
            }
            # Secondary stacks (e.g. Python bindings on a Rust core)
            for secondary in stacks[1:3]:
                if secondary.name != primary.name and secondary.detected_entry:
                    key = f"api_surface_{secondary.language}"
                    truth_sources[key] = {
                        "infer_from":   secondary.detected_entry,
                        "pattern":      secondary.api_pattern,
                        "auto_extract": True,
                        "stack":        secondary.name,
                    }
            # Store detected never_touch extensions
            all_exts: set[str] = set()
            all_mutex_kws: set[str] = set()
            for s in stacks[:3]:
                all_exts.update(s.never_touch_exts)
                all_mutex_kws.update(s.mutex_keywords)
            ctx._detected_never_touch_exts = list(all_exts)
            ctx._detected_mutex_keywords   = list(all_mutex_kws)
        else:
            # Fallback for unknown stacks
            truth_sources["api_surface"] = {
                "infer_from":   "src/index.js,src/index.ts,src/lib.rs,src/__init__.py",
                "pattern":      "^(export|pub fn|def |class )",
                "auto_extract": True,
            }
            ctx._detected_never_touch_exts = []
            ctx._detected_mutex_keywords   = []

        # Universal truth sources — always present regardless of stack
        truth_sources["conventions"] = {
            "infer_from": ".git/commits",
            "last_n":     100,
            "auto_learn": True,
        }
        truth_sources["invariants"] = {
            "infer_from":    "tests/",
            "pattern":       "test_invariant_*",
            "auto_register": True,
        }
        truth_sources["dependencies"] = {
            "infer_from":   "Cargo.toml,package.json,requirements.txt,pyproject.toml",
            "auto_extract": True,
        }

        ctx.truth_sources = truth_sources
        self.confidence["stack"] = stacks[0].confidence if stacks else 0.5

    # ──────────────────────────────────────────────────────────
    # Scanner 3 — Git History → Hard Rules
    # ──────────────────────────────────────────────────────────

    def _scan_git(self, ctx) -> None:
        """
        Mine git history for hard rules, decisions, and anti-patterns.

        Strategy:
        - Revert commits → something was tried and rejected
        - Commits with "never", "always", "fix:", "remove:" → rules
        - PRs with architectural language → decisions
        """
        hard_rules: list[str] = []
        timeline: list[dict]  = []

        try:
            import git
            repo = git.Repo(self.root)

            commits = list(repo.iter_commits(max_count=200))

            skip_rule_fragments = [
                "[[", "]]", "typeerror", "assert", "expect(", "tobe(",
                "toequal(", "pattern", "multiple of", "fall back to",
                "on cache error", "insert the text", "chunk", "pipeline on"
            ]

            for commit in commits:
                msg = commit.message.strip().lower()

                # Revert commits → something was wrong
                if msg.startswith("revert"):
                    original = commit.message.replace("Revert", "").strip().strip('"').strip("'")
                    if len(original) > 5:
                        rule = f"NEVER: reintroduce {original[:80]}"
                        if rule not in hard_rules:
                            hard_rules.append(rule)

                # Explicit rule keywords in commit messages.
                # NOTE: "must" excluded — too common in test assertion messages
                # (e.g. "must be multiple of 3", "must match entire pattern").
                rule_patterns = [
                    r"never\s+([a-z][a-z0-9 _\-]{9,59})",
                    r"always\s+([a-z][a-z0-9 _\-]{9,59})",
                    r"forbidden[:\s]+([a-z][a-z0-9 _\-]{9,59})",
                    r"do not\s+([a-z][a-z0-9 _\-]{9,59})",
                    r"removed?\s+([a-z][a-z0-9 _\-]{9,59})\s+because",
                ]
                # Skip commit messages that look like test output or changelogs
                _skip = ["[[","]]","typeerror","assert","expect(","tobe(",
                         "toequal(","pattern","multiple of","fall back to"]
                if any(s in msg for s in _skip):
                    continue
                for pattern in rule_patterns:
                    match = re.search(pattern, msg)
                    if match:
                        # Extract the core rule text
                        raw_text = match.group(1).strip()
                        raw_match = match.group(0).lower()
                        
                        # Normalize prefix
                        prefix = "NEVER" if any(kw in raw_match for kw in ["never", "forbidden", "do not", "removed"]) else "ALWAYS"
                        rule = f"{prefix}: {raw_text.capitalize()}"[:100]

                        # Skip short or obviously-noisy rules
                        if (len(rule) > 20 and
                            not any(j in rule.lower() for j in skip_rule_fragments)):
                            if rule not in hard_rules:
                                hard_rules.append(rule)

                # Architecture decisions → timeline
                arch_keywords = ["migrate", "deprecate", "introduce", "switch to",
                                  "replace", "refactor", "lock", "freeze"]
                if any(kw in msg for kw in arch_keywords):
                    timeline.append({
                        "date": commit.committed_datetime.strftime("%Y-%m"),
                        "event": commit.message.split("\n")[0][:80],
                        "hash": str(commit.hexsha)[:8],
                    })

        except Exception:
            # Git not available or not a git repo — skip silently
            pass

        # Scan source comments for explicit rules
        hard_rules.extend(self._scan_source_comments_for_rules())

        # Deduplicate and limit
        seen: set[str] = set()
        unique_rules: list[str] = []
        for rule in hard_rules:
            normalized = rule.lower()[:50]
            if normalized not in seen:
                seen.add(normalized)
                unique_rules.append(rule)

        ctx.hard_rules = unique_rules[:10]  # top 10 most important
        self.confidence["hard_rules"] = 0.75

    def _scan_source_comments_for_rules(self) -> list[str]:
        """Find explicit rules in source code comments."""
        rules: list[str] = []
        patterns = [
            r"#\s*(NEVER|ALWAYS|MUST|INVARIANT|CRITICAL)[:\s]+(.{10,80})",
            r"//\s*(NEVER|ALWAYS|MUST|INVARIANT|CRITICAL)[:\s]+(.{10,80})",
            r"/\*\s*(NEVER|ALWAYS|MUST|INVARIANT)[:\s]+(.{10,80})",
        ]
        source_extensions = {".py", ".rs", ".ts", ".js", ".go", ".java", ".cpp"}
        # Skip test dirs — test assertion strings pollute rules badly
        skip_dirs = {"tests", "test", "spec", "__tests__", "node_modules",
                     ".git", "dist", "build", "target"}
        for fpath in self.root.rglob("*"):
            # Skip if any parent directory is a test/build dir
            if any(part in skip_dirs for part in fpath.parts):
                continue
            if fpath.suffix in source_extensions and fpath.stat().st_size < 100_000:
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                    for pattern in patterns:
                        for match in re.finditer(pattern, content, re.IGNORECASE):
                            # group(2) is the actual rule text after the keyword
                            rule_text = match.group(2).strip()[:100] if match.lastindex and match.lastindex >= 2 else match.group(0).lstrip("/#* ").strip()[:100]
                            keyword = match.group(1).upper()
                            rule = f"{keyword}: {rule_text.capitalize()}"
                            # Skip test-like fragments and internal implementation notes
                            skip_rule_fragments = [
                                "[[","]]","tobe(","toequal(","assert(",
                                "multiple of","fall back","match entire",
                                "on cache error",  # implementation detail, not a constitution rule
                                "insert the text", # too specific/internal to be a hard rule
                                "chunk",           # data pipeline internals
                                "pipeline on",     # too vague without full context
                            ]
                            if (len(rule) > 20 and
                                not any(j in rule.lower() for j in skip_rule_fragments)):
                                rules.append(rule)
                except Exception:
                    continue
        return rules[:5]

    # ──────────────────────────────────────────────────────────
    # Scanner 4 — Source files → trust config
    # ──────────────────────────────────────────────────────────

    def _scan_sources(self, ctx) -> None:
        """Infer trust config and mutex files from source structure."""
        trust: dict[str, Any] = {"default": "read_only"}
        mutex_files: list[str] = []
        never_touch: list[str] = []

        # Runtime files — must never be touched regardless of project type
        # These are live process state, not build artifacts.
        for ext in [".lock", ".pid", ".sock", ".socket", ".backup"]:
            never_touch.append(f"*{ext}")

        # Also detect SQLite and other embedded db files
        for db_ext in [".db", ".sqlite", ".sqlite3"]:
            for fpath in self.root.rglob(f"*{db_ext}"):
                # Only add if not in tests/ or fixtures/
                if not any(p in {"tests","test","fixtures","mock"} for p in fpath.parts):
                    never_touch.append(f"*{db_ext}")
                    break

        # Critical source files become mutex — scan recursively for WAL-like files
        # These are the files where bugs cause data corruption.
        wal_keywords  = {"journal", "mvcc", "transaction", "container", "hnsw"}
        api_keywords  = {"__init__", "index", "lib", "exports", "public"}
        skip_mutex_dirs = {"tests","test","spec","__tests__","node_modules","dist","target","build"}

        for fpath in self.root.rglob("*.rs"):
            if any(p in skip_mutex_dirs for p in fpath.parts): continue
            if any(kw in fpath.stem.lower() for kw in wal_keywords):
                rel = str(fpath.relative_to(self.root))
                if rel not in mutex_files:
                    mutex_files.append(rel)

        for fpath in self.root.rglob("*.py"):
            if any(p in skip_mutex_dirs for p in fpath.parts): continue
            if fpath.stem == "__init__":
                # Public API files are mutex — changing them changes the contract
                rel = str(fpath.relative_to(self.root))
                if rel not in mutex_files:
                    mutex_files.append(rel)

        for pattern in ["*.ts", "*.js"]:
            for fpath in self.root.rglob(pattern):
                if any(p in skip_mutex_dirs for p in fpath.parts): continue
                if any(kw in fpath.stem.lower() for kw in wal_keywords):
                    rel = str(fpath.relative_to(self.root))
                    if rel not in mutex_files:
                        mutex_files.append(rel)

        if mutex_files:
            trust["mutex_files"] = mutex_files
        if never_touch:
            trust["never_touch"] = list(set(never_touch))

        # Default agent roles
        trust["agents"] = {
            "architect": {
                "can": ["read_all", "propose_changes"],
                "cannot": ["write", "delete"],
            },
            "implementor": {
                "can": ["write_code", "run_tests"],
                "cannot": ["change_architecture", "touch_mutex_files"],
            },
            "reviewer": {
                "can": ["read_all", "flag_violations"],
                "cannot": ["write"],
            },
        }

        ctx.trust = trust
        self.confidence["trust"] = 0.8

    # ──────────────────────────────────────────────────────────
    # Scanner 5 — Tests → invariants
    # ──────────────────────────────────────────────────────────

    def _scan_tests(self, ctx) -> None:
        """Register test files as invariants automatically."""
        # truth_sources already set up in _scan_stack
        # Here we scan actual test files and add specific invariants
        test_invariants: list[str] = []

        test_dirs = ["tests", "test", "spec", "__tests__"]
        for test_dir_name in test_dirs:
            test_dir = self.root / test_dir_name
            if not test_dir.exists():
                continue
            for fpath in test_dir.rglob("*"):
                if fpath.suffix in {".py", ".rs", ".ts", ".js"}:
                    name = fpath.stem
                    if "invariant" in name.lower():
                        test_invariants.append(str(fpath.relative_to(self.root)))

        if test_invariants:
            ctx.truth_sources["test_invariants"] = {
                "infer_from": test_invariants,
                "treat_as": "hard_invariant",
                "auto_register": True,
            }

    # ──────────────────────────────────────────────────────────
    # Scanner 6 — Ethics
    # ──────────────────────────────────────────────────────────

    def _scan_ethics(self, ctx) -> None:
        """Infer ethics config from .gitignore, .env.example, comments."""
        ethics: dict[str, Any] = {}
        never_expose: list[str] = []

        # .gitignore patterns → sensitive data hints
        gitignore = self._read_file(".gitignore") or ""
        sensitive_terms = {
            "secret": "secrets", "password": "passwords", "key": "api_keys",
            "token": "tokens", "credential": "credentials",
            "private": "private_data", "auth": "auth_tokens",
        }
        for term, label in sensitive_terms.items():
            if term in gitignore.lower():
                if label not in never_expose:
                    never_expose.append(label)

        # .env.example → explicit sensitive fields
        env_example = self._read_file(".env.example") or self._read_file(".env.sample") or ""
        for line in env_example.split("\n"):
            if "=" in line and not line.startswith("#"):
                key = line.split("=")[0].strip()
                if any(t in key.lower() for t in ["key", "secret", "password", "token"]):
                    label = key.lower()
                    if label not in never_expose:
                        never_expose.append(label)

        # Always include these baseline protections
        for baseline in ["user_data", "api_keys", "private_keys"]:
            if baseline not in never_expose:
                never_expose.append(baseline)

        ethics["never_expose"] = never_expose
        ethics["never_delete"] = ["*.backup"]

        # Try to infer data sovereignty from git config / README
        country = self._infer_country()
        if country:
            ethics["data_sovereignty"] = country

        ctx.ethics = ethics
        self.confidence["ethics"] = 0.85

    def _infer_country(self) -> Optional[str]:
        """Try to infer data sovereignty country from available signals."""
        signals: list[str] = []

        # Git config email domain
        email = self._from_git_config("user.email") or ""
        tld = email.split(".")[-1].lower() if "." in email else ""
        tld_to_country = {"in": "India", "de": "Germany", "fr": "France",
                           "uk": "United Kingdom", "au": "Australia", "ca": "Canada"}
        if tld in tld_to_country:
            signals.append(tld_to_country[tld])

        # README mentions
        readme = self._read_readme() or ""
        country_mentions = re.findall(
            r"\b(India|Germany|France|United Kingdom|Australia|Canada|USA|United States)\b",
            readme, re.IGNORECASE
        )
        signals.extend(country_mentions)

        # Return most common mention
        if signals:
            from collections import Counter
            return Counter(signals).most_common(1)[0][0]
        return None

    # ──────────────────────────────────────────────────────────
    # Scanner 7 — Cognitive / Dialect defaults
    # ──────────────────────────────────────────────────────────

    def _build_cognitive_defaults(self, ctx) -> None:
        ctx.cognitive = {
            "modes": {
                "debug": {
                    "prioritize": ["logs", "invariants", "hard_rules"],
                },
                "build": {
                    "prioritize": ["api_surface", "dependencies", "trust_tiers"],
                },
                "refactor": {
                    "prioritize": ["invariants", "architecture", "decisions"],
                },
            },
            "critical":  ["api_surface", "invariants", "trust_tiers", "hard_rules"],
            "important": ["architecture", "decisions", "conventions"],
            "reference": ["full_history", "benchmarks", "detailed_api"],
            "token_budget": {
                "claude":  12000,
                "gpt4":    8000,
                "gemini":  20000,
                "local":   2000,
            },
        }

    def _build_inference_config(self, ctx) -> None:
        ctx.inference = {
            "enabled": True,
            "mode": "propose_only",
            "require_validation": True,
            "sources": ["codebase", "git", "tests", "dependencies"],
            "auto_learn": True,
            "confidence_threshold": 0.8,
            "human_review_queue": ".brain-ctx.proposals.yaml",
        }

    def _build_observability_defaults(self, ctx) -> None:
        ctx.observability = {
            "enabled":    True,
            "log_file":   ".brain-ctx.log",
            "log_format": "json",
            "retention":  "90_days",
            "capture":    ["writes", "proposals", "rejections", "violations"],
        }

    # ──────────────────────────────────────────────────────────
    # The one optional question
    # ──────────────────────────────────────────────────────────

    def _ask_one_question(self, ctx) -> None:
        """
        Ask exactly one optional question.
        This is the ONLY human interaction in the entire flow.
        Press Enter = skip = fully automatic.
        """
        try:
            from rich.console import Console
            from rich.prompt import Prompt
            console = Console()
            console.print("\n[bold cyan]brain.ctx generated.[/bold cyan]")
            console.print(
                "\n[dim]One optional question:[/dim]\n"
                "[bold]Is there anything your AI must NEVER do in this project[/bold]\n"
                "[dim]that isn't already in the code? (Press Enter to skip)[/dim]\n"
            )
            answer = Prompt.ask("", default="").strip()
            if answer:
                ctx.hard_rules.insert(0, answer)
                console.print(f"[green]✓ Added rule:[/green] {answer}")
        except Exception:
            # Non-interactive or rich not available
            pass

    # ──────────────────────────────────────────────────────────
    # File reading helpers
    # ──────────────────────────────────────────────────────────

    def _read_file(self, relative_path: str) -> Optional[str]:
        fpath = self.root / relative_path
        if fpath.exists():
            try:
                return fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return None
        return None

    def _read_json(self, relative_path: str) -> Optional[dict]:
        import json
        content = self._read_file(relative_path)
        if content:
            try:
                return json.loads(content)
            except Exception:
                return None
        return None

    def _read_readme(self) -> Optional[str]:
        for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
            content = self._read_file(name)
            if content:
                return content
        return None

    def _from_package_json(self, key: str) -> Optional[str]:
        pkg = self._read_json("package.json") or {}
        val = pkg.get(key)
        return str(val) if val else None

    def _from_cargo_toml(self, key: str, first: bool = False) -> Optional[str]:
        content = self._read_file("Cargo.toml")
        if not content:
            return None
        try:
            # Try stdlib tomllib (Python 3.11+) or tomli
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore
                except ImportError:
                    # Manual regex fallback
                    match = re.search(rf'^{key}\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
                    return match.group(1) if match else None

            data = tomllib.loads(content)
            val = data.get("package", {}).get(key)
            if val is None:
                return None
            if first and isinstance(val, list):
                val = val[0]
            # Authors in Cargo.toml are "Name <email>" format
            if isinstance(val, str) and "<" in val:
                val = val.split("<")[0].strip()
            return str(val)
        except Exception:
            return None

    def _from_pyproject(self, key: str, first: bool = False) -> Optional[str]:
        content = self._read_file("pyproject.toml")
        if not content:
            return None
        try:
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore
                except ImportError:
                    return None
            data = tomllib.loads(content)
            val = data.get("project", {}).get(key)
            if val is None:
                return None
            if first and isinstance(val, list):
                item = val[0]
                if isinstance(item, dict):
                    val = item.get("name", str(item))
                else:
                    val = str(item)
            return str(val)
        except Exception:
            return None

    def _from_git_config(self, key: str) -> Optional[str]:
        try:
            import git
            repo = git.Repo(self.root)
            reader = repo.config_reader()
            section, option = key.split(".")
            return reader.get_value(section, option, None)
        except Exception:
            return None

    def _from_readme_url(self) -> Optional[str]:
        readme = self._read_readme() or ""
        # Look for website/homepage mentions in first 500 chars
        urls = re.findall(r"https?://[^\s\)\]\"'<>]+\.[a-z]{2,6}[^\s\)\]\"'<>]*", readme[:500])
        # Filter out GitHub, shields.io, etc.
        skip = {"github.com", "shields.io", "travis-ci", "codecov", "badge"}
        for url in urls:
            if not any(s in url for s in skip):
                return url
        return None

    def _from_cname_file(self) -> Optional[str]:
        content = self._read_file("CNAME")
        if content:
            return content.strip()
        return None

    def _detect_license_file(self) -> Optional[str]:
        license_map = {
            "mit": "MIT", "apache": "Apache-2.0", "gpl": "GPL-3.0",
            "agpl": "AGPL-3.0", "bsd": "BSD-3-Clause", "sspl": "SSPL-1.0",
        }
        for name in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]:
            content = self._read_file(name)
            if content:
                content_lower = content[:500].lower()
                for key, spdx in license_map.items():
                    if key in content_lower:
                        return spdx
        return None

    def _clean_package_name(self, name: str) -> str:
        """Convert package name to display name: my-cool-lib → My Cool Lib"""
        if not name:
            return "Unknown"
        return name.replace("-", " ").replace("_", " ").title()

    def _clean_url(self, url: str) -> str:
        """Strip protocol from URL for clean display."""
        return re.sub(r"^https?://", "", url).rstrip("/")
