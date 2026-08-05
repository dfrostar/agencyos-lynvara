# AgencyOS — Product Requirements Document (PRD)
## Levels 5/7/8 Gap Closure

**Version:** 1.0.0
**Date:** 2026-08-05
**Owner:** Darren Frost (Cheval-Volant, LLC)
**Repo:** `/home/dtfrost5/agencyOS/`
**Status:** DRAFT

---

## 1. Product Overview

### 1.1 Vision

Transform AgencyOS from a passive monitoring tool into an **active operations layer** that detects external events in real time, operates with specialized roles that can be independently scaled, and orchestrates business functions autonomously within human-defined safety bounds.

### 1.2 Product Positioning

**AgencyOS is not a Level 10 Autonomous Business Layer.** It is an operations intelligence layer that makes humans faster and decisions data-driven. The system proposes, experiments, and recommends — humans approve and execute for high-impact changes.

### 1.3 Target Users

| User | Needs | Interaction |
|------|-------|-------------|
| **Solo Founder** (Darren) | Reduce operational overhead, proactive health management | Dashboard review, approve/reject proposals |
| **Future Team Members** | Specialized roles they can own and improve | Role-specific interfaces and alerts |
| **Future Tenants** (if multi-tenant SaaS) | Automated operations with oversight | Department configuration, approval workflows |

---

## 2. Feature Requirements

### 2.1 Level 5: Webhook Ingestion System

#### Feature: Webhook Receiver

**User Story:** As the system, I need to receive webhook events from external providers so that I can process them in real time instead of polling.

**Requirements:**

- Accept POST requests at `/api/agent-os/webhooks/{source}` where source ∈ {github, stripe, custom}
- Verify HMAC-SHA256 signatures using tenant-registered secrets
- Return 200 OK immediately (async processing — queue and respond)
- Return 400 Bad Request for invalid payloads or signatures
- Return 403 Forbidden for unrecognized tenants
- Return 429 Rate Limited when > 100 events/minute/tenant

**Implementation Notes:**

- Webhook events are stored in `webhook_events` table before processing
- A background worker polls the `webhook_events` table every second for new events
- Each event is processed exactly once (idempotency via `event_id` UNIQUE constraint)

#### Feature: GitHub Webhook Normalizer

**User Story:** As the system, I need to convert GitHub webhook payloads into canonical Signal format so that the signal detector can analyze them.

**Supported Events:**

| GitHub Event | Metric Name | Value | Metadata |
|--------------|-------------|-------|----------|
| `push` | `github.push.count` | 1.0 | branch, repo, pusher, commit_count |
| `pull_request` (opened) | `github.pr.opened` | 1.0 | repo, author, base_branch, head_branch |
| `pull_request` (closed/merged) | `github.pr.merged` | 1.0 | repo, author, merge_time_hours |
| `issues` (opened) | `github.issue.opened` | 1.0 | repo, author, labels |
| `issues` (closed) | `github.issue.closed` | 1.0 | repo, author, resolution_time_hours |
| `workflow_run` (completed) | `github.ci.status` | 0.0 (failure) or 1.0 (success) | repo, workflow, duration_minutes |

#### Feature: Stripe Webhook Normalizer

**User Story:** As the system, I need to convert Stripe webhook payloads into canonical Signal format so that I can track business metrics in real time.

**Supported Events:**

| Stripe Event | Metric Name | Value | Metadata |
|--------------|-------------|-------|----------|
| `payment_intent.succeeded` | `stripe.payment.success` | amount_cents | currency, customer, payment_method |
| `payment_intent.failed` | `stripe.payment.failure` | 1.0 | error_code, customer, amount_cents |
| `customer.subscription.created` | `stripe.subscription.created` | 1.0 | plan, customer, interval |
| `customer.subscription.deleted` | `stripe.subscription.churn` | 1.0 | plan, customer, cancellation_reason |
| `charge.refunded` | `stripe.refund.amount` | amount_cents | reason, customer, payment_intent |
| `invoice.paid` | `stripe.revenue.recurring` | amount_cents | subscription, customer, period_days |

#### Feature: Custom Webhook Normalizer

