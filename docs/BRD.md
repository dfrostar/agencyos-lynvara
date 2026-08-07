# AgencyOS — Business Requirements Document (BRD)
## Levels 5/7/8 Gap Closure

**Version:** 2.0.0
**Date:** 2026-08-07
**Owner:** Darren Frost (Cheval-Volant, LLC)
**Repo:** `/home/dtfrost/agencyOS/`
**Status:** Phase 1 Complete | Phase 2 In Progress

---

## 1. Business Context

### 1.1 Current Situation

AgencyOS operates a Level 6 (Closed-Loop) engine that automatically detects anomalies in business metrics, proposes experiments, runs A/B tests, and promotes or rolls back changes based on results. Level 9 (Self-Improving) capabilities track tuner incumbents and learn from experiment history.

The current trigger mechanism is **time-based only** (cron jobs). This means:
- An anomaly that occurs at 2:00 AM may not be detected until the next scheduled poll at 6:00 AM (4-hour delay)
- Real-time events (payment failures, user signups, code deployments) enter the system only through manual metric pushes
- The engine cannot react to external ecosystem events without human intervention

The current architecture is **single-engine**:
- Detection, correlation, proposal generation, and promotion all run in one process
- No separation of concerns between "what's happening" and "what to do about it"
- Cannot evolve the engine's own detection rules autonomously — only tuner values and baselines

Business functions (outreach, engagements, feedback) are extracted as **read-only routes**:
- Data flows in through API calls from external systems or humans
- No autonomous action is taken on business data
- No closed-loop orchestration of business operations

### 1.2 Business Problem

1. **Latency:** Time-based polling creates 1-6 hour detection delays for critical business events. During a payment processing outage or security incident, delayed detection means lost revenue and increased risk.

2. **Scalability:** A single engine must handle all signal processing, experimentation, and promotion. As metric volume grows (more tenants, more projects, more data sources), the engine becomes a bottleneck.

3. **Evolution Gap:** The engine improves its internal parameters (tuner values) but cannot propose new detection rules, new correlation strategies, or new experiment types. All architectural improvements require human engineering.

4. **Operational Opacity:** Business function data (outreach sequences, engagement health, feedback quality) is stored but not acted on. No autonomous optimization of business operations exists.

### 1.3 Business Goal

Transform AgencyOS from a **passive monitoring tool** into an **active operations layer** that:

- Detects external events in **real time** (seconds, not hours)
- Operates with **specialized roles** that can be independently scaled and improved
- **Orchestrates business functions** autonomously within human-defined safety bounds

---

## 2. Business Requirements

### 2.1 Phase 1: Server + Core Modules (COMPLETE)

#### BR-P1.1 Server + Health Endpoint

**Requirement:** AgencyOS SHALL run an HTTP server exposing API routes and a health endpoint.

**Acceptance Criteria:**
- [x] Server starts on port 9000 (configurable via `PORT` env var)
- [x] `GET /health` returns `{"status": "ok", "version": "1.0.0"}` with HTTP 200
- [x] All routes are tenant-scoped via bearer-token auth
- [x] Body-based auth bypass removed (C1 fix)
- [x] Body `tenant_id` trust removed (C2 fix)
- [x] Max body size enforced at 1 MiB (H1 fix)
- [x] Chunked encoding rejected (H2 fix)
- [x] 145 tests passing across 7 test files

#### BR-P1.2 Knowledge Base Module

**Requirement:** AgencyOS SHALL provide tenant-scoped CRUD for organizational knowledge.

**Acceptance Criteria:**
- [x] `GET /api/agent-os/knowledge` — list entries for tenant
- [x] `POST /api/agent-os/knowledge` — create entry
- [x] `GET /api/agent-os/knowledge/{id}` — get single entry
- [x] `PATCH /api/agent-os/knowledge/{id}` — update entry
- [x] `DELETE /api/agent-os/knowledge/{id}` — delete entry
- [x] `GET /api/agent-os/knowledge/search?q=...` — full-text search
- [x] All routes require bearer-token auth
- [x] All queries use parameterized SQL (no injection)
- [x] Entry types: decision, sop, research, feedback, custom

#### BR-P1.3 Financial Tracking

**Requirement:** AgencyOS SHALL track revenue, costs, and invoices per tenant.

