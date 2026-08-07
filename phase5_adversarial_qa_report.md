# AgencyOS Phase 5 — Adversarial QA Review Report

**Scope:** New files introduced in Phase 5 (L7-8)
**Date:** 2026-08-07
**Reviewer:** Hermes Agent (automated adversarial QA)

---

## Executive Summary

Phase 5 introduces a SQLite-backed message bus (`MessageBus`), four agent roles (`DetectorRole`, `CorrelatorRole`, `EvolverRole`, `CoordinatorRole`), two departments (`OutreachDepartment`, `EngagementDepartment`), and the wiring in `server.py`/`store.py`.

**Overall assessment:** One CRITICAL vulnerability (tenant isolation bypass in the message bus), one HIGH vulnerability (CPU exhaustion via unvalidated config), and several MEDIUM/LOW issues.

---

## Findings

### 1. Tenant Isolation Bypass in Message Bus

- **File:** `agent_os/store.py`
- **Lines:** 303–313 (schema), 1423–1440 (consume query)
- **Severity:** CRITICAL
- **Description:**
  The `agent_messages` table schema lacks a `tenant_id` column:
  ```sql
  CREATE TABLE IF NOT EXISTS agent_messages (
      message_id TEXT PRIMARY KEY,
      topic TEXT NOT NULL,
      payload TEXT NOT NULL,
      from_role TEXT NOT NULL,
      to_role TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      consumed_at TEXT,
      consume_count INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'pending'
  );
  ```
  The `consume_bus_messages()` query filters only by `topic`, `status`, and `to_role` — never by tenant:
  ```sql
  SELECT * FROM agent_messages
  WHERE topic = ? AND status = 'pending'
    AND (to_role = ? OR to_role IS NULL)
  ```
  Because all tenants use the same role names (`detector`, `correlator`, etc.), a `DetectorRole` instance for Tenant A will receive all pending `metric_value` messages intended for Tenant B's detector. This is a complete cross-tenant data exposure.
- **Patch:**
  1. Add `tenant_id TEXT NOT NULL` to the `agent_messages` schema.
  2. Populate `tenant_id` in `insert_bus_message()` from the `Message` object (add `tenant_id` field to `Message` class).
  3. Filter by tenant in ALL bus queries: `consume_bus_messages`, `get_pending_bus_messages`, `acknowledge_bus_message` (for ownership verification), `cleanup_expired_bus_messages`.
  4. Add a foreign key or CHECK constraint to enforce tenant existence.

---

### 2. CPU Exhaustion via `poll_interval=0`

- **File:** `agent_os/roles/base.py`
- **Line:** 83
- **Severity:** HIGH
- **Description:**
  `_run_loop()` reads `poll_interval` from config without validation:
  ```python
  time.sleep(self._config.get("poll_interval", 1.0))
  ```
  If `poll_interval` is `0`, `time.sleep(0)` yields but the loop spins at maximum speed, consuming 100% of a CPU core. A negative value causes `ValueError` (caught, but loop retries immediately). If an attacker can influence role configuration (e.g., via a config update endpoint, environment variable injection, or malicious plugin), they can cause CPU exhaustion across all running roles/departments.
- **Patch:**
  ```python
  poll_interval = self._config.get("poll_interval", 1.0)
  try:
      poll_interval = float(poll_interval)
  except (TypeError, ValueError):
      poll_interval = 1.0
  time.sleep(max(0.1, min(poll_interval, 300.0)))  # clamp [0.1, 300]
  ```

---

### 3. Dead Letter Queue Poisoning

- **File:** `agent_os/store.py`
- **Lines:** 1443–1462
- **Severity:** MEDIUM
- **Description:**
  Messages are marked `dead` after 3 consumption attempts without acknowledgment. An attacker who can publish messages to the bus (e.g., via a webhook ingestion path that publishes `metric_value` messages, or by directly calling `MessageBus.publish()`) can send malformed payloads that cause roles to crash during processing. Each crashed consumption increments `consume_count`, and after 3 attempts the message is moved to `dead` status. Dead messages accumulate for 7 days (until `cleanup_expired_bus_messages` runs). There is no rate limiting on `publish()`, no max-DLQ-size guard, and no alerting on DLQ growth.
- **Patch:**
  1. Add rate limiting to `MessageBus.publish()` (e.g., token bucket per role/tenant).
  2. Add a `MAX_DEAD_MESSAGES` constant and reject new publishes when the DLQ is full.
  3. Add a monitoring endpoint that alerts when DLQ size exceeds a threshold.
  4. Use `MAX_DELIVERY_ATTEMPTS` constant (defined in `bus.py:13`) instead of hardcoded `3` in `acknowledge_bus_message`.

---

### 4. `can_auto_execute` Uses Class Attributes; Config Is Silently Ignored

- **File:** `agent_os/departments/base.py`
- **Lines:** 78–83 (method), `outreach.py:31-32`, `engagements.py:31-32`
- **Severity:** LOW (logic bug, not a security bypass)
- **Description:**
  `can_auto_execute()` compares against `self.AUTO_EXECUTE_MAX_IMPROVEMENT` and `self.AUTO_EXECUTE_MAX_COST` (class attributes). But `OutreachDepartment.__init__` and `EngagementDepartment.__init__` set instance attributes `self._auto_execute_max_improvement` and `self._auto_execute_max_cost` from config. These instance attributes are never read by `can_auto_execute()`. Config values are silently ignored, and the hardcoded class defaults (10%, $50) are always enforced.
  - **Security impact:** Positive — config cannot bypass safety bounds.
  - **Functional impact:** Admins cannot tune safety bounds via config.
