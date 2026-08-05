# AgencyOS — Architecture for Framework Level Progression

**Version:** 1.0.0
**Date:** 2026-08-05
**Owner:** Darren Frost (Cheval-Volant, LLC)
**Repo:** `/home/dtfrost5/agencyOS/`

---

## 1. Current State Summary

AgencyOS is a **Level 6 (Closed-Loop) system with Level 9 (Self-Improving) engine capabilities**. It operates a continuous loop:

```
Signal → Insight → Proposal → Experiment → Promote/Rollback
```

Currently deployed with **time-based triggers only** (cron jobs). The signal detector uses Page-Hinkley anomaly detection. Experiments run A/B comparisons with threshold evaluation. Promotions are automatic with rollback on regression.

### Honest Capability Map

| Level | Status | What's Missing |
|-------|--------|----------------|
| 1-2 | ✅ DONE | CLI + cron |
| 3 | ⚠️ Partial | Via Hermes, not AgencyOS-native |
| 4 | ✅ DONE | HTTP server (:9000), SQLite, postgres client |
| 5 | ⚠️ Partial | Signal detection works, **no webhook ingestion** |
| 6 | ✅ DONE | Full closed-loop engine |
| 7 | ❌ **NOT DONE** | Single engine, no role separation |
| 8 | ❌ **NOT DONE** | Extraction planned, not autonomous |
| 9 | ✅ DONE | Tuner incumbents, promotion/rollback |
| 10 | ❌ Out of Scope | Correctly scoped out |

---

## 2. Target Architecture (Levels 5→7→8)

### 2.1 Level 5 Completion: Webhook Ingestion

**Current gap:** The signal detector only fires on cron-based polling. No external event can trigger the loop in real time.

**Additions:**

```
┌─────────────────────────────────────────────────────────────────┐
│                     External Event Sources                       │
│  GitHub Webhooks │ Stripe Events │ Email Webhooks │ Custom API  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Webhook Ingestion Layer                         │
│                                                                  │
│  POST /api/agent-os/webhooks/github                              │
│  POST /api/agent-os/webhooks/stripe                              │
│  POST /api/agent-os/webhooks/custom                              │
│                                                                  │
│  • HMAC signature verification                                   │
│  • Event normalization → Signal format                           │
│  • Idempotency dedup (event_id)                                  │
│  • Tenant resolution from payload metadata                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Existing Signal Detector                        │
│                  (Page-Hinkley anomaly)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
                        [Level 6 Loop]
```

**New modules:**
- `agent_os/webhooks.py` — HMAC verification, event parsing, idempotency
- `agent_os/sources/` — per-provider event normalizers (github.py, stripe.py, custom.py)
- `agent_os/store.py` — `webhook_events` table with `event_id` UNIQUE constraint

### 2.2 Level 7: Specialised Agent Teams

**Current gap:** Single engine handles detection, correlation, proposal, and promotion. No role separation.

**Target architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Role Registry                            │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Detector   │  │   Correlator │  │   Evolver    │          │
│  │   (existing) │  │   (existing) │  │   (NEW)      │          │
│  │              │  │              │  │              │          │
│  │ • Page-Hinkley│  │ • Git diff   │  │ • Rule change│          │
│  │ • Anomaly    │  │ • Config     │  │   proposals  │          │
│  │   detection  │  │   change     │  │ • Gap-based  │          │
│  │ • Webhook    │  │   matching   │  │   evolutions │          │
│  │   ingestion  │  │ • Blame      │  │ • Cross-tenant│         │
│  │              │  │   assignment │  │   pattern    │          │
│  └──────┬───────┘  └──────┬───────┘  │   mining     │          │
│         │                 │         └──────┬───────┘          │
│         │                 │                │                   │
│         └────────┬────────┴────────────────┘                   │
│                  │                                              │
│                  ▼                                              │
│         ┌──────────────┐                                        │
│         │   Message    │                                        │
│         │   Bus        │                                        │
│         │   (NEW)      │                                        │
│         │              │                                        │
│         │ • SQLite-    │                                        │
│         │   backed     │                                        │
│         │ • pub/sub    │                                        │
│         │ • tenant-    │                                        │
│         │   scoped     │         ┌──────────────┐              │
│         └──────┬───────┘         │   Executor   │              │
│                │                 │   (promo +   │              │
│                │                 │   rollback)  │              │
│                │                 └──────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

**New modules:**
- `agent_os/roles/base.py` — `AgentRole` abstract class
- `agent_os/roles/detector.py` — wraps existing signal detector as role
- `agent_os/roles/correlator.py` — wraps existing correlator as role
- `agent_os/roles/evolver.py` — NEW: proposes rule changes based on gap analysis
- `agent_os/bus.py` — SQLite-backed message bus with pub/sub
- `agent_os/coordinator.py` — routes messages between roles, enforces role boundaries

**Role responsibilities:**

| Role | Reads | Writes | Cannot |
|------|-------|--------|--------|
| Detector | Raw metrics, webhook events | Signal records | Propose rule changes |
| Correlator | Signals, git history, configs | Insights | Execute promotions |
| Evolver | Experiment history, tuner incumbents | Rule change proposals | Direct metric access |
| Executor | Proposals, experiments | Promotions, rollbacks | Generate insights |

### 2.3 Level 8: Orchestrated Departments

**Current gap:** Business functions (outreach, engagements, feedback) are extracted as read-only routes. No autonomous orchestration.

