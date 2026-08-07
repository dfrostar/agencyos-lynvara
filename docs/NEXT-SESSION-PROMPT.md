# Next Session Prompt — AgencyOS + cmmc20 Integration Plan

**asOf:** 2026-08-08  
**Tests:** 224/224 passing (AgencyOS)  
**Repos:** `/home/dtfrost/agencyOS/` (master `6242a03`), `/home/dtfrost/cmmc20/` (master)  
**Goal:** Integration plan + L9/L10 success criteria

---

## Current State

### AgencyOS — L8 Complete ✅

| Component | Status |
|-----------|--------|
| Phases 1-5 | ✅ Code-complete |
| Tests | ✅ 224 passing |
| GLM-5.2 QA (Phase 4) | ✅ 5 MEDIUM patched, 4 safe |
| GLM-5.2 QA (Phase 5) | ✅ 1 CRITICAL + 1 HIGH + 4 LOW patched |
| DeepSeek Documentation Audit | ✅ `DOCUMENTATION-AUDIT.md` |
| DeepSeek Level 10 Plan | ✅ `LEVEL-10-PLAN-2026-08-08.md` |
| NeuralMind Index | ✅ 1,837 nodes, 25 communities |

### cmmc20 — L2Logic Platform

| Component | Status |
|-----------|--------|
| Backend | ❌ 502 (missing STRIPE_SECRET_KEY) |
| Frontend | ✅ 107/107 tests |
| NeuralMind | ✅ Healthy |
| QA Gate | ✅ 680 tests green |
| RFI Response | ❌ NOT SUBMITTED (due Aug 14, Issue #158) |

---

## Integration Architecture (Draft)

### Signal Flow: cmmc20 → AgencyOS

```
cmmc20 Assessment.created → webhook → AgencyOS /api/agent-os/webhooks/custom
cmmc20 PracticeAssessment.scored → webhook → AgencyOS metric update
cmmc20 SPRS.calculated → webhook → AgencyOS cmmc.sprs.score
cmmc20 Client.onboarded → webhook → AgencyOS tenant provisioning
cmmc20 Engagement.status_changed → webhook → AgencyOS signal
```

### Outcome Flow: AgencyOS → cmmc20

```
AgencyOS experiment.promoted → cmmc20 accepts parameter change
AgencyOS experiment.rolled_back → cmmc20 reverts parameter change
AgencyOS weekly_report → cmmc20 dashboard widget
AgencyOS engine.outcomes → cmmc20 reads via polling (no push)
```

### Tenant Mapping

| cmmc20 | AgencyOS |
|--------|----------|
| Organization.id | tenant_id |
| Client.id | (scoped under org tenant) |
| Assessment.id | experiment context |
| PracticeAssessment | metric signal |
| SPRS Score | `cmmc.sprs.score` metric |

---

## L9 Success Criteria

**Goal:** Prove the self-improving engine learns from real data.

### Metrics to Track

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Promotion rate | >50% | `outcomes WHERE verdict='promoted' / total` |
| Rollback rate | <20% | `outcomes WHERE verdict='rolled_back' / total` |
| Lambda convergence | Stable | `signal_states.lambda_threshold` plateaus over 30 days |
| Signal quality | <5% false positive | Manual review of triggered signals |
| Outcome velocity | >10 outcomes/week | `outcomes COUNT per week` |

### Validation Plan

1. **Wire AgencyOS to cmmc20 signals** (assessment events, practice scores, SPRS)
2. **Run for 30 days** with roles/departments DISABLED (observation mode)
3. **Collect 100+ real outcomes** before enabling autonomous actions
4. **Review weekly** — human approves/rolls back all experiments
5. **After 90 days** — if promotion rate >50% and rollback rate <20%, L9 is proven

### L9 Technical Requirements

- [ ] cmmc20 webhook → AgencyOS integration (custom webhook source)
- [ ] Tenant provisioning sync (cmmc20 org → AgencyOS tenant)
- [ ] Signal mapping (cmmc20 events → AgencyOS metrics)
- [ ] Outcome feedback loop (AgencyOS → cmmc20 dashboard)
- [ ] Weekly review automation (AgencyOS → cmmc20 email/widget)

---

## L10 Success Criteria

**Goal:** Autonomous business operations with human oversight.

### Prerequisites (Must Be True Before L10)

| Prerequisite | How to Verify |
|--------------|---------------|
| L9 proven on real data | 90 days of production outcomes, promotion rate >50% |
| Legal entity | LLC formed, operating agreement signed |
| Insurance | E&O + D&O + Cyber liability active |
| Safety architecture | `agent_os/safety.py` with hardcoded immutable boundaries |
| Kill switches | `/api/agent-os/emergency-stop` endpoint tested |
| Audit trail | Every autonomous action logged with rationale |
| Circuit breakers | System stops itself on anomalous behavior |
| 24/7 coverage | On-call rotation (not solo operator) |

### L10 Decision Framework

| Action Level | Examples | Autonomy |
|--------------|----------|----------|
| L1: Internal | Adjust lambda, detect anomalies, generate reports | ✅ Fully autonomous |
| L2: Propose | Create experiments, suggest scoring changes | ✅ Auto-create, human approves |
| L3: Notify | Alert on anomalies, recommend actions | ✅ Auto-notify, human decides |
| L4: External low-risk | Send status emails, update dashboards | ⚠️ Human approval required |
| L5: External high-risk | Process payments, sign contracts, hire/fire | ❌ Never autonomous |

### L10 Technical Requirements

- [ ] `agent_os/safety.py` — hardcoded immutable safety boundaries
- [ ] `agent_os/kill_switch.py` — emergency stop (soft pause, hard stop, full shutdown)
- [ ] `agent_os/audit.py` — every action logged with rationale + evidence
- [ ] `agent_os/approval.py` — human approval workflow for L4+ actions
- [ ] `agent_os/circuit_breaker.py` — self-monitoring + auto-stop
- [ ] External action execution layer (email, API calls, payment processing)
- [ ] Multi-tenant production deployment (PostgreSQL, connection pooling)
- [ ] Monitoring + alerting (PagerDuty/Opsgenie integration)

---

## Implementation Roadmap

### Phase 6: Real Data Validation (Months 1-3)

**Goal:** Prove L9 on real cmmc20 signals.

| Week | Task |
|------|------|
| 1-2 | Deploy AgencyOS to Render (separate service) |
| 3-4 | Wire cmmc20 webhooks → AgencyOS custom webhook source |
| 5-6 | Tenant provisioning sync (cmmc20 orgs → AgencyOS tenants) |
| 7-8 | Signal mapping + outcome feedback loop |
| 9-12 | Observation mode: collect outcomes, no autonomous actions |

**Deliverable:** 100+ real outcomes, weekly review reports.

### Phase 7: Production Deployment (Month 4)

**Goal:** First paying customer.

| Week | Task |
|------|------|
| 1-2 | Deploy to Render with monitoring |
| 3-4 | Onboard 5 CMMC consultants (manual) |
| 5-8 | Validate willingness-to-pay ($200-500/month) |

**Deliverable:** 1 paying customer, MRR > $0.

### Phase 8: Legal Wrapper (Months 4-6, parallel)

**Goal:** Reduce liability exposure.

| Week | Task |
|------|------|
| 1-4 | Form LLC (Wyoming or Delaware) |
| 5-8 | Obtain EIN, business bank account |
| 9-12 | Purchase insurance (E&O, D&O, Cyber) |
| 13-16 | Draft operating agreement with AgencyOS authority bounds |

**Deliverable:** LLC active, insurance bound, operating agreement signed.

### Phase 9: Safety Architecture (Months 5-6)

**Goal:** Hard boundaries that cannot be bypassed.

| Week | Task |
|------|------|
| 1-2 | Implement `agent_os/safety.py` (hardcoded limits) |
| 3-4 | Implement `agent_os/kill_switch.py` (emergency stop) |
| 5-6 | Implement `agent_os/audit.py` (immutable audit trail) |
| 7-8 | Implement `agent_os/circuit_breaker.py` (self-monitoring) |
| 9-12 | Test all safety systems under failure scenarios |

**Deliverable:** Safety architecture tested, documented, verified.

### Phase 10: Autonomous Execution (Months 7-9)

**Goal:** External action execution with human oversight.

| Week | Task |
|------|------|
| 1-4 | Implement `agent_os/approval.py` (human approval workflow) |
| 5-8 | External action layer (email via Resend, API calls) |
| 9-12 | Integration testing with human-in-the-loop |
| 13-16 | Graduated autonomy rollout (L1 → L2 → L3 → L4) |

**Deliverable:** L10 system with human oversight, graduated autonomy.

---

## This Week's Priorities

### 1. Documentation Fixes (Blocking)

- [ ] QA_REPORT.md — Fix "5 MEDIUM patched" → "3 patched, 3 outstanding"
- [ ] ARCHITECTURE.md — Update Phase 5 status (✅ DONE), L7/L8 (⚠️)
- [ ] KANBAN.md — Fix Phase 5 header contradiction
- [ ] TRD.md — Update async ABC → synchronous threading

### 2. cmmc20 Integration Design

- [ ] Define webhook payload format (cmmc20 → AgencyOS)
- [ ] Define outcome polling API (AgencyOS → cmmc20)
- [ ] Define tenant provisioning flow
- [ ] Define signal mapping table

### 3. RFI Response Completion (Due Aug 14)

- [ ] Add Q2 response (controls with most uplift)
- [ ] Add Q3 response (controls with highest overhead)
- [ ] Add cover letter
- [ ] Submit to DoW

### 4. GitHub Issues Cleanup

- [ ] Close or update cmmc20 #158 (RFI submission)

---

## Key Files

| File | Purpose |
|------|---------|
| `docs/QA_REPORT.md` | QA record (needs correction) |
| `docs/LEVEL-10-PLAN-2026-08-08.md` | L10 plan (1,458 lines) |
| `DOCUMENTATION-AUDIT.md` | Drift audit (fix overclaims) |
| `phase5_adversarial_qa_report.md` | Phase 5 QA findings |
| `cmmc20/docs/cmmc-watch/RFI-RESPONSE-DRAFT.md` | RFI draft (2 questions missing) |

---

## Honest Assessment

**L9 is achievable in 3-6 months** if you wire AgencyOS to real cmmc20 data and collect 100+ outcomes. The self-improving engine works mechanically — it just needs real signals to learn from.

**L10 is achievable in 12-18 months** but requires:
- Legal entity formation ($2,000-5,000)
- Insurance ($3,000-10,000/year)
- Safety architecture (2-4 months engineering)
- 24/7 operational coverage (not solo)

**The honest recommendation:** Ship AgencyOS as an L8 co-pilot product now ($200-500/month per tenant), prove L9 on real data over 6 months, then reassess L10 based on actual business traction.

---

*Pattern: SOTA Build Loop v2.0 | Prompt version: v2026.08.08.6 | Last updated: 2026-08-08*
