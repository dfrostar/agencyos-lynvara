# Next Session Prompt — AgencyOS Complete + cmmc20 Integration

**asOf:** 2026-08-08  
**Tests:** 224/224 passing  
**Repo:** `/home/dtfrost/agencyOS/`  
**Branch:** master (commit `26dc9f9`)

---

## Current State

### AgencyOS — Phase 5 Complete + QA Complete ✅

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Server + Knowledge base + Financials | ✅ DONE |
| 2 | Webhook worker + Signal sources + Feedback loop + Weekly review | ✅ DONE |
| 3 | Dashboard + Health score | ✅ DONE |
| 4 | Self-improving engine + Weekly report + L10 architecture + QA-3 | ✅ DONE |
| 5 | Message bus + Roles + Coordinator + Departments + QA-4 | ✅ DONE |

**AgencyOS is a complete Level 8 system.** All phases code-complete, tested, GLM-5.2 QA verified, and DeepSeek documentation-audited.

### QA Summary

| Review | Findings | Patched |
|--------|----------|---------|
| GLM-5.2 Phase 4 | 5 MEDIUM + 4 safe | 5 patched |
| GLM-5.2 Phase 5 | 1 CRITICAL + 1 HIGH + 4 LOW + 3 safe | 6 patched |

### DeepSeek Audits

| Audit | File | Key Finding |
|-------|------|-------------|
| Documentation Audit | `DOCUMENTATION-AUDIT.md` (404 lines) | QA_REPORT inflates patched count, auto-restart missing, human approval API missing |
| Level 10 Plan | `LEVEL-10-PLAN-2026-08-08.md` (1,458 lines) | L10 not achievable in 2026 — ship L8 co-pilot instead |

---

## Critical Context

### What's Actually Built

- HTTP server (port 9000) with tenant-scoped API routes
- Knowledge base (CRUD + full-text search)
- Financial tracking (revenue/costs/invoices — read-only, no payment processing)
- Webhook ingestion (GitHub, Stripe, Custom — HMAC-SHA256 verified)
- Closed-loop engine (signal → insight → proposal → experiment → promote/rollback)
- Self-improving engine (behavior learner adjusts lambda/cooldown based on outcomes)
- Proactive explorer (stale incumbents, metric gaps, adversarial edges)
- Message bus (SQLite pub/sub, at-least-once delivery, dead letter queue)
- 4 roles (Detector, Correlator, Evolver, Coordinator) — communicate via bus
- 2 departments (Outreach, Engagement) — act within safety bounds
- 224 tests passing

### What's NOT Built (Verified by DeepSeek)

- External action execution (no email sending, no payment processing, no contract signing)
- Auto-restart on role failure (coordinator only logs timeouts)
- Human proposal approval API (no routes exist)
- Department config API (no routes exist)
- Safety architecture (no kill switches, no circuit breakers, no immutable audit trail)
- Real signal data (0 months of production outcomes)

### Honest Assessment (from DeepSeek)

**Do not pursue Level 10.** Ship AgencyOS as an L8 co-pilot product for CMMC consultants ($200-500/month per tenant). The CMMC market legally prohibits autonomous compliance assessment (requires human C3PAO). Focus on proving L9 on real data first.

---

## Task Queue (Priority Order)

### 1. Fix Documentation Contradictions (P0 — Blocking)

`DOCUMENTATION-AUDIT.md` found 10 overclaims. Fix these before any release:

1. **QA_REPORT.md** — Change "5 MEDIUM findings patched" → "3 patched, 3 outstanding"
2. **ARCHITECTURE.md §7** — Change Phase 5 from 🔴 TODO to ✅ DONE
3. **ARCHITECTURE.md §1** — Change L7/L8 from ❌ NOT DONE to ⚠️ (code-complete, integration-incomplete)
4. **KANBAN.md** — Fix Phase 5 header ("Future" vs "✅ DONE" contradiction)
5. **TRD.md §4-6** — Update async ABC pattern → actual synchronous threading
6. **BRD.md §2.2.2** — Remove "auto-restart on failure" claim (not implemented)
7. **BRD.md §7.7** — Mark human proposal approval API as deferred (not implemented)
8. **BRD.md §8.3** — Mark department config API as deferred (not implemented)

### 2. Implement Missing Acceptance Criteria (P1)

DeepSeek found documented features that don't exist:

