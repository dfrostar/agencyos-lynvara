# Next Session Prompt — AgencyOS Phase 5 + Integration Ready

**asOf:** 2026-08-08  
**Tests:** 207/207 passing + Phase 5 unit tests  
**Repo:** `/home/dtfrost/agencyOS/`  
**Branch:** master (commit `7825089` + Phase 5 WIP)

---

## Current State

### AgencyOS — Phase 4 Complete, Phase 5 In Progress

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Server + Knowledge base + Financials | ✅ DONE |
| 2 | Webhook worker + Signal sources + Feedback loop + Weekly review | ✅ DONE |
| 3 | Dashboard + Health score | ✅ DONE |
| 4 | Self-improving engine + Weekly report + L10 architecture + QA-3 | ✅ DONE |
| **5** | **Roles + Departments** | **IN PROGRESS** |

**Phase 5 deliverables (this session):**
- `agent_os/bus.py` — SQLite-backed message bus (B-12)
- `agent_os/roles/base.py` — Abstract AgentRole class (B-13)
- `agent_os/roles/detector.py` — Detector role wrapper (B-14)
- `agent_os/roles/correlator.py` — Correlator role wrapper (B-14)
- `agent_os/roles/evolver.py` — Evolver role (B-14)
- `agent_os/roles/coordinator.py` — Role lifecycle manager (B-16)
- `agent_os/departments/base.py` — Department base class (B-17)
- `agent_os/departments/outreach.py` — Outreach department (B-17)
- `agent_os/departments/engagements.py` — Engagement department (B-18)
- `agent_os/store.py` — Added agent_messages + agent_roles tables + bus/role methods
- `agent_os/server.py` — Wired roles + departments into `create_app()` with feature flags

**Tests:**
- 207 existing tests still passing
- `tests/test_phase5_bus.py` — 11 new tests for message bus
- `tests/test_phase5_roles.py` — 4 new tests for roles
- **Total: 222 tests**

---

## What Remains for Phase 5

### Immediate (this session)

1. **Verify all 222 tests pass** — run full suite
2. **Run GLM-5.2 adversarial QA on Phase 5 code** — new attack vectors:
   - Message bus poisoning (SQL injection via payload)
   - Role impersonation (can a role spoof from_role?)
   - Infinite loop in role polling (DoS via bad config)
   - Department auto-execute without approval
   - Tenant isolation bypass via message bus
3. **Patch verified findings** — RED-GREEN TDD for CRITICAL, test alongside for HIGH
4. **Update docs to SOTA** — KANBAN, QA_REPORT, ARCHITECTURE, BRD, TRD
5. **Commit + push** — Phase 5 complete

### After Phase 5 (Integration with cmmc20)

AgencyOS is now a standalone repo. Integration with cmmc20 is a separate task:

| Task | Description |
|------|-------------|
| Wire AgencyOS webhooks to cmmc20 signals | cmmc20 backend sends signals to AgencyOS `/api/agent-os/webhooks/custom` |
| Wire AgencyOS outcomes to cmmc20 experiments | AgencyOS experiment results inform cmmc20 feature flags |
| Deploy AgencyOS to Render | Separate service, connected to cmmc20 via webhooks |
| Unified monitoring | Both services report to shared dashboard |

---

## Phase 5 Architecture

### Message Flow

```
SignalDetector.push() → metric_value message (bus)
    ↓
DetectorRole._poll() → consumes metric_value → detects anomaly
    ↓
signal message (bus) → CorrelatorRole._poll() → correlates
    ↓
insight message (bus) → EvolverRole._poll() → gap analysis
    ↓
proposal message (bus) → CoordinatorRole → routes to auto-trigger
    ↓
experiment → outcome → BehaviorLearner adjusts parameters
    ↓
Department._poll() → consumes signals → takes action (within bounds)
```

### Safety Boundaries

| Boundary | Hardcoded | Rationale |
|----------|-----------|-----------|
| `AUTO_EXECUTE_MAX_IMPROVEMENT` = 10% | Yes | Prevents large autonomous changes |
| `AUTO_EXECUTE_MAX_COST` = $50 | Yes | Prevents expensive autonomous actions |
| `MAX_DELIVERY_ATTEMPTS` = 3 | Yes | Dead letter queue prevents infinite loops |
| `RETENTION_DAYS` = 7 | Yes | Auto-cleanup of consumed messages |
| `heartbeat_timeout` = 60s | Yes | Detect stuck roles |
| Roles require `enable_roles=True` | Yes | Feature flag — off by default |
| Departments require `enable_departments=True` | Yes | Feature flag — off by default |

---

## Files Changed This Session

### New Files
- `agent_os/bus.py` — MessageBus + Message classes
- `agent_os/roles/__init__.py` — Package init
- `agent_os/roles/base.py` — AgentRole abstract class
- `agent_os/roles/detector.py` — DetectorRole
- `agent_os/roles/correlator.py` — CorrelatorRole
- `agent_os/roles/evolver.py` — EvolverRole
- `agent_os/roles/coordinator.py` — CoordinatorRole
- `agent_os/departments/__init__.py` — Package init
- `agent_os/departments/base.py` — Department base class
- `agent_os/departments/outreach.py` — OutreachDepartment
- `agent_os/departments/engagements.py` — EngagementDepartment
- `tests/test_phase5_bus.py` — 11 bus tests
- `tests/test_phase5_roles.py` — 4 role tests

### Modified Files
- `agent_os/store.py` — Added agent_messages + agent_roles schema + bus/role methods
- `agent_os/server.py` — Wired bus, roles, departments into create_app()

---

## Quick Reference

```bash
# AgencyOS
cd /home/dtfrost/agencyOS
python -m pytest tests/ -q --tb=short          # Run all tests (222 total)
python -m agent_os.server                        # Start server
curl http://localhost:9000/health               # Health check

# cmmc20 (separate repo)
cd /home/dtfrost/cmmc20
git log --oneline -10                           # Recent commits
```

---

## Recommendation

Finish Phase 5 adversarial QA and commit. Then decide:
- **Integrate with cmmc20** (wire webhooks, deploy both services)
- **Stop at Phase 5** (standalone L7-8 system, ready for real data)
- **Ship to production** (deploy to Render, start collecting real outcomes)

---

*Pattern: SOTA Build Loop v2.0 | Prompt version: v2026.08.08.3 | Last updated: 2026-08-08*
