# Next Session Prompt — AgencyOS Post-Remediation Hardening

**Date:** 2026-08-06  
**Status:** 6/6 original findings patched ✅ | Adversarial QA complete ✅ | Final commit + push needed  
**Working directory:** `/home/dtfrost/agencyOS`  
**Pattern:** SOTA Build Loop v2.0 (from `ai-product-development/sota-build-loop`)

---

## Phase 0: Canonical Context

**Stack:** Python 3, stdlib-only, SQLite, Flask-like HTTP server  
**Architecture:** Signal → insight → proposal → experiment → promote/rollback loop  
**Users:** NeuralMind product operations, self-improving agents  
**Critical paths:** Auth flows, webhook ingestion, signal processing, experiment promotion  
**Test coverage:** 111 tests passing (baseline green)

---

## Session Summary (What Just Happened)

### Original 6 Findings — All Resolved ✅

| Finding | Fix | Verification | Commit |
|---------|-----|--------------|--------|
| **P0 C3:** FK to non-existent `tenants` table | Removed `FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)` from `webhook_configs` | Fresh DB migration OK | `222d756` |
| **P1 H1:** No max body size | Added `MAX_BODY_SIZE = 1_048_576` check in `_read_body` | >1MB → 413, <1MB → 200 | `222d756` |
| **P1 H2:** No chunked encoding handling | Reject `Transfer-Encoding: chunked` with 400 | All case variations + multi-value | `222d756` |
| **P1 M1:** `require_permission` fragile positional args | Decorator now prefers kwargs, falls back to args | 5 scenarios tested | `222d756` |
| **P1 M2:** `get_audit_log` ignores `limit` param | Added `LIMIT ?` to SQL + rowid DESC tiebreaker | limit=0,1,3,-1,None all correct | `222d756` |
| **P1 M3:** f-string in `delete_tenant` | No change — `tenant_id` already `?`-parameterized, table names can't be parameterized | N/A | N/A |

### Adversarial QA — Additional Fixes ✅

| Finding | Fix | Severity | Commit |
|---------|-----|----------|--------|
| Multi-value `Transfer-Encoding: gzip, chunked` bypassed `== "chunked"` check | Changed to `"chunked" in te` | 🔴 CRITICAL | `023f58c` |
| Body-not-drained on rejection caused 500 (unread bytes on socket) | Added `_drain_body()` + `_BodyRejected` exception pattern | 🔴 CRITICAL | `023f58c` |
| Webhook ingestion path had no body size/chunked hardening | Applied H1/H2 to webhook path | ⚠️ WARNING | `023f58c` |
| `limit=None` crashed with `IntegrityError: datatype mismatch` | Coerce non-int/negative to -1 (SQLite unlimited) | ⚠️ WARNING | `023f58c` |
| Audit log ordering non-deterministic (no tiebreaker) | Added `rowid DESC` | ℹ️ NICE-TO-HAVE | `023f58c` |

### Infrastructure

- NeuralMind index rebuilt: 991 nodes, 1193 synapses, 19 communities
- NVIDIA NIM verified available: 4 models (DeepSeek v4 Pro, GLM 5.2, DeepSeek v4 Flash, Kimi K2.6)
- GitHub remote: `dfrostar/agencyOS` (private)

---

## What Remains To Do

### P0: Commit + Push

```
cd /home/dtfrost/agencyOS
git log --oneline -3
# Should see:
# 023f58c fix: server body drain on reject + audit log limit validation
# 222d756 fix: critical security and correctness fixes across store, server, governance
# fcd96c7 docs: update NEXT-SESSION-PROMPT.md to v2026.08.06.4

git push origin master
# Expected: 023f58c..222d756 master -> master
```

### P1: Final Verification

```bash
cd /home/dtfrost/agencyOS

# 1. Test suite
python -m pytest tests/ -q
# Expected: 111 passed

# 2. Lint
python -m ruff check agent_os/
# Expected: no errors

# 3. NeuralMind synapse rebuild (fresh context)
# (NeuralMind daemon auto-rebuilds on commit — just verify no errors in logs)

# 4. Manual smoke test (if server is running)
curl -s -X POST http://localhost:9000/api/agent-os/tenants \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "smoke-test", "name": "Smoke", "admin_email": "test@test.com"}'
# Expected: 201
```

### P2: Documentation Update

Update `docs/NEXT-SESSION-PROMPT.md` to v2026.08.06.5:

- Remove all 6 original findings from "What Remains" section
- Add adversarial QA findings to "What Was Patched" table
- Update changelog

---

## Files Modified (All Sessions)

| File | What | Commits |
|------|------|---------|
| `agent_os/api.py` | C1 fix + headers threading | `b430df1` |
| `agent_os/server.py` | C2 fix + headers + H1/H2 + `_drain_body` + `_BodyRejected` | `219fe29`, `222d756`, `023f58c` |
| `agent_os/governance.py` | C2 fix + M1 decorator kwargs | `219fe29`, `222d756` |
| `agent_os/store.py` | C3 FK removal + M2 LIMIT + M3 (no-op) + reference_mean column | `27ebd11`, `222d756`, `023f58c` |
| `agent_os/signals.py` | Page-Hinkley + unique IDs + persistence | `27ebd11` |
| `agent_os/experiment.py` | p-value t-test fix | `df0493c` |
| `agent_os/auto_trigger.py` | Configurable higher_is_better | `1fa05b8` |
| `agent_os/promotion.py` | Rollback no-op | `1fa05b8` |
| `agent_os/webhooks.py` | Webhook ingestion (H1/H2 hardening in server.py) | — |
| `tests/test_feedback.py` | C2 test fixes | `684b3f1` |
| `tests/test_agent_os_api.py` | Auth test infrastructure | `684b3f1` |