**User Story:** As a tenant, I need to define custom mappings so that I can send arbitrary events to AgencyOS without modifying core code.

**Requirements:**

- Tenant config includes: `payload_path` (dot-notation path to value), `metric_name`, `value_type` (float, int, bool), `value_transform` (optional: abs, log, normalize)
- Example config: `{"payload_path": "data.user_count", "metric_name": "tenant.user.count", "value_type": "int"}`
- Custom events skip HMAC verification (tenant_id must be in payload) but require tenant authentication
- Rate limit: 1000 events/minute/tenant for custom source

#### Feature: Webhook Registration API

**User Story:** As a tenant admin, I need to register webhook secrets and configure source-specific settings so that external providers can send events to AgencyOS.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agent-os/tenants/{id}/webhooks` | Register webhook config |
| GET | `/api/agent-os/tenants/{id}/webhooks` | List webhook configs |
| DELETE | `/api/agent-os/tenants/{id}/webhooks/{source}` | Remove webhook config |

**Request Body:**

```json
{
  "source": "github",
  "secret": "whsec_...",
  "enabled_events": ["push", "pull_request"],
  "project_mapping": {
    "dfrostar/agencyOS": "tenant-main",
    "dfrostar/cmmc20": "tenant-level2logic"
  }
}
```

---

### 2.2 Level 7: Specialised Agent Roles

#### Feature: Agent Role Base Class

**User Story:** As a developer, I need a common base class for all roles so that I can add new roles without modifying the coordinator.

**Requirements:**

```python
class AgentRole(ABC):
    role_name: str  # 'detector', 'correlator', 'evolver'
    
    @abstractmethod
    def __init__(self, tenant_id: str, bus: MessageBus, store: AgentOSStore) -> None: ...
    
    @abstractmethod
    def subscriptions(self) -> list[str]: ...  # topics this role consumes
    
    @abstractmethod
    async def process(self, message: dict) -> list[dict]: ...  # returns messages to publish
    
    def heartbeat(self) -> dict: ...  # health status for coordinator
    
    def start(self) -> None: ...  # begin consuming from bus
    
    def stop(self) -> None: ...  # graceful shutdown
```

**Requirements:**

- Each role runs as an asyncio task (non-blocking)
- Roles are stateless between messages (all state in bus or store)
- Role crashes are caught by coordinator and restarted
- Role health is reported via `heartbeat()` method every 30 seconds

#### Feature: Detector Role

**User Story:** As the system, I need a Detector role that consumes metric values and webhook events so that anomalies are identified.

**Consumes:** `metric_value`, `webhook_event` messages

**Produces:** `signal` messages

**Logic:**

1. On `metric_value`: Run Page-Hinkley detection → if anomaly, publish `signal` with: signal_id, metric_name, value, baseline, z_score, tenant_id
2. On `webhook_event`: Look up event in `webhook_events` table → already normalized by webhook worker → publish `signal` with the normalized data

**Configuration:**

```json
{
  "page_hinkley_delta": 0.005,
  "page_hinkley_threshold": 50,
  "min_baseline_samples": 30
}
```

#### Feature: Correlator Role

**User Story:** As the system, I need a Correlator role that consumes signals and identifies root causes.

**Consumes:** `signal` messages

**Produces:** `insight` messages

**Logic:**

1. On `signal`: Query recent git commits, config changes, and deployments for the same tenant/time window
2. Match signal time to config change within ±5 minutes → `config_change` cause
3. Match signal time to git commit within ±10 minutes → `code_change` cause
4. No match → `unknown` cause (signal published for human review)
5. Publish `insight` with: insight_id, signal_id, cause_type, cause_ref (commit SHA or config path), confidence

#### Feature: Evolver Role

**User Story:** As the system, I need an Evolver role that proposes new detection rules based on experiment history and gap analysis.

**Consumes:** `experiment_completed` messages (as trigger for analysis)

**Produces:** `proposal` messages

**Logic:**

1. Daily: Analyze all experiments from last 30 days
2. Identify: Metrics with high false positive rate (>20%) → propose tightening thresholds
3. Identify: Rules that haven't fired in 30 days → propose deprecation
4. Identify: Correlation patterns that repeat → propose new rule
5. Weekly: Cross-tenant pattern mining (aggregated, anonymized) → propose rules based on common patterns
6. Publish `proposal` with: proposal_id, rule_type, definition, expected_impact, confidence, requires_human_approval

**Human Interaction:**

- Proposals appear in `GET /api/agent-os/proposals/pending`
- Approve: `POST /api/agent-os/proposals/{id}/approve` → rule activated
- Reject: `POST /api/agent-os/proposals/{id}/reject` → stored as rejected with reason
- Expire: 30 days without review → auto-rejected

#### Feature: Message Bus

**User Story:** As a role, I need a message bus so that I can publish messages without knowing which role will consume them.

**Requirements:**

- SQLite-backed persistence (no external message broker)
- Topics: `signal`, `insight`, `proposal`, `experiment`, `promotion`, `alert`, `command`
- At-least-once delivery with explicit acknowledgment
- Dead letter queue for messages failing 3+ times
- Message retention: 7 days (configurable)
- Tenant-scoped: `WHERE tenant_id = ?` on all queries

**Schema:**

```sql
CREATE TABLE agent_messages (
    message_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT,  -- NULL = broadcast
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    consumed_at TEXT,
    consume_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending'  -- pending, processing, consumed, failed, dead
);

