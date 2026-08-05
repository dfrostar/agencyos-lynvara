# AgencyOS — Framework Progression Kanban

**Repo:** /home/dtfrost5/agencyOS/
**Date:** 2026-08-05
**Scope:** Close Levels 5/7/8 gaps in the 10-Level Maturity Framework
**Docs:** `agencyOS/docs/` (ARCHITECTURE.md, BRD.md, PRD.md, TRD.md)

---

## Current Maturity

```
Level 10: Autonomous Business Layer          ❌ Out of scope
Level 9:  Self-Improving Systems             ✅ (engine only — tuner values)
Level 8:  Orchestrated Departments           ❌ NOT DONE
Level 7:  Specialised Agent Teams            ❌ NOT DONE
Level 6:  Closed-Loop Workflows              ✅ (core)
Level 5:  Trigger-Based Workflows            ✅ DONE (webhooks committed 2026-08-05)
Level 4:  Tool-Connected                     ✅
Level 3:  Claude Code                        ⚠️ Via Hermes
Level 2:  Co-Work                            ✅
Level 1:  Chat                               ✅
```

---

## Active

| ID | Task | Level | Status | Owner | Notes |
|----|------|-------|--------|-------|-------|
| A-01 | Webhook ingestion layer | 5 | ✅ DONE | Hermes | server.py extension + webhooks.py |
| A-02 | GitHub event normalizer | 5 | ✅ DONE | Hermes | sources/github.py — 6 event types |
| A-03 | Stripe event normalizer | 5 | ✅ DONE | Hermes | sources/stripe.py — 6 event types |
| A-04 | Custom event normalizer | 5 | ✅ DONE | Hermes | sources/custom.py — tenant-defined mapping |
| A-05 | Webhook config + tenant resolution | 5 | ✅ DONE | Hermes | store.py extension + API routes |
| A-06 | Webhook background worker | 5 | ✅ DONE | Hermes | WebhookWorker coded, needs server wiring |
| A-07 | Message bus | 7 | 🔴 TODO | — | SQLite-backed pub/sub |
| A-08 | Role base class | 7 | 🔴 TODO | — | roles/base.py |
| A-09 | Detector role wrapper | 7 | 🔴 TODO | — | Wraps SignalDetector |
| A-10 | Correlator role wrapper | 7 | 🔴 TODO | — | Wraps RootCauseCorrelator |
| A-11 | Evolver role | 7 | 🔴 TODO | — | Rule proposal engine |
| A-12 | Coordinator | 7 | 🔴 TODO | — | Role lifecycle + health monitor |
| A-13 | Human approval workflow | 7 | 🔴 TODO | — | Proposal review API |
| A-14 | Outreach department loop | 8 | 🔴 TODO | — | 3 sub-loops (scoring, templates, timing) |
| A-15 | Engagement health loop | 8 | 🔴 TODO | — | 2 sub-loops (velocity, stagnation) |
| A-16 | Department config API | 8 | 🔴 TODO | — | Tenant-controlled activation |

---

## Dependency Chain

```
A-01 → A-02 → A-03 → A-04 → A-05 → A-06  (Level 5 — Webhooks) ✅ DONE
                                          │
                                          ▼
                                        A-07  (Message bus) 🔴 TODO
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                        A-08            A-09            A-10  (Level 7 — Roles) 🔴 TODO
                          │               │               │
                          └───────────────┼───────────────┘
                                          ▼
                                        A-11  (Evolver) 🔴 TODO
                                          │
                                          ▼
                                        A-12  (Coordinator) 🔴 TODO
                                          │
                                          ▼
                                        A-13  (Approval workflow) 🔴 TODO
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               │               ▼
                        A-14              │             A-15  (Level 8 — Departments) 🔴 TODO
                          │               │               │
                          └───────────────┼───────────────┘
                                          ▼
                                        A-16  (Config API) 🔴 TODO
```

---

## Phase 1: Level 5 Completion (Webhooks) — ✅ DONE (2026-08-05)

**Goal:** Accept GitHub/Stripe/Custom webhook events → create Signals

**Commit:** `6d13361` — 17 files, +45,354 lines

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Create webhook_events + webhook_configs tables | ✅ | Migration runs on server startup |
| 2 | Build WebhookIngester with HMAC verification | ✅ | GitHub, Stripe, Custom all supported |
| 3 | Add webhook POST routes to server.py | ✅ | `/api/agent-os/webhooks/{source}` |
| 4 | Build GitHub normalizer | ✅ | push, PR, issues, workflow_run, deployment |
| 5 | Build Stripe normalizer | ✅ | payments, subscriptions, refunds, invoices |
| 6 | Build Custom normalizer | ✅ | Tenant-defined dot-notation mapping |
| 7 | Build WebhookWorker async loop | ✅ | Coded, needs server wiring for full e2e |
| 8 | Add webhook monitoring stats API | ✅ | `GET /api/agent-os/webhooks/stats` |
| 9 | Write integration tests | ⏳ Deferred | Worker wiring + tests = next session |

**Remaining:** Worker server wiring + 15+ integration tests before Phase 1 is fully complete. Core ingestion logic committed.

---

## Phase 2: Level 7 Start (Roles Foundation) — 🔴 TODO

**Goal:** Message bus + role base classes + coordinator + wrap existing detector/correlator

