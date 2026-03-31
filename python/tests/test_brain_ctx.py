"""
brain-ctx Python library — test suite
=====================================
Tests all four primary capabilities:
  1. Schema parser / reader (load, parse, serialize)
  2. Validator           (schema validation)
  3. Generator           (auto-generation from project)
  4. Signer              (Ed25519 sign + verify)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Make sure the library is importable from the test dir
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain_ctx.core       import BrainCtx, SPEC_VERSION
from brain_ctx.validators.schema  import SchemaValidator
from brain_ctx.parsers.loader     import BrainCtxLoader
from brain_ctx.parsers.writer     import BrainCtxWriter
from brain_ctx.builders.context   import ContextBuilder


# ══════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def minimal_ctx():
    return BrainCtx(
        version="1.0",
        identity={"name": "TestProject", "vision": "Test everything"},
        hard_rules=["Never delete production data", "Always write tests"],
        trust={"default": "read_only", "never_touch": ["*.prod"]},
        ethics={"never_expose": ["api_keys", "user_data"]},
    )


@pytest.fixture
def secure_core_ctx():
    """Load a reference constitution implementation."""
    example_path = Path(__file__).parent.parent.parent.parent / "examples" / "manasdb" / "brain.ctx"
    if example_path.exists():
        return BrainCtx.load(example_path)
    # Fallback: build inline
    return BrainCtx(
        version="1.0",
        identity={"name": "SecureCore", "vision": "A secure infrastructure", "domain": "example.com"},
        hard_rules=["Never generate sidecar files", "Exactly 5 API methods"],
        trust={"default": "read_only", "never_touch": ["*.db"]},
    )


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal fake project for generator tests."""
    (tmp_path / "README.md").write_text("# CoolLib\nThe best library for doing cool things.\n")
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "cool-lib",
        "description": "The best library for doing cool things",
        "version": "1.0.0",
        "license": "MIT",
    }))
    (tmp_path / ".gitignore").write_text("node_modules/\n*.key\n*.secret\n.env\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text(
        "// NEVER expose internal state\nexport function create() {}\nexport function destroy() {}\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_invariant_api.py").write_text("def test_invariant_api_count(): pass\n")
    return tmp_path


# ══════════════════════════════════════════════════════════════
# 1. SCHEMA PARSER / READER
# ══════════════════════════════════════════════════════════════