CREATE INDEX idx_messages_tenant_topic ON agent_messages (tenant_id, topic, status);
```

#### Feature: Coordinator

**User Story:** As an operator, I need a coordinator so that roles are managed, monitored, and restarted automatically.

**Requirements:**

- Start all roles on server startup (from `agent_roles` table)
- Route messages: publish to bus → coordinator delivers to subscribed roles
- Health check: poll each role's heartbeat every 30 seconds
- Restart: if heartbeat missing for 60 seconds, restart role
- Alert: if role fails 3 consecutive restarts, publish `alert` message
- Graceful degradation: failed role doesn't block others
- API endpoints for manual control:
  - `POST /api/agent-os/roles/{name}/pause`
  - `POST /api/agent-os/roles/{name}/resume`
  - `GET /api/agent-os/roles` (list with health status)

#### Feature: Human Approval Workflow

**User Story:** As an operator, I need to review and approve/reject Evolver proposals so that the system doesn't change its own rules without oversight.

**Workflow:**

1. Evolver publishes `proposal` message
2. Coordinator stores proposal in `proposals` table with status `pending`
3. Operator reviews via `GET /api/agent-os/proposals/pending`
4. Operator approves: `POST /api/agent-os/proposals/{id}/approve`
5. Coordinator activates rule and notifies Evolver via `command` message
6. Evolver tracks: proposals_submitted++, proposals_accepted++

**Requirements:**

- Proposals include: rule_type, definition (executable code or config), expected_impact, confidence_score, risk_level
- Risk levels: low (parameter change), medium (new rule), high (delete rule)
- Low risk: auto-approve if confidence > 0.8
- Medium risk: require human approval
- High risk: require human approval + 24-hour waiting period

---

### 2.3 Level 8: Department Orchestration

#### Feature: Outreach Department Loop

**User Story:** As a business operator, I want outreach sequences to be optimized automatically so that reply rates improve without manual experimentation.

**Sub-Loops:**

**Sub-Loop 1: Lead Scoring**

- Signal: `lead_score` drops below threshold for >10% of leads
- Action: Proposal to adjust scoring weights (company_size_weight, industry_fit_weight, etc.)
- Experiment: A/B test current scoring vs proposed scoring on new leads
- Metric: conversion_rate (lead → first contact)
- Auto-execute threshold: improvement < 5%

**Sub-Loop 2: Sequence Template Optimization**

- Signal: `reply_rate` drops below threshold for a specific sequence template
- Action: Generate variant templates (different subject lines, different body lengths, different CTAs)
- Experiment: A/B test template variants on next 100 outbound emails
- Metric: reply_rate (replies / emails_sent)
- Auto-execute threshold: improvement < 10%

**Sub-Loop 3: Follow-Up Timing**

- Signal: `engagement_score` low for leads idle > 7 days
- Action: Propose new follow-up activity (different channel, different time of day)
- Experiment: A/B test follow-up timing strategies
- Metric: re-engagement_rate (activities / follow_ups_sent)
- Auto-execute threshold: improvement < 5%

**Configuration:**

```json
{
  "enabled": true,
  "auto_execute_max_improvement": 0.10,
  "auto_execute_max_cost": 50.0,
  "scoring_threshold": 0.6,
  "reply_rate_threshold": 0.05,
  "idle_days_threshold": 7
}
```

#### Feature: Engagement Health Loop

**User Story:** As a business operator, I want engagement health to be monitored automatically so that stalled engagements are caught early.

**Sub-Loops:**

**Sub-Loop 1: Velocity Degradation**

- Signal: `assessment_completions_per_week` drops below baseline for 2+ weeks
- Action: Investigate cause (via Correlator) → propose intervention
- Intervention options: simplify assessment, send encouragement, reassign assessor
- Auto-execute: send encouragement email
- Human approval: reassign assessor, pause engagement

**Sub-Loop 2: Activity Stagnation**

- Signal: `days_since_last_activity` exceeds tenant threshold (default: 14 days)
- Action: Create follow-up activity (reminder, status check, value-add content)
- Auto-execute: create activity with reminder type
- Human approval: create activity with call/email type (requires human execution)

**Sub-Loop 3: Completion Rate Drop**

- Signal: `assessment_completion_rate` drops below 50% of baseline
- Action: Propose assessment simplification (fewer questions, clearer language)
- Experiment: A/B test simplified vs original on new engagements
- Metric: completion_rate, time_to_complete
- Auto-execute threshold: improvement < 10%

#### Feature: Department Configuration API

**User Story:** As a tenant admin, I need to configure which departments are auto-orchestrated and with what thresholds.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agent-os/departments` | List departments + status |
| POST | `/api/agent-os/departments/{name}/config` | Set configuration |
| POST | `/api/agent-os/departments/{name}/activate` | Enable auto-loop |
| POST | `/api/agent-os/departments/{name}/pause` | Disable auto-loop |
| GET | `/api/agent-os/departments/{name}/history` | Recent actions log |