**Target: Autonomous feedback loop for one department first (Outreach).**

```
┌─────────────────────────────────────────────────────────────────┐
│              Orchestrated Department: Outreach                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Sub-Loop 1: Lead Scoring                               │    │
│  │  Signal: lead_score drops below threshold               │    │
│  │  Action: Auto-create proposal to adjust scoring rules   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Sub-Loop 2: Sequence Optimization                      │    │
│  │  Signal: reply_rate drops for a sequence template       │    │
│  │  Action: A/B test new template variants                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Sub-Loop 3: Follow-Up Timing                           │    │
│  │  Signal: engagement_score low for leads idle > 7 days   │    │
│  │  Action: Auto-schedule follow-up activity               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Human Approval Gate:                                            │
│  • Auto-execute if improvement > 10%                             │
│  • Require sign-off if improvement > 20% or cost > $X            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model Extensions

### 3.1 Webhook Events Table

```sql
CREATE TABLE webhook_events (
    event_id TEXT PRIMARY KEY,          -- provider event ID (idempotency)
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,               -- 'github', 'stripe', 'custom'
    event_type TEXT NOT NULL,           -- 'push', 'payment.succeeded', etc.
    payload TEXT NOT NULL,              -- raw JSON
    normalized_signal_id TEXT,          -- FK to signals table (after processing)
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT,
    status TEXT DEFAULT 'pending'       -- pending, processed, failed
);
```

### 3.2 Message Bus Table

```sql
CREATE TABLE agent_messages (
    message_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    from_role TEXT NOT NULL,            -- 'detector', 'correlator', 'evolver'
    to_role TEXT NOT NULL,              -- target role or 'broadcast'
    message_type TEXT NOT NULL,         -- 'signal', 'insight', 'proposal', 'command'
    payload TEXT NOT NULL,              -- JSON
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    consumed_at TEXT,
    consumed_by TEXT
);
```

### 3.3 Role Registry Table

```sql
CREATE TABLE agent_roles (
    role_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    role_name TEXT NOT NULL,            -- 'detector', 'correlator', 'evolver'
    status TEXT DEFAULT 'active',       -- active, paused, error
    last_heartbeat TEXT,
    config TEXT,                        -- JSON role-specific config
    UNIQUE(tenant_id, role_name)
);
```

---

## 4. API Extensions

### 4.1 Webhook Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agent-os/webhooks/github` | GitHub push/PR/issue events |
| POST | `/api/agent-os/webhooks/stripe` | Stripe payment/subscription events |
| POST | `/api/agent-os/webhooks/custom` | Custom tenant-defined events |

### 4.2 Role Management Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agent-os/roles` | List active roles |
| POST | `/api/agent-os/roles/{name}/pause` | Pause a role |
| POST | `/api/agent-os/roles/{name}/resume` | Resume a role |
| GET | `/api/agent-os/messages` | Read unconsumed messages (for role) |

### 4.3 Department Orchestration Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agent-os/departments` | List orchestrated departments |
| POST | `/api/agent-os/departments/outreach/activate` | Enable auto-loop for outreach |
| GET | `/api/agent-os/departments/outreach/status` | Get loop health + recent actions |

---

## 5. Security & Governance

### 5.1 Webhook Security

- HMAC-SHA256 signature verification (provider-specific secrets)
- Idempotency: `event_id` UNIQUE constraint prevents replay
- Tenant resolution: from webhook payload metadata (repo → tenant mapping)
- Rate limiting: max 100 webhook events/minute/tenant

### 5.2 Role Isolation

- Each role has its own DB read/write scope (enforced in store layer)
- Message bus is tenant-scoped: roles cannot cross tenant boundaries
- Role actions are audit-logged with `actor_role` field

### 5.3 Human Approval Gates

| Scenario | Auto-Execute Threshold | Human Approval Required |
|----------|----------------------|------------------------|
| Promotion (improvement < 10%) | ✅ Yes | No |
| Promotion (improvement 10-20%) | ❌ No | Yes |
| Promotion (improvement > 20%) | ❌ No | Yes |
| New rule creation | ❌ No | Yes |
| Rule deletion | ❌ No | Always |
| Department deactivation | ❌ No | Always |

---

## 6. Implementation Order

| Phase | Level | Deliverable | Est. Effort |
|-------|-------|-------------|-------------|
| 1 | 5 (complete) | Webhook ingestion layer | 2-3 days |
| 2 | 5 (complete) | GitHub + Stripe normalizers | 1 day |
| 3 | 7 (start) | Message bus + role base classes | 2 days |
| 4 | 7 (start) | Evolver role (rule proposals) | 2 days |
| 5 | 7 (complete) | Coordinator + inter-role routing | 1 day |
| 6 | 8 (start) | Outreach department loop | 2-3 days |
| 7 | 8 (expand) | Engagement department loop | 2 days |

**Total estimate: ~12-14 days of focused work.**

---

## 7. Out of Scope (Correctly)

- **Level 10 (Autonomous Business):** Not achievable or desirable. Human oversight is a feature for compliance work.
- **Level 3 (Claude Code integration):** Hermes handles this. AgencyOS should not duplicate.
- **Multi-engine consensus:** No need for 3-model agreement in internal tooling. Human is the arbiter.

---

*Architecture validated against the 10-Level Framework. Target: Level 6 → Level 7 (complete) + Level 8 (one department).*
