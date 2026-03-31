"""
Tests for the 5 new brain-ctx features:
  1. Doctor (health checks)
  2. Diff (observability log reader)
  3. Pattern Library (stack detection)
  4. Conditional Rules
  5. Inheritance
  6. Writer extra fields
"""

import json, os, shutil, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain_ctx.core              import BrainCtx
from brain_ctx.doctors.health    import DoctorRunner
from brain_ctx.diff.log_reader   import DiffReader, LogEntry
from brain_ctx.patterns.library  import StackDetector, PATTERNS
from brain_ctx.rules.conditional import ConditionalRuleEngine, ConditionalRule, RuleContext
from brain_ctx.inherit.resolver  import InheritanceResolver


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def healthy_ctx(tmp_dir):
    (tmp_dir / "src").mkdir()
    (tmp_dir / "src" / "core.py").write_text("def main(): pass")
    return BrainCtx(
        version="1.0",
        identity={
            "name":   "HealthyProject",
            "vision": "A well-configured project with good brain.ctx hygiene",
            "author": "Test Author",
        },
        hard_rules=[
            "Never expose API keys in logs or responses",
            "Always use parameterized queries — never string interpolation",
            "Never delete records — use soft delete with deleted_at",
        ],
        trust={
            "default": "read_only",
            "never_touch": ["*.key", "*.pem", "*.pid", "*.sock", "*.lock"],
            "mutex_files": [str(tmp_dir / "src" / "core.py")],
            "agents": {
                "architect":   {"can": ["read_all"], "cannot": ["write"]},
                "implementor": {"can": ["write_code"], "cannot": ["delete"]},
            },
        },
        ethics={
            "never_expose": ["api_keys", "user_pii"],
            "data_sovereignty": "EU",
        },
        cognitive={"token_budget": {"claude": 12000, "gpt4": 8000, "local": 2000}},
        observability={"enabled": True, "log_file": ".brain-ctx.log", "retention": "90_days"},
    )


@pytest.fixture
def log_file(tmp_dir):
    path = tmp_dir / ".brain-ctx.log"
    now  = datetime.now(timezone.utc)
    entries = [
        {"ts": (now-timedelta(hours=2)).isoformat(), "session_id":"sess-aaa","model":"claude","role":"implementor","action":"write","path":"src/OrderService.ts","allowed":True,"summary":"Added validation"},
        {"ts": (now-timedelta(hours=2,minutes=-5)).isoformat(), "session_id":"sess-aaa","model":"claude","role":"implementor","action":"write","path":"src/PaymentService.ts","allowed":False,"reason":"mutex file"},
        {"ts": (now-timedelta(hours=1)).isoformat(), "session_id":"sess-bbb","model":"gpt4","role":"reviewer","action":"read","path":"src/Transaction.ts","allowed":True},
        {"ts": (now-timedelta(minutes=30)).isoformat(), "session_id":"sess-aaa","model":"claude","role":"implementor","action":"propose","summary":"Add retry logic","allowed":True},
    ]
    with open(path,"w") as f:
        for e in entries: f.write(json.dumps(e)+"\n")
    return path


def write_ctx(tmp_dir, filename, content):
    p = tmp_dir / filename
    p.write_text(content)
    return BrainCtx.load(p)


# ══════════════════════════════════════════════════════════════
# 1. DOCTOR
# ══════════════════════════════════════════════════════════════