**Configuration Schema:**

```json
{
  "enabled": true,
  "auto_execute_max_improvement": 0.10,
  "auto_execute_max_cost": 50.0,
  "require_approval_above_improvement": 0.20,
  "require_approval_above_cost": 200.0,
  "max_actions_per_day": 10,
  "alert_channels": ["log"]
}
```

---

## 3. API Reference

### 3.1 Webhook Endpoints

```
POST /api/agent-os/webhooks/github
Content-Type: application/json
X-Hub-Signature-256: sha256=...
X-GitHub-Event: push
X-GitHub-Delivery: <uuid>

Payload: GitHub webhook payload (normalized internally)
```

```
POST /api/agent-os/webhooks/stripe
Content-Type: application/json
Stripe-Signature: t=...,v1=...

Payload: Stripe webhook payload (normalized internally)
```

```
POST /api/agent-os/webhooks/custom
Content-Type: application/json
Authorization: Bearer <tenant_token>

Payload: Custom payload (tenant-defined mapping applied)
```

### 3.2 Role & Message Endpoints

```
GET /api/agent-os/roles
Authorization: Bearer <token>

Response: [{role_name, status, last_heartbeat, messages_processed_24h}]
```

```
POST /api/agent-os/roles/{name}/pause
Authorization: Bearer <token>

Response: {status: "paused"}
```

```
POST /api/agent-os/roles/{name}/resume
Authorization: Bearer <token>

Response: {status: "active"}
```

### 3.3 Proposal Endpoints

```
GET /api/agent-os/proposals/pending
Authorization: Bearer <token>

Response: [{proposal_id, rule_type, definition, confidence, created_at}]
```

```
POST /api/agent-os/proposals/{id}/approve
Authorization: Bearer <token>

Response: {status: "activated", rule_id: "..."}
```

```
POST /api/agent-os/proposals/{id}/reject
Authorization: Bearer <token>
Body: {reason: "..."}

Response: {status: "rejected"}
```

### 3.4 Department Endpoints

```
GET /api/agent-os/departments
Authorization: Bearer <token>

Response: [{name, enabled, last_action_at, actions_30d, actions_blocked_30d}]
```

