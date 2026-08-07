# QA Report — Phase 1: Server + Core Modules

**Date:** 2026-08-07
**Modules:** `server.py`, `knowledge.py`, `finance.py`, `webhooks.py`, `sources/`
**Test Suite:** 145/145 passing
**QA Method:** Adversarial review + inline patching (no subagent dispatch needed — findings were verified against actual code immediately)

---

## Summary

Phase 1 shipped fast (B-01 → B-02 → B-03 in 3 commits over 2 days). QA caught up in subsequent sessions. All CRITICAL and HIGH findings are patched and committed. The webhooks module (A-01 through A-06) was also built inline during the catch-up.

---

## Findings & Patches

### CRITICAL

| ID | Module | Finding | Status | Commit |
|----|--------|---------|--------|--------|
| C1 | `api.py` → `server.py` | Body-based auth bypass — `_get_auth` accepted `email` from request body as "backward-compat" fallback. Any request with `{"email": "x"}` bypassed bearer-token auth. Handlers never passed `headers` to `_get_auth`, making token-auth path dead code. | ✅ Patched | `b430df1` |
| C2 | `server.py` → `outreach.py`, `feedback.py` | `_default_get_auth` trusted `body["tenant_id"]`. Any caller could read/modify data for any tenant by spoofing `tenant_id` in the request body. | ✅ Patched | `219fe29`, `684b3f1` |
| C3 | `store.py` | FK to non-existent `tenants` table in `webhook_configs` schema. | ✅ Patched (prior session) | `222d756` |
| C4 | `store.py` | Schema version check broke on fresh databases. | ✅ Patched (prior session) | `222d756` |

### HIGH

| ID | Module | Finding | Status | Commit |
|----|--------|---------|--------|--------|
| H1 | `server.py` | No body size limit — `_read_body` read `Content-Length` bytes with no max. Memory exhaustion via large `Content-Length`. | ✅ Patched | `023f58c` |
| H2 | `server.py` | No chunked encoding handling. | ✅ Patched | `023f58c` |
| H3 | `webhooks.py` | Stripe signature verification lacked timestamp validation (replay attack). | ✅ Patched | `219fe29` (5-min window) |

### MEDIUM

| ID | Module | Finding | Status | Commit |
|----|--------|---------|--------|--------|
| M1 | `governance.py` | `require_permission` decorator fragile arg extraction. | ✅ Patched | `023f58c` |
| M2 | `store.py` | `get_audit_log` limit parameter ignored. | ✅ Patched | `023f58c` |
| M3 | `store.py` | f-string in `delete_tenant` SQL (bad practice). | ✅ Patched | `023f58c` |

---

## Phase 1 Module QA — Inline Review Results

### `server.py` (575 lines)

**Reviewed:** Route dispatch, body parsing, auth, webhook ingestion

Findings:
- Path-param extraction uses regex — handles `{id}` correctly, no injection
- Query string parsing for GET uses `parse_qs` — safe
- `_read_body` properly enforces MAX_BODY_SIZE (1 MiB) and rejects chunked encoding
- Webhook paths duplicate the chunked/size checks (defense in depth — acceptable)
- All route handlers receive `headers=dict(self.headers)` — auth is handler's responsibility
- `_default_get_auth` returns unauthenticated context — handlers must check `auth.is_authenticated`
- `_find_handler` iterates routes in dict insertion order — search route registered before `{id}` (correct)

**Verdict:** Clean after C1/C2/H1/H2 patches. No remaining CRITICAL/HIGH issues.

### `knowledge.py` (373 lines)

**Reviewed:** CRUD, search, auth, tenant scoping

Findings:
- `_resolve_tenant_id` properly checks `auth.is_authenticated` before returning `tenant_id`
- All queries use parameterized SQL (`?` placeholders) — no injection
- Search uses `LIKE ?` with bound parameter — safe
- `limit` is capped at 200, `query` at 200 chars — input limits present
- `title` capped at 500 chars, `content` at 50,000 chars — reasonable
- Route registration: search route (`/search`) registered before `{id}` — correct ordering
- No body-based auth fallback — uses `_resolve_auth` with bearer <REDACTED>

**Verdict:** Clean. No CRITICAL/HIGH issues. Tenant scoping is enforced at every endpoint.

### `finance.py` (553 lines)

**Reviewed:** Revenue, costs, invoices, summary, monthly reports

Findings:
- Auth pattern identical to `knowledge.py` — bearer-token only
- All SQL uses parameterized queries
- `amount` is validated as `float()` with `TypeError/ValueError` handling
- `currency` is whitelist-checked against `["USD", "EUR", "GBP"]`
- Invoice lifecycle: `draft → sent → paid/overdue → cancelled` — enforced via whitelist
- `get_summary` uses `COALESCE(SUM(amount), 0)` — handles NULL gracefully
- `marginPercent` calculation divides by `total_revenue` — zero-check present
- `outstandingInvoices` only sums `sent` + `overdue` status — excludes `paid`

**Verdict:** Clean. No CRITICAL/HIGH issues. Financial calculations are safe.

### `webhooks.py` (280 lines)

**Reviewed:** Ingestion, signature verification, background worker, normalizers

Findings:
- GitHub HMAC uses `hmac.compare_digest` — constant-time comparison
- Stripe verification includes 5-minute timestamp window (replay protection)
- Tenant resolution separated from signature verification — correct order (resolve → verify)
- Idempotency: `webhook_event_exists` check before insert
- Background worker uses asyncio — processes events in poll loop
- Signal IDs use `uuid.uuid4().hex[:12]` — unique enough
- Normalizers in `sources/` — provider-specific, no shared state

**Verdict:** Clean. No CRITICAL/HIGH issues.

---

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| `test_server.py` | 38 | ✅ All pass |
| `test_knowledge.py` | 28 | ✅ All pass |
| `test_finance.py` | 32 | ✅ All pass |
| `test_agent_os_api.py` | 18 | ✅ All pass |
| `test_feedback.py` | 12 | ✅ All pass |
| `test_agent_os.py` | 10 | ✅ All pass |
| `test_agent_os_v2.py` | 7 | ✅ All pass |
| **Total** | **145** | ✅ **145/145** |

---

## Phase 1 Completion Checklist

- [x] Server running on port 9000 with `/health` endpoint
- [x] Knowledge base CRUD + search (tenant-scoped)
- [x] Financial tracking (revenue, costs, invoices, summary)
- [x] Webhook ingestion layer (GitHub, Stripe, Custom)
- [x] Event normalizers for all 3 providers
- [x] Auth hardening (body-based bypass removed, tenant_id trust removed)
- [x] Server hardening (body size limit, chunked encoding rejection)
- [x] All 145 tests passing
- [x] QA_REPORT.md created

---

*QA complete. Phase 1 ready for Phase 2 (Automation Pipeline).*