class TestDoctor:

    def test_healthy_passes(self, healthy_ctx, tmp_dir):
        report = DoctorRunner(healthy_ctx, project_root=tmp_dir).run()
        assert len(report.errors) == 0, [r.message for r in report.errors]

    def test_missing_name_error(self, tmp_dir):
        ctx    = BrainCtx(version="1.0", identity={})
        report = DoctorRunner(ctx, tmp_dir).run()
        assert any(r.check=="identity.name" and r.severity=="ERROR" for r in report.results)

    def test_missing_vision_warn(self, tmp_dir):
        ctx    = BrainCtx(version="1.0", identity={"name":"X"})
        report = DoctorRunner(ctx, tmp_dir).run()
        assert any("vision" in r.check and r.severity=="WARN" for r in report.results)

    def test_too_few_rules_warn(self, tmp_dir):
        ctx    = BrainCtx(version="1.0", identity={"name":"X","vision":"Long enough vision here"}, hard_rules=["One rule"])
        report = DoctorRunner(ctx, tmp_dir).run()
        assert any("hard_rules.count" in r.check and r.severity=="WARN" for r in report.results)

    def test_vague_rules_flagged(self, tmp_dir):
        ctx    = BrainCtx(version="1.0", identity={"name":"X","vision":"Long enough vision here"}, hard_rules=["Be careful with db","Try to validate"])
        report = DoctorRunner(ctx, tmp_dir).run()
        assert any("precision" in r.check and r.severity=="WARN" for r in report.results)

    def test_broken_truth_source_error(self, tmp_dir):
        ctx    = BrainCtx(version="1.0", identity={"name":"X","vision":"Long enough vision"}, truth_sources={"api":{"infer_from":"does_not_exist.ts","auto_extract":True}})
        report = DoctorRunner(ctx, tmp_dir).run()
        assert any("truth_sources.paths" in r.check and r.severity=="ERROR" for r in report.results)

    def test_valid_truth_source_passes(self, tmp_dir):
        (tmp_dir/"src").mkdir(exist_ok=True)
        (tmp_dir/"src"/"index.ts").write_text("export function x(){}")
        ctx    = BrainCtx(version="1.0", identity={"name":"X","vision":"Long enough vision"}, truth_sources={"api":{"infer_from":"src/index.ts","auto_extract":True}})
        report = DoctorRunner(ctx, tmp_dir).run()
        assert not any("truth_sources.paths" in r.check and r.severity=="ERROR" for r in report.results)

    def test_contradictory_agent_perms_error(self, tmp_dir):
        ctx = BrainCtx(version="1.0", identity={"name":"X","vision":"Long enough vision"},
                       trust={"default":"read_only","agents":{"broken":{"can":["write"],"cannot":["write"]}}})
        report = DoctorRunner(ctx, tmp_dir).run()
        assert any("agents.broken" in r.check and r.severity=="ERROR" for r in report.results)

    def test_read_write_default_warn(self, tmp_dir):
        ctx    = BrainCtx(version="1.0", identity={"name":"X","vision":"Long enough vision"}, trust={"default":"read_write"})
        report = DoctorRunner(ctx, tmp_dir).run()
        assert any("trust.default" in r.check and r.severity=="WARN" for r in report.results)

    def test_invalid_token_budget_warn(self, tmp_dir):
        ctx    = BrainCtx(version="1.0", identity={"name":"X","vision":"Long enough vision"}, cognitive={"token_budget":{"claude":12000,"local":99999}})
        report = DoctorRunner(ctx, tmp_dir).run()
        assert any("token_budget" in r.check and r.severity=="WARN" for r in report.results)

    def test_report_to_dict(self, healthy_ctx, tmp_dir):
        d = DoctorRunner(healthy_ctx, tmp_dir).run().to_dict()
        assert {"passed","errors","warnings","ok","checks"} <= set(d.keys())

    def test_summary_format(self, healthy_ctx, tmp_dir):
        s = DoctorRunner(healthy_ctx, tmp_dir).run().summary()
        assert "brain.ctx doctor" in s
        assert "HEALTHY" in s or "UNHEALTHY" in s


# ══════════════════════════════════════════════════════════════
# 2. DIFF
# ══════════════════════════════════════════════════════════════

