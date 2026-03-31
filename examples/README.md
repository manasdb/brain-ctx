# brain.ctx — Example Files

Real-world brain.ctx examples for different project types.
Use these as starting points or reference implementations.

---

## stripe-payments/brain.ctx
**Project:** PayCore API — Stripe payments backend  
**Stack:** Node.js + TypeScript + PostgreSQL + Redis + Stripe SDK  
**Shows:** PCI-DSS compliance rules, payment idempotency constraints,
webhook safety, financial data protection, multi-agent roles (CI, security scanner),
temporal decision record, EU GDPR data sovereignty.

**Key features demonstrated:**
- 12 hard rules covering money, database, API, and async safety
- 5 agent roles including `ci_agent` and `security_agent`
- 8 truth sources including `webhook_events` and `db_schema`
- `timeline` block — architectural decision history the AI reads
- Compliance layer: PCI-DSS-Level-2, GDPR, SOC2-Type-II
- 365-day observability retention (financial audit requirement)

---

## How to use an example

```bash
# Copy to your project root
cp examples/stripe-payments/brain.ctx /your/project/brain.ctx

# Edit the HUMAN-WRITTEN section only (identity, hard_rules, ethics)
# Everything else will be auto-inferred when you run:
brain-ctx init   # regenerates auto-inferred sections from your codebase

# Validate
brain-ctx validate brain.ctx

# See AI Score
brain-ctx score brain.ctx
```

---

## Add your own

Send a PR with a `brain.ctx` for your project type:
- Django REST API
- React + Next.js frontend  
- ML training pipeline
- Kubernetes operator
- CLI tool in Rust
- Mobile app (React Native)

The more examples exist, the faster the standard spreads.