**Acceptance Criteria:**
- [x] `GET /api/agent-os/finance/revenue` — list revenue entries
- [x] `POST /api/agent-os/finance/revenue` — record revenue
- [x] `GET /api/agent-os/finance/costs` — list cost entries
- [x] `POST /api/agent-os/finance/costs` — record cost
- [x] `GET /api/agent-os/finance/invoices` — list invoices
- [x] `POST /api/agent-os/finance/invoices` — create invoice
- [x] `PATCH /api/agent-os/finance/invoices/{id}/status` — update status
- [x] `GET /api/agent-os/finance/summary` — financial summary
- [x] Invoice lifecycle: draft → sent → paid/overdue → cancelled
- [x] Multi-currency support (USD, EUR, GBP)

---

### 2.2 Level 5 Completion: Real-Time Event Ingestion

#### BR-5.1 Webhook Ingestion Capability

**Requirement:** AgencyOS SHALL accept webhook events from external sources and convert them into the internal Signal format.

**Rationale:** Eliminates polling latency for critical events. Enables real-time response to payment failures, security incidents, code deployments, and business milestones.

**Acceptance Criteria:**
- [ ] AgencyOS accepts POST requests at `/api/agent-os/webhooks/{source}` where source ∈ {github, stripe, custom}
- [ ] All webhook events are verified via HMAC-SHA256 signature validation before processing
- [ ] Duplicate events (same `event_id`) are rejected with HTTP 200 (idempotency)
- [ ] Each webhook event creates exactly one Signal record in the database
- [ ] Failed webhook processing (parse error, invalid payload) returns HTTP 400 and logs the error
- [ ] Webhook endpoint responds within 500ms (async processing — queue and respond)

#### BR-5.2 Event Source Normalizers

**Requirement:** AgencyOS SHALL provide per-provider normalizers that convert provider-specific payloads into the canonical Signal format.

**Rationale:** Different providers use different payload structures. Normalizers abstract this complexity so the signal detector works with uniform input regardless of source.

**Acceptance Criteria:**
- [ ] GitHub normalizer handles: `push`, `pull_request` (opened, closed, merged), `issues` (opened, closed)
- [ ] Stripe normalizer handles: `payment_intent.succeeded`, `payment_intent.failed`, `customer.subscription.created`, `customer.subscription.deleted`, `charge.refunded`
- [ ] Custom normalizer accepts a user-defined mapping (tenant config) from arbitrary payload → signal
- [ ] Each normalizer extracts: `metric_name` (string), `value` (float), `timestamp` (ISO 8601), `metadata` (dict)
- [ ] Normalizers are pluggable: new sources can be added without modifying core engine

#### BR-5.3 Webhook Registration & Tenant Resolution

**Requirement:** Tenants SHALL register webhook secrets and source-specific configurations. AgencyOS SHALL resolve the correct tenant from each webhook payload.

**Rationale:** Multi-tenant isolation must be maintained. A webhook from GitHub for tenant A must not create signals in tenant B's scope.

**Acceptance Criteria:**
- [ ] Tenants can register webhook secrets via `POST /api/agent-os/tenants/{id}/webhooks`
- [ ] Tenant resolution uses source-specific rules:
  - GitHub: `repository.full_name` → project mapping → tenant_id
  - Stripe: `account` header → tenant_id
  - Custom: `tenant_id` field in payload (verified against signature)
- [ ] Unrecognized tenant returns HTTP 403 (not 404 — avoid leaking existence)
- [ ] Webhook config includes: source, secret, enabled event types, project mapping

#### BR-5.4 Webhook Monitoring & Observability

**Requirement:** AgencyOS SHALL track webhook health metrics and expose them via the dashboard API.

**Rationale:** Silent webhook failures (provider downtime, signature misconfiguration) must be detectable.

**Acceptance Criteria:**
- [ ] Dashboard endpoint `GET /api/agent-os/webhooks/stats` returns: events_received, events_processed, events_failed, last_event_at
- [ ] Failed webhook events are stored with error reason and raw payload (truncated to 10KB)
- [ ] Alert generated if webhook failure rate exceeds 10% in a 5-minute window
- [ ] Alert generated if no webhook events received for any active source in 24 hours

---

### 2.2 Level 7: Specialised Agent Roles

#### BR-7.1 Role Architecture Foundation

**Requirement:** AgencyOS SHALL implement a role-based architecture where each capability (detection, correlation, evolution, execution) runs as an independent role with defined boundaries.

**Rationale:** Enables independent scaling, testing, and evolution of each capability. Prevents a single bug from crashing the entire engine. Allows specialized logic per role.

