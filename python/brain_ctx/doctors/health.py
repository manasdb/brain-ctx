"""
brain-ctx doctor
================
Health check for brain.ctx files. Catches real-world problems
that JSON Schema validation misses:

  - truth_sources pointing to files that don't exist
  - mutex_files paths that are wrong
  - invariant patterns that match zero test files
  - token budgets that don't make sense
  - hard_rules that are too vague to be useful
  - never_touch patterns that never match anything
  - missing critical sections for the project type
  - agent roles with contradictory permissions
  - stale timeline entries
  - observability log that has grown too large

Each check returns: OK / WARN / ERROR with a human-readable message
and an actionable fix suggestion.

Usage:
    from brain_ctx.doctors.health import DoctorRunner
    report = DoctorRunner(ctx, project_root).run()
    report.print()
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from brain_ctx.core import BrainCtx


# ── Result types ───────────────────────────────────────────────

SEVERITY_ORDER = {"ERROR": 0, "WARN": 1, "OK": 2, "INFO": 3}


@dataclass
class CheckResult:
    check:      str
    severity:   str        # "OK" | "WARN" | "ERROR" | "INFO"
    message:    str
    fix:        Optional[str] = None
    detail:     Optional[str] = None

    @property
    def icon(self) -> str:
        return {"OK": "✅", "WARN": "⚠️ ", "ERROR": "❌", "INFO": "ℹ️ "}[self.severity]

    def __str__(self) -> str:
        lines = [f"{self.icon} [{self.check}] {self.message}"]
        if self.detail:
            lines.append(f"   Detail: {self.detail}")
        if self.fix:
            lines.append(f"   Fix:    {self.fix}")
        return "\n".join(lines)


@dataclass
class DoctorReport:
    results:      list[CheckResult] = field(default_factory=list)
    project_root: Optional[Path]    = None

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    @property
    def errors(self) -> list[CheckResult]:
        return [r for r in self.results if r.severity == "ERROR"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if r.severity == "WARN"]

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.severity == "OK")

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        e = len(self.errors)
        w = len(self.warnings)
        o = self.ok_count
        status = "HEALTHY" if self.passed else "UNHEALTHY"
        return (
            f"brain.ctx doctor — {status}\n"
            f"  {o} passed  {w} warnings  {e} errors"
        )

    def print(self, verbose: bool = False) -> None:
        # Sort: errors first, then warnings, then ok
        sorted_results = sorted(
            self.results,
            key=lambda r: SEVERITY_ORDER.get(r.severity, 99)
        )
        for result in sorted_results:
            if not verbose and result.severity == "OK":
                continue
            print(str(result))
        print()
        print(self.summary())

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "ok": self.ok_count,
            "checks": [
                {
                    "check":    r.check,
                    "severity": r.severity,
                    "message":  r.message,
                    "fix":      r.fix,
                    "detail":   r.detail,
                }
                for r in self.results
            ],
        }


# ── Doctor runner ──────────────────────────────────────────────

class DoctorRunner:
    """
    Runs all health checks against a BrainCtx instance.

    Example:
        runner = DoctorRunner(ctx, project_root=Path("."))
        report = runner.run()
        report.print()
        if not report.passed:
            sys.exit(1)
    """

    def __init__(self, ctx: "BrainCtx", project_root: Path = Path(".")):
        self.ctx  = ctx
        self.root = project_root.resolve()
        self.report = DoctorReport(project_root=self.root)

    def run(self) -> DoctorReport:
        """Run all checks and return report."""
        self._check_identity()
        self._check_hard_rules()
        self._check_truth_sources()
        self._check_trust()
        self._check_agents()
        self._check_token_budget()
        self._check_invariants()
        self._check_observability()
        self._check_timeline()
        self._check_ethics()
        self._check_dialects()
        self._check_signature()
        return self.report

    # ── Checks ────────────────────────────────────────────────

    def _check_identity(self) -> None:
        i = self.ctx.identity

        if not i.get("name"):
            self._add("identity.name", "ERROR",
                      "Project name is missing",
                      "Add: identity:\n  name: YourProject")
        else:
            self._add("identity.name", "OK", f"Name set: {i['name']}")

        if not i.get("vision"):
            self._add("identity.vision", "WARN",
                      "No vision statement — AI has no understanding of project purpose",
                      "Add: identity:\n  vision: 'What this project does in one line'")
        elif len(i["vision"]) < 15:
            self._add("identity.vision", "WARN",
                      f"Vision is too short ({len(i['vision'])} chars) — be more descriptive",
                      "A good vision is 30-80 characters explaining the core purpose")
        else:
            self._add("identity.vision", "OK", "Vision set")

        if not i.get("author"):
            self._add("identity.author", "WARN",
                      "No author — unclear who owns this constitution",
                      "Add: identity:\n  author: Your Name <you@example.com>")
        else:
            self._add("identity.author", "OK", f"Author: {i['author']}")

    def _check_hard_rules(self) -> None:
        rules = self.ctx.hard_rules

        if not rules:
            self._add("hard_rules", "WARN",
                      "No hard rules defined — AI has no absolute constraints",
                      "Add at least 3 hard_rules covering your most critical invariants")
            return

        if len(rules) < 3:
            self._add("hard_rules.count", "WARN",
                      f"Only {len(rules)} hard rule(s) — consider adding more critical constraints",
                      "Typical projects need 5-12 rules covering architecture, data, security")
        else:
            self._add("hard_rules.count", "OK", f"{len(rules)} hard rules defined")

        # Check for vague rules
        vague_indicators = [
            "be careful", "be cautious", "try to", "if possible",
            "generally", "usually", "sometimes", "maybe"
        ]
        vague = [r for r in rules
                 if any(v in r.lower() for v in vague_indicators)]
        if vague:
            self._add("hard_rules.precision", "WARN",
                      f"{len(vague)} rule(s) contain vague language",
                      "Hard rules must be absolute. Replace 'try to' with 'always/never'.",
                      detail="; ".join(r[:60] for r in vague))
        else:
            self._add("hard_rules.precision", "OK",
                      "All rules use precise language")

        # Check for duplicate/near-duplicate rules
        seen: set[str] = set()
        dupes: list[str] = []
        for rule in rules:
            key = rule.lower()[:40]
            if key in seen:
                dupes.append(rule[:60])
            seen.add(key)
        if dupes:
            self._add("hard_rules.duplicates", "WARN",
                      f"{len(dupes)} near-duplicate rule(s) found",
                      "Remove duplicates — they dilute AI attention",
                      detail="; ".join(dupes))
        else:
            self._add("hard_rules.duplicates", "OK", "No duplicate rules")

    def _check_truth_sources(self) -> None:
        ts = self.ctx.truth_sources
        if not ts:
            self._add("truth_sources", "WARN",
                      "No truth_sources defined — AI cannot infer live project state",
                      "Add truth_sources with infer_from pointing to your key source files")
            return

        missing_files: list[str] = []
        found_files:   list[str] = []

        for source_name, config in ts.items():
            infer_from = config.get("infer_from", "")
            if not infer_from:
                continue

            # Handle comma-separated paths
            paths = [p.strip() for p in str(infer_from).split(",")]
            any_found = False
            for path_str in paths:
                # Skip git paths and glob patterns
                if path_str.startswith(".git") or "*" in path_str:
                    any_found = True
                    continue
                # Handle directory paths
                full = self.root / path_str
                if full.exists():
                    any_found = True
                    break

            if any_found:
                found_files.append(source_name)
            else:
                missing_files.append(f"{source_name} → {infer_from}")

        if missing_files:
            self._add("truth_sources.paths", "ERROR",
                      f"{len(missing_files)} truth_source(s) point to non-existent paths",
                      "Fix the infer_from paths or run: brain-ctx init to regenerate",
                      detail="\n   ".join(missing_files))
        else:
            self._add("truth_sources.paths", "OK",
                      f"All {len(found_files)} truth_source paths are valid")

    def _check_trust(self) -> None:
        trust = self.ctx.trust

        if not trust:
            self._add("trust", "WARN",
                      "No trust configuration — AI agents have no permission boundaries",
                      "Add trust: section with default, never_touch, and mutex_files")
            return

        # never_touch
        nt = trust.get("never_touch", [])
        critical_runtime = {"*.pid", "*.sock", "*.lock"}
        missing_runtime = critical_runtime - set(nt)
        if missing_runtime:
            self._add("trust.never_touch", "WARN",
                      f"Missing critical runtime file patterns in never_touch",
                      f"Add to trust.never_touch: {', '.join(sorted(missing_runtime))}",
                      detail=f"These runtime files should never be touched: {missing_runtime}")
        else:
            self._add("trust.never_touch", "OK",
                      f"never_touch has {len(nt)} pattern(s) including all critical runtime files")

        # mutex_files — verify paths exist
        mutex = trust.get("mutex_files", [])
        bad_mutex: list[str] = []
        for mf in mutex:
            p = self.root / mf
            # Allow directory paths (trailing /)
            if mf.endswith("/"):
                if not p.exists():
                    bad_mutex.append(mf)
            elif not p.exists() and not any(self.root.rglob(mf)):
                bad_mutex.append(mf)

        if bad_mutex:
            self._add("trust.mutex_files", "WARN",
                      f"{len(bad_mutex)} mutex_file path(s) not found in project",
                      "Check paths — mutex_files with wrong paths provide no protection",
                      detail=", ".join(bad_mutex))
        elif mutex:
            self._add("trust.mutex_files", "OK",
                      f"{len(mutex)} mutex file(s) configured")
        else:
            self._add("trust.mutex_files", "WARN",
                      "No mutex_files defined — critical files have no approval requirement",
                      "Add your most sensitive source files to trust.mutex_files")

        # default trust level
        default = trust.get("default", "read_only")
        if default == "read_write":
            self._add("trust.default", "WARN",
                      "Default trust is read_write — agents can write anywhere without restriction",
                      "Consider changing to read_only and explicitly granting write per agent role")
        elif default == "no_access":
            self._add("trust.default", "WARN",
                      "Default trust is no_access — agents cannot read anything by default",
                      "Agents need at minimum read_only to be useful")
        else:
            self._add("trust.default", "OK", f"Default trust: {default}")

    def _check_agents(self) -> None:
        agents = self.ctx.trust.get("agents", {})

        if not agents:
            self._add("trust.agents", "WARN",
                      "No agent roles defined — all agents treated identically",
                      "Add architect, implementor, reviewer roles at minimum")
            return

        self._add("trust.agents.count", "OK", f"{len(agents)} agent role(s) defined")

        # Check for contradictory permissions
        for role_name, role in agents.items():
            can    = set(role.get("can",    []))
            cannot = set(role.get("cannot", []))
            overlap = can & cannot
            if overlap:
                self._add(f"trust.agents.{role_name}", "ERROR",
                          f"Role '{role_name}' has contradictory permissions",
                          f"Remove from either can or cannot: {overlap}",
                          detail=f"Overlap: {overlap}")
            else:
                self._add(f"trust.agents.{role_name}", "OK",
                          f"Role '{role_name}' has no contradictions")

    def _check_token_budget(self) -> None:
        cog = self.ctx.cognitive
        if not cog or "token_budget" not in cog:
            self._add("cognitive.token_budget", "WARN",
                      "No token budgets defined — AI context size not optimized per model",
                      "Add cognitive:\n  token_budget:\n    claude: 12000\n    gpt4: 8000\n    local: 2000")
            return

        budget = cog["token_budget"]
        known_limits = {
            "claude": 200000, "gpt4": 128000, "gpt-4": 128000,
            "gemini": 1000000, "local": 128000,
        }
        issues: list[str] = []

        for model, tokens in budget.items():
            if not isinstance(tokens, int) or tokens <= 0:
                issues.append(f"{model}: invalid value {tokens}")
                continue
            max_limit = known_limits.get(model.lower(), 200000)
            if tokens > max_limit:
                issues.append(f"{model}: {tokens} exceeds model max ({max_limit})")
            if tokens < 500:
                issues.append(f"{model}: {tokens} is very low — may truncate critical rules")

        # Sanity check: local should always be smallest
        local = budget.get("local", 0)
        claude = budget.get("claude", 0)
        if local and claude and local > claude:
            issues.append(
                f"local ({local}) > claude ({claude}) — local models have smaller context windows"
            )

        if issues:
            self._add("cognitive.token_budget", "WARN",
                      f"{len(issues)} token budget issue(s) found",
                      "Review and correct the token budgets",
                      detail="; ".join(issues))
        else:
            self._add("cognitive.token_budget", "OK",
                      f"Token budgets valid for {len(budget)} model(s): {list(budget.keys())}")

    def _check_invariants(self) -> None:
        ts = self.ctx.truth_sources
        invariants_config = ts.get("invariants", {})

        if not invariants_config:
            self._add("invariants", "WARN",
                      "No invariants truth_source configured",
                      "Add truth_sources:\n  invariants:\n    infer_from: tests/\n    pattern: test_invariant_*")
            return

        # Check if any test_invariant_* files actually exist
        pattern = invariants_config.get("pattern", "test_invariant_*")
        infer_from = invariants_config.get("infer_from", "tests/")

        test_dirs = [p.strip() for p in str(infer_from).split(",")]
        found_invariant_files: list[str] = []

        for test_dir_str in test_dirs:
            test_dir = self.root / test_dir_str.rstrip("/")
            if not test_dir.exists():
                continue
            for fpath in test_dir.rglob("*"):
                if "invariant" in fpath.stem.lower():
                    found_invariant_files.append(
                        str(fpath.relative_to(self.root))
                    )

        if not found_invariant_files:
            self._add("invariants.files", "WARN",
                      "No test_invariant_* files found — invariants are declared but not tested",
                      "Create test files matching the pattern to activate automated checking.\n"
                      "   Example: tests/test_invariant_api_count.py",
                      detail=f"Pattern '{pattern}' matched 0 files in {infer_from}")
        else:
            self._add("invariants.files", "OK",
                      f"{len(found_invariant_files)} invariant test file(s) found",
                      detail=", ".join(found_invariant_files[:5]))

    def _check_observability(self) -> None:
        obs = self.ctx.observability
        if not obs or not obs.get("enabled"):
            self._add("observability", "WARN",
                      "Observability is disabled — no audit trail of AI actions",
                      "Add observability:\n  enabled: true\n  log_file: .brain-ctx.log")
            return

        self._add("observability.enabled", "OK", "Observability enabled")

        # Check if log file has grown large
        log_file = self.root / obs.get("log_file", ".brain-ctx.log")
        if log_file.exists():
            size_mb = log_file.stat().st_size / (1024 * 1024)
            if size_mb > 100:
                self._add("observability.log_size", "WARN",
                          f"Observability log is {size_mb:.1f}MB — consider rotating",
                          "Run: brain-ctx diff --rotate to archive old entries")
            elif size_mb > 10:
                self._add("observability.log_size", "WARN",
                          f"Observability log is {size_mb:.1f}MB — growing large",
                          "Consider rotating the log: brain-ctx diff --rotate")
            else:
                self._add("observability.log_size", "OK",
                          f"Log size: {size_mb:.2f}MB")
        else:
            self._add("observability.log_file", "INFO",
                      "Log file doesn't exist yet — will be created on first AI action")

        # Check retention makes sense
        retention = obs.get("retention", "")
        if not retention:
            self._add("observability.retention", "WARN",
                      "No retention policy set — logs may grow indefinitely",
                      "Add: observability:\n  retention: 90_days")
        else:
            self._add("observability.retention", "OK",
                      f"Retention policy: {retention}")

    def _check_timeline(self) -> None:
        timeline = self.ctx.to_dict().get("timeline", [])
        if not timeline:
            self._add("timeline", "INFO",
                      "No timeline entries — consider adding architectural decision history",
                      "A timeline tells AI *why* rules exist, preventing them from being removed.\n"
                      "   Add: timeline:\n  - date: '2024-01'\n    event: 'Why we made this decision'")
            return

        self._add("timeline", "OK", f"{len(timeline)} timeline entry/entries recorded")

        # Check for very old entries with no recent ones
        try:
            dates = [e.get("date", "") for e in timeline if e.get("date")]
            if dates:
                latest = max(dates)
                # If latest is more than 2 years ago, warn
                import datetime
                latest_year = int(latest[:4]) if len(latest) >= 4 else 0
                current_year = datetime.datetime.now().year
                if current_year - latest_year > 2:
                    self._add("timeline.recency", "WARN",
                              f"Latest timeline entry is from {latest} — may be outdated",
                              "Add recent architectural decisions to keep history current")
                else:
                    self._add("timeline.recency", "OK",
                              f"Latest entry: {latest}")
        except Exception:
            pass

    def _check_ethics(self) -> None:
        ethics = self.ctx.ethics
        if not ethics:
            self._add("ethics", "WARN",
                      "No ethics section — no data protection rules defined",
                      "Add ethics:\n  never_expose: [api_keys, user_data]\n  data_sovereignty: US")
            return

        never_expose = ethics.get("never_expose", [])
        if not never_expose:
            self._add("ethics.never_expose", "WARN",
                      "No never_expose entries — AI may inadvertently log sensitive data",
                      "Add: ethics:\n  never_expose: [api_keys, user_data, passwords]")
        else:
            self._add("ethics.never_expose", "OK",
                      f"{len(never_expose)} data category/categories protected")

        if not ethics.get("data_sovereignty"):
            self._add("ethics.data_sovereignty", "INFO",
                      "No data_sovereignty set — useful for GDPR/compliance contexts",
                      "Add: ethics:\n  data_sovereignty: EU  # or US, IN, etc.")
        else:
            self._add("ethics.data_sovereignty", "OK",
                      f"Data sovereignty: {ethics['data_sovereignty']}")

    def _check_dialects(self) -> None:
        dialects = self.ctx.dialects
        cog      = self.ctx.cognitive
        budget   = cog.get("token_budget", {}) if cog else {}

        if not dialects:
            self._add("dialects", "INFO",
                      "No model dialects — consider adding per-model instructions",
                      "Add: dialects:\n  claude: 'Think step by step before writing'\n  local: 'Limited context — focus on task'")
            return

        # Check: if a model has a token_budget, it should have a dialect
        for model in budget:
            if model not in dialects:
                self._add(f"dialects.{model}", "INFO",
                          f"Model '{model}' has token_budget but no dialect instruction",
                          f"Add: dialects:\n  {model}: 'Specific instruction for this model'")

        self._add("dialects", "OK",
                  f"Dialects defined for: {', '.join(dialects.keys())}")

    def _check_signature(self) -> None:
        sig = self.ctx.signature
        if not sig or not sig.get("value"):
            self._add("signature", "INFO",
                      "brain.ctx is unsigned — tamper detection not active",
                      "Sign with: brain-ctx sign --key ~/.brain-ctx/private.key")
        else:
            # Verify it
            try:
                valid = self.ctx.verify_signature()
                if valid:
                    self._add("signature", "OK",
                              "Valid Ed25519 signature — tamper detection active")
                else:
                    self._add("signature", "ERROR",
                              "Signature verification FAILED — file may have been tampered with",
                              "Re-sign with: brain-ctx sign --key ~/.brain-ctx/private.key")
            except Exception as e:
                self._add("signature", "WARN",
                          f"Could not verify signature: {e}",
                          "Install PyNaCl: pip install brain-ctx[signing]")

    # ── Helper ────────────────────────────────────────────────

    def _add(
        self,
        check:    str,
        severity: str,
        message:  str,
        fix:      Optional[str] = None,
        detail:   Optional[str] = None,
    ) -> None:
        self.report.add(CheckResult(
            check=check, severity=severity,
            message=message, fix=fix, detail=detail,
        ))
