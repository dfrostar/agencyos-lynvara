# Next Session Prompt — AgencyOS Phase 4 QA + Phase 5 Planning

**asOf:** 2026-08-08  
**Tests:** 210/210 (178 existing + 32 Phase 4, minus 2 known failures)  
**Repo:** `/home/dtfrost/agencyOS/`

---

## Context

AgencyOS Phase 4 (Intelligence Layer) is **code-complete but not yet QA-verified**. The feedback loop is wired: outcomes → BehaviorLearner → parameter adjustment → proactive exploration → weekly report. All 5 new modules are in place, but 2 tests are failing and the GLM-5.2 adversarial review is still pending.

---

## Phase 4 Status (Built, Tests Partial, QA Pending)

| Component | Lines | Status |
|-----------|-------|--------|
| B-09 Outcome Tracking (`store.py`) | +200 | ✅ 5/5 tests pass |
| B-09 BehaviorLearner | 276 | ✅ 5/5 tests pass |
| B-09 ProactiveExplorer | 257 | 🟡 5/7 tests (2 `sqlite3.Row.get()` bugs) |
| B-09 Server Wiring (`self_improvement.py`) | 251 | 🟡 5/7 tests (fixture bug) |
| B-10 Weekly Report | 252 | ✅ 5/5 tests pass |
| B-11 L10 Architecture | doc | ✅ Complete |

---

## This Session's Work (Priority Order)

### Step 1: Fix Known Test Failures

**2 failures in `proactive_explorer.py`:**
- `test_run_cycle_proposes_for_stale`
- `test_run_cycle_updates_proposals_made`

Both caused by `row.get('history', '')` on `sqlite3.Row` at line 135. Fix:
```python
# Before:
f"... History: {row.get('history', '')}"
# After:
f"... History: {row['history'] or ''}"
```

**6 failures in `test_phase4.py` engine endpoints:**
All caused by the server fixture not passing `self_improvement_engine` to `create_app()`. Fix: update the `server` fixture to create a `SelfImprovementEngine` instance and pass it.

### Step 2: Verify All Tests Green

```bash
cd /home/dtfrost/agencyOS && python -m pytest tests/ -q --tb=short
# Expected: 210/210 passing
```

### Step 3: Dispatch GLM-5.2 Adversarial QA (QA-3)

Review scope (7 files):

| File | Lines | Focus |
|------|-------|-------|
| `agent_os/behavior_learner.py` | 276 | Lambda drift, cooldown extremes, outcome bypass |
| `agent_os/proactive_explorer.py` | 257 | SQL injection via metric_name, unbounded proposals |
| `agent_os/self_improvement.py` | 251 | Thread safety, store connection leaks, recursion |
| `agent_os/weekly_self_improvement.py` | 252 | AVG(delta) None crash, report data integrity |
| `agent_os/promotion.py` (+25) | - | outcome_recorder DI, exception masking |
| `agent_os/auto_trigger.py` (+10) | - | Callback chain integrity |
| `agent_os/server.py` (+30) | - | Auth bypass on new endpoints |

**Adversarial angles:**

| Angle | Attack Vector | Severity |
|-------|--------------|----------|
| Outcome recording bypass | Can outcome_recorder be None silently? | CRITICAL |
| Lambda drift | Can lambda bypass _LAMBDA_MIN/MAX? | HIGH |
| Cooldown drift | Can cooldown reach 0 or infinity? | HIGH |
| ProactiveExplorer injection | metric_name in adversarial query | CRITICAL |
| Background thread crash | _behavior_loop exception handling | MEDIUM |
| Store connection leak | SQLite connection lifecycle | HIGH |
| Auth bypass on engine endpoints | /engine/status without token | CRITICAL |
| AutoTriggerLoop recursion | signal→proposal→experiment loop | MEDIUM |
| AVG(delta) None crash | Empty outcome stats | LOW |

### Step 4: Patch Verified Findings

For each GLM-5.2 finding:
1. Re-read actual source (don't trust subagent summary)
2. If CRITICAL → Full RED-GREEN TDD (test first, watch fail, patch, watch pass)
3. If HIGH → Test alongside patch
4. If MEDIUM/LOW → Patch + run existing tests

### Step 5: Update Docs to SOTA

All behavior-changing commits must update docs in the same commit:
- `KANBAN.md` — Mark Phase 4 QA complete
- `QA_REPORT.md` — Add GLM-5.2 findings, patches, test counts
- `ARCHITECTURE.md` — Update Honest Capability Map (Phase 4 + QA)
- `BRD.md` — Mark B-09/B-10/B-11 acceptance criteria
- `TRD.md` — Update module structure to include new modules

### Step 6: Commit + Push

Conventional commit format:
- `test: fix sqlite3.Row.get() in proactive_explorer`
- `fix: wire SelfImprovementEngine to test fixture`
- `security: patch GLM-5.2 CRITICAL findings`
- `docs: update KANBAN, QA_REPORT, ARCHITECTURE for Phase 4`

---

## Next Session Kickoff

```bash
cd /home/dtfrost/agencyOS
# Fix tests, dispatch GLM-5.2 QA, patch, commit
```

---

*Pattern: SOTA Build Loop v2.0 | Prompt version: v2026.08.08.1 | Last updated: 2026-08-08*