**Acceptance Criteria:**
- [ ] Each role inherits from `agent_os.roles.base.AgentRole` abstract class
- [ ] Roles communicate exclusively through the message bus (no direct function calls)
- [ ] Each role has its own read/write scope in the data store (enforced at store layer)
- [ ] Role lifecycle: start → consume messages → process → publish → heartbeat
- [ ] Role failure (crash, timeout) triggers automatic restart and alerts if restart fails 3 times
- [ ] Roles are tenant-scoped: a role instance processes messages for exactly one tenant

#### BR-7.2 Detector Role (Existing Capability)

**Requirement:** The existing signal detection capability SHALL be wrapped as a Detector role.

**Rationale:** Provides the foundation for role-based architecture while preserving existing functionality.

**Acceptance Criteria:**
- [ ] `agent_os/roles/detector.py` wraps existing `SignalDetector` class
- [ ] Consumes messages of type `metric_value` and `webhook_event`
- [ ] Publishes messages of type `signal` when anomaly detected
- [ ] Reads from: metrics table, webhook_events table
- [ ] Writes to: signals table
- [ ] Cannot: propose experiments, modify tuner values, read business function data

#### BR-7.3 Correlator Role (Existing Capability)

**Requirement:** The existing root cause correlation capability SHALL be wrapped as a Correlator role.

**Rationale:** Separates correlation logic from detection, allowing independent improvement.

**Acceptance Criteria:**
- [ ] `agent_os/roles/correlator.py` wraps existing `RootCauseCorrelator` class
- [ ] Consumes messages of type `signal`
- [ ] Publishes messages of type `insight` when correlation found
- [ ] Reads from: signals table, git history, config change logs
- [ ] Writes to: insights table
- [ ] Cannot: run experiments, modify rules, access raw metrics

#### BR-7.4 Evolver Role (NEW Capability)

**Requirement:** AgencyOS SHALL implement an Evolver role that proposes new detection rules, correlation strategies, and experiment types based on gap analysis and experiment history.

**Rationale:** The current system can optimize parameters but cannot propose new capabilities. Evolver closes this gap — it's the mechanism for architectural self-improvement.

**Acceptance Criteria:**
- [ ] `agent_os/roles/evolver.py` reads experiment history, tuner incumbent history, and signal patterns
- [ ] Identifies gaps: metrics with high noise (false positive signals), stale rules (no signal for 30+ days), untried correlations
- [ ] Proposes new rules as `proposal` messages with: rule_type, rule_definition, expected_impact, confidence_score
- [ ] Proposed rules are human-approved before activation (see BR-7.7)
- [ ] Evolver performance is tracked: proposals_submitted, proposals_accepted, proposals_rejected, proposals_active
- [ ] Runs on a schedule: daily gap analysis, weekly pattern mining
- [ ] Cannot: directly modify rules, access raw business data (only aggregated experiment metrics)

#### BR-7.5 Message Bus

**Requirement:** AgencyOS SHALL implement a SQLite-backed message bus for inter-role communication.

**Rationale:** Decouples roles. Roles can be added/removed without modifying other roles. Enables replay and debugging of role interactions.

**Acceptance Criteria:**
- [ ] `agent_os/bus.py` implements `MessageBus` class with: `publish(topic, message)`, `subscribe(topic, callback)`, `consume()`
- [ ] Messages are persisted in `agent_messages` table with delivery status
- [ ] At-least-once delivery: messages remain in queue until explicitly acknowledged
- [ ] Tenant-scoped: messages for tenant A are invisible to tenant B
- [ ] Message retention: 7 days (configurable per tenant)
- [ ] Dead letter queue: messages failing processing 3 times moved to `dead_messages` table
- [ ] Topics: `signal`, `insight`, `proposal`, `experiment`, `promotion`, `alert`, `command`

#### BR-7.6 Coordinator

**Requirement:** AgencyOS SHALL implement a Coordinator that manages role lifecycle, routes messages between roles, and enforces role boundaries.

**Rationale:** Central orchestration point. Ensures roles interact correctly and system-wide invariants are maintained.

**Acceptance Criteria:**
- [ ] `agent_os/coordinator.py` starts/stops all roles on server startup/shutdown
- [ ] Routes messages based on `to_role` field and role subscriptions
- [ ] Enforces read/write permissions (role attempts to write outside its scope → rejected)
- [ ] Monitors role health: heartbeat timeout (no heartbeat in 60s → restart)
- [ ] Publishes system health metric: `agent_os.coordinator.roles_healthy`
- [ ] Graceful degradation: if one role fails, others continue operating
- [ ] Manual override: admin can pause/resume individual roles via API

