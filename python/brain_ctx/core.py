"""
Core BrainCtx class — the main entry point for the Python library.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


SPEC_VERSION = "1.0"
FILENAME     = "brain.ctx"


@dataclass
class BrainCtx:
    """
    Represents a brain.ctx AI Constitution file.

    This is the central object in the brain-ctx library.
    Every operation — generation, loading, validation,
    context building, signing — flows through this class.
    """

    version:       str              = SPEC_VERSION
    identity:      dict[str, Any]   = field(default_factory=dict)
    inference:     dict[str, Any]   = field(default_factory=dict)
    trust:         dict[str, Any]   = field(default_factory=dict)
    hard_rules:    list[str]        = field(default_factory=list)
    ethics:        dict[str, Any]   = field(default_factory=dict)
    truth_sources: dict[str, Any]   = field(default_factory=dict)
    cognitive:     dict[str, Any]   = field(default_factory=dict)
    dialects:      dict[str, Any]   = field(default_factory=dict)
    mesh:          dict[str, Any]   = field(default_factory=dict)
    observability: dict[str, Any]   = field(default_factory=dict)
    signature:     dict[str, Any]   = field(default_factory=dict)
    verification:  dict[str, Any]   = field(default_factory=dict)


    # Internal tracking
    _source_path:  Optional[Path]   = field(default=None, repr=False)
    _confidence:   dict[str, float] = field(default_factory=dict, repr=False)

    # ──────────────────────────────────────────────────────────
    # Class-level factory methods
    # ──────────────────────────────────────────────────────────

    @classmethod
    def generate(cls, project_path: str | Path = ".") -> "BrainCtx":
        """
        Auto-generate a brain.ctx from an existing project.

        Scans: codebase, git history, tests, dependencies, README.
        Requires ZERO human input. Runs fully automatically.

        Args:
            project_path: Root directory of the project to scan.

        Returns:
            A fully populated BrainCtx instance ready to save.

        Example:
            ctx = BrainCtx.generate(".")
            ctx.save()
        """
        from brain_ctx.generators.auto import AutoGenerator
        return AutoGenerator(Path(project_path)).run()

    @classmethod
    def load(cls, path: str | Path = FILENAME) -> "BrainCtx":
        """
        Load an existing brain.ctx file.

        Args:
            path: Path to brain.ctx file. Defaults to './brain.ctx'.

        Returns:
            A BrainCtx instance populated from the file.

        Example:
            ctx = BrainCtx.load("./brain.ctx")
            print(ctx.identity["name"])
        """
        from brain_ctx.parsers.loader import BrainCtxLoader
        return BrainCtxLoader.load(Path(path))

    @classmethod
    def find(cls, start: str | Path = ".") -> Optional["BrainCtx"]:
        """
        Walk up directory tree to find the nearest brain.ctx file.
        Like how git finds .git — works from any subdirectory.

        Args:
            start: Directory to start searching from.

        Returns:
            BrainCtx if found, None otherwise.
        """
        current = Path(start).resolve()
        while True:
            candidate = current / FILENAME
            if candidate.exists():
                return cls.load(candidate)
            parent = current.parent
            if parent == current:
                return None
            current = parent

    # ──────────────────────────────────────────────────────────
    # Instance methods
    # ──────────────────────────────────────────────────────────

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate this brain.ctx against the official JSON schema.

        Returns:
            Tuple of (is_valid: bool, errors: list[str])

        Example:
            valid, errors = ctx.validate()
            if not valid:
                for error in errors:
                    print(error)
        """
        from brain_ctx.validators.schema import SchemaValidator
        return SchemaValidator().validate(self.to_dict())

    def build_context(
        self,
        model: str = "claude",
        token_budget: Optional[int] = None,
        live: bool = True,
        mode: Optional[str] = None,
    ) -> str:
        """
        Build the AI context string optimized for a specific model.

        Automatically adapts content based on:
        - Model's token budget (from cognitive layer)
        - Model-specific dialect instructions
        - Priority tiers (critical > important > reference)
        - Live truth source resolution (if live=True)

        Args:
            model:        Target model name (claude/gpt4/gemini/local)
            token_budget: Override token limit. None = use spec default.
            live:         If True, resolve truth_sources from live code.

        Returns:
            A formatted string ready to inject into any AI context.

        Example:
            context = ctx.build_context(model="claude", token_budget=12000)
            # Inject into your AI call
        """
        from brain_ctx.builders.context import ContextBuilder
        return ContextBuilder(self).build(
            model=model,
            token_budget=token_budget,
            live=live,
            mode=mode,
        )

    def ai_score(self) -> str:
        """
        Generate the AI Score acknowledgment line.
        This is what AI models output when they successfully absorb brain.ctx.

        Returns:
            Formatted AI Score string.

        Example:
            >>> print(ctx.ai_score())
            ✓ brain.ctx loaded — ManasDB v1.0 | Trust: read+write | 7 invariants active
        """
        name       = self.identity.get("name", "Unknown")
        trust      = self.trust.get("default", "read_only")
        invariants = len(self.hard_rules)
        agents     = len(self.trust.get("agents", {}))
        signed     = "✓" if self.signature.get("value") else "✗"
        verified   = "✓" if self.verification.get("auto_verify") else "!" if self.verification else "✗"

        parts = [
            f"✓ brain.ctx loaded — {name} v{self.version}",
            f"Trust: {trust}",
            f"{invariants} invariants active",
        ]
        if agents:
            parts.append(f"{agents} agents registered")
        parts.append(f"Signed: {signed}")
        parts.append(f"Verified: {verified}")
        return " | ".join(parts)


    def save(
        self,
        path: str | Path = FILENAME,
        include_comments: bool = True,
    ) -> Path:
        """
        Save brain.ctx to disk as YAML.

        Args:
            path:             Output file path. Defaults to './brain.ctx'.
            include_comments: Add helpful comments to the YAML output.

        Returns:
            Path to saved file.
        """
        from brain_ctx.parsers.writer import BrainCtxWriter
        output_path = Path(path)
        BrainCtxWriter.write(self, output_path, include_comments=include_comments)
        self._source_path = output_path
        return output_path

    def sign(self, private_key_path: str | Path) -> "BrainCtx":
        """
        Cryptographically sign this brain.ctx using Ed25519.

        Requires: pip install brain-ctx[signing]

        Args:
            private_key_path: Path to Ed25519 private key file.

        Returns:
            Self (mutated with signature block).
        """
        from brain_ctx.signers.ed25519 import Ed25519Signer
        self.signature = Ed25519Signer.sign(self, Path(private_key_path))
        return self

    def verify_signature(self) -> bool:
        """
        Verify the cryptographic signature of this brain.ctx.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not self.signature:
            return False
        from brain_ctx.signers.ed25519 import Ed25519Signer
        return Ed25519Signer.verify(self)

    def propose_update(self, project_path: str | Path = ".") -> list[dict]:
        """
        Scan project for new patterns and propose brain.ctx updates.
        Based on: new commits, new tests, dependency changes.

        Returns:
            List of proposals: [{"field": str, "value": Any, "confidence": float, "reason": str}]
        """
        from brain_ctx.generators.updater import UpdateProposer
        return UpdateProposer(self, Path(project_path)).propose()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict (for YAML/JSON output)."""
        out: dict[str, Any] = {"version": self.version}
        for field_name in [
            "identity", "inference", "trust", "hard_rules",
            "ethics", "truth_sources", "cognitive", "dialects",
            "mesh", "observability", "signature", "verification",
        ]:

            val = getattr(self, field_name)
            if val:
                out[field_name] = val
        # Include extra fields (inherit, timeline, conditional_rules)
        extra = getattr(self, "_extra", {}) or {}
        out.update(extra)
        return out

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        return yaml.dump(
            self.to_dict(),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def __repr__(self) -> str:
        name = self.identity.get("name", "unnamed")
        return f"BrainCtx(name={name!r}, version={self.version!r})"
