# AgencyOS — Framework Progression Kanban

**Repo:** /home/dtfrost5/agencyOS/
**Date:** 2026-08-06
**Scope:** Close Levels 5/7/8 gaps in the 10-Level Maturity Framework
**Docs:** `agencyOS/docs/` (ARCHITECTURE.md, BRD.md, PRD.md, TRD.md)
**Honest assessment:** `docs/HONEST-COMPLETION-ASSESSMENT-2026-08-06.md`

---

## Current Maturity

```
Level 10: Autonomous Business Layer          ❌ Out of scope
Level 9:  Self-Improving Systems             ✅ (engine only — tuner values)
Level 8:  Orchestrated Departments           ❌ NOT DONE
Level 7:  Specialised Agent Teams            ❌ NOT DONE
Level 6:  Closed-Loop Workflows              ✅ (core — unit tested, NOT run on real data)
Level 5:  Trigger-Based Workflows            ✅ DONE (webhooks committed 2026-08-05)
Level 4:  Tool-Connected                     ✅
Level 3:  Claude Code                        ⚠️ Via Hermes
Level 2:  Co-Work                            ✅
Level 1:  Chat                               ✅
```

---

## 🏗️ ACTIVE: Pragmatic Completion Path (Option B — 20 hours)

**Goal:** Get AgencyOS running on REAL business data. Prove closed-loop value before building Level 7-8.

| ID | Task | Est. | Status | Verification |
|----|------|------|--------|--------------|
| B-01 | Wire webhook worker into server | 3h | 🔴 TODO | Server starts with `ENABLE_WEBHOOKS=true` |
| B-02 | Start server + connect to cmmc20 proxy | 2h | 🔴 TODO | `curl localhost:9000/health` returns 200 |
| B-03 | Run real outreach data through loop | 5h | 🔴 TODO | Outreach lead → signal → experiment → promotion chain executes |
| B-04 | Verify closed-loop on REAL data | 5h | 🔴 TODO | Experiment makes good decision on real lead |
| B-05 | Dashboard showing actual signals | 5h | 🔴 TODO | Real-time signals + experiments visible |

**Success metric:** AgencyOS processes real outreach data and makes a good automated decision WITHOUT human intervention.

---

## 🔮 FUTURE: Level 7-8 (Deferred — 39 hours)

**Only pursue if Option B proves closed-loop value on real data.**

### Phase 2: Level 7 Start (Roles Foundation) — 15 hours

| ID | Task | Est. | Status | Verification |
|----|------|------|--------|--------------|
| A-07 | Message bus (SQLite-backed pub/sub) | 3h | 🔴 TODO | Unit tests pass (pub, sub, ack, dead letter) |
| A-08 | Role base class | 2h | 🔴 TODO | Abstract methods enforced |
| A-09 | Detector role wrapper | 1h | 🔴 TODO | Consumes metric_value, produces signal |
| A-10 | Correlator role wrapper | 1h | 🔴 TODO | Consumes signal, produces insight |
| A-11 | Evolver role | 4h | 🔴 TODO | Identifies high-FP rules, stale rules |
| A-12 | Coordinator | 3h | 🔴 TODO | Starts roles, restarts on crash |
| A-13 | Human approval workflow | 1h | 🔴 TODO | Proposal review API |

### Phase 3: Level 8 (Department Orchestration) — 12 hours

| ID | Task | Est. | Status | Verification |
|----|------|------|--------|--------------|
| A-14 | Outreach department loop | 4h | 🔴 TODO | 3 sub-loops (scoring, templates, timing) |
| A-15 | Engagement health loop | 2h | 🔴 TODO | Velocity + stagnation queries |
| A-16 | Department config API | 1h | 🔴 TODO | Tenant-controlled activation |
| — | Wire departments into coordinator | 1h | 🔴 TODO | Evaluation runs on schedule |
| — | Department tests | 4h | 🔴 TODO | 15+ tests pass |

---

## Kill Criteria

**Re-evaluate AgencyOS track after pragmatic path. Kill if:**
- Real-data closed-loop makes bad decisions (worse than human)
- cmmc20 has no paying customers to feed real data
- Maintenance > 20% of total engineering time
- Level 7-8 features never get used by actual tenants

---

## Completed (Verified)

| ID | Task | Commit | Evidence |
|----|------|--------|----------|
| A-01 | Webhook ingestion layer | `6d13361` | `webhooks.py` + tests |
| A-02 | GitHub event normalizer | `6d13361` | `sources/github.py` |
| A-03 | Stripe event normalizer | `6d13361` | `sources/stripe.py` |
| A-04 | Custom event normalizer | `6d13361` | `sources/custom.py` |
| A-05 | Webhook config + tenant resolution | `6d13361` | `store.py` extension |
| A-06 | Webhook background worker | `6d13361` | Coded, not server-wired |
| D1 | Feedback loop extraction | `3ab1440` | `feedback.py` + 12 tests |
| D2 | Framework docs (ARCH/BRD/PRD/TRD) | `30a7d21` | 5 docs, ~100KB total |
| D3 | Kanban (cmmc20) | `d7a1cd0` | Synced with AgencyOS progress |
| D4 | 110 tests passing | — | All green |

---

## Deferred (No Immediate Need)

| Item | Status | Why |
|------|--------|-----|
| Knowledge base extraction | DEFERRED | No immediate tenant need |
| Billing integration | DEFERRED | No paying tenants |
| WebSocket/gRPC | DEFERRED | HTTP sufficient for now |
| Multi-region sync | DEFERRED | Single-node sufficient |

---

## Blocked

| ID | Task | Blocked On |
|----|------|------------|
| B1 | Server not running | Code exists, not started |
| B2 | cmmc20 proxy wiring | AgencyOS proxy in cmmc20 needs testing |
| B3 | Real data | cmmc20 needs paying customers |

---

## Key Files

| File | Purpose | Phase |
|------|---------|-------|
| `agent_os/webhooks.py` | Webhook ingestion + worker | 1 (code complete, not wired) |
| `agent_os/sources/github.py` | GitHub normalizer | 1 |
| `agent_os/sources/stripe.py` | Stripe normalizer | 1 |
| `agent_os/sources/custom.py` | Custom normalizer | 1 |
| `agent_os/bus.py` | Message bus | 2 (not started) |
| `agent_os/roles/base.py` | Role abstract class | 2 (not started) |
| `agent_os/roles/detector.py` | Detector role | 2 (not started) |
| `agent_os/roles/correlator.py` | Correlator role | 2 (not started) |
| `agent_os/coordinator.py` | Role lifecycle manager | 2 (not started) |
| `agent_os/roles/evolver.py` | Evolver role | 3 (not started) |
| `agent_os/departments/outreach.py` | Outreach orchestrator | 3 (not started) |
| `agent_os/departments/engagements.py` | Engagement orchestrator | 3 (not started) |

---

## Verification Commands

```bash
# Run all tests
cd /home/dtfrost5/agencyOS && python -m pytest tests/ -q --tb=short

# Start server with webhook worker
ENABLE_WEBHOOKS=true python -m agent_os.server

# Test webhook endpoint
curl -X POST http://localhost:9000/api/agent-os/webhooks/custom \
  -H "Content-Type: application/json" \
  -d '{"event_id":"test-1","tenant_id":"test","metric_name":"test.metric","value":1.0}'

# Check role health
curl http://localhost:9000/api/agent-os/roles
```

---

*Kanban for AgencyOS framework progression. Revised 2026-08-06 after honest completion assessment. 5-task pragmatic path (20h) takes priority over 16-task full framework (54h).*