class TestDiff:

    def test_loads_all_entries(self, log_file):
        assert len(DiffReader(log_file).all().entries) == 4

    def test_writes_filter(self, log_file):
        writes = DiffReader(log_file).all().writes
        assert len(writes)==1 and writes[0].path=="src/OrderService.ts"

    def test_blocked_filter(self, log_file):
        blocked = DiffReader(log_file).all().blocked
        assert len(blocked)==1 and blocked[0].path=="src/PaymentService.ts"

    def test_proposals_filter(self, log_file):
        proposals = DiffReader(log_file).all().proposals
        assert len(proposals)==1 and "retry" in proposals[0].summary.lower()

    def test_sessions_grouping(self, log_file):
        sessions = DiffReader(log_file).all().sessions
        assert "sess-aaa" in sessions and len(sessions["sess-aaa"])==3

    def test_files_touched_excludes_blocked(self, log_file):
        files = DiffReader(log_file).all().files_touched
        assert "src/OrderService.ts"  in files
        assert "src/PaymentService.ts" not in files

    def test_for_role_filter(self, log_file):
        entries = DiffReader(log_file).for_role("reviewer").entries
        assert all(e.role=="reviewer" for e in entries) and len(entries)==1

    def test_violations_only(self, log_file):
        entries = DiffReader(log_file).violations_only().entries
        assert all(e.allowed is False for e in entries)

    def test_rotate_archives_all(self, log_file):
        reader  = DiffReader(log_file)
        n, path = reader.rotate(keep_days=0)
        assert n==4 and path.exists()
        assert len(reader._load_entries())==0

    def test_stats(self, log_file):
        s = DiffReader(log_file).stats()
        assert s["total"]==4 and s["writes"]==1 and s["blocked"]==1 and s["sessions"]==2

    def test_empty_log_is_fine(self, tmp_dir):
        report = DiffReader(tmp_dir/"none.log").all()
        assert len(report.entries)==0

    def test_log_entry_parses_timestamp(self):
        e = LogEntry.from_dict({"ts":"2026-01-15T10:30:00Z","session_id":"x","model":"claude","role":"impl","action":"write","allowed":True})
        assert e.ts.year==2026 and e.model=="claude"


# ══════════════════════════════════════════════════════════════
# 3. PATTERN LIBRARY
# ══════════════════════════════════════════════════════════════

class TestPatternLibrary:

    def test_patterns_not_empty(self):
        assert len(PATTERNS) >= 15

    def test_all_patterns_have_required_fields(self):
        for p in PATTERNS:
            assert p.name and p.language and p.api_pattern and p.entry_files

    def test_detect_node_project(self, tmp_dir):
        (tmp_dir/"package.json").write_text('{"name":"app","dependencies":{"express":"^4"}}')
        (tmp_dir/"src").mkdir()
        (tmp_dir/"src"/"index.js").write_text("export function x(){}")
        stacks = StackDetector(tmp_dir).detect()
        assert len(stacks)>0 and any("Node" in s.name or "Express" in s.name for s in stacks)

    def test_detect_rust_project(self, tmp_dir):
        (tmp_dir/"Cargo.toml").write_text('[package]\nname="mylib"\nversion="0.1.0"')
        (tmp_dir/"src").mkdir()
        (tmp_dir/"src"/"lib.rs").write_text("pub fn hello() {}")
        assert any("Rust" in s.name for s in StackDetector(tmp_dir).detect())

    def test_detect_fastapi_project(self, tmp_dir):
        (tmp_dir/"requirements.txt").write_text("fastapi==0.100.0\nuvicorn")
        (tmp_dir/"main.py").write_text("from fastapi import FastAPI\napp=FastAPI()")
        assert any("FastAPI" in s.name for s in StackDetector(tmp_dir).detect())

    def test_js_preferred_over_ts(self, tmp_dir):
        (tmp_dir/"package.json").write_text('{"name":"x"}')
        (tmp_dir/"src").mkdir()
        (tmp_dir/"src"/"index.js").write_text("export function x(){}")
        stacks = StackDetector(tmp_dir).detect()
        node   = next((s for s in stacks if "Node" in s.name), None)
        if node and node.detected_entry:
            assert ".js" in node.detected_entry

    def test_all_api_patterns_are_valid_regex(self):
        import re
        for p in PATTERNS:
            try: re.compile(p.api_pattern)
            except re.error as e: pytest.fail(f"{p.name}: invalid regex: {e}")

    def test_detect_primary_returns_highest_confidence(self, tmp_dir):
        (tmp_dir/"Cargo.toml").write_text('[package]\nname="x"\nversion="0.1.0"')
        (tmp_dir/"src").mkdir()
        (tmp_dir/"src"/"lib.rs").write_text("pub fn x() {}")
        primary = StackDetector(tmp_dir).detect_primary()
        assert primary is not None and primary.confidence > 0


