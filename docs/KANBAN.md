# AgencyOS — Kanban

**Last updated:** 2026-08-06
**Plan:** `docs/BUSINESS-PLAN-2026-08-06.md`
**Stream:** B — Business Operations
**Owner:** Hermes (engineering), Darren (strategy/decisions)

---

## Current State

```
Tests:     111 passing (all green, post-remediation)
Server:    ❌ NOT RUNNING
Level 6:   ✅ DONE (closed-loop engine)
Level 9:   ✅ DONE (tuner incumbents + adversarial QA hardening)
Level 7-8: ❌ NOT BUILT
QA:        ✅ COMPLETE (6 findings patched + adversarial QA closed)
```

---

## Phase 1: Foundation — Server + Core Modules (7.5h)

| ID | Task | Level | Est. | Status | Verification |
|----|------|-------|------|--------|--------------|
| B-01 | Start server, health endpoint | — | 0.5h | 🔴 TODO | `curl localhost:9000/health` → 200 |
| B-02 | Knowledge base module | 4 | 4h | 🔴 TODO | CRUD + semantic search for decisions, SOPs, research |
| B-03 | Financial tracking | 4 | 3h | 🔴 TODO | Revenue, costs, invoicing per client/engagement |

**Deliverable:** Server running, core data modules in place. Unblocks B-04, B-07, B-08.

---

## Phase 2: Automation Pipeline (10h)

| ID | Task | Level | Est. | Status | Verification |
|----|------|-------|------|--------|--------------|
| B-05 | Wire webhook worker to server | 5 | 2h | 🔴 TODO | Webhook creates signal automatically |
| B-06 | Connect signal sources | 5 | 3h | 🔴 TODO | Competitor, regulatory, market signals flow in |
| B-07 | Feedback → knowledge loop | 6 | 2h | 🔴 TODO | Client feedback auto-creates knowledge entry |
| B-08 | Weekly business review | 6 | 3h | 🔴 TODO | Auto-summarize pipeline, revenue, signals |

**Deliverable:** Automated pipeline — webhooks create signals, feedback becomes knowledge, weekly reviews auto-generate.

---

## Phase 3: Dashboard + Visibility (4h)

| ID | Task | Level | Est. | Status | Verification |
|----|------|-------|------|--------|--------------|
| B-04 | Business health dashboard | 4 | 4h | 🔴 TODO | Leads, revenue, engagement status visible |

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
| B1 | Server not running | Phase 1 |
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
| A-06 | Webhook background worker | `6d13361` | Coded, not server-wired |
| D1 | Feedback loop extraction | `3ab1440` | `feedback.py` + 12 tests |
| D2 | Framework docs (ARCH/BRD/PRD/TRD) | `30a7d21` | 5 docs |
| D3 | Outreach extraction | `74521f2` | `outreach.py` + 12 tests |
| D4 | Engagement extraction | `74521f2` | `engagements.py` + 8 tests |
| D5 | 111 tests passing (post-remediation) | — | All green |
| QA-1 | Remediation: 6 findings patched | `222d756`, `023f58c` | FK, body size, chunked, decorator, audit log |
| QA-2 | Adversarial QA hardening | `023f58c` | Multi-value TE, body drain, webhook path, limit validation |

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
