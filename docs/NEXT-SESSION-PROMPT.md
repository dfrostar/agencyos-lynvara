# Next Session Prompt — AgencyOS QA Remediation

**Date:** 2026-08-06
**Priority:** C3 → H1-H2 → M1-M3 → commit + push
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

## Phase 1: Discover ✅ COMPLETE

- NeuralMind indexed: 991 nodes, 19 communities
- Baseline test suite: 110/110 pass
- Blast radius mapped for all findings
- **C4 confirmed as false positive** (schema_version table already handled correctly in `store.py:259-271`)
- **H3 (Stripe replay) removed** — no `webhooks.py` file exists; finding was false positive

### Test Infrastructure Changes (IMPORTANT)

The test suite was updated to support bearer <REDACTED>:

1. **`tests/test_agent_os_api.py`**:
   - Added `_TestBundle` wrapper class that bundles routes with `session_store`
   - `_post()` and `_get()` auto-authenticate via `_auto_auth()` when body contains `email`
   - Direct `routes[("METHOD", path)]({...})` calls also auto-authenticate via `__getitem__` wrapper
   - Added `session_store` fixture
   - Added `from agent_os.auth import SessionStore` import

2. **`tests/test_feedback.py`**:
   - `_post()`, `_get()`, `_patch()` now accept `headers` parameter (default: `None`)
   - Added `auto_auth=True` parameter — when True, auto-creates session if no headers provided
   - Added `_auth_headers(server_url, email, tenant_id)` helper — creates tenant and returns `{"Authorization": "Bearer <token>"}`
   - `_auth_headers()` calls `_post(..., auto_auth=False)` to avoid infinite recursion; if tenant already exists, creates a session directly via `SessionStore`

3. **`agent_os/api.py`**:
   - All 10 handler functions now accept `headers: dict[str, str] | None = None`
   - `_get_auth(body, headers)` extracts bearer <REDACTED> from headers first
   - **Body-based auth fallback REMOVED** (C1 fix)

4. **`agent_os/server.py`**:
   - `_default_get_auth()` now returns unauthenticated context (C2 fix)
   - `do_GET`, `do_POST`, `do_PATCH`, `do_DELETE` all pass `headers=dict(self.headers)` to handlers

5. **`agent_os/outreach.py`** and **`agent_os/feedback.py`**:
   - Added `_resolve_auth(body, headers)` helper that checks bearer <REDACTED> first
   - All handler functions accept `headers` parameter
   - `get_auth(body)` replaced with `_resolve_auth(body, headers)` everywhere

---

## What Was Already Patched (All Committed ✅)

| Area | Fix | Commit |
|------|-----|--------|
| C1. Body auth bypass | Removed body-based fallback from `_get_auth`. Require bearer <REDACTED> for all endpoints except `create_tenant`. | `b430df1` |
| C2. `_default_get_auth` trusts body tenant_id | Returns unauthenticated context; handlers enforce auth via `_resolve_auth(body, headers)` | `219fe29` |
| C2 test bugs | `_patch` data encoding fixed; `_auth_headers` handles existing tenants | `684b3f1` |
| Signals | Page-Hinkley uses frozen reference mean; signal IDs unique; persistence debounced | `27ebd11` |
| Experiment p-value | Two-sided t-test against H₀: delta=0 using population std | `df0493c` |
| Auto-trigger/promotion | Configurable `higher_is_better`; rollback is no-op (no data loss) | `1fa05b8` |

---

## What Remains To Patch

### CRITICAL

**C3. FK references non-existent `tenants` table — `store.py`**
- `webhook_configs` table has `FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)` but no `tenants` table exists
- Fix: Remove FK reference (tenants are managed by TenantRegistry in JSON files, not DB).
- **Verify:** Fresh DB migrates without FK violation.

### HIGH

**H1. No body size limit — `server.py`**
- `_read_body` reads `Content-Length` bytes with no max → memory exhaustion
- Fix: Add `MAX_BODY_SIZE = 1_048_576` (1MB) check before reading.
- **Verify:** Body >1MB → 413. Body <1MB → 200.

**H2. No chunked encoding handling — `server.py`**
- Fix: Reject `Transfer-Encoding: chunked` with 400 or implement chunked parsing.
- **Verify:** Chunked request → 400 or correctly parsed body.

### MEDIUM

