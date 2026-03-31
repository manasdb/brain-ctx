"""
SchemaValidator
===============
Validates brain.ctx files against the official JSON Schema.
Schema lives in spec/brain-ctx.schema.json (shared across Python + Node).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

_BUNDLED = Path(__file__).parent.parent / "spec" / "brain-ctx.schema.json"
_DEV     = Path(__file__).parent.parent.parent.parent / "spec" / "brain-ctx.schema.json"


class SchemaValidator:
    """
    Validates brain.ctx data against the official JSON Schema (Draft 7).

    Falls back to built-in basic checks if jsonschema is not installed.

    Example:
        v = SchemaValidator()
        ok, errors = v.validate(ctx.to_dict())
    """

    def __init__(self):
        self._schema: dict | None = None

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        schema = self._load_schema()
        try:
            import jsonschema
            validator = jsonschema.Draft7Validator(schema)
            errs = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
            if errs:
                return False, [self._fmt(e) for e in errs]
            return True, []
        except ImportError:
            return self._basic(data)

    def validate_file(self, path: str | Path) -> tuple[bool, list[str]]:
        import yaml
        try:
            data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
            return self.validate(data or {})
        except yaml.YAMLError as e:
            return False, [f"YAML parse error: {e}"]
        except FileNotFoundError:
            return False, [f"File not found: {path}"]

    def _load_schema(self) -> dict:
        if self._schema is not None:
            return self._schema
        for p in [_BUNDLED, _DEV]:
            if p.exists():
                self._schema = json.loads(p.read_text())
                return self._schema
        # Minimal inline fallback
        self._schema = {
            "type": "object", "required": ["version", "identity"],
            "properties": {
                "version":  {"type": "string"},
                "identity": {"type": "object", "required": ["name"],
                             "properties": {"name": {"type": "string"}}},
            },
        }
        return self._schema

    def _fmt(self, e) -> str:
        path = " → ".join(str(p) for p in e.path) if e.path else "root"
        return f"[{path}] {e.message}"

    def _basic(self, data: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not isinstance(data, dict):
            return False, ["root must be a YAML mapping"]
        if "version" not in data:
            errors.append("[version] required field missing")
        if "identity" not in data:
            errors.append("[identity] required field missing")
        elif "name" not in data.get("identity", {}):
            errors.append("[identity.name] required field missing")
        td = data.get("trust", {}).get("default")
        if td and td not in ("read_only", "read_write", "no_access"):
            errors.append(f"[trust.default] invalid value '{td}'")
        return len(errors) == 0, errors
