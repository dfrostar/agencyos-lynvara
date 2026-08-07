# Next Session Prompt — AgencyOS Phase 5 + RFI Submission

**asOf:** 2026-08-08  
**Tests:** 207/207 passing  
**Repo:** `/home/dtfrost/agencyOS/`  
**Branch:** master (commit `7825089`)

---

## Current State

### AgencyOS — Phase 4 Complete ✅

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Server + Knowledge base + Financials | ✅ DONE |
| 2 | Webhook worker + Signal sources + Feedback loop + Weekly review | ✅ DONE |
| 3 | Dashboard + Health score | ✅ DONE |
| 4 | Self-improving engine + Weekly report + L10 architecture + QA-3 | ✅ DONE |

**Phase 4 deliverables:**
- `agent_os/behavior_learner.py` (282 lines) — outcome-driven parameter adjustment
- `agent_os/proactive_explorer.py` (282 lines) — gap detection + adversarial probing
- `agent_os/self_improvement.py` (251 lines) — engine wiring + 4 endpoints
- `agent_os/weekly_self_improvement.py` (257 lines) — WoW delta report
- GLM-5.2 adversarial QA: 9 attack vectors assessed, 5 MEDIUM findings patched, 4 safe
- All docs updated: BRD, ARCHITECTURE, TRD, QA_REPORT, KANBAN

### Phase 5: Level 7-8 — DEFERRED

| ID | Task | Level | Est. | Status |
|----|------|-------|------|--------|
| B-12 | Message bus | 7 | — | DEFERRED |
| B-13 | Role base class | 7 | — | DEFERRED |
| B-14 | Detector role | 7 | — | DEFERRED |
| B-15 | Correlator role | 7 | — | DEFERRED |
| B-16 | Coordinator | 7 | — | DEFERRED |
| B-17 | Outreach department | 8 | — | DEFERRED |
| B-18 | Engagement department | 8 | — | DEFERRED |

**Rationale for deferral:** Level 9 needs to be proven on real data (6+ months of outcomes) before L7-8 autonomy is safe to deploy.

---

## Priority Options for Next Session

### Option A: RFI Submission (URGENT — Due Aug 14, 7 days)

The CMMC RFI response is drafted but **NOT SUBMITTED**. Deadline is August 14, 2026.

**Current state:**
- Draft: `cmmc20/docs/cmmc-watch/RFI-RESPONSE-DRAFT.md`
- DOCX + PDF generated, emailed to darren.frost@gmail.com (thread: 68c677d8)
- Issue #158 created: "🔴 PRIORITY: RFI Response Due Aug 14"
- **Gap:** Draft reads like a white paper, not an RFI response. Only 1 of 7 RFI questions answered directly.

**Tasks:**
1. Restructure draft around the 7 RFI questions (direct Q&A format)
2. Fill coverage gaps: Q2 (controls with uplift), Q3 (overhead/least improvement), Q4 (commercial capabilities), Q7 (resilience reforms)
3. Add 1-page cover letter (excluded from 10-page limit)
4. Regenerate DOCX/PDF
5. Submit by email to:
   - whs.mc-alex.ad.mbx.eosd-psb-branch-mailbox@mail.mil
   - leanne.m.condren.civ@mail.mil

**Submission addresses:**
- `whs.mc-alex.ad.mbx.eosd-psb-branch-mailbox@mail.mil`
- `leanne.m.condren.civ@mail.mil`

### Option B: AgencyOS Phase 5 (Level 7-8)

If you want to continue building, Phase 5 is the next technical milestone.

**Pre-requisites before starting:**
- L9 proven on real data (currently 0 real outcomes — all tests use synthetic data)
- Safety architecture for autonomous roles
- Human approval workflow for rule changes

**Estimated effort:** ~30 hours total
- B-12 Message bus: ~4h
- B-13 Role base class: ~3h
- B-14 Detector role: ~4h
- B-15 Correlator role: ~4h
- B-16 Coordinator: ~5h
- B-17 Outreach department: ~5h
- B-18 Engagement department: ~5h

**Risk:** Building L7-8 before L9 is proven on real data creates scaffolding without validation. The honest path is to wire AgencyOS to real cmmc20 data first, let it learn from real outcomes, then add roles/departments.

### Option C: cmmc20 Stripe Implementation

The other agent has been working on cmmc20 (NeuralMind fixes, Issue model, pre-deploy scripts). Stripe integration is queued in the unified kanban.

**Tasks:**
- Create Stripe service + checkout endpoint
- Add subscription gating middleware
- Deploy updated docker-compose + .env to Render

---

## Recommendation

**Submit the RFI first.** The deadline is firm, and the draft needs structural revision. After submission, decide between:
- Starting Phase 5 (if you want to keep building)
- Wiring AgencyOS to real cmmc20 data (if you want to validate L9)
- Stripe implementation (if you want to unblock cmmc20 monetization)

---

## Quick Reference

```bash
# AgencyOS
cd /home/dtfrost/agencyOS
python -m pytest tests/ -q --tb=short          # Run tests (207 pass)
python -m agent_os.server                       # Start server
curl http://localhost:9000/health               # Health check

# cmmc20
cd /home/dtfrost/cmmc20
git log --oneline -5                            # Recent commits
cat docs/cmmc-watch/RFI-RESPONSE-DRAFT.md       # RFI draft
```

---

*Pattern: SOTA Build Loop v2.0 | Prompt version: v2026.08.08.2 | Last updated: 2026-08-08*
