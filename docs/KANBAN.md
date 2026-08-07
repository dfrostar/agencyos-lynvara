# AgencyOS — Kanban

**Last updated:** 2026-08-07
**Plan:** `docs/BUSINESS-PLAN-2026-08-06.md`
**Stream:** B — Business Operations
**Owner:** Hermes (engineering), Darren (strategy/decisions)

---

## Current State

```
Tests:     178 passing (all green)
Server:    ✅ RUNNING (port 9000)
Level 5:   ✅ DONE (webhook ingestion + sources)
Level 6:   ✅ DONE (closed-loop engine)
Level 9:   ✅ DONE (tuner incumbents + adversarial QA hardening)
Level 7-8: ❌ NOT BUILT
B-04:      ✅ DONE (dashboard health score + 3 endpoints)
B-05:      ✅ DONE (webhook worker background thread)
B-06:      ✅ DONE (signal sources + raw signal ingestion)
B-08:      ✅ DONE (weekly review aggregation)
B-07:      ✅ DONE (feedback→knowledge loop, verified wired)
QA:        ✅ COMPLETE (all CRITICAL/HIGH/MEDIUM patched, QA_REPORT.md created)
```

---

## Phase 1: Foundation — Server + Core Modules (7.5h)

| ID | Task | Level | Est. | Status | Verification |
|----|------|-------|------|--------|--------------|
| B-01 | Start server, health endpoint | — | 0.5h | ✅ DONE | `curl localhost:9000/health` → 200 |
| B-02 | Knowledge base module | 4 | 4h | ✅ DONE | CRUD + search for decisions, SOPs, research |
| B-03 | Financial tracking | 4 | 3h | ✅ DONE | Revenue, costs, invoicing per client/engagement |

**Deliverable:** ✅ Server running, core data modules in place.

---

## Phase 2: Automation Pipeline (10h)

| ID | Task | Level | Est. | Status | Verification |
|----|------|-------|------|--------|--------------|
| B-05 | Wire webhook worker to server | 5 | 2h | ✅ DONE | WebhookWorker runs in daemon thread, processes queued events |
| B-06 | Connect signal sources | 5 | 3h | ✅ DONE | signal_sources.py + raw_signals table, 7 new routes |
| B-07 | Feedback → knowledge loop | 6 | 2h | ✅ DONE | feedback.py _create_knowledge_entry wired into PATCH status=applied |
| B-08 | Weekly business review | 6 | 3h | ✅ DONE | weekly_review.py aggregates finance/outreach/engagements/feedback/signals/webhooks/knowledge |

**Deliverable:** ✅ Automated pipeline — webhooks create signals, feedback becomes knowledge, weekly reviews auto-generate.

---

## Phase 3: Dashboard + Visibility (4h)

| ID | Task | Level | Est. | Status | Verification |
|----|------|-------|------|--------|--------------|
| B-04 | Business health dashboard | 4 | 4h | ✅ DONE | dashboard.py: health score + 3 endpoints (full/health/metrics) |

**Deliverable:** Single pane of glass — leads, revenue, engagement status, signal activity visible.

---

## Phase 4: Intelligence Layer (12h)

| ID | Task | Level | Est. | Status | Verification |
|----|------|-------|------|--------|--------------|
| B-09 | Self-improving engine (full) | 9 | 6h | 🔴 TODO | System learns from outcomes, modifies behavior |
| B-10 | Weekly self-improvement report | 9 | 2h | 🔴 TODO | Report shows delta week-over-week |
| B-11 | Level 10 architecture design | 10 | 4h | 🔴 TODO | Architecture doc with L10 section (deferred scope) |

**Deliverable:** System modifies its own behavior based on results, reports on improvement, L10 path documented.

---

## Phase 5: Level 7-8 — Roles + Departments (Future, After L9 Proven)

| ID | Task | Level | Est. | Status |
|----|------|-------|------|--------|
| B-12 | Message bus | 7 | — | DEFERRED |
| B-13 | Role base class | 7 | — | DEFERRED |
| B-14 | Detector role | 7 | — | DEFERRED |
| B-15 | Correlator role | 7 | — | DEFERRED |
| B-16 | Coordinator | 7 | — | DEFERRED |
| B-17 | Outreach department | 8 | — | DEFERRED |
| B-18 | Engagement department | 8 | — | DEFERRED |

---

## Blocked

| ID | Task | Blocked On |
|----|------|------------|
| B1 | Server not running | Phase 1 (DONE) |
| B2 | Real data | Phase 1 (wire to cmmc20 leads) |
| B3 | Level 10 scope | Deferred to Phase 4 |

---

## Completed

| ID | Task | Commit | Evidence |
|----|------|--------|----------|
| A-01 | Webhook ingestion layer | `6d13361` | `webhooks.py` + tests |
| A-02 | GitHub event normalizer | `6d13361` | `sources/github.py` |
| A-03 | Stripe event normalizer | `6d13361` | `sources/stripe.py` |
| A-04 | Custom event normalizer | `6d13361` | `sources/custom.py` |
| A-05 | Webhook config + tenant resolution | `6d13361` | `store.py` extension |
| A-06 | Webhook background worker | `6d13361` | Coded, server-wired in Phase 2 |
| D1 | Feedback loop extraction | `3ab1440` | `feedback.py` + 12 tests |
| D2 | Framework docs (ARCH/BRD/PRD/TRD) | `30a7d21` | 5 docs |
| D3 | Outreach extraction | `74521f2` | `outreach.py` + 12 tests |
| D4 | Engagement extraction | `74521f2` | `engagements.py` + 8 tests |
| B-01 | Server + health endpoint | `d8678e5` | `server.py`, `agent_os/` init |
| B-02 | Knowledge base module | `45f4928` | `knowledge.py` |
| B-03 | Financial tracking | `6bc7a6f` | `finance.py` |
| QA-1 | C1-C4 security patches | `b430df1`, `219fe29`, `222d756` | Auth bypass, tenant_id, FK, schema |
| QA-2 | H1-H3 server hardening | `023f58c`, `219fe29` | Body size limit, chunked, Stripe replay |
| QA-3 | M1-M3 cleanup | `023f58c` | Decorator, audit log, f-string |
| QA-4 | Phase 1 inline review | — | This document |
| B-05 | Webhook worker wired | — | server.py:564-579, daemon thread |
| B-06 | Signal sources | — | signal_sources.py + store.py, 20 tests |
| B-07 | Feedback→knowledge verified | — | feedback.py:68-109, 318-339 |
| B-08 | Weekly review | — | weekly_review.py, 7 routes |

---

## Verification Commands

```bash
# Run all tests
cd /home/dtfrost/agencyOS && python -m pytest tests/ -q --tb=short

# Start server
cd /home/dtfrost/agencyOS && python -m agent_os.server

# Test health
curl http://localhost:9000/health
```

---

*Kanban for AgencyOS. Stream B of Level2Logic Cybersecurity Platform. Target: Level 9 (proven) → Level 7-8 (deferred until L9 validated on real data).*
