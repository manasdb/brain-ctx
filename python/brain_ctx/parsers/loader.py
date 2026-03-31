"""
BrainCtxLoader — load brain.ctx from disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class BrainCtxLoader:

    @staticmethod
    def load(path: Path) -> "BrainCtx":
        from brain_ctx.core import BrainCtx

        if not path.exists():
            raise FileNotFoundError(f"brain.ctx not found at: {path}")

        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

        ctx = BrainCtx(
            version       = raw.get("version", "1.0"),
            identity      = raw.get("identity", {}),
            inference     = raw.get("inference", {}),
            trust         = raw.get("trust", {}),
            hard_rules    = raw.get("hard_rules", []),
            ethics        = raw.get("ethics", {}),
            truth_sources = raw.get("truth_sources", {}),
            cognitive     = raw.get("cognitive", {}),
            dialects      = raw.get("dialects", {}),
            mesh          = raw.get("mesh", {}),
            observability = raw.get("observability", {}),
            signature     = raw.get("signature", {}),
        )
        ctx._source_path = path
        # Preserve extra fields not in the dataclass schema
        # (inherit, timeline, conditional_rules, etc.)
        known = {"version","identity","inference","trust","hard_rules","ethics",
                 "truth_sources","cognitive","dialects","mesh","observability","signature"}
        ctx._extra = {k: v for k, v in raw.items() if k not in known}
        return ctx
