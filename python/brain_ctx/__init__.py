"""
brain.ctx — AI Constitution Standard v1.0
==========================================
Invented by ManasDB (manasdb.com)

The self-maintaining project intelligence file that gives every AI model,
agent, and tool instant understanding of your codebase — automatically.

Quick start:
    from brain_ctx import BrainCtx

    ctx = BrainCtx.generate(".")   # zero human input
    ctx.save()

    ctx = BrainCtx.load()
    print(ctx.ai_score())

CLI:
    brain-ctx init       # generate brain.ctx
    brain-ctx doctor     # health check
    brain-ctx diff       # what did AI do?
    brain-ctx rules      # active rules for current env
    brain-ctx resolve    # resolve inheritance chain
    brain-ctx stacks     # detect tech stacks
    brain-ctx validate   # schema validation
    brain-ctx sign       # cryptographic signing
"""

__version__      = "1.0.0"
__author__       = "ManasDB"
__license__      = "Apache-2.0"
__spec_version__ = "1.0"

from brain_ctx.core                    import BrainCtx
from brain_ctx.parsers.loader          import BrainCtxLoader
from brain_ctx.validators.schema       import SchemaValidator
from brain_ctx.generators.auto         import AutoGenerator
from brain_ctx.generators.updater      import UpdateProposer
from brain_ctx.builders.context        import ContextBuilder
from brain_ctx.doctors.health          import DoctorRunner, DoctorReport
from brain_ctx.diff.log_reader         import DiffReader, DiffReport
from brain_ctx.patterns.library        import StackDetector, StackPattern
from brain_ctx.rules.conditional       import (
    ConditionalRuleEngine, ConditionalRule,
    RuleContext, ActiveRule,
)
from brain_ctx.inherit.resolver        import InheritanceResolver

__all__ = [
    "BrainCtx",
    "BrainCtxLoader",
    "SchemaValidator",
    "AutoGenerator",
    "UpdateProposer",
    "ContextBuilder",
    "DoctorRunner",
    "DoctorReport",
    "DiffReader",
    "DiffReport",
    "StackDetector",
    "StackPattern",
    "ConditionalRuleEngine",
    "ConditionalRule",
    "RuleContext",
    "ActiveRule",
    "InheritanceResolver",
]
