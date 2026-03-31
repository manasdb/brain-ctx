"""
UpdateProposer
==============
Scans a project for new patterns since the last brain.ctx update
and proposes additions — with confidence scores.

The human only approves, never writes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from brain_ctx.core import BrainCtx


class UpdateProposer:
    """
    Scans project for patterns that should be added to brain.ctx.

    Example:
        proposer = UpdateProposer(ctx, project_path)
        proposals = proposer.propose()
        # proposals = [
        #   {"field": "hard_rules", "value": "Never use async in WAL",
        #    "confidence": 0.85, "reason": "Found in 3 commit messages"}
        # ]
    """

    CONFIDENCE_THRESHOLD = 0.75

    def __init__(self, ctx: "BrainCtx", project_path: Path):
        self.ctx  = ctx
        self.root = project_path.resolve()

    def propose(self) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        proposals.extend(self._scan_new_git_rules())
        proposals.extend(self._scan_new_comments())
        proposals.extend(self._scan_new_tests())
        proposals.extend(self._scan_dependency_changes())
        # Filter by confidence threshold
        return [p for p in proposals if p.get("confidence", 0) >= self.CONFIDENCE_THRESHOLD]

    # ── Scanners ───────────────────────────────────────────

    def _scan_new_git_rules(self) -> list[dict]:
        """Find new rules in recent git commits not already in brain.ctx."""
        proposals: list[dict] = []
        existing_rules_lower = {r.lower()[:40] for r in self.ctx.hard_rules}

        try:
            import git
            repo    = git.Repo(self.root)
            commits = list(repo.iter_commits(max_count=20))
            rule_patterns = [
                r"never\s+(.{10,60})",
                r"always\s+(.{10,60})",
                r"do not\s+(.{10,60})",
                r"must not\s+(.{10,60})",
            ]
            rule_counts: dict[str, int] = {}
            for commit in commits:
                msg = commit.message.lower()
                for pattern in rule_patterns:
                    for match in re.finditer(pattern, msg):
                        rule = match.group(0).strip().capitalize()[:80]
                        if rule.lower()[:40] not in existing_rules_lower:
                            rule_counts[rule] = rule_counts.get(rule, 0) + 1

            for rule, count in rule_counts.items():
                if count >= 2:  # mentioned in 2+ commits = meaningful signal
                    proposals.append({
                        "field":      "hard_rules",
                        "value":      rule,
                        "confidence": min(0.6 + count * 0.1, 0.95),
                        "reason":     f"Found in {count} recent commit messages",
                    })
        except Exception:
            pass

        return proposals

    def _scan_new_comments(self) -> list[dict]:
        """Find new NEVER/ALWAYS comments in source code."""
        proposals: list[dict] = []
        existing_lower = {r.lower()[:40] for r in self.ctx.hard_rules}
        patterns = [
            r"#\s*(NEVER|ALWAYS|MUST NOT)[:\s]+(.{10,80})",
            r"//\s*(NEVER|ALWAYS|MUST NOT)[:\s]+(.{10,80})",
        ]
        skip_dirs = {"tests", "test", "spec", "__tests__", "node_modules",
                     ".git", "dist", "build", "target"}
        for fpath in self.root.rglob("*"):
            if any(part in skip_dirs for part in fpath.parts):
                continue
            if fpath.suffix not in {".py", ".rs", ".ts", ".js", ".go"}:
                continue
            if fpath.stat().st_size > 200_000:
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                for pattern in patterns:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        rule = match.group(0).lstrip("#/ ").strip()[:100]
                        if rule.lower()[:40] not in existing_lower:
                            proposals.append({
                                "field":      "hard_rules",
                                "value":      rule,
                                "confidence": 0.88,
                                "reason":     f"Explicit NEVER/ALWAYS comment in {fpath.name}",
                            })
            except Exception:
                continue
        return proposals

    def _scan_new_tests(self) -> list[dict]:
        """Find new test_invariant_* files not yet registered."""
        proposals: list[dict] = []
        registered = str(self.ctx.truth_sources.get("test_invariants", {}).get("infer_from", ""))

        for test_dir in ["tests", "test", "spec"]:
            tdir = self.root / test_dir
            if not tdir.exists():
                continue
            for fpath in tdir.rglob("*"):
                if "invariant" in fpath.stem.lower():
                    rel = str(fpath.relative_to(self.root))
                    if rel not in registered:
                        proposals.append({
                            "field":      "truth_sources.test_invariants",
                            "value":      rel,
                            "confidence": 0.92,
                            "reason":     f"New invariant test found: {fpath.name}",
                        })
        return proposals

    def _scan_dependency_changes(self) -> list[dict]:
        """Detect new major dependencies that should be reflected in brain.ctx."""
        proposals: list[dict] = []
        known_stack = str(self.ctx.truth_sources)

        # Check for new significant deps in Cargo.toml
        cargo = self._read("Cargo.toml") or ""
        interesting_deps = {
            "tokio":    "async runtime (tokio) detected — consider adding async patterns to dialects",
            "rayon":    "rayon detected — project uses data parallelism",
            "wasm-bindgen": "WASM target detected — add WASM constraints to hard_rules",
            "diesel":   "diesel ORM detected — add migration safety rules",
            "sqlx":     "sqlx detected — add query safety rules",
        }
        for dep, note in interesting_deps.items():
            if dep in cargo and dep not in known_stack:
                proposals.append({
                    "field":      "hard_rules",
                    "value":      note,
                    "confidence": 0.78,
                    "reason":     f"New dependency '{dep}' detected in Cargo.toml",
                })

        return proposals

    def _read(self, path: str) -> str | None:
        try:
            return (self.root / path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
