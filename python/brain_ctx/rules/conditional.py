"""
Conditional Rules Engine
========================
Evaluates brain.ctx rules based on runtime context.

Problem:
    Hard rules are always-on. But many constraints are
    environment-specific:
    - "Never use mock payment processor" — only in production
    - "Always use test Stripe key" — only in development
    - "Never skip 2FA" — only for external users

Solution:
    A conditional rule format in brain.ctx:

    conditional_rules:
      - rule: "Never use mock payment processor"
        when:
          env: [production, staging]
        severity: ERROR

      - rule: "Always use test mode for Stripe"
        when:
          env: [development, test]
        severity: WARN

      - rule: "Never commit with failing tests"
        when:
          branch: [main, master, release/*]
        severity: ERROR

      - rule: "Database migrations require DBA approval"
        when:
          path_changed: ["*/migrations/*"]
          env: [production]
        severity: ERROR

Usage:
    from brain_ctx.rules.conditional import ConditionalRuleEngine

    engine  = ConditionalRuleEngine(ctx)
    context = RuleContext(env="production", branch="main")
    active  = engine.evaluate(context)
    for rule in active:
        print(rule.rule, rule.severity)
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from brain_ctx.core import BrainCtx


# ── Context ────────────────────────────────────────────────────

@dataclass
class RuleContext:
    """
    The runtime context in which rules are evaluated.
    brain-ctx reads this from environment variables by default.

    Example:
        ctx = RuleContext.from_environment()
        # Reads BRAIN_CTX_ENV, BRAIN_CTX_BRANCH, etc.
    """
    env:            str         = "development"  # production / staging / development / test
    branch:         str         = ""             # git branch name
    agent_role:     str         = ""             # current agent role
    changed_paths:  list[str]   = field(default_factory=list)
    tags:           list[str]   = field(default_factory=list)
    user:           str         = ""

    @classmethod
    def from_environment(cls) -> "RuleContext":
        """
        Build context from environment variables.

        Reads:
          BRAIN_CTX_ENV     — environment name (default: development)
          BRAIN_CTX_BRANCH  — git branch (falls back to git command)
          BRAIN_CTX_ROLE    — agent role
          BRAIN_CTX_USER    — current user
          CI                — if set, env becomes 'ci'
        """
        env = os.environ.get("BRAIN_CTX_ENV", "")

        # CI detection
        if not env and os.environ.get("CI"):
            env = "ci"

        # Detect from common env vars
        if not env:
            node_env = os.environ.get("NODE_ENV", "")
            flask_env = os.environ.get("FLASK_ENV", "")
            django_env = os.environ.get("DJANGO_SETTINGS_MODULE", "")
            if "prod" in node_env.lower() or "prod" in flask_env.lower():
                env = "production"
            elif "test" in node_env.lower():
                env = "test"
            elif django_env and "prod" in django_env.lower():
                env = "production"
            else:
                env = "development"

        # Branch from env or git
        branch = os.environ.get("BRAIN_CTX_BRANCH", "")
        if not branch:
            branch = os.environ.get("GITHUB_REF_NAME", "")
        if not branch:
            try:
                import subprocess
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0:
                    branch = result.stdout.strip()
            except Exception:
                pass

        return cls(
            env=env,
            branch=branch,
            agent_role=os.environ.get("BRAIN_CTX_ROLE", ""),
            user=os.environ.get("BRAIN_CTX_USER", os.environ.get("USER", "")),
        )

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod", "live"}

    @property
    def is_protected_branch(self) -> bool:
        protected = {"main", "master", "release", "production", "prod"}
        return any(p in self.branch.lower() for p in protected)


# ── Rule types ─────────────────────────────────────────────────

@dataclass
class ConditionalRule:
    """A rule with conditions on when it applies."""
    rule:         str
    when:         dict[str, Any]   = field(default_factory=dict)
    severity:     str              = "ERROR"    # ERROR | WARN | INFO
    reason:       str              = ""
    source:       str              = "brain.ctx"

    def applies_to(self, context: RuleContext) -> bool:
        """
        Evaluate whether this rule applies in the given context.
        All conditions in `when` must match (AND logic).
        """
        when = self.when
        if not when:
            return True   # no conditions = always applies

        # env condition
        if "env" in when:
            allowed_envs = when["env"]
            if isinstance(allowed_envs, str):
                allowed_envs = [allowed_envs]
            if not any(
                self._match_env(context.env, e) for e in allowed_envs
            ):
                return False

        # branch condition
        if "branch" in when:
            allowed_branches = when["branch"]
            if isinstance(allowed_branches, str):
                allowed_branches = [allowed_branches]
            if not context.branch:
                return False  # unknown branch — don't apply branch rules
            if not any(
                fnmatch.fnmatch(context.branch, b) for b in allowed_branches
            ):
                return False

        # agent_role condition
        if "role" in when:
            allowed_roles = when["role"]
            if isinstance(allowed_roles, str):
                allowed_roles = [allowed_roles]
            if context.agent_role and context.agent_role not in allowed_roles:
                return False

        # path_changed condition
        if "path_changed" in when and context.changed_paths:
            path_patterns = when["path_changed"]
            if isinstance(path_patterns, str):
                path_patterns = [path_patterns]
            if not any(
                fnmatch.fnmatch(path, pattern)
                for path in context.changed_paths
                for pattern in path_patterns
            ):
                return False

        # tag condition
        if "tags" in when:
            required_tags = when["tags"]
            if isinstance(required_tags, str):
                required_tags = [required_tags]
            if not any(t in context.tags for t in required_tags):
                return False

        return True

    def _match_env(self, current: str, pattern: str) -> bool:
        """Match environment name with aliases."""
        aliases = {
            "prod":        ["production", "prod", "live"],
            "production":  ["production", "prod", "live"],
            "dev":         ["development", "dev", "local"],
            "development": ["development", "dev", "local"],
            "test":        ["test", "testing", "ci", "github-actions"],
            "ci":          ["ci", "test", "testing", "github-actions"],
            "staging":     ["staging", "stage", "uat", "preprod"],
        }
        expanded = aliases.get(pattern.lower(), [pattern.lower()])
        return current.lower() in expanded


@dataclass
class ActiveRule:
    """A rule that is active in the current context."""
    rule:     str
    severity: str
    reason:   str
    source:   str
    context:  RuleContext


# ── Engine ─────────────────────────────────────────────────────

class ConditionalRuleEngine:
    """
    Evaluates conditional rules from brain.ctx against a runtime context.

    Example:
        engine  = ConditionalRuleEngine(ctx)
        context = RuleContext.from_environment()
        active  = engine.evaluate(context)

        for rule in active:
            if rule.severity == "ERROR":
                print(f"❌ {rule.rule}")
            elif rule.severity == "WARN":
                print(f"⚠️  {rule.rule}")
    """

    def __init__(self, ctx: "BrainCtx"):
        self.ctx = ctx
        self._rules = self._load_conditional_rules()

    def _load_conditional_rules(self) -> list[ConditionalRule]:
        """Load conditional_rules from brain.ctx data."""
        raw = self.ctx.to_dict().get("conditional_rules", [])
        rules: list[ConditionalRule] = []
        for item in raw:
            if isinstance(item, str):
                # Plain string = always-on rule
                rules.append(ConditionalRule(rule=item))
            elif isinstance(item, dict):
                rules.append(ConditionalRule(
                    rule=item.get("rule", ""),
                    when=item.get("when", {}),
                    severity=item.get("severity", "ERROR"),
                    reason=item.get("reason", ""),
                    source="brain.ctx",
                ))
        return rules

    def evaluate(self, context: Optional[RuleContext] = None) -> list[ActiveRule]:
        """
        Evaluate all conditional rules against the given context.
        Returns only the rules that apply.

        Args:
            context: Runtime context. If None, auto-detects from environment.
        """
        if context is None:
            context = RuleContext.from_environment()

        active: list[ActiveRule] = []
        for rule in self._rules:
            if rule.applies_to(context):
                active.append(ActiveRule(
                    rule=rule.rule,
                    severity=rule.severity,
                    reason=rule.reason,
                    source=rule.source,
                    context=context,
                ))

        # Also include unconditional hard_rules as always-ERROR
        for hard_rule in self.ctx.hard_rules:
            active.append(ActiveRule(
                rule=hard_rule,
                severity="ERROR",
                reason="Unconditional hard rule",
                source="hard_rules",
                context=context,
            ))

        return active

    def evaluate_for_env(self, env: str, branch: str = "") -> list[ActiveRule]:
        """Convenience: evaluate for a specific environment."""
        return self.evaluate(RuleContext(env=env, branch=branch))

    def all_rules(self) -> list[ConditionalRule]:
        """Return all conditional rules regardless of context."""
        return self._rules

    def rules_for_env(self, env: str) -> list[ConditionalRule]:
        """Return all rules that would apply in a given environment."""
        ctx = RuleContext(env=env, branch="main")
        return [r for r in self._rules if r.applies_to(ctx)]

    def summary(self, context: Optional[RuleContext] = None) -> str:
        """Return a human-readable summary of active rules."""
        if context is None:
            context = RuleContext.from_environment()
        active = self.evaluate(context)
        errors = [r for r in active if r.severity == "ERROR"]
        warns  = [r for r in active if r.severity == "WARN"]
        lines  = [
            f"Active rules for env={context.env}, branch={context.branch or 'unknown'}",
            f"  {len(errors)} errors  {len(warns)} warnings  {len(active)} total",
        ]
        for r in errors[:5]:
            lines.append(f"  ❌ {r.rule[:80]}")
        for r in warns[:3]:
            lines.append(f"  ⚠️  {r.rule[:80]}")
        return "\n".join(lines)