- **Patch:**
  ```python
  # In base.py, change can_auto_execute to use instance attributes with class fallback:
  def can_auto_execute(self, improvement: float, cost: float) -> bool:
      max_imp = getattr(self, "_auto_execute_max_improvement", self.AUTO_EXECUTE_MAX_IMPROVEMENT)
      max_cost = getattr(self, "_auto_execute_max_cost", self.AUTO_EXECUTE_MAX_COST)
      return improvement < max_imp and cost < max_cost
  ```
  Also add validation in `__init__` to clamp config values to sane ranges (e.g., `max_improvement <= 0.50`, `max_cost <= 500`).

---

### 5. `get_pending_bus_messages` Has No Result Limit

- **File:** `agent_os/store.py`
- **Lines:** 1465–1491
- **Severity:** LOW
- **Description:**
  `get_pending_bus_messages()` returns ALL pending messages with no limit. The coordinator calls this on every poll cycle (`coordinator.py:61`). Under high message volume or after a backlog, this could return millions of rows, causing memory pressure and GC thrash.
- **Patch:**
  ```python
  def get_pending_bus_messages(self, topic: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
      ...
      # append LIMIT ? to both query branches
  ```

---

### 6. `publish()` Holds Lock During Subscriber Callbacks

- **File:** `agent_os/bus.py`
- **Lines:** 85–96
- **Severity:** LOW (latent — no subscribers currently registered in Phase 5)
- **Description:**
  `MessageBus.publish()` holds `self._lock` while iterating and invoking synchronous subscriber callbacks. If a subscriber blocks or is slow, the entire bus is frozen — no other role can publish or consume. Currently, no code registers subscribers (roles use pull-based `consume()`), so this is not exploitable today. But it is a latent DoS vector for future code.
- **Patch:**
  ```python
  def publish(self, message: Message) -> None:
      with self._lock:
          self._store.insert_bus_message(message.to_dict())
          topic_subs = list(self._subscribers.get(message.topic, []))
          broadcast_subs = list(self._subscribers.get("*", []))
      # Notify outside the lock
      for cb in topic_subs + broadcast_subs:
          try:
              cb(message)
          except Exception:
              log.exception(...)
  ```

---

## Attack Vectors Ruled NOT Exploitable

### Message Bus Poisoning (publish as another role)
**Evidence:** `AgentRole.publish()` (base.py:89–98) hardcodes `from_role=self.ROLE_NAME`, which is a class constant (e.g., `"detector"`). No code path accepts user input for `from_role`. The `Message` constructor could be called directly with a spoofed `from_role`, but no public API exposes this.

### SQL Injection via Payload
**Evidence:** All bus SQL uses parameterized queries (`?` placeholders). The `payload` column is stored as opaque TEXT and never interpolated into SQL. `_parse_payload()` (bus.py:65–70) uses `json.loads()`, which is safe (no code execution).

### Role Impersonation
**Evidence:** Same as message bus poisoning. `from_role` is derived from `ROLE_NAME` class constant. No API accepts arbitrary `from_role`.

### Department Auto-Execute Without Approval
**Evidence:** Safety bounds are hardcoded class attributes (`AUTO_EXECUTE_MAX_IMPROVEMENT = 0.10`, `AUTO_EXECUTE_MAX_COST = 50.0`). Config values are set but never used (see Finding #4). Bounds are properly checked before auto-execute.

### Coordinator Single Point of Failure
**Evidence:** Roles are independent daemon threads. The coordinator's `_route_messages()` is a no-op (comment says "Role will pick it up via consume() in its own _poll()"). If the coordinator crashes, roles continue consuming and publishing. Only health monitoring is lost.

### Store Connection Exhaustion
**Evidence:** The store uses a single `sqlite3.Connection` instance (`self._conn`) protected by a single lock. All operations are serialized. Bus messages do not create new connections.

### Feature Flag Bypass
**Evidence:** `enable_roles` and `enable_departments` are parameters to `create_app()`, which is called once at server startup (`main()`). There is no HTTP endpoint to modify these flags at runtime. Default is `False`.

---

## Summary Table

| # | Finding | File | Severity | Exploitable? |
|---|---------|------|----------|--------------|
| 1 | Tenant isolation bypass in agent_messages | store.py | CRITICAL | YES |
| 2 | CPU exhaustion via poll_interval=0 | roles/base.py | HIGH | YES |
| 3 | DLQ poisoning via malformed messages | store.py | MEDIUM | YES |
| 4 | can_auto_execute ignores config (bug) | departments/base.py | LOW | N/A (functional) |
| 5 | get_pending_bus_messages unbounded | store.py | LOW | YES (resource exhaustion) |
| 6 | publish() holds lock during callbacks | bus.py | LOW | Latent |

---

## Recommended Priority

1. **Immediate:** Fix #1 (tenant isolation) — this is a data breach vector.
2. **This sprint:** Fix #2 (poll_interval validation) and #3 (DLQ rate limiting).
3. **Next sprint:** Address #4–#6 as defensive depth.
