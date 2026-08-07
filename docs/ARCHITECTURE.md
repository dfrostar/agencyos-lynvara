# AgencyOS — Architecture for Framework Level Progression

**Version:** 2.0.0
**Date:** 2026-08-07
**Owner:** Darren Frost (Cheval-Volant, LLC)
**Repo:** `/home/dtfrost/agencyOS/`

---

## 1. Current State Summary

AgencyOS is a **Level 6 (Closed-Loop) system with Level 9 (Self-Improving) engine capabilities**. It operates a continuous loop:

```
Signal → Insight → Proposal → Experiment → Promote/Rollback
```

**Phase 1 Complete (2026-08-07):**
- HTTP server with tenant-scoped API routes
- Knowledge base (CRUD + full-text search)
- Financial tracking (revenue, costs, invoices, reports)
- Webhook ingestion layer (GitHub, Stripe, Custom normalizers)
- Auth hardening: removed body-based bypass, removed tenant_id trust
- Server hardening: 1 MiB body limit, chunked encoding rejection, Stripe replay protection

### Honest Capability Map

| Level | Status | What's Missing |
|-------|--------|----------------|
| 1-2 | ✅ DONE | CLI + cron |
| 3 | ⚠️ Partial | Via Hermes, not AgencyOS-native |
| 4 | ✅ DONE | HTTP server (:9000), SQLite |
| 5 | ✅ DONE | Webhook ingestion, event normalizers |
| 6 | ✅ DONE | Full closed-loop engine |
| 7 | ❌ **NOT DONE** | Single engine, no role separation |
| 8 | ❌ **NOT DONE** | Extraction planned, not autonomous |
| 9 | ✅ DONE | Tuner incumbents, promotion/rollback |
| 10 | ❌ Out of Scope | Correctly scoped out |

---

## 2. Target Architecture (Levels 7→8)

### 2.1 Level 7: Specialised Agent Teams

(Same as original — message bus, role base classes, evolver, coordinator)

### 2.2 Level 8: Orchestrated Departments

(Same as original — outreach loop, engagement health)

---

## 3. Data Model

### 3.1 Phase 1 Tables (Implemented)

```sql
-- Created by server.py _ensure_outreach_tables(), _ensure_engagement_tables(), _ensure_feedback_tables()
-- Plus knowledge.py + finance.py store methods

CREATE TABLE IF NOT EXISTS outreach_leads (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    phone TEXT,
    linkedin_url TEXT,
    naics_code TEXT,
    employee_count INTEGER,
    source TEXT DEFAULT 'manual',
    status TEXT DEFAULT 'identified',
    notes TEXT,
    assigned_to TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outreach_activities (...);
CREATE TABLE IF NOT EXISTS engagements (...);
CREATE TABLE IF NOT EXISTS engagement_notes (...);
CREATE TABLE IF NOT EXISTS skill_feedback (...);
CREATE TABLE IF NOT EXISTS knowledge_entries (...);
CREATE TABLE IF NOT EXISTS revenue_entries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    engagement_id TEXT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    source TEXT DEFAULT 'manual',
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cost_entries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    engagement_id TEXT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    category TEXT DEFAULT 'operational',
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    engagement_id TEXT,
    invoice_number TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    status TEXT DEFAULT 'draft',
    notes TEXT,
    due_at TEXT,
    paid_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    normalized_signal_id TEXT,
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT,
    status TEXT DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS webhook_configs (
    config_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    secret TEXT NOT NULL,
    enabled_events TEXT,
    project_mapping TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    UNIQUE(tenant_id, source)
);
```

### 3.2 Phase 2 Tables (Planned)

```sql
-- Message bus (Level 7)
CREATE TABLE agent_messages (
    message_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    consumed_at TEXT,
    consume_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending'
);

-- Role registry (Level 7)
CREATE TABLE agent_roles (
    role_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    role_name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    last_heartbeat TEXT,
    config TEXT,
    UNIQUE(tenant_id, role_name)
);
```

---

## 4. API Extensions (Implemented in Phase 1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/agent-os/webhooks/stats` | Webhook health metrics |
| POST | `/api/agent-os/webhooks/github` | GitHub events |
| POST | `/api/agent-os/webhooks/strip` | Stripe events |
| POST | `/api/agent-os/webhooks/custom` | Custom events |
| GET/POST | `/api/agent-os/knowledge` | Knowledge base CRUD |
| GET/PATCH/DELETE | `/api/agent-os/knowledge/{id}` | Single entry operations |
| GET | `/api/agent-os/knowledge/search` | Full-text search |
| GET/POST | `/api/agent-os/finance/revenue` | Revenue tracking |
| GET/POST | `/api/agent-os/finance/costs` | Cost tracking |
| GET/POST | `/api/agent-os/finance/invoices` | Invoice management |
| PATCH | `/api/agent-os/finance/invoices/{id}/status` | Invoice status update |
| GET | `/api/agent-os/finance/summary` | Financial summary |
| GET | `/api/agent-os/finance/reports/monthly` | Monthly report |
| GET/POST | `/api/agent-os/outreach/leads` | Outreach lead management |
| GET/POST | `/api/agent-os/engagements` | Engagement management |
| POST | `/api/agent-os/feedback` | Skill feedback submission |

