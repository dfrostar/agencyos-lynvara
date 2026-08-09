# Agent OS — Governance

**Date:** 2026-08-08
**Status:** Active
**Scope:** `dfrostar/agencyOS` (private)

---

## 1. Role of this repo

Agent OS is the private, multi-tenant product-operations layer for NeuralMind:
the signal → insight → proposal → experiment → promote/rollback loop, behind a
tenant-scoped daemon. It is internal operator tooling — never distributed to
end users. Governance here is therefore **operational** (who may change what,
and what may act autonomously), not community governance: the public project's
stewardship lives in `dfrostar/neuralmind` `GOVERNANCE.md`, and this document
deliberately does not duplicate it.

---

## 2. Roles & decision rights

- **Maintainer/operator:** Darren Frost (@dfrostar). Sole approver for schema
  migrations, detector/threshold changes, cross-tenant operations, tenant
  deletion, and anything that crosses to the public repo or reaches a
  customer-visible surface.
- **In-product RBAC** governs tenant-scoped API actions (role assignment via
  the RBAC endpoint). Repo-level decisions are never delegated to in-product
  roles.
- **AI agents** working in this repo implement and verify; they never approve
  their own promotions, merges, or sign-offs.

---

## 3. Autonomy guardrails — the promote/rollback loop

| May act autonomously | Requires the maintainer |
|---|---|
| Signal → proposal → experiment auto-runs, scoped to one tenant | Changing `MIN_SIGNALS` or detector thresholds (ADR required) |
| Auto-promotion of tuner incumbents where the change is reversible and the rollback path is exercised by the ExperimentRunner | Schema migrations (incl. SQLite → PostgreSQL) |
| Automatic ROLLED_BACK on a failed verdict | Cross-tenant operations of any kind |
| | Tenant deletion (see §4) |
| | Any change that reaches public NeuralMind users |

- **Kill switch:** the loop runs only inside the daemon. Stopping the daemon
  halts all autonomous action; no component may schedule work outside it.
- **No unrecorded promotions:** every PROMOTED / ROLLED_BACK verdict is
  persisted with its experiment. A promotion without a recorded experiment is
  a defect, not a shortcut.

---

## 4. Tenant & RBAC governance

- **Tenant DELETE is destructive.** It requires explicit confirmation, an
  audit entry, and — for any tenant representing a real business — a data
  export before deletion.
- Role assignments are logged. Default to least privilege.
- **Tenant isolation is a hard invariant.** A cross-tenant read or write is a
  CRITICAL defect regardless of impact.

---

## 5. Change control

- **ADRs** (Context → Decision → Rationale → Consequences, numbered) for
  irreversible or cross-tenant changes — the same decision discipline as
  neuralmind-autopilot's docs, without the 6-doc wave gate (see §10 for why).
- CI (lint + tests) green before merge to `master`; never merge on red.

---

## 6. Boundary with public NeuralMind

- Extraction is **one-way**: the public repo retains zero agent-os code, and
  that stays true.
- Nothing moves from this repo to `dfrostar/neuralmind` without an explicit
  maintainer decision and a licence check — the public MIT core accepts no
  commercial or private code (see the public repo's `LICENSING.md`).
- Any price, entity name, or commercial term this platform emits must match
  the public repo's `commercial-terms.json` (the CI-gated source of truth).

---

## 7. Data & secrets

- No secrets in git — configuration via environment (`NEURALMIND_AGENTOS_DIR`,
  database credentials). SQLite state files are never committed.
- The PostgreSQL migration path carries the same obligations: per-tenant
  isolation and audited destructive operations.

---

## 8. AI tooling in this repo

- This repo **is** indexable by NeuralMind/graphify (unlike
  `neuralmind-autopilot`, which is never indexed — that rule is recorded in
  its own GOVERNANCE.md).
- Cross-tool memory queries are scoped with an `[agencyOS]` prefix — memU,
  Hermes memory, and session-search do not isolate by project.

---

## 9. Continuity

Access is the maintainer's GitHub account plus local clones. Loss of this repo
does not affect public NeuralMind users in any way; it suspends the
self-improving ops loop until restored from a clone.

---

## 10. Borrowed practices — and why each is relevant here

Leading practices are borrowed only where they fit this repo's role:

- **NIST AI RMF (GOVERN / MANAGE):** an autonomous promote/rollback loop is
  exactly the "AI system acting with delegated authority" case the framework
  addresses — and NeuralMind's public materials already use "NIST AI RMF
  aligned" framing, so the internal loop must clear the same bar (§3).
- **ADRs (Nygard):** borrowed from neuralmind-autopilot's decision discipline
  because platform changes here — schemas, thresholds — are the irreversible
  kind ADRs exist for (§5).
- **Stewardship & continuity (public NeuralMind `GOVERNANCE.md`):** translated
  to private form as decision rights + continuity only (§2, §9).
- **Deliberately not borrowed:** autopilot's 6-doc wave gate and claim-tiering
  (they govern outward marketing surfaces this repo doesn't have), and the
  public doc's community/forkability sections (there is no community here).

---

## Change log

| Date | Version | Change |
|------|---------|--------|
| 2026-08-08 | v1.0.0 | Initial governance doc. |