#### BR-7.7 Human Approval for Rule Changes

**Requirement:** All new rules proposed by the Evolver role SHALL require explicit human approval before activation.

**Rationale:** Prevents the system from autonomously changing its own detection logic without oversight. Human is the arbiter for architectural changes.

**Acceptance Criteria:**
- [ ] `GET /api/agent-os/proposals/pending` lists proposed rules awaiting review
- [ ] `POST /api/agent-os/proposals/{id}/approve` activates the proposed rule
- [ ] `POST /api/agent-os/proposals/{id}/reject` marks the proposal as rejected with reason
- [ ] Proposals expire after 30 days if not reviewed
- [ ] Evolver tracks acceptance rate to improve future proposal quality

---

### 2.3 Level 8: Department Orchestration

#### BR-8.1 Autonomous Outreach Loop

**Requirement:** AgencyOS SHALL autonomously optimize outreach sequences (scoring, templates, timing) within human-defined safety bounds.

**Rationale:** Outreach is the highest-ROI business function to automate. Reply rates directly drive revenue. Small improvements compound significantly.

**Acceptance Criteria:**
- [ ] Signal: `lead_score` drops below configurable threshold → triggers proposal to adjust scoring weights
- [ ] Signal: `reply_rate` drops below threshold for a sequence template → triggers A/B test of new variants
- [ ] Signal: `engagement_score` low for leads idle > 7 days → triggers follow-up activity creation
- [ ] All outreach actions are logged with `actor_role` = 'orchestrator' and `approval_status`
- [ ] Auto-execute threshold: improvements < 10% and cost < $50
- [ ] Human approval required: improvements 10-20%, or cost $50-$200, or any deletion
- [ ] Human approval always required: deactivating outreach for a tenant

#### BR-8.2 Autonomous Engagement Health

**Requirement:** AgencyOS SHALL autonomously detect and respond to engagement health degradation.

**Rationale:** Stalled engagements represent unrealized revenue. Early intervention prevents churn.

**Acceptance Criteria:**
- [ ] Signal: `engagement_velocity` drops (fewer assessment completions than baseline) → triggers investigation
- [ ] Signal: `days_since_last_activity` exceeds threshold → triggers check-in activity creation
- [ ] Signal: `assessment_completion_rate` drops → triggers proposal to simplify or resequence
- [ ] Health score computed daily per engagement, visible in dashboard
- [ ] Auto-execute: add reminder activity, send status report to owner
- [ ] Human approval: change engagement timeline, reassign assessor, pause engagement

#### BR-8.3 Department Orchestration Configuration

**Requirement:** Tenants SHALL configure which departments are auto-orchestrated and with what thresholds.

**Rationale:** Different tenants have different risk tolerances. Configuration must be per-tenant.

**Acceptance Criteria:**
- [ ] `POST /api/agent-os/departments/{name}/config` sets: enabled (bool), auto_execute_max_improvement (float), auto_execute_max_cost (float)
- [ ] Default: enabled=false, max_improvement=0.10 (10%), max_cost=50.0
- [ ] `GET /api/agent-os/departments` returns: name, enabled, last_action_at, actions_30d, actions_blocked_30d
- [ ] Department can be paused via `POST /api/agent-os/departments/{name}/pause`
- [ ] Pausing a department stops all auto-execute but preserves data collection

---

### 2.4 Phase 4: Intelligence Layer (COMPLETE)

#### BR-P4.1 Self-Improving Engine (B-09)

**Requirement:** AgencyOS SHALL implement a self-improving engine that learns from experiment outcomes and proactively proposes new experiments.

**Rationale:** Without learning, the engine can only react to anomalies. With learning, it optimizes its own parameters and discovers unexplored improvement areas.

**Acceptance Criteria:**
- [x] `agent_os/behavior_learner.py` — adjusts lambda threshold and cooldown based on outcome history
- [x] Lambda bounded: `_LAMBDA_MIN=1.0` to `_LAMBDA_MAX=20.0` (prevents dead/hypersensitive detector)
- [x] Cooldown bounded: `_COOLDOWN_MIN=10s` to `_COOLDOWN_MAX=3600s` (prevents flooding/muting)
- [x] Min outcomes for adjustment: `_MIN_OUTCOMES_FOR_ADJUSTMENT=5` (prevents overfitting)
- [x] `agent_os/proactive_explorer.py` — detects stale incumbents, metric gaps, adversarial edges
- [x] `agent_os/self_improvement.py` — wires AutoTriggerLoop + BehaviorLearner + ProactiveExplorer
- [x] Background threads: behavior learner (hourly), proactive explorer (daily)
- [x] 4 engine endpoints: status, trigger, outcomes, parameters
- [x] All engine endpoints require bearer-token auth