| # | Task | Est. | Verification |
|---|------|------|-------------|
| 1 | Build MessageBus (publish/consume/ack) | 3h | Unit tests pass (pub, sub, ack, dead letter) |
| 2 | Build AgentRole base class | 2h | Abstract methods enforced, heartbeat works |
| 3 | Wrap SignalDetector as DetectorRole | 1h | Consumes metric_value, produces signal |
| 4 | Wrap RootCauseCorrelator as CorrelatorRole | 1h | Consumes signal, produces insight |
| 5 | Build Coordinator | 3h | Starts roles, restarts on crash, monitors health |
| 6 | Add role management API routes | 1h | `GET /api/agent-os/roles` returns role health |
| 7 | Wire coordinator into server.py | 1h | Server starts with `ENABLE_ROLES=true` |
| 8 | Write role tests | 3h | 20+ tests pass |

**Phase 2 Total: ~15 hours**

---

## Phase 3: Level 7 Complete (Evolver)

**Goal:** Evolver role proposes rules, human approval workflow

| # | Task | Est. | Verification |
|---|------|------|-------------|
| 1 | Build EvolverRole with daily analysis | 4h | Identifies high-FP rules, stale rules |
| 2 | Implement gap analysis queries | 2h | `analyze_false_positive_rate` returns correct metrics |
| 3 | Build proposal creation | 1h | Proposals stored with risk_level, confidence |
| 4 | Build approval workflow API | 2h | `POST /approve`, `POST /reject` work |
| 5 | Add pending proposals dashboard | 1h | `GET /proposals/pending` lists proposals |
| 6 | Write Evolver tests | 3h | 10+ tests pass |

**Phase 3 Total: ~12 hours**

---

## Phase 4: Level 8 Start (Department Orchestration)

**Goal:** Outreach department runs autonomously within thresholds

| # | Task | Est. | Verification |
|---|------|------|-------------|
| 1 | Build department base class | 1h | Abstract evaluate() method |
| 2 | Build OutreachOrchestrator | 4h | 3 sub-loops implemented |
| 3 | Build engagement health queries | 2h | SQL queries for velocity, stagnation |
| 4 | Build department config API | 1h | Tenant can set thresholds, enable/disable |
| 5 | Wire departments into coordinator | 1h | Department evaluation runs on schedule |
| 6 | Write department tests | 3h | 15+ tests pass |

**Phase 4 Total: ~12 hours**

---

## Total Estimate

| Phase | Level | Hours | Cumulative | Status |
|-------|-------|-------|------------|--------|
| 1 | 5 (complete) | 15 | 15 | ✅ Committed (2026-08-05) |
| 2 | 7 (start) | 15 | 30 | 🔴 TODO |
| 3 | 7 (complete) | 12 | 42 | 🔴 TODO |
| 4 | 8 (start) | 12 | 54 | 🔴 TODO |

**~54 hours of focused work = ~7 working days total**

---

## Completed

| ID | Task | Owner | Commit |
|----|------|-------|--------|
| A-01 | Webhook ingestion layer | Hermes | 6d13361 |
| A-02 | GitHub event normalizer | Hermes | 6d13361 |
| A-03 | Stripe event normalizer | Hermes | 6d13361 |
| A-04 | Custom event normalizer | Hermes | 6d13361 |
| A-05 | Webhook config + tenant resolution | Hermes | 6d13361 |
| A-06 | Webhook background worker | Hermes | 6d13361 |

---

## Blocked

| ID | Task | Blocked On |
|----|------|------------|
| — | — | Nothing currently blocked |

---

## Out of Scope (Correctly)

- **Level 10:** Not achievable or desirable for compliance tool
- **Level 3 (Claude Code):** Hermes handles this
- **Cross-tenant learning:** Each tenant isolated by design
- **External action execution:** AgencyOS proposes, humans/external systems execute
- **Multi-model consensus:** Internal tooling, human is arbiter

---

## Key Files

| File | Purpose | Phase |
|------|---------|-------|
| `agent_os/webhooks.py` | Webhook ingestion + worker | 1 |
| `agent_os/sources/github.py` | GitHub normalizer | 1 |
| `agent_os/sources/stripe.py` | Stripe normalizer | 1 |
| `agent_os/sources/custom.py` | Custom normalizer | 1 |
| `agent_os/bus.py` | Message bus | 2 |
| `agent_os/roles/base.py` | Role abstract class | 2 |
| `agent_os/roles/detector.py` | Detector role | 2 |
| `agent_os/roles/correlator.py` | Correlator role | 2 |
| `agent_os/coordinator.py` | Role lifecycle manager | 2 |
| `agent_os/roles/evolver.py` | Evolver role | 3 |
| `agent_os/departments/outreach.py` | Outreach orchestrator | 4 |
| `agent_os/departments/engagements.py` | Engagement orchestrator | 4 |

---

## Verification Commands

```bash
# Run all tests
cd /home/dtfrost5/agencyOS && python -m pytest tests/ -q --tb=short

# Start server with new features
ENABLE_WEBHOOKS=true ENABLE_ROLES=true python -m agent_os.server

# Test webhook endpoint
curl -X POST http://localhost:9000/api/agent-os/webhooks/custom \
  -H "Content-Type: application/json" \
  -d '{"event_id":"test-1","tenant_id":"test","metric_name":"test.metric","value":1.0}'

# Check role health
curl http://localhost:9000/api/agent-os/roles
```

---

*Kanban for AgencyOS framework progression. 16 tasks across 4 phases. All requirements derived from AGENCYOS-MATURITY-FRAMEWORK.md gap analysis.*