---

## 5. Security & Governance

### 5.1 Auth Hardening (Phase 1 Complete)

- Bearer-token auth via `Authorization: Bearer <token>` header
- Body-based auth bypass removed (C1 — commit `b430df1`)
- Body `tenant_id` trust removed (C2 — commit `219fe29`)
- Session resolution: `extract_bearer_token` → `SessionStore.get_session`

### 5.2 Input Validation

- Body size limit: 1 MiB (H1 — commit `023f58c`)
- Chunked encoding rejection (H2 — commit `023f58c`)
- All SQL uses parameterized queries (`?` placeholders)
- Search queries capped at 200 chars
- Content fields capped (title: 500, content: 50,000)
- Limit parameters capped at 200 (pagination)

### 5.3 Webhook Security

- HMAC-SHA256 signature verification (constant-time `compare_digest`)
- Idempotency: `event_id` UNIQUE constraint
- Stripe replay protection: 5-minute timestamp window
- Tenant resolution separated from signature verification

---

## 6. Module Dependency Graph (Phase 1)

```
agent_os/
├── __init__.py
├── cli.py                    # Level 1-2
├── server.py                 # HTTP server (Phase 1)
├── store.py                  # SQLite persistence
├── auth.py                   # Session management
├── api.py                    # Core API routes
├── signals.py                # Signal detection
├── correlator.py             # Root cause correlation
├── auto_trigger.py           # Auto-trigger loop
├── experiment.py             # A/B experiment runner
├── promotion.py              # Promotion/rollback engine
├── governance.py             # RBAC governance
├── outreach.py               # Outreach routes
├── engagements.py            # Engagement routes
├── feedback.py               # Feedback routes
├── knowledge.py              # Knowledge base (Phase 1)
├── finance.py                # Financial tracking (Phase 1)
├── webhooks.py               # Webhook ingestion (Phase 1)
├── sources/
│   ├── github.py             # GitHub normalizer (Phase 1)
│   ├── stripe.py             # Stripe normalizer (Phase 1)
│   └── custom.py             # Custom normalizer (Phase 1)
├── postgres.py               # PostgreSQL client
├── adversarial.py            # Adversarial QA
├── tenant.py                 # Tenant registry
├── signals_log.py            # Signals log
├── behavior_learner.py       # Phase 4: outcome-driven parameter adjustment
├── proactive_explorer.py     # Phase 4: gap detection + adversarial probing
├── self_improvement.py       # Phase 4: engine wiring + background threads
└── weekly_self_improvement.py # Phase 4: WoW delta report
```

---

## 7. Implementation Order

| Phase | Level | Deliverable | Status | Est. Effort |
|-------|-------|-------------|--------|-------------|
| 1 | 4+5 | Server, core modules, webhook ingestion | ✅ **DONE** | 7.5h |
| 2 | 5+6 | Wire webhook worker, connect signal sources, feedback loop, weekly review | ✅ **DONE** | 10h |
| 3 | 4 | Business health dashboard | ✅ **DONE** | 4h |
| 4 | 9 | Self-improving engine (full), self-improvement report, L10 architecture | ✅ **DONE** | 12h |
| 5 | 7 | Message bus, role base, detector/correlator/evolver roles, coordinator | 🔴 TODO | 8h |
| 6 | 8 | Outreach department loop, engagement department loop | 🔴 TODO | 6h |

---

## 8. Out of Scope (Correctly)

- **Level 10 (Autonomous Business):** Not achievable or desirable without significant prerequisites. See `docs/ARCHITECTURE-L10.md` for the full L10 path, prerequisites, safety boundaries, and honest viability assessment.
- **Level 3 (Claude Code integration):** Hermes handles this. AgencyOS should not duplicate.
- **Multi-engine consensus:** No need for 3-model agreement in internal tooling.
- **External action execution:** AgencyOS proposes actions but does not execute them externally.

---

## 9. L10 Path

Level 10 (autonomous business operations) is **deferred** pending:
- L9 proven on real data (6+ months of outcomes)
- L7 (specialized roles) and L8 (orchestrated departments) stable
- Legal wrapper (LLC) and financial authority integration
- Immutable safety architecture

See `docs/ARCHITECTURE-L10.md` for the complete design.