# ══════════════════════════════════════════════════════════════
# 4. CONDITIONAL RULES
# ══════════════════════════════════════════════════════════════

class TestConditionalRules:

    def test_no_conditions_always_applies(self):
        r = ConditionalRule(rule="X")
        assert r.applies_to(RuleContext(env="production"))
        assert r.applies_to(RuleContext(env="development"))

    def test_env_string_condition(self):
        r = ConditionalRule(rule="X", when={"env":"production"})
        assert     r.applies_to(RuleContext(env="production"))
        assert not r.applies_to(RuleContext(env="development"))

    def test_env_list_condition(self):
        r = ConditionalRule(rule="X", when={"env":["production","staging"]})
        assert r.applies_to(RuleContext(env="staging"))
        assert not r.applies_to(RuleContext(env="development"))

    def test_env_aliases(self):
        r = ConditionalRule(rule="X", when={"env":"prod"})
        assert r.applies_to(RuleContext(env="production"))
        assert r.applies_to(RuleContext(env="live"))
        r2 = ConditionalRule(rule="X", when={"env":"dev"})
        assert r2.applies_to(RuleContext(env="development"))
        assert r2.applies_to(RuleContext(env="local"))

    def test_branch_exact(self):
        r = ConditionalRule(rule="X", when={"branch":"main"})
        assert     r.applies_to(RuleContext(env="x", branch="main"))
        assert not r.applies_to(RuleContext(env="x", branch="feature/x"))

    def test_branch_wildcard(self):
        r = ConditionalRule(rule="X", when={"branch":["main","release/*"]})
        assert     r.applies_to(RuleContext(env="x", branch="release/v2.0"))
        assert not r.applies_to(RuleContext(env="x", branch="feature/y"))

    def test_role_condition(self):
        r = ConditionalRule(rule="X", when={"role":"reviewer"})
        assert     r.applies_to(RuleContext(env="x", agent_role="reviewer"))
        assert not r.applies_to(RuleContext(env="x", agent_role="implementor"))

    def test_path_changed_condition(self):
        r = ConditionalRule(rule="X", when={"path_changed":["src/migrations/*"]})
        assert     r.applies_to(RuleContext(env="x", changed_paths=["src/migrations/001.sql"]))
        assert not r.applies_to(RuleContext(env="x", changed_paths=["src/app.ts"]))

    def test_multiple_conditions_and_logic(self):
        r = ConditionalRule(rule="X", when={"env":"production","branch":"main"})
        assert     r.applies_to(RuleContext(env="production", branch="main"))
        assert not r.applies_to(RuleContext(env="production", branch="feature/x"))
        assert not r.applies_to(RuleContext(env="development", branch="main"))

    def test_hard_rules_always_on_in_engine(self):
        ctx = BrainCtx(version="1.0", identity={"name":"X"}, hard_rules=["Never expose keys"])
        active = ConditionalRuleEngine(ctx).evaluate(RuleContext(env="development"))
        assert any(r.rule=="Never expose keys" and r.source=="hard_rules" for r in active)

    def test_is_production_helper(self):
        assert     RuleContext(env="production").is_production
        assert     RuleContext(env="prod").is_production
        assert     RuleContext(env="live").is_production
        assert not RuleContext(env="development").is_production
        assert not RuleContext(env="staging").is_production

    def test_is_protected_branch_helper(self):
        assert     RuleContext(env="x", branch="main").is_protected_branch
        assert     RuleContext(env="x", branch="master").is_protected_branch
        assert not RuleContext(env="x", branch="feature/my-feature").is_protected_branch

    def test_engine_summary_contains_env(self):
        ctx     = BrainCtx(version="1.0", identity={"name":"X"}, hard_rules=["Rule"])
        summary = ConditionalRuleEngine(ctx).summary(RuleContext(env="production", branch="main"))
        assert "production" in summary