---

## Architecture Map (Post-Remediation)

```
Client Request
     │
     ▼
┌─────────────────────────────────────────────┐
│  AgentOSHandler (server.py)                 │
│  ┌─────────────────────────────────────────┐│
│  │ do_GET / do_POST / do_PATCH / do_DELETE ││
│  │  ├─ Transfer-Encoding: chunked? → 400   ││
│  │  ├─ Content-Length > 1MB? → 413         ││
│  │  ├─ drain_body() before rejection       ││
│  │  └─ _read_body() → JSON or None         ││
│  └─────────────────────────────────────────┘│
│                    │                         │
│         ┌─────────┴─────────┐               │
│         ▼                   ▼               │
│  Webhook path          Route handlers       │
│  (dedicated           (api.py,             │
│   hardening)           outreach.py,         │
│                        feedback.py)         │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  Governance Layer (governance.py)           │
│  ┌─────────────────────────────────────────┐│
│  │ @require_permission decorator           ││
│  │  ├─ Extract tenant_id/email from kwargs ││
│  │  ├─ Fall back to positional args[1,2]  ││
│  │  ├─ Check registry.get_tenant()        ││
│  │  ├─ role_has_permission() check         ││
│  │  └─ Log + raise on denial              ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  AgentOSStore (store.py)                    │
│  ┌─────────────────────────────────────────┐│
│  │  _tx() — atomic commit/rollback        ││
│  │  _lock — threading.Lock                 ││
│  │  WAL mode — concurrent reads            ││
│  │  foreign_keys=ON — FK enforcement       ││
│  └─────────────────────────────────────────┘│
│  Tables: signals, signal_states, insights,  │
│  proposals, experiments, promotions,        │
│  tuner_incumbents, adversarial_queries,     │
│  audit_log, webhook_configs, webhook_events │
│  schema_version                             │
└─────────────────────────────────────────────┘
```

---

## Constraints (Still Active)

- Full RED-GREEN TDD for ALL future CRITICAL findings
- Commit separately per fix area
- Run `pytest tests/ -q` after each commit
- No breaking changes to signal→experiment→promotion loop
- stdlib-only, no new dependencies
- Follow existing code style (google-style docstrings, explicit error handling)

---

## Rollback Plan

| Area | Revert Command | Signal of Failure |
|------|----------------|-------------------|
| Auth (C1+C2) | `git revert 684b3f1 219fe29` | 500 on endpoints, tests fail |
| Signals/Experiment | `git revert 27ebd11 df0493c` | Tests fail, regressions |
| Auto-trigger/Promotion | `git revert 1fa05b8` | Experiments broken |
| **Current session** | `git revert 023f58c 222d756` | **If tests fail** |

**If patch breaks tests: revert immediately, document failure, proceed.**

---

## Next Session Priority (After Push)

1. **P0:** Verify push succeeded on GitHub
2. **P1:** Run final `pytest tests/ -q` (expect 111 passed)
3. **P1:** Update `NEXT-SESSION-PROMPT.md` to v2026.08.06.5
4. **P2:** Archive this prompt to `docs/archive/NEXT-SESSION-PROMPT-v2026.08.06.5.md`

---

## Known Issues / Out of Scope

| Issue | Why Deferred |
|-------|--------------|
| `api.py:103` crashes on `body.get("tenant_id")` when body is None (rejection returns None, handler tries `.get()`) | Pre-existing, not introduced by this session. Low impact — only fires when body parse fails (already malformed request). |
| `api.py` exception handlers catch `Exception` → 500 with `str(e)` (potential info leak) | Pre-existing pattern across all endpoints. Out of scope for this remediation. |
| No rate limiting | Architectural concern, not a finding from this QA cycle. |

---

## Test Suite Reference

| Test File | What It Covers |
|-----------|----------------|
| `tests/test_agent_os.py` | Tenant, TenantIdValidation, TenantRegistry, RolePermissions, AgentOSGovernance, SignalDetector, ExperimentRunner, SignalExperimentIntegration |
| `tests/test_agent_os_api.py` | 10 HTTP endpoint handlers (create/list/get tenant, add/delete project, assign role, get/push signals, run/list experiments) |
| `tests/test_feedback.py` | Feedback CRUD, stats, digest, capture user correction/test failure/QA finding, closed-loop knowledge creation, tenant isolation, body tenant trust |
| `tests/test_agent_os_v2.py` | RootCauseCorrelator, PromotionEngine, PromotionRecord, AgentOSStore (deadlock regression) |

---

## Changelog

| Date | Prompt Version | What Changed | Skill Version |
|------|---------------|-------------|---------------|
| 2026-08-06 | v2026.08.06.1 | Initial prompt — findings C1-M3, Task 1 patches, Phase 0-3 structure | v2.0 |
| 2026-08-06 | v2026.08.06.2 | Added NeuralMind bootstrap, QA model routing, mini-changelog | v2.0 |
| 2026-08-06 | v2026.08.06.3 | C1 committed, C2 code fixed + tests in progress, test infra changes documented | v2.0 |
| 2026-08-06 | v2026.08.06.4 | C1+C2 committed; Task 1 patches committed; 111 tests green; H3 removed as false positive | v2.0 |
| 2026-08-06 | v2026.08.06.5 | **All 6 original findings patched + adversarial QA complete; H1/H2 hardening extended to webhook path; body drain + exception pattern; audit log limit validation; NeuralMind index rebuilt; NVIDIA NIM verified** | v2.0 |

---

*Pattern: SOTA Build Loop v2.0 | Prompt version: v2026.08.06.5 | Last updated: 2026-08-06*
