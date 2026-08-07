# Next Session Prompt — AgencyOS Phased Build Plan

**Date:** 2026-08-06
**Status:** ✅ Remediation complete | Adversarial QA closed | Phased plan active
**Working directory:** `/home/dtfrost/agencyOS`
**Pattern:** SOTA Build Loop v2.0 (from `ai-product-development/sota-build-loop`)

---

## Phase 0: Canonical Context

**Stack:** Python 3, stdlib-only, SQLite, Flask-like HTTP server
**Architecture:** Signal → insight → proposal → experiment → promote/rollback loop
**Users:** NeuralMind product operations, self-improving agents
**Critical paths:** Auth flows, webhook ingestion, signal processing, experiment promotion
**Test coverage:** 111 tests passing (baseline green, post-remediation)

---

## What Was Already Patched (All Committed ✅)

| Area | Fix | Commit |
|------|-----|--------|
| C1. Body auth bypass | Removed body-based fallback from `_get_auth`. Require bearer <REDACTED> for all endpoints except `create_tenant`. | `b430df1` |
| C2. `_default_get_auth` trusts body tenant_id | Returns unauthenticated context; handlers enforce auth via `_resolve_auth(body, headers)` | `219fe29` |
| C3. FK references non-existent `tenants` table | Removed `FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)` from `webhook_configs` | `222d756` |
| H1. No body size limit | Added `MAX_BODY_SIZE = 1_048_576` check in `_read_body` | `222d756` |
| H2. No chunked encoding handling | Reject `Transfer-Encoding: chunked` with 400 | `222d756` |
| M1. `require_permission` fragile arg extraction | Decorator prefers kwargs, falls back to args | `222d756` |
| M2. `get_audit_log` limit parameter ignored | Added `LIMIT ?` to SQL + rowid DESC tiebreaker | `222d756` |
| M3. f-string in `delete_tenant` | No change — `tenant_id` already `?`-parameterized | N/A |
| Adversarial: Multi-value TE bypass | Changed `== "chunked"` to `"chunked" in te` | `023f58c` |
| Adversarial: Body-not-drained on rejection | Added `_drain_body()` + `_BodyRejected` exception pattern | `023f58c` |
| Adversarial: Webhook path no hardening | Applied H1/H2 to webhook path | `023f58c` |
| Adversarial: `limit=None` crash | Coerce non-int/negative to -1 | `023f58c` |
| Adversarial: Audit log non-deterministic | Added `rowid DESC` | `023f58c` |

---

## Phased Build Plan

### Phase 1: Foundation — Server + Core Modules (7.5h)

| ID | Task | Est. | Status |
|----|------|------|--------|
| B-01 | Start server, health endpoint | 0.5h | 🔴 TODO |
| B-02 | Knowledge base module | 4h | 🔴 TODO |
| B-03 | Financial tracking | 3h | 🔴 TODO |

### Phase 2: Automation Pipeline (10h)

| ID | Task | Est. | Status |
|----|------|------|--------|
| B-05 | Wire webhook worker to server | 2h | 🔴 TODO |
| B-06 | Connect signal sources | 3h | 🔴 TODO |
| B-07 | Feedback → knowledge loop | 2h | 🔴 TODO |
| B-08 | Weekly business review | 3h | 🔴 TODO |

### Phase 3: Dashboard + Visibility (4h)

| ID | Task | Est. | Status |
|----|------|------|--------|
| B-04 | Business health dashboard | 4h | 🔴 TODO |

### Phase 4: Intelligence Layer (12h)

| ID | Task | Est. | Status |
|----|------|------|--------|
| B-09 | Self-improving engine (full) | 6h | 🔴 TODO |
| B-10 | Weekly self-improvement report | 2h | 🔴 TODO |
| B-11 | Level 10 architecture design | 4h | 🔴 TODO |

### Phase 5: Level 7-8 — Roles + Departments (Deferred)

| ID | Task | Status |
|----|------|--------|
| B-12..18 | Message bus, roles, coordinator, departments | DEFERRED |

---

## Constraints (Active)

- Full RED-GREEN TDD for ALL CRITICAL findings
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
| Remediation | `git revert 023f58c 222d756` | If tests fail |

---

## Known Issues / Out of Scope

| Issue | Why Deferred |
|-------|--------------|
| `api.py` body `.get()` on None | Pre-existing. Low impact — fires only on malformed requests. |
| `api.py` `Exception` → 500 with `str(e)` | Pre-existing pattern. Info leak. |
| No rate limiting | Architectural, not a QA finding. |

---

## Test Suite Reference

| Test File | What It Covers |
|-----------|----------------|
| `tests/test_agent_os.py` | Tenant, TenantIdValidation, TenantRegistry, RolePermissions, AgentOSGovernance, SignalDetector, ExperimentRunner, SignalExperimentIntegration |
| `tests/test_agent_os_api.py` | 10 HTTP endpoint handlers |
| `tests/test_feedback.py` | Feedback CRUD, stats, digest, capture, closed-loop knowledge, tenant isolation |
| `tests/test_agent_os_v2.py` | RootCauseCorrelator, PromotionEngine, PromotionRecord, AgentOSStore |

---

## Changelog

| Date | Prompt Version | What Changed | Skill Version |
|------|---------------|-------------|---------------|
| 2026-08-06 | v2026.08.06.1 | Initial prompt — findings C1-M3, Task 1 patches | v2.0 |
| 2026-08-06 | v2026.08.06.2 | Added NeuralMind bootstrap, QA model routing | v2.0 |
| 2026-08-06 | v2026.08.06.3 | C1 committed, C2 code fixed + tests in progress | v2.0 |
| 2026-08-06 | v2026.08.06.4 | C1+C2 committed; Task 1 patches committed; 111 tests green | v2.0 |
| 2026-08-06 | v2026.08.06.5 | All 6 findings patched + adversarial QA complete | v2.0 |
| 2026-08-06 | v2026.08.06.6 | **Phased build plan active — Phase 1 ready to start** | v2.0 |

---

*Pattern: SOTA Build Loop v2.0 | Prompt version: v2026.08.06.6 | Last updated: 2026-08-06*