# ══════════════════════════════════════════════════════════════
# 5. INHERITANCE
# ══════════════════════════════════════════════════════════════

class TestInheritance:

    def test_no_inherit_returns_unchanged(self, tmp_dir):
        ctx    = BrainCtx(version="1.0", identity={"name":"Standalone"})
        merged = InheritanceResolver(ctx, tmp_dir).resolve()
        assert merged.identity["name"] == "Standalone"

    def test_hard_rules_accumulate(self, tmp_dir):
        write_ctx(tmp_dir,"parent.ctx","version: '1.0'\nidentity:\n  name: P\nhard_rules:\n  - Parent rule\n")
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: parent.ctx\nidentity:\n  name: C\nhard_rules:\n  - Child rule\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        assert "Parent rule" in merged.hard_rules
        assert "Child rule"  in merged.hard_rules

    def test_no_duplicate_rules(self, tmp_dir):
        write_ctx(tmp_dir,"parent.ctx","version: '1.0'\nidentity:\n  name: P\nhard_rules:\n  - Shared rule\n")
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: parent.ctx\nidentity:\n  name: C\nhard_rules:\n  - Shared rule\n  - Child rule\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        assert merged.hard_rules.count("Shared rule") == 1

    def test_child_identity_wins(self, tmp_dir):
        write_ctx(tmp_dir,"parent.ctx","version: '1.0'\nidentity:\n  name: Parent\n  vision: Parent vision\n")
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: parent.ctx\nidentity:\n  name: Child\n  vision: Child vision\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        assert merged.identity["name"]   == "Child"
        assert merged.identity["vision"] == "Child vision"

    def test_never_touch_combined(self, tmp_dir):
        write_ctx(tmp_dir,"parent.ctx","version: '1.0'\nidentity:\n  name: P\ntrust:\n  default: read_only\n  never_touch: ['*.key']\n")
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: parent.ctx\nidentity:\n  name: C\ntrust:\n  never_touch: ['*.pem']\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        nt     = merged.trust.get("never_touch", [])
        assert "*.key" in nt and "*.pem" in nt

    def test_child_agent_overrides_parent(self, tmp_dir):
        write_ctx(tmp_dir,"parent.ctx","version: '1.0'\nidentity:\n  name: P\ntrust:\n  default: read_only\n  agents:\n    implementor:\n      can: [write_code]\n      cannot: [delete]\n")
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: parent.ctx\nidentity:\n  name: C\ntrust:\n  agents:\n    implementor:\n      can: [write_code, run_tests]\n      cannot: [delete, run_live_charges]\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        impl   = merged.trust.get("agents", {}).get("implementor", {})
        assert "run_live_charges" in impl.get("cannot", [])
        assert "run_tests"        in impl.get("can",    [])

    def test_ethics_combined(self, tmp_dir):
        write_ctx(tmp_dir,"parent.ctx","version: '1.0'\nidentity:\n  name: P\nethics:\n  data_sovereignty: EU\n  never_expose: [api_keys]\n")
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: parent.ctx\nidentity:\n  name: C\nethics:\n  data_sovereignty: US\n  never_expose: [passwords]\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        assert merged.ethics.get("data_sovereignty") == "US"
        ne = merged.ethics.get("never_expose", [])
        assert "api_keys" in ne and "passwords" in ne

    def test_missing_parent_warning(self, tmp_dir, capsys):
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: nonexistent.ctx\nidentity:\n  name: Child\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        assert merged.identity["name"] == "Child"
        assert "not found" in capsys.readouterr().out

    def test_three_level_chain(self, tmp_dir):
        (tmp_dir/"gp.ctx").write_text("version: '1.0'\nidentity:\n  name: GP\nhard_rules:\n  - GP rule\n")
        (tmp_dir/"parent.ctx").write_text("version: '1.0'\ninherit: gp.ctx\nidentity:\n  name: Parent\nhard_rules:\n  - Parent rule\n")
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: parent.ctx\nidentity:\n  name: Child\nhard_rules:\n  - Child rule\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        assert all(r in merged.hard_rules for r in ["GP rule","Parent rule","Child rule"])
        assert merged.identity["name"] == "Child"

    def test_signature_never_inherited(self, tmp_dir):
        write_ctx(tmp_dir,"parent.ctx","version: '1.0'\nidentity:\n  name: P\nsignature:\n  algorithm: ed25519\n  value: fakesig\n")
        child  = write_ctx(tmp_dir,"child.ctx","version: '1.0'\ninherit: parent.ctx\nidentity:\n  name: C\n")
        merged = InheritanceResolver(child, tmp_dir).resolve()
        assert not merged.signature.get("value")

    def test_monorepo_example(self):
        examples = Path(__file__).parent.parent.parent/"examples"/"monorepo-inherit"
        if not (examples/"brain.ctx").exists():
            pytest.skip("Monorepo example not found")
        child  = BrainCtx.load(examples/"services"/"notifications"/"brain.ctx")
        merged = InheritanceResolver(child, examples/"services"/"notifications").resolve()
        assert "Never log sensitive PII" in " ".join(merged.hard_rules)
        assert any("opt-out" in r for r in merged.hard_rules)
        assert merged.identity["name"] == "Acme Notifications Service"


