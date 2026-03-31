"""
brain.ctx Inheritance System
============================
Allows a brain.ctx to inherit from a parent brain.ctx.
Solves the monorepo problem: 12 packages sharing 80% of rules.

Usage in brain.ctx:
    inherit: ../brain.ctx          # local parent
    inherit: ../../shared/brain.ctx
    # OR from registry:
    inherit: github://org/repo/brain.ctx

Merge behavior (local always wins):
    - hard_rules:   parent rules + local rules (deduplicated)
    - ethics:       deep merged, local overrides per key
    - trust:        deep merged, local overrides per key
    - dialects:     local overrides per model
    - cognitive:    local overrides per key
    - identity:     local always wins (child has own identity)
    - truth_sources: local overrides per key, new keys appended
    - conditional_rules: parent + local (both apply)

Override example:
    # packages/payments/brain.ctx
    inherit: ../../brain.ctx

    identity:
      name: PayCore Payments Service
      vision: "Payment processing microservice"

    # These ADD to parent's rules (not replace):
    hard_rules:
      - "Never process charge without idempotency key"

    # This OVERRIDES parent's implementor role:
    trust:
      agents:
        implementor:
          can: [write_code, run_tests]
          cannot: [change_architecture, touch_mutex_files, delete, run_live_charges]

Usage:
    from brain_ctx.inherit.resolver import InheritanceResolver
    merged = InheritanceResolver(ctx, base_path=Path(".")).resolve()
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from brain_ctx.core import BrainCtx


class InheritanceResolver:
    """
    Resolves brain.ctx inheritance chains and produces a merged BrainCtx.

    Supports:
      - Local file paths: inherit: ../brain.ctx
      - Relative paths from project root
      - Up to 5 levels of inheritance (prevents circular refs)

    Local always wins (like CSS specificity):
      child > parent > grandparent

    Example:
        resolver = InheritanceResolver(child_ctx, base_path=Path("."))
        merged   = resolver.resolve()
        print(merged.hard_rules)  # parent + child rules merged
    """

    MAX_DEPTH = 5

    def __init__(self, ctx: "BrainCtx", base_path: Path = Path(".")):
        self.ctx       = ctx
        self.base_path = base_path.resolve()
        self._seen:    set[str] = set()  # prevent circular inheritance

    def resolve(self) -> "BrainCtx":
        """
        Resolve the full inheritance chain and return the merged BrainCtx.
        If no inherit key, returns the original ctx unchanged.
        """
        inherit_path = self._get_inherit_path(self.ctx)
        if not inherit_path:
            return self.ctx

        return self._resolve_chain(self.ctx, depth=0)

    def _resolve_chain(self, ctx: "BrainCtx", depth: int) -> "BrainCtx":
        if depth >= self.MAX_DEPTH:
            return ctx

        inherit_str = self._get_inherit_path(ctx)
        if not inherit_str:
            return ctx

        parent_path = self._resolve_path(inherit_str, ctx)
        if not parent_path or not parent_path.exists():
            # Parent not found — return child as-is with a warning
            print(f"⚠️  brain-ctx: inherit path not found: {inherit_str}")
            return ctx

        canonical = str(parent_path.resolve())
        if canonical in self._seen:
            print(f"⚠️  brain-ctx: circular inheritance detected at {canonical}")
            return ctx
        self._seen.add(canonical)

        from brain_ctx.core import BrainCtx
        parent_ctx = BrainCtx.load(parent_path)

        # Recursively resolve parent's inheritance first
        resolved_parent = self._resolve_chain(parent_ctx, depth + 1)

        # Merge: parent base + child overrides
        return self._merge(resolved_parent, ctx)

    def _merge(self, parent: "BrainCtx", child: "BrainCtx") -> "BrainCtx":
        """
        Merge parent and child BrainCtx.
        Child always wins on conflicts.
        """
        from brain_ctx.core import BrainCtx

        merged_data = copy.deepcopy(parent.to_dict())
        child_data  = child.to_dict()

        # ── identity: child always wins entirely ──────────────
        if child_data.get("identity"):
            merged_data["identity"] = child_data["identity"]

        # ── hard_rules: append child rules to parent ──────────
        parent_rules = merged_data.get("hard_rules", [])
        child_rules  = child_data.get("hard_rules",  [])
        combined     = parent_rules + [
            r for r in child_rules if r not in parent_rules
        ]
        merged_data["hard_rules"] = combined

        # ── conditional_rules: append (all apply) ─────────────
        p_cond = merged_data.get("conditional_rules", [])
        c_cond = child_data.get("conditional_rules",  [])
        merged_data["conditional_rules"] = p_cond + c_cond

        # ── ethics: deep merge, child overrides per key ────────
        if child_data.get("ethics"):
            parent_ethics = merged_data.get("ethics", {})
            child_ethics  = child_data["ethics"]
            merged_ethics = copy.deepcopy(parent_ethics)
            for key, val in child_ethics.items():
                if key == "never_expose" and key in parent_ethics:
                    # Combine lists
                    merged_ethics[key] = list(set(
                        parent_ethics[key] + val
                    ))
                elif key == "never_delete" and key in parent_ethics:
                    merged_ethics[key] = list(set(
                        parent_ethics[key] + val
                    ))
                else:
                    merged_ethics[key] = val
            merged_data["ethics"] = merged_ethics

        # ── trust: deep merge, child overrides per key ─────────
        if child_data.get("trust"):
            parent_trust = merged_data.get("trust", {})
            child_trust  = child_data["trust"]
            merged_trust = copy.deepcopy(parent_trust)

            # never_touch: combine lists
            if "never_touch" in child_trust:
                existing = set(merged_trust.get("never_touch", []))
                existing.update(child_trust["never_touch"])
                merged_trust["never_touch"] = list(existing)

            # mutex_files: combine lists
            if "mutex_files" in child_trust:
                existing = set(merged_trust.get("mutex_files", []))
                existing.update(child_trust["mutex_files"])
                merged_trust["mutex_files"] = list(existing)

            # default: child wins
            if "default" in child_trust:
                merged_trust["default"] = child_trust["default"]

            # agents: child role overrides parent role
            if "agents" in child_trust:
                parent_agents = merged_trust.get("agents", {})
                child_agents  = child_trust["agents"]
                merged_agents = copy.deepcopy(parent_agents)
                merged_agents.update(child_agents)  # child agent overrides
                merged_trust["agents"] = merged_agents

            merged_data["trust"] = merged_trust

        # ── truth_sources: child overrides per key ─────────────
        if child_data.get("truth_sources"):
            parent_ts = merged_data.get("truth_sources", {})
            child_ts  = child_data["truth_sources"]
            merged_ts = copy.deepcopy(parent_ts)
            merged_ts.update(child_ts)  # child overrides per key
            merged_data["truth_sources"] = merged_ts

        # ── cognitive: child overrides per key ─────────────────
        if child_data.get("cognitive"):
            parent_cog = merged_data.get("cognitive", {})
            child_cog  = child_data["cognitive"]
            merged_cog = copy.deepcopy(parent_cog)
            # token_budget: child overrides per model
            if "token_budget" in child_cog:
                merged_cog["token_budget"] = {
                    **parent_cog.get("token_budget", {}),
                    **child_cog["token_budget"],
                }
            for key in ["critical", "important", "reference"]:
                if key in child_cog:
                    merged_cog[key] = child_cog[key]
            merged_data["cognitive"] = merged_cog

        # ── dialects: child overrides per model ────────────────
        if child_data.get("dialects"):
            parent_d = merged_data.get("dialects", {})
            merged_data["dialects"] = {**parent_d, **child_data["dialects"]}

        # ── observability: child overrides ─────────────────────
        if child_data.get("observability"):
            merged_data["observability"] = child_data["observability"]

        # ── timeline: combine (parent historical + child recent) ─
        p_timeline = merged_data.get("timeline", [])
        c_timeline = child_data.get("timeline",  [])
        if p_timeline or c_timeline:
            merged_data["timeline"] = p_timeline + c_timeline

        # ── mesh: child overrides ──────────────────────────────
        if child_data.get("mesh"):
            merged_data["mesh"] = child_data["mesh"]

        # ── Remove inherit key from merged output ──────────────
        merged_data.pop("inherit", None)

        # ── Build merged BrainCtx ──────────────────────────────
        merged = BrainCtx(
            version=child_data.get("version", parent.version),
            identity=merged_data.get("identity", {}),
            inference=merged_data.get("inference", {}),
            trust=merged_data.get("trust", {}),
            hard_rules=merged_data.get("hard_rules", []),
            ethics=merged_data.get("ethics", {}),
            truth_sources=merged_data.get("truth_sources", {}),
            cognitive=merged_data.get("cognitive", {}),
            dialects=merged_data.get("dialects", {}),
            mesh=merged_data.get("mesh", {}),
            observability=merged_data.get("observability", {}),
            signature={},  # signature is never inherited
        )
        # Store extra fields (timeline, conditional_rules)
        merged._extra = {
            k: v for k, v in merged_data.items()
            if k not in {
                "version","identity","inference","trust","hard_rules",
                "ethics","truth_sources","cognitive","dialects",
                "mesh","observability","signature"
            }
        }
        return merged

    def _get_inherit_path(self, ctx: "BrainCtx") -> Optional[str]:
        """Extract inherit path from brain.ctx data."""
        data = ctx.to_dict()
        return data.get("inherit") or getattr(ctx, "_extra", {}).get("inherit")

    def _resolve_path(self, inherit_str: str, ctx: "BrainCtx") -> Optional[Path]:
        """Resolve the inherit path relative to the child's location."""
        if inherit_str.startswith("github://"):
            # Future: mesh registry resolution
            print(f"ℹ️  brain-ctx: remote inherit not yet supported: {inherit_str}")
            return None

        # Relative to child's source path or base_path
        base = (
            ctx._source_path.parent
            if ctx._source_path
            else self.base_path
        )
        resolved = (base / inherit_str).resolve()
        return resolved
