"""
ContextBuilder
==============
Builds an AI-ready context string from a BrainCtx.

Adapts content based on:
- Model identity (claude, gpt4, gemini, local)
- Token budget (per cognitive layer config)
- Priority tiers (critical > important > reference)
- Live truth source resolution (reads actual code)
- Model-specific dialect instructions
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from brain_ctx.core import BrainCtx


class ContextBuilder:
    """
    Builds optimized context strings for different AI models.

    Example:
        builder = ContextBuilder(ctx)
        context = builder.build(model="claude", token_budget=12000)
        # Inject into your Anthropic / OpenAI / etc. API call
    """

    # Rough chars-per-token estimate (conservative)
    CHARS_PER_TOKEN = 4

    def __init__(self, ctx: "BrainCtx"):
        self.ctx = ctx

    def build(
        self,
        model: str = "claude",
        token_budget: Optional[int] = None,
        live: bool = False,
        mode: Optional[str] = None,
    ) -> str:
        """
        Build a context string optimized for the given model and mode.
        """
        budget  = token_budget or self._budget_for(model)
        char_budget = budget * self.CHARS_PER_TOKEN

        # ── 1. Resolve Priorities ──
        cog = self.ctx.cognitive or {}
        
        # Determine prioritised sections for this mode
        priorities = []
        if mode and "modes" in cog and mode in cog["modes"]:
            priorities = cog["modes"][mode].get("prioritize", [])
        
        # Merge with critical tier (critical is always prioritized)
        critical = cog.get("critical", ["api_surface", "invariants", "trust_tiers", "hard_rules"])
        
        # Ordered list of all potential sections by priority
        tier_order = priorities + critical + cog.get("important", []) + cog.get("reference", [])
        
        # Deduplicate while preserving order
        seen = set()
        unique_order = []
        for item in tier_order:
            if item not in seen:
                unique_order.append(item)
                seen.add(item)

        # ── 2. Build Sections ──
        sections: list[str] = [self._section_header()]
        used = len(sections[0])

        # Mandatory foundational sections (always try to include)
        foundational = ["identity", "hard_rules", "trust_tiers"]
        for f in foundational:
            content = self._build_by_key(f, model, live)
            if content:
                sections.append(content)
                used += len(content)

        # Priority-driven sections
        for key in unique_order:
            if key in foundational: continue # already added
            
            content = self._build_by_key(key, model, live)
            if content:
                if used + len(content) < char_budget * 0.9:
                    sections.append(content)
                    used += len(content)
                else:
                    break # budget reached

        # Always include footer if it fits
        footer = self._section_footer()
        if used + len(footer) < char_budget:
            sections.append(footer)

        result = "\n".join(s for s in sections if s.strip())

        # Trim to budget accurately
        if len(result) > char_budget:
            result = result[:char_budget] + "\n\n[Context trimmed to fit token budget]"

        return result

    def _build_by_key(self, key: str, model: str, live: bool) -> str:
        """Map cognitive keys to section builder methods."""
        mapping = {
            "identity":     lambda: self._section_identity(),
            "hard_rules":   lambda: self._section_hard_rules(),
            "trust_tiers":  lambda: self._section_trust(),
            "ethics":       lambda: self._section_ethics(),
            "dialect":      lambda: self._section_dialect(model),
            "api_surface":  lambda: self._section_live_truth_sources(filter_key="api_surface") if live else "",
            "invariants":   lambda: self._section_live_truth_sources(filter_key="invariants") if live else "",
            "mesh":         lambda: self._section_mesh(),
            "logs":         lambda: self._section_observability(),
            "conventions":  lambda: self._section_live_truth_sources(filter_key="conventions") if live else "",
            "architecture": lambda: self._section_timeline(),
            "decisions":    lambda: self._section_timeline(),
        }
        builder = mapping.get(key)
        return builder() if builder else ""

    # ── Section builders ───────────────────────────────────

    def _section_header(self) -> str:
        return (
            "## brain.ctx — AI Constitution\n"
            "You are operating under a project constitution. "
            "Read all sections before taking any action.\n"
        )

    def _section_identity(self) -> str:
        i = self.ctx.identity
        lines = [f"### Project: {i.get('name', 'Unknown')}"]
        if i.get("vision"):
            lines.append(f"Vision: {i['vision']}")
        if i.get("domain"):
            lines.append(f"Domain: {i['domain']}")
        if i.get("author"):
            lines.append(f"Author: {i['author']}")
        return "\n".join(lines)

    def _section_hard_rules(self) -> str:
        rules = self.ctx.hard_rules
        if not rules:
            return ""
        lines = ["\n### Hard Rules — NEVER violate these"]
        lines += [f"- {r}" for r in rules]
        lines.append("\nThese are absolute. No exception. No workaround. If in doubt, stop and ask.")
        return "\n".join(lines)

    def _section_trust(self) -> str:
        t = self.ctx.trust
        if not t:
            return ""
        lines = ["\n### Trust Configuration"]
        lines.append(f"Default: {t.get('default', 'read_only')}")
        if t.get("never_touch"):
            lines.append(f"Never touch: {', '.join(t['never_touch'])}")
        if t.get("mutex_files"):
            lines.append(f"Mutex files (require approval): {', '.join(t['mutex_files'])}")
        agents = t.get("agents", {})
        if agents:
            lines.append("\nAgent roles:")
            for role, perms in agents.items():
                can    = ", ".join(perms.get("can",    []))
                cannot = ", ".join(perms.get("cannot", []))
                lines.append(f"  {role}: can=[{can}] cannot=[{cannot}]")
        return "\n".join(lines)

    def _section_ethics(self) -> str:
        e = self.ctx.ethics
        if not e:
            return ""
        lines = ["\n### Ethics & Data Protection"]
        if e.get("never_expose"):
            lines.append(f"Never expose: {', '.join(e['never_expose'])}")
        if e.get("never_delete"):
            lines.append(f"Never delete: {', '.join(e['never_delete'])}")
        if e.get("data_sovereignty"):
            lines.append(f"Data sovereignty: {e['data_sovereignty']}")
        return "\n".join(lines)

    def _section_dialect(self, model: str) -> str:
        dialects = self.ctx.dialects
        if not dialects:
            return ""
        instruction = dialects.get(model) or dialects.get("default", "")
        if not instruction:
            return ""
        return f"\n### Model-Specific Instructions ({model})\n{instruction}"

    def _section_live_truth_sources(self, filter_key: Optional[str] = None) -> str:
        """Resolve truth_sources pointers against live code."""
        ts = self.ctx.truth_sources
        if not ts:
            return ""
        
        sources_to_process = {filter_key: ts[filter_key]} if filter_key and filter_key in ts else ts
        if not sources_to_process:
            return ""

        lines = []
        for source_name, config in sources_to_process.items():
            infer_from = config.get("infer_from", "")
            pattern    = config.get("pattern", "")
            if infer_from and pattern:
                extracted = self._extract_live(str(infer_from), pattern)
                if extracted:
                    lines.append(f"\n{source_name.replace('_', ' ').title()} (from {infer_from}):")
                    lines += [f"  {item}" for item in extracted[:20]]
        
        return "\n".join(lines) if lines else ""

    def _section_timeline(self) -> str:
        """Build the architectural timeline / decision history section."""
        timeline = getattr(self.ctx, "timeline", [])
        if not timeline:
            return ""
        lines = ["\n### Decision History"]
        for entry in timeline[:10]:
            date  = entry.get("date", "Unknown")
            event = entry.get("event", "")
            lesson = entry.get("lesson", "")
            lines.append(f"- [{date}] {event}")
            if lesson:
                lines.append(f"  Lesson: {lesson}")
        return "\n".join(lines)

    def _extract_live(self, glob_path: str, pattern: str) -> list[str]:
        """Extract matching lines from live source files."""
        import re
        from pathlib import Path
        results: list[str] = []
        try:
            for file_path in Path(".").rglob(glob_path.lstrip("*/")):
                if file_path.stat().st_size > 500_000:
                    continue
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for line in content.split("\n"):
                    if re.search(pattern, line):
                        results.append(line.strip())
                if len(results) >= 20:
                    break
        except Exception:
            pass
        return results

    def _section_mesh(self) -> str:
        m = self.ctx.mesh
        if not m or not m.get("imports"):
            return ""
        lines = ["\n### Federated Imports"]
        for imp in m["imports"]:
            lines.append(f"- {imp}")
        return "\n".join(lines)

    def _section_observability(self) -> str:
        o = self.ctx.observability
        if not o or not o.get("enabled"):
            return ""
        return (
            f"\n### Observability\n"
            f"All your actions are logged to {o.get('log_file', '.brain-ctx.log')}. "
            f"This is an audit trail. Act accordingly."
        )

    def _section_footer(self) -> str:
        return f"\n---\n{self.ctx.ai_score()}\nI understand this project. Ready."

    def _budget_for(self, model: str) -> int:
        cognitive = self.ctx.cognitive
        if cognitive and "token_budget" in cognitive:
            return cognitive["token_budget"].get(model, 8000)
        defaults = {
            "claude": 12000, "gpt4": 8000, "gpt-4": 8000,
            "gemini": 20000, "local": 2000,
        }
        return defaults.get(model.lower(), 8000)