```
POST /api/agent-os/departments/outreach/config
Authorization: Bearer <token>
Body: {enabled, auto_execute_max_improvement, ...}

Response: {status: "updated", config: {...}}
```

```
GET /api/agent-os/departments/outreach/history?days=30
Authorization: Bearer <token>

Response: [{action_type, triggered_at, metric_before, metric_after, approval_status}]
```

### 3.5 Dashboard Stats

```
GET /api/agent-os/webhooks/stats
Authorization: Bearer <token>

Response: {
  events_received_24h: 142,
  events_processed_24h: 140,
  events_failed_24h: 2,
  avg_processing_ms: 45,
  last_event_at: "2026-08-05T12:34:56Z"
}
```

---

## 4. Data Model

### 4.1 New Tables

**webhook_events** — Raw webhook payloads before processing
- event_id TEXT PK, tenant_id, source, event_type, payload TEXT, normalized_signal_id FK, received_at, processed_at, status

**agent_messages** — Message bus persistence
- message_id TEXT PK, tenant_id, topic, from_role, to_role, payload TEXT, created_at, consumed_at, consume_count, status

**agent_roles** — Role registry
- role_id TEXT PK, tenant_id, role_name, status, last_heartbeat, config TEXT
- UNIQUE(tenant_id, role_name)

### 4.2 Modified Tables

**proposals** — Add new columns:
- rule_type TEXT — 'detection', 'correlation', 'experiment'
- definition TEXT — executable rule definition
- confidence_score REAL — 0.0 to 1.0
- risk_level TEXT — 'low', 'medium', 'high'
- actor_role TEXT — 'evolver', 'human', 'system'

**signals** — Add new column:
- source TEXT — 'polling', 'webhook:github', 'webhook:stripe', 'webhook:custom'

---

## 5. User Interface

### 5.1 Dashboard Views

**Webhook Health Panel:**
- Events received/processed/failed (last 24h)
- Processing latency p50/p95/p99
- Last event timestamp per source
- Alert banner if failure rate > 10%

**Role Health Panel:**
- List of active roles with status (healthy, restarting, failed)
- Messages processed per role (last 24h)
- Last heartbeat per role
- Pause/Resume buttons

**Pending Proposals Panel:**
- List of proposals awaiting review
- Each proposal shows: rule_type, confidence, risk_level, expected_impact
- Approve/Reject buttons with required reason for rejection

**Department Orchestration Panel:**
- Per-department status (active/paused)
- Last action timestamp
- Actions taken / blocked / pending (last 30 days)
- Configuration editor

---

## 6. Constraints

### 6.1 Technical Constraints

- All new modules must use stdlib-only dependencies (no external packages beyond existing: scipy for signals)
- Message bus must use SQLite (no Redis/RabbitMQ)
- All endpoints must be tenant-scoped
- All actions must be audit-logged

### 6.2 Process Constraints

- No new code without tests (pytest must pass)
- Adversarial QA on all claims (DeepSeek + GLM parallel)
- Brutal honesty in all documentation
- Free tier first (no paid dependencies)

### 6.3 Security Constraints

- HMAC verification required for all webhook endpoints
- Tenant isolation enforced at store layer (not just application layer)
- Rate limiting on all external-facing endpoints
- Human approval required for all rule deletions

---

## 7. Success Criteria

| Feature | Success Metric | Measurement |
|---------|---------------|-------------|
| Webhook Ingestion | < 500ms p99 response time | Server logs |
| Webhook Processing | < 5s p99 signal creation | Server logs |
| Detector Role | Zero regression in anomaly detection | Existing tests pass |
| Correlator Role | Zero regression in root cause correlation | Existing tests pass |
| Evolver Role | 10+ proposals/month after ramp-up | proposals table |
| Message Bus | Zero message loss | Dead queue monitoring |
| Outreach Loop | 10%+ reply rate improvement | outreach_activities table |
| Human Approval | 100% of high-risk proposals reviewed | audit log |

---

*PRD aligned with BRD.md and ARCHITECTURE.md. Product requirements derived from 10-Level Framework gap analysis.*