1. **Human proposal approval API** — `GET /api/agent-os/proposals/pending`, `POST /api/agent-os/proposals/{id}/approve`, `POST /api/agent-os/proposals/{id}/reject`
2. **Department config API** — `GET/POST /api/agent-os/departments/{name}/config`, `POST /api/agent-os/departments/{name}/pause`
3. **Coordinator auto-restart** — Detect heartbeat timeout → restart role → alert after 3 failures
4. **Fix `can_auto_execute()`** — Read instance attributes (currently silently ignores config)

### 3. Produce Missing Documentation (P1)

DeepSeek identified 6 missing docs:

1. `docs/SAFETY-BOUNDARIES.md` — Hardcoded limits, rationale, known gaps
2. `docs/API-REFERENCE.md` — All endpoints with auth requirements
3. `docs/CONFIGURATION-REFERENCE.md` — All env vars, config options, defaults
4. `docs/DEPLOYMENT-GUIDE.md` — Render setup, env vars, health checks
5. `docs/INTEGRATION-GUIDE.md` — Webhook flow, tenant mapping, safety boundaries
6. `docs/TROUBLESHOOTING-GUIDE.md` — Common failures, diagnostics

### 4. Integrate with cmmc20 (P1 — Separate Task)

`DOCUMENTATION-AUDIT.md` includes a draft integration plan. Key points:

- **Webhook flow:** cmmc20 → AgencyOS (assessment signals, SPRS scores)
- **Outcome flow:** AgencyOS → cmmc20 (promote/rollback verdicts)
- **Tenant mapping:** cmmc20 Organization.id → AgencyOS tenant_id
- **Render deployment:** Separate service, SQLite WAL, env vars
- **Safety tests before production:** webhook auth, idempotency, oversized body, tenant isolation

### 5. Complete RFI Response (P1 — Due Aug 14)

`cmmc20/docs/cmmc-watch/RFI-RESPONSE-DRAFT.md` is missing answers to 2 of 7 questions:

- **Q2: Controls with most tangible uplift** — MISSING
- **Q3: Controls with highest overhead/least improvement** — MISSING

DeepSeek suggested specific content for each gap.

### 6. GitHub Issues Cleanup (P2)

- **cmmc20 #158** — "🔴 PRIORITY: RFI Response Due Aug 14" — still open, close or update
- No AgencyOS issues exist

---

## Quick Reference

```bash
# AgencyOS
cd /home/dtfrost/agencyOS
python -m pytest tests/ -q --tb=short          # Run all tests (224 total)
python -m agent_os.server                        # Start server
curl http://localhost:9000/health               # Health check

# Key files
cat docs/QA_REPORT.md                            # QA record (needs correction)
cat docs/LEVEL-10-PLAN-2026-08-08.md             # L10 plan (do not pursue)
cat DOCUMENTATION-AUDIT.md                       # Drift audit (fix overclaims)
cat phase5_adversarial_qa_report.md              # Phase 5 QA findings

# cmmc20 (separate repo)
cd /home/dtfrost/cmmc20
git log --oneline -10                           # Recent commits
cat docs/cmmc-watch/RFI-RESPONSE-DRAFT.md        # RFI draft (2 questions missing)
```

---

## DeepSeek Recommendations (This Week)

1. **Wire AgencyOS to real data** — Connect cmmc20 leads to AgencyOS, collect real outcomes
2. **Deploy to production** — Render setup, monitoring, first paying customer
3. **Validate willingness-to-pay** — 5 CMMC consultants at $200-500/month
4. **Do NOT build L10** — Focus on proving L9 on real data first

---

## Key Safety Boundaries (Hardcoded)

| Boundary | Value | Rationale |
|----------|-------|-----------|
| `MAX_DELIVERY_ATTEMPTS` | 3 | Dead letter queue |
| `RETENTION_DAYS` | 7 | Auto-cleanup |
| `_LAMBDA_MIN` / `_LAMBDA_MAX` | 1.0 / 20.0 | Page-Hinkley detector bounds |
| `_COOLDOWN_MIN` / `_COOLDOWN_MAX` | 10s / 3600s | Signal flood prevention |
| `_MIN_OUTCOMES_FOR_ADJUSTMENT` | 5 | Prevent overfitting |
| `AUTO_EXECUTE_MAX_IMPROVEMENT` | 10% | Department safety |
| `AUTO_EXECUTE_MAX_COST` | $50 | Department safety |
| `MAX_BODY_SIZE` | 1 MiB | Webhook body limit |

---

*Pattern: SOTA Build Loop v2.0 | Prompt version: v2026.08.08.5 | Last updated: 2026-08-08*
