# AgencyOS — Kanban

**Last updated:** 2026-08-06
**Plan:** `docs/BUSINESS-PLAN-2026-08-06.md`
**Stream:** B — Business Operations
**Owner:** Hermes (engineering), Darren (strategy/decisions)

---

## Current State

```
Tests:     110 passing (all green)
Server:    ❌ NOT RUNNING
Level 6:   ✅ DONE (closed-loop engine)
Level 9:   ❌ NOT BUILT (target)
Level 10:  🔮 TBD (deferred, in scope)
```

---

## Sprint 1: Core Operations (11.5h)

| ID | Task | Level | Status | Est. | Verification |
|----|------|-------|--------|------|--------------|
| B-01 | Start server, health endpoint | — | 🔴 TODO | 0.5h | `curl localhost:9000/health` returns 200 |
| B-02 | Knowledge base module | 4 | 🔴 TODO | 4h | CRUD + semantic search for decisions, SOPs, research |
| B-03 | Financial tracking | 4 | 🔴 TODO | 3h | Revenue, costs, invoicing per client/engagement |
| B-04 | Business health dashboard | 4 | 🔴 TODO | 4h | Leads, revenue, engagement status visible |

**Outcome:** Daily-use business tool tracking pipeline, knowledge, finances

---

## Sprint 2: Signals + Automation (10h)

| ID | Task | Level | Status | Est. | Verification |
|----|------|-------|--------|------|--------------|
| B-05 | Wire webhook worker to server | 5 | 🔴 TODO | 2h | Webhook creates signal automatically |
| B-06 | Connect signal sources | 5 | 🔴 TODO | 3h | Competitor, regulatory, market signals flow in |
| B-07 | Feedback → knowledge loop | 6 | 🔴 TODO | 2h | Client feedback auto-creates knowledge entry |
| B-08 | Weekly business review | 6 | 🔴 TODO | 3h | Auto-summarize pipeline, revenue, signals |

**Outcome:** Automated business reviews + market awareness

---

## Sprint 3: Level 9 + L10 Design (12h)

| ID | Task | Level | Status | Est. | Verification |
|----|------|-------|--------|------|--------------|
| B-09 | Self-improving engine (full) | 9 | 🔴 TODO | 6h | System learns from outcomes, modifies behavior |
| B-10 | Weekly self-improvement report | 9 | 🔴 TODO | 2h | Report shows delta week-over-week |
| B-11 | Level 10 architecture design | 10 | 🔴 TODO | 4h | Architecture doc with L10 section (deferred scope) |

**Outcome:** System learns from outcomes + L10 documented based on L6-9 learnings

---

## Sprint 4: Level 7-8 (Future, After L9 Proven)

| ID | Task | Level | Status | Est. | Verification |
|----|------|-------|--------|------|--------------|
| B-12 | Message bus | 7 | DEFERRED | — | — |
| B-13 | Role base class | 7 | DEFERRED | — | — |
| B-14 | Detector role | 7 | DEFERRED | — | — |
| B-15 | Correlator role | 7 | DEFERRED | — | — |
| B-16 | Coordinator | 7 | DEFERRED | — | — |
| B-17 | Outreach department | 8 | DEFERRED | — | — |
| B-18 | Engagement department | 8 | DEFERRED | — | — |

---

## Blocked

| ID | Task | Blocked On |
|----|------|------------|
| B1 | Server not running | Sprint 1 |
| B2 | Real data | Sprint 1 (wire to cmmc20 leads) |
| B3 | Level 10 scope | Deferred to Sprint 3 |

---

## Completed

| ID | Task | Commit | Evidence |
|----|------|--------|----------|
| A-01 | Webhook ingestion layer | `6d13361` | `webhooks.py` + tests |
| A-02 | GitHub event normalizer | `6d13361` | `sources/github.py` |
| A-03 | Stripe event normalizer | `6d13361` | `sources/stripe.py` |
| A-04 | Custom event normalizer | `6d13361` | `sources/custom.py` |
| A-05 | Webhook config + tenant resolution | `6d13361` | `store.py` extension |
| A-06 | Webhook background worker | `6d13361` | Coded, not server-wired |
| D1 | Feedback loop extraction | `3ab1440` | `feedback.py` + 12 tests |
| D2 | Framework docs (ARCH/BRD/PRD/TRD) | `30a7d21` | 5 docs |
| D3 | Outreach extraction | `74521f2` | `outreach.py` + 12 tests |
| D4 | Engagement extraction | `74521f2` | `engagements.py` + 8 tests |
| D5 | 110 tests passing | — | All green |

---

## Verification Commands

```bash
# Run all tests
cd /home/dtfrost5/agencyOS && python -m pytest tests/ -q --tb=short

# Start server
cd /home/dtfrost5/agencyOS && python -m agent_os.server

# Test health
curl http://localhost:9000/health
```

---

*Kanban for AgencyOS. Stream B of Level2Logic Cybersecurity Platform. Target: Level 9 (Level 10 TBD).*