# ══════════════════════════════════════════════════════════════
# 6. WRITER EXTRA FIELDS
# ══════════════════════════════════════════════════════════════

class TestWriterExtraFields:

    def test_inherit_preserved_on_save(self, tmp_dir):
        ctx        = BrainCtx(version="1.0", identity={"name":"X"})
        ctx._extra = {"inherit": "../brain.ctx"}
        out        = tmp_dir/"out.ctx"
        ctx.save(out, include_comments=False)
        assert yaml.safe_load(out.read_text()).get("inherit") == "../brain.ctx"

    def test_timeline_preserved_on_save(self, tmp_dir):
        ctx        = BrainCtx(version="1.0", identity={"name":"X"})
        ctx._extra = {"timeline": [{"date":"2024-01","event":"Initial commit"}]}
        out        = tmp_dir/"out.ctx"
        ctx.save(out, include_comments=False)
        loaded = yaml.safe_load(out.read_text())
        assert loaded.get("timeline", [{}])[0].get("date") == "2024-01"

    def test_conditional_rules_preserved_on_save(self, tmp_dir):
        ctx        = BrainCtx(version="1.0", identity={"name":"X"})
        ctx._extra = {"conditional_rules": [{"rule":"Prod only","when":{"env":"production"},"severity":"ERROR"}]}
        out        = tmp_dir/"out.ctx"
        ctx.save(out, include_comments=False)
        loaded = yaml.safe_load(out.read_text())
        assert loaded.get("conditional_rules", [{}])[0].get("rule") == "Prod only"

    def test_stripe_example_roundtrip(self, tmp_dir):
        stripe = Path(__file__).parent.parent.parent/"examples"/"stripe-payments"/"brain.ctx"
        if not stripe.exists():
            pytest.skip("Stripe example not found")
        ctx = BrainCtx.load(stripe)
        out = tmp_dir/"stripe_copy.ctx"
        ctx.save(out, include_comments=False)
        reloaded = BrainCtx.load(out)
        assert reloaded.identity["name"]       == ctx.identity["name"]
        assert reloaded.hard_rules             == ctx.hard_rules
        assert len(reloaded._extra.get("conditional_rules",[])) == len(ctx._extra.get("conditional_rules",[]))
        assert len(reloaded._extra.get("timeline",[])) == len(ctx._extra.get("timeline",[]))