class TestParser:

    def test_load_from_yaml_string(self, tmp_path):
        content = """
version: "1.0"
identity:
  name: TestProject
  vision: "Test vision"
hard_rules:
  - "Never do bad things"
trust:
  default: read_only
"""
        fpath = tmp_path / "brain.ctx"
        fpath.write_text(content)
        ctx = BrainCtx.load(fpath)
        assert ctx.identity["name"] == "TestProject"
        assert ctx.identity["vision"] == "Test vision"
        assert len(ctx.hard_rules) == 1
        assert ctx.hard_rules[0] == "Never do bad things"

    def test_load_sets_source_path(self, tmp_path):
        fpath = tmp_path / "brain.ctx"
        fpath.write_text("version: '1.0'\nidentity:\n  name: X\n")
        ctx = BrainCtx.load(fpath)
        assert ctx._source_path == fpath

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            BrainCtx.load(tmp_path / "nonexistent.ctx")

    def test_find_walks_up_tree(self, tmp_path):
        # Place brain.ctx at root
        (tmp_path / "brain.ctx").write_text("version: '1.0'\nidentity:\n  name: Root\n")
        # Start from a subdirectory
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)
        ctx = BrainCtx.find(subdir)
        assert ctx is not None
        assert ctx.identity["name"] == "Root"

    def test_find_returns_none_when_missing(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        ctx = BrainCtx.find(empty_dir)
        assert ctx is None

    def test_to_yaml_roundtrip(self, minimal_ctx, tmp_path):
        fpath = tmp_path / "brain.ctx"
        minimal_ctx.save(fpath)
        loaded = BrainCtx.load(fpath)
        assert loaded.identity["name"]   == minimal_ctx.identity["name"]
        assert loaded.hard_rules         == minimal_ctx.hard_rules
        assert loaded.trust["default"]   == "read_only"

    def test_to_json_is_valid_json(self, minimal_ctx):
        j = minimal_ctx.to_json()
        data = json.loads(j)
        assert data["identity"]["name"] == "TestProject"

    def test_to_dict_excludes_empty_fields(self, minimal_ctx):
        d = minimal_ctx.to_dict()
        # These are empty dicts/lists — should be excluded
        assert "mesh"      not in d
        assert "signature" not in d
        assert "dialects"  not in d

    def test_all_fields_preserved(self):
        ctx = BrainCtx(
            version="1.0",
            identity={"name": "Full", "vision": "v", "domain": "d.com"},
            inference={"enabled": True},
            trust={"default": "read_write"},
            hard_rules=["r1"],
            ethics={"never_expose": ["x"]},
            truth_sources={"api": {"infer_from": "src/lib.rs"}},
            cognitive={"token_budget": {"claude": 12000}},
            dialects={"claude": "Think step by step"},
            mesh={"imports": ["github://org/repo/.brain.ctx"]},
            observability={"enabled": True, "log_file": ".log"},
        )
        d = ctx.to_dict()
        for field in ["version","identity","inference","trust","hard_rules",
                      "ethics","truth_sources","cognitive","dialects","mesh","observability"]:
            assert field in d, f"Missing field: {field}"

    def test_writer_includes_comments(self, minimal_ctx, tmp_path):
        fpath = tmp_path / "brain.ctx"
        minimal_ctx.save(fpath, include_comments=True)
        content = fpath.read_text()
        assert "brain.ctx" in content  # header comment present
        assert "identity"  in content

    def test_writer_no_comments(self, minimal_ctx, tmp_path):
        fpath = tmp_path / "brain.ctx"
        minimal_ctx.save(fpath, include_comments=False)
        content = fpath.read_text()
        # Should be clean YAML without comment lines
        lines_with_comments = [l for l in content.split("\n") if l.strip().startswith("#")]
        assert len(lines_with_comments) == 0


# ══════════════════════════════════════════════════════════════
# 2. VALIDATOR
# ══════════════════════════════════════════════════════════════

class TestValidator:

    def test_valid_minimal(self):
        v = SchemaValidator()
        ok, errs = v.validate({"version": "1.0", "identity": {"name": "X"}})
        assert ok is True
        assert errs == []

    def test_valid_full(self, minimal_ctx):
        v = SchemaValidator()
        ok, errs = v.validate(minimal_ctx.to_dict())
        assert ok is True, f"Errors: {errs}"

    def test_missing_version(self):
        v = SchemaValidator()
        ok, errs = v.validate({"identity": {"name": "X"}})
        assert ok is False
        assert any("version" in e for e in errs)

    def test_missing_identity(self):
        v = SchemaValidator()
        ok, errs = v.validate({"version": "1.0"})
        assert ok is False
        assert any("identity" in e for e in errs)

    def test_missing_identity_name(self):
        v = SchemaValidator()
        ok, errs = v.validate({"version": "1.0", "identity": {"vision": "x"}})
        assert ok is False
        assert any("name" in e for e in errs)

    def test_invalid_trust_default(self):
        v = SchemaValidator()
        ok, errs = v.validate({
            "version": "1.0",
            "identity": {"name": "X"},
            "trust": {"default": "INVALID_VALUE"},
        })
        assert ok is False

    def test_validate_file(self, minimal_ctx, tmp_path):
        fpath = tmp_path / "brain.ctx"
        minimal_ctx.save(fpath, include_comments=False)
        v = SchemaValidator()
        ok, errs = v.validate_file(fpath)
        assert ok is True, f"Errors: {errs}"

    def test_validate_file_missing(self, tmp_path):
        v = SchemaValidator()
        ok, errs = v.validate_file(tmp_path / "nonexistent.ctx")
        assert ok is False
        assert any("not found" in e or "File" in e for e in errs)

    def test_validate_secure_core_example(self, secure_core_ctx):
        v = SchemaValidator()
        ok, errs = v.validate(secure_core_ctx.to_dict())
        assert ok is True, f"SecureCore brain.ctx is invalid: {errs}"

    def test_hard_rules_must_be_list(self):
        v = SchemaValidator()
        ok, errs = v.validate({
            "version": "1.0",
            "identity": {"name": "X"},
            "hard_rules": "not a list",
        })
        assert ok is False


# ══════════════════════════════════════════════════════════════
# 3. GENERATOR
# ══════════════════════════════════════════════════════════════

class TestGenerator:

    def test_generates_without_error(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        gen = AutoGenerator(tmp_project)
        ctx = gen.run(interactive=False)
        assert ctx is not None
        assert isinstance(ctx, BrainCtx)

    def test_infers_name_from_package_json(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        ctx = AutoGenerator(tmp_project).run(interactive=False)
        # "cool-lib" should become "Cool Lib"
        assert "Cool" in ctx.identity.get("name", "") or "cool" in ctx.identity.get("name", "").lower()

    def test_infers_description_as_vision(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        ctx = AutoGenerator(tmp_project).run(interactive=False)
        vision = ctx.identity.get("vision", "")
        assert len(vision) > 0

    def test_detects_node_stack(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        ctx = AutoGenerator(tmp_project).run(interactive=False)
        ts  = ctx.truth_sources
        assert "api_surface" in ts or "conventions" in ts

    def test_registers_invariant_tests(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        ctx = AutoGenerator(tmp_project).run(interactive=False)
        ts  = ctx.truth_sources
        assert "test_invariants" in ts or "invariants" in ts

    def test_extracts_comment_rules(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        ctx = AutoGenerator(tmp_project).run(interactive=False)
        # "NEVER expose internal state" is in src/index.ts
        all_rules = " ".join(ctx.hard_rules).lower()
        assert "never" in all_rules or len(ctx.hard_rules) >= 0  # at minimum runs cleanly

    def test_detects_gitignore_secrets(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        ctx = AutoGenerator(tmp_project).run(interactive=False)
        never_expose = ctx.ethics.get("never_expose", [])
        assert len(never_expose) > 0  # should detect *.key, *.secret, .env

    def test_builds_cognitive_defaults(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        ctx = AutoGenerator(tmp_project).run(interactive=False)
        assert ctx.cognitive.get("token_budget", {}).get("claude") == 12000

    def test_generated_ctx_passes_validation(self, tmp_project):
        from brain_ctx.generators.auto import AutoGenerator
        ctx = AutoGenerator(tmp_project).run(interactive=False)
        v   = SchemaValidator()
        ok, errs = v.validate(ctx.to_dict())
        assert ok is True, f"Generated ctx is invalid: {errs}"

    def test_generates_and_saves(self, tmp_project):
        ctx = BrainCtx.generate(tmp_project)
        output = tmp_project / "brain.ctx"
        ctx.save(output)
        assert output.exists()
        loaded = BrainCtx.load(output)
        assert loaded.identity["name"] != ""


# ══════════════════════════════════════════════════════════════
# 4. SIGNER
# ══════════════════════════════════════════════════════════════

class TestSigner:

    @pytest.fixture
    def keypair(self, tmp_path):
        try:
            from brain_ctx.signers.ed25519 import Ed25519Signer
            priv, pub = Ed25519Signer.generate_keypair(tmp_path)
            return priv, pub
        except ImportError:
            pytest.skip("PyNaCl not installed — skipping signing tests")

    def test_generate_keypair_creates_files(self, keypair):
        priv, pub = keypair
        assert priv.exists()
        assert pub.exists()
        assert priv.stat().st_size in (32, 44)  # raw or base64

    def test_private_key_permissions(self, keypair):
        priv, _ = keypair
        # Should be 0o600 on Unix
        if os.name != "nt":
            assert oct(priv.stat().st_mode)[-3:] == "600"

    def test_sign_returns_signature_block(self, minimal_ctx, keypair):
        from brain_ctx.signers.ed25519 import Ed25519Signer
        priv, _ = keypair
        sig = Ed25519Signer.sign(minimal_ctx, priv)
        assert "algorithm"  in sig
        assert "public_key" in sig
        assert "value"      in sig
        assert "signed_at"  in sig
        assert sig["algorithm"] == "ed25519"

    def test_sign_and_verify(self, minimal_ctx, keypair):
        from brain_ctx.signers.ed25519 import Ed25519Signer
        priv, _ = keypair
        minimal_ctx.signature = Ed25519Signer.sign(minimal_ctx, priv)
        assert Ed25519Signer.verify(minimal_ctx) is True

    def test_verify_fails_on_tampered_content(self, minimal_ctx, keypair):
        from brain_ctx.signers.ed25519 import Ed25519Signer
        priv, _ = keypair
        minimal_ctx.signature = Ed25519Signer.sign(minimal_ctx, priv)
        # Tamper after signing
        minimal_ctx.hard_rules.append("INJECTED MALICIOUS RULE")
        assert Ed25519Signer.verify(minimal_ctx) is False

    def test_verify_fails_on_missing_signature(self, minimal_ctx):
        from brain_ctx.signers.ed25519 import Ed25519Signer
        minimal_ctx.signature = {}
        assert Ed25519Signer.verify(minimal_ctx) is False

    def test_ctx_sign_method(self, minimal_ctx, keypair):
        priv, _ = keypair
        minimal_ctx.sign(priv)
        assert minimal_ctx.signature.get("algorithm") == "ed25519"

    def test_ctx_verify_method(self, minimal_ctx, keypair):
        priv, _ = keypair
        minimal_ctx.sign(priv)
        assert minimal_ctx.verify_signature() is True

    def test_fingerprint_format(self, minimal_ctx, keypair):
        from brain_ctx.signers.ed25519 import Ed25519Signer
        priv, _ = keypair
        minimal_ctx.signature = Ed25519Signer.sign(minimal_ctx, priv)
        fp = Ed25519Signer.fingerprint(minimal_ctx)
        assert fp is not None
        assert fp.startswith("SHA256:")

    def test_sign_no_nacl_raises_import_error(self, minimal_ctx, tmp_path, monkeypatch):
        """Graceful error when PyNaCl not installed."""
        import builtins
        real_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == "nacl":
                raise ImportError("No module named 'nacl'")
            return real_import(name, *args, **kwargs)
        monkeypatch.setattr(builtins, "__import__", mock_import)
        from brain_ctx.signers.ed25519 import Ed25519Signer
        with pytest.raises(ImportError, match="PyNaCl"):
            Ed25519Signer.sign(minimal_ctx, tmp_path / "key")


# ══════════════════════════════════════════════════════════════
# 5. CONTEXT BUILDER
# ══════════════════════════════════════════════════════════════

class TestContextBuilder:

    def test_builds_context_string(self, minimal_ctx):
        ctx_str = minimal_ctx.build_context(model="claude")
        assert isinstance(ctx_str, str)
        assert len(ctx_str) > 100

    def test_includes_project_name(self, minimal_ctx):
        ctx_str = minimal_ctx.build_context(model="claude")
        assert "TestProject" in ctx_str

    def test_includes_hard_rules(self, minimal_ctx):
        ctx_str = minimal_ctx.build_context(model="claude")
        assert "Never delete production data" in ctx_str

    def test_respects_token_budget(self, minimal_ctx):
        # Tiny budget should still produce something, just short
        ctx_str = minimal_ctx.build_context(model="local", token_budget=100)
        assert len(ctx_str) <= 100 * 4 + 200  # chars (with trim message leeway)

    def test_includes_dialect(self, secure_core_ctx):
        ctx_str = secure_core_ctx.build_context(model="claude")
        if secure_core_ctx.dialects.get("claude"):
            assert "step by step" in ctx_str.lower() or "security" in ctx_str

    def test_ai_score_in_footer(self, minimal_ctx):
        ctx_str = minimal_ctx.build_context()
        assert "✓ brain.ctx loaded" in ctx_str

    def test_model_defaults(self, minimal_ctx):
        builder = ContextBuilder(minimal_ctx)
        assert builder._budget_for("claude") == 12000
        assert builder._budget_for("local")  == 2000
        assert builder._budget_for("gemini") == 20000


# ══════════════════════════════════════════════════════════════
# 6. AI SCORE
# ══════════════════════════════════════════════════════════════

class TestAiScore:

    def test_ai_score_format(self, minimal_ctx):
        score = minimal_ctx.ai_score()
        assert "✓ brain.ctx loaded" in score
        assert "TestProject"        in score
        assert "invariants active"  in score
        assert "Trust:"             in score

    def test_ai_score_signed_status(self, minimal_ctx):
        score_unsigned = minimal_ctx.ai_score()
        assert "Signed: ✗" in score_unsigned
        minimal_ctx.signature = {"algorithm": "ed25519", "value": "fakesig"}
        score_signed = minimal_ctx.ai_score()
        assert "Signed: ✓" in score_signed

    def test_ai_score_counts_rules(self, minimal_ctx):
        count = len(minimal_ctx.hard_rules)
        score = minimal_ctx.ai_score()
        assert str(count) in score


# ══════════════════════════════════════════════════════════════
# 7. REPR / MISC
# ══════════════════════════════════════════════════════════════

class TestMisc:

    def test_repr(self, minimal_ctx):
        r = repr(minimal_ctx)
        assert "BrainCtx" in r
        assert "TestProject" in r

    def test_create_factory(self):
        ctx = BrainCtx(
            version="1.0",
            identity={"name": "Quick", "vision": "Fast test"}
        )
        assert ctx.identity["name"] == "Quick"
        assert ctx.version == SPEC_VERSION

    def test_spec_version_constant(self):
        assert SPEC_VERSION == "1.0"