#### BR-P4.2 Weekly Self-Improvement Report (B-10)

**Requirement:** AgencyOS SHALL generate a week-over-week delta report showing self-improvement activity.

**Acceptance Criteria:**
- [x] `GET /api/agent-os/review/self-improvement` — full WoW delta report
- [x] `GET /api/agent-os/review/self-improvement/summary` — condensed summary
- [x] Report includes: experiments run, promotion rate, avg delta, tuner changes, threshold adjustments, proactive experiments

#### BR-P4.3 L10 Architecture Document (B-11)

**Requirement:** AgencyOS SHALL document the Level 10 architecture path and prerequisites.

**Acceptance Criteria:**
- [x] `docs/ARCHITECTURE-L10.md` — L10 design with safety boundaries
- [x] Prerequisites: L9 proven on real data, L7-8 stable, legal wrapper, safety architecture
- [x] Immutable safety boundaries defined: spending limits, legal commitments, self-modification constraints

#### BR-P4.4 Outcome Tracking Schema

**Requirement:** AgencyOS SHALL persist experiment outcomes for behavior learning.

**Acceptance Criteria:**
- [x] `improvement_outcomes` table with: outcome_id, tenant_id, proposal_id, experiment_id, metric_name, verdict, delta, baseline_value, candidate_value, applied_at
- [x] Verdict constrained: `CHECK(verdict IN ('promoted', 'rolled_back', 'rejected'))`
- [x] Indexes: tenant, metric+tenant, verdict+tenant, applied_at+tenant

---

## 3. Non-Functional Requirements

### 3.1 Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Webhook ingestion latency | < 500ms p99 | Time from POST to 200 response |
| Signal-to-detection latency | < 5s p99 | Time from signal creation to anomaly classification |
| Message bus publish latency | < 100ms p99 | Time from publish to persist |
| Role restart time | < 10s | Time from failure detection to healthy status |
| Dashboard API response | < 200ms p95 | All GET endpoints |

### 3.2 Reliability

| Metric | Target | Notes |
|--------|--------|-------|
| Webhook delivery | 99.9% | At-least-once, dedup handles replays |
| Role uptime | 99.5% | Auto-restart on failure |
| Message loss | 0% | SQLite persistence, ack before processing |
| False positive rate | < 5% | For anomaly detection |

### 3.3 Security

- All webhook endpoints require HMAC-SHA256 signature verification
- Message bus is tenant-scoped: cross-tenant message access is impossible
- Role permissions are enforced at store layer, not just application layer
- All actions are audit-logged with actor identification
- Rate limiting on all external-facing endpoints

### 3.4 Observability

- All role actions publish to `agent_os.audit` log
- Dashboard exposes per-role health: messages_processed, messages_failed, last_heartbeat
- Webhook stats: events_received, events_processed, events_failed, avg_latency
- Department orchestration stats: actions_taken, actions_blocked, actions_pending

---

## 4. Out of Scope

The following are explicitly **not** part of this BRD:

1. **Level 10 (Autonomous Business):** Full business automation is not achievable or desirable for a compliance tool. Human oversight remains primary.

2. **Cross-tenant learning:** Each tenant's data and rules are isolated. No pattern sharing between tenants in this phase.

3. **External action execution:** AgencyOS proposes actions but does not execute them externally (e.g., sending emails, making API calls to providers). Human or external system executes approved actions.

4. **Multi-model consensus:** Internal tooling does not require 3-model agreement. Human is the arbiter.

5. **Level 3 (Claude Code integration):** Hermes handles code generation. AgencyOS focuses on operations, not code writing.

---

## 5. Success Metrics

| Metric | Baseline (Current) | Target (Post-Implementation) |
|--------|-------------------|------------------------------|
| Detection latency (external events) | 1-6 hours (polling) | < 5 seconds |
| Rule proposals per month | 0 (no Evolver) | 10-20 |
| Proposal acceptance rate | N/A | > 50% |
| Outreach actions automated | 0% | 70% (within thresholds) |
| Engagement health alerts | 0 (reactive) | 100% (proactive) |
| Engine downtime per month | Variable | < 30 minutes |

---

*BRD aligned with AGENCYOS-MATURITY-FRAMEWORK.md and ARCHITECTURE.md. Business requirements derived from 10-Level Framework gap analysis.*
