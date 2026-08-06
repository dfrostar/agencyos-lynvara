# AgencyOS — Business Plan

**Date:** 2026-08-06
**Status:** ACTIVE
**Owner:** Darren Frost (Level2Logic)
**Stream:** B — AgencyOS Maturity to Level 9 (Level 10 TBD)

---

## 1. Product Positioning

AgencyOS is the **operating system for Level2Logic**. It runs the business operations so Darren can focus on high-value work (strategy, client relationships, compliance decisions).

**Not a product. Not a platform. A private operator tool.**

---

## 2. What "Running the Business" Means

### Human Stays In Control For:
- Compliance sign-off (CMMC assessments require human C3PAO)
- Client relationships and strategic decisions
- Final approval on major financial commitments

### AgencyOS Runs:
- Lead pipeline and follow-ups
- Client engagement tracking
- Knowledge base (decisions, SOPs, research)
- Financial tracking (revenue, costs, invoicing)
- Market signal detection (competitor, regulatory)
- Closed-loop business experiments
- Weekly business health reporting
- Self-improvement (learns from outcomes, modifies behavior)

---

## 3. Framework (Revised)

```
Level 10: Autonomous Business Layer          🔮 TBD (design after 6-9 prove value)
Level 9:  Self-Improving Systems             ✅ TARGET (system learns + adapts)
Level 8:  Orchestrated Departments           ❌ NOT STARTED
Level 7:  Specialised Agent Teams            ❌ NOT STARTED
Level 6:  Closed-Loop Workflows              ✅ DONE (engine exists)
Level 5:  Trigger-Based Workflows            ✅ DONE (webhooks committed)
Level 4:  Tool-Connected                     ✅ DONE
Level 3:  Claude Code                        ⚠️ Via Hermes
Level 2:  Co-Work                            ✅ DONE
Level 1:  Chat                               ✅ DONE
```

**Level 10 is IN SCOPE but deferred.** We design it after Levels 6-9 prove what actually matters for running a business. The architecture will accommodate it, but we don't build what we don't yet understand.

---

## 4. Current State (Verified)

| Component | Level | Status | Evidence |
|-----------|-------|--------|----------|
| HTTP server | — | ❌ NOT RUNNING | `curl localhost:9000` → refused |
| Store (SQLite, multi-tenant) | 4 | ✅ | 1120 lines, 25 tests |
| Outreach extraction | 4 | ✅ | 470 lines, 12 tests |
| Engagement extraction | 4 | ✅ | 540 lines, 8 tests |
| Feedback loop | 6 | ✅ | 700 lines, 12 tests |
| Webhook ingestion | 5 | ✅ Code, not wired | 270 lines, 6 tests |
| Signal detection | 5 | ✅ | 340 lines, 12 tests |
| Experiment runner | 6 | ✅ | 230 lines, 8 tests |
| Promotion/rollback | 6 | ✅ | 350 lines, 8 tests |
| Auto-trigger (closed-loop) | 6 | ✅ | 220 lines, 6 tests |
| Knowledge base | 4 | ❌ NOT BUILT | — |
| Financial tracking | 4 | ❌ NOT BUILT | — |
| Business health dashboard | 4 | ❌ NOT BUILT | — |
| Self-improving engine (full) | 9 | ❌ NOT BUILT | Engine only |
| 110 tests passing | — | ✅ | All green |

---

## 5. What's Left (Execution Plan)

### Sprint 1: Core Operations (Week 1)

| ID | Task | Level | Est. | Why | Verification |
|----|------|-------|------|-----|--------------|
| B-01 | Start server, health endpoint | — | 0.5h | Must run before anything | `curl localhost:9000/health` |
| B-02 | Knowledge base module | 4 | 4h | Store decisions, SOPs, research | CRUD + semantic search |
| B-03 | Financial tracking | 4 | 3h | Revenue, costs, invoicing | Track $ per client/engagement |
| B-04 | Business health dashboard | 4 | 4h | Leads, revenue, engagement status | Dashboard shows live data |

**Sprint 1 Total: 11.5 hours**

### Sprint 2: Signals + Automation (Week 2)

| ID | Task | Level | Est. | Why | Verification |
|----|------|-------|------|-----|--------------|
| B-05 | Wire webhook worker to server | 5 | 2h | Process real events | Webhook creates signal |
| B-06 | Connect signal sources | 5 | 3h | Competitor, regulatory, market | Sources feed into signals |
| B-07 | Feedback → knowledge loop | 6 | 2h | Auto-create knowledge from feedback | Feedback creates entry |
| B-08 | Weekly business review | 6 | 3h | Auto-summarize pipeline, revenue | Report generated |

**Sprint 2 Total: 10 hours**

### Sprint 3: Level 9 + Level 10 Design (Week 3)

| ID | Task | Level | Est. | Why | Verification |
|----|------|-------|------|-----|--------------|
| B-09 | Self-improving engine (full) | 9 | 6h | System learns from outcomes, modifies behavior | Engine proposes + applies improvements |
| B-10 | Weekly self-improvement report | 9 | 2h | Show what system learned | Report shows delta week-over-week |
| B-11 | Level 10 architecture design | 10 | 4h | Document what L10 looks like after L6-9 prove value | Architecture doc with L10 section |

**Sprint 3 Total: 12 hours**

---

## 6. Level 10 Approach (Deferred)

**Principle:** Don't build what you don't understand yet.

After Levels 6-9 prove value, we'll know:
- Which business functions actually benefit from autonomy
- Where human judgment is truly required vs habit
- What data the system needs to make good decisions

Level 10 design will be a **separate document** written Sprint 3, based on real operational data from L6-9.

---

## 7. Framework Progression Strategy

| Phase | Levels | What We Build | What Proves It |
|-------|--------|---------------|----------------|
| Now → Sprint 1 | 4-5 | Core ops + dashboard | You use it daily |
| Sprint 2 | 5-6 | Signals + feedback loop | It saves you time |
| Sprint 3 | 9 | Self-improvement | It makes you money |
| Future | 10 | TBD based on L6-9 learnings | — |

---

## 8. Blockers

| ID | Blocked On | Status |
|----|------------|--------|
| B1 | Server not running | Sprint 1 |
| B2 | Real data | Sprint 1 (wire to cmmc20 leads) |
| B3 | Level 10 scope | Deferred to Sprint 3 |

---

## 9. Success Criteria

AgencyOS is "done" when:
- [ ] You check it daily for business health
- [ ] It auto-generates weekly business reviews
- [ ] It proposes experiments that you approve/reject
- [ ] It learns from outcomes (Level 9 proven)
- [ ] Level 10 architecture is documented based on real data

---

*Plan for AgencyOS. Part of Level2Logic Cybersecurity Platform. Runs the business operations.*