**M1. `require_permission` decorator fragile arg extraction — `governance.py`**
- Relies on positional args `(self, tenant_id, email)` — breaks if signature changes
- Fix: Extract from kwargs or use explicit parameters.

**M2. `get_audit_log` limit parameter ignored — `store.py`**
- Fix: Add `LIMIT ?` to query.

**M3. f-string in `delete_tenant` — `store.py`**
- Cosmetic but bad practice (SQL injection risk if pattern replicated)
- Fix: Use parameterized query.

---

## Constraints

- Full RED-GREEN TDD for ALL CRITICAL findings (test first, watch FAIL, patch, watch PASS)
- Commit separately per fix area (auth, server, store, webhooks)
- Run `pytest tests/ -q` after each commit
- No breaking changes to signal→experiment→promotion loop (Task 1 patches are load-bearing)
- Follow existing code style (stdlib-only, no new dependencies)

---

## Rollback Plan

| Area | Revert Command | Signal of Failure |
|------|----------------|-------------------|
| Auth (C1) | `git revert b430df1` | 500 on any endpoint, tests fail |
| Auth (C2) | `git revert <commit>` | 500 on POST, tests fail |
| Server (H1-H2) | `git revert <commit>` | 500 on POST, tests fail |
| Store (C3, M2-M3) | `git revert <commit>` | Migration error, tests fail |

**If patch breaks tests: revert immediately, document failure, proceed.**

---

## Files Modified (This and Prior Sessions)

- `/home/dtfrost/agencyOS/agent_os/api.py` — C1 fix + headers threading (committed `b430df1`)
- `/home/dtfrost/agencyOS/agent_os/server.py` — C2 fix + headers threading (committed `219fe29`)
- `/home/dtfrost/agencyOS/agent_os/outreach.py` — C2 fix + headers threading (committed `219fe29`)
- `/home/dtfrost/agencyOS/agent_os/feedback.py` — C2 fix + headers threading (committed `219fe29`)
- `/home/dtfrost/agencyOS/agent_os/signals.py` — Page-Hinkley + unique IDs + persistence (committed `27ebd11`)
- `/home/dtfrost/agencyOS/agent_os/store.py` — reference_mean column (committed `27ebd11`)
- `/home/dtfrost/agencyOS/agent_os/experiment.py` — p-value fix (committed `df0493c`)
- `/home/dtfrost/agencyOS/agent_os/auto_trigger.py` — configurable higher_is_better (committed `1fa05b8`)
- `/home/dtfrost/agencyOS/agent_os/promotion.py` — rollback no-op (committed `1fa05b8`)
- `/home/dtfrost/agencyOS/tests/test_feedback.py` — C2 test fixes (committed `684b3f1`)

---

## Test Suite Location

- Tests: `/home/dtfrost/agencyOS/tests/`
- Runner: `pytest tests/ -q` (from repo root)
- Coverage: `pytest --cov=agent_os tests/` (run during Phase 1)

---

## Next (ordered)

| Priority | Task | TDD? | Status |
|----------|------|------|--------|
| **P0** | Patch C3 (FK to non-existent table in store.py) | ✅ test-first | pending |
| **P1** | Patch H1-H2 (body size limit, chunked encoding) | alongside | pending |
| **P1** | Patch M1-M3 (decorator, audit log, f-string) | existing | pending |
| **P1** | Run full test suite after all patches | — | pending |
| **P1** | Security scan (bandit) | — | pending |
| **P2** | Commit per fix area + push to origin/main | — | pending |

---

## Changelog

| Date | Prompt Version | What Changed | Skill Version |
|------|---------------|-------------|---------------|
| 2026-08-06 | v2026.08.06.1 | Initial prompt — findings C1-M3, Task 1 patches, Phase 0-3 structure | v2.0 |
| 2026-08-06 | v2026.08.06.2 | Added NeuralMind bootstrap, QA model routing, mini-changelog | v2.0 |
| 2026-08-06 | v2026.08.06.3 | C1 committed, C2 code fixed + tests in progress, test infra changes documented | v2.0 |
| 2026-08-06 | v2026.08.06.4 | C1+C2 committed (684b3f1, 219fe29, 684b3f1); Task 1 patches committed (27ebd11, df0493c, 1fa05b8); 111 tests green; H3 (Stripe) removed as false positive (no webhooks.py exists) | v2.0 |

---

*Pattern: SOTA Build Loop v2.0 | Prompt version: v2026.08.06.4 | Last updated: 2026-08-06*
