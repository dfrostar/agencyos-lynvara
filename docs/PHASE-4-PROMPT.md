# Phase 4: Intelligence Layer — Implementation Prompt

**Estimated:** 12 hours | **Level:** 9 (Self-Improving) → 10 (Architecture Design)

---

## Context

AgencyOS has a working signal→proposal→experiment→promotion pipeline (`auto_trigger.py` + `promotion.py` + `tuner_incumbents`). However, this pipeline is **reactive** — it only acts when anomalies fire. Phase 4 makes the system **actually learn**: modifying its own detection thresholds, exploring under-tested areas proactively, and reporting on week-over-week improvement deltas.

**Current gap:** The AutoTriggerLoop is coded but never started by the server. Tuner incumbents track values but don't learn from patterns. There's no feedback from promotion outcomes back into detection parameters.

---

## B-09: Self-Improving Engine (Full) — 6h

### Problem
The existing system reacts to anomalies but doesn't learn from outcomes. A metric that fires constantly should become less sensitive. A metric that never fires should be explored. Successful promotions should lower the bar for similar future proposals.

### Deliverables

#### 1. Outcome Tracking (store.py)
Add a new table `improvement_outcomes`:
```sql
CREATE TABLE IF NOT EXISTS improvement_outcomes (
    outcome_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK(verdict IN ('promoted', 'rolled_back', 'rejected')),
    delta REAL NOT NULL,
    baseline_value REAL NOT NULL,
    candidate_value REAL NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```
Add store methods: `record_outcome()`, `get_outcomes(tenant_id, metric_name, limit)`, `get_outcome_stats(tenant_id)`.

#### 2. Behavior Modification Engine (new: behavior_learner.py)
A `BehaviorLearner` class that adjusts system parameters based on outcomes:

- **Lambda threshold tuning**: If a metric has >80% rollback rate, increase its Page-Hinkley lambda_threshold (make it less sensitive). If a metric has >80% promotion rate and few signals, decrease lambda (make it more sensitive).
- **Cooldown adjustment**: If signals fire in bursts (>5 in 60s), increase cooldown. If signals are sparse (<1/day), decrease cooldown.
- **Auto-promote threshold**: Track promotion success rate per metric category. If success rate >75%, lower `MIN_SIGNALS_BEFORE_AUTO_PROMOTE` for that category. If <25%, raise it.

The learner runs after every promotion/rollback verdict and persists adjusted parameters to `signal_states` table.

#### 3. Proactive Experimentation (new: proactive_explorer.py)
A `ProactiveExplorer` class that identifies unexplored areas:

- **Stale incumbent detection**: Find tuner incumbents with no experiments in 7+ days. Propose exploratory experiments.
- **Metric coverage analysis**: Compare raw_signals metrics against experiments metrics. Identify metrics that are tracked but never experimented on.
- **Adversarial probing**: Use `generate_adversarial_query()` from the existing adversarial module to find edge cases in current tuner values, then auto-propose experiments to validate.

The explorer runs on a schedule (daily via cron or background thread).

#### 4. HTTP Integration (server.py + new endpoints)
Wire the full engine into server startup:

- Start `AutoTriggerLoop` + `BehaviorLearner` + `ProactiveExplorer` as background threads on server boot (similar to webhook worker B-05).
- New endpoints:
  - `GET /api/agent-os/engine/status` — current engine state (running/paused, last run, proposals pending)
  - `POST /api/agent-os/engine/trigger` — manually trigger a self-improvement cycle
  - `GET /api/agent-os/engine/outcomes` — recent outcomes with filtering
  - `GET /api/agent-os/engine/parameters` — current per-metric thresholds (shows what the system has learned)

#### 5. Outcome Recording Hook (promotion.py)
Add a callback to `PromotionEngine.process_result()` that calls `store.record_outcome()` after every verdict. This is the feedback loop that powers the BehaviorLearner.

---

## B-10: Weekly Self-Improvement Report — 2h

### Problem
There's no visibility into whether the self-improvement engine is actually improving anything. The weekly business review (B-08) covers revenue/pipeline but not system learning.

### Deliverables

#### New endpoint: `GET /api/agent-os/review/self-improvement`
Returns a week-over-week delta report:

```json
{
  "period": "weekly",
  "generated_at": "2026-08-07T17:00:00Z",
  "summary": "This week the system ran 3 experiments, promoted 2 (+133% vs last week)...",
  "experiments": {
    "run_this_week": 3,
    "run_last_week": 1,
    "delta_pct": 200.0,
    "promotion_rate": 0.67,
    "avg_delta": 0.15
  },
  "tuner_changes": [
    {
      "metric_name": "outreach.email.follow_up_days",
      "old_value": 3.0,
      "new_value": 2.0,
      "verdict": "promoted",
      "delta": -0.33
    }
  ],
  "threshold_adjustments": [
    {
      "metric_name": "github.ci.status",
      "parameter": "lambda_threshold",
      "old_value": 4.0,
      "new_value": 5.0,
      "reason": "rollback_rate_85_percent"
    }
  ],
  "proactive_experiments": {
    "proposed": 2,
    "run": 1,
    "promoted": 0
  },
  "learning_summary": "CI status metric becoming less sensitive due to noisy signals. Follow-up timing optimized via promotion."
}
```

**Implementation note:** Reuse `store.get_outcomes()` and `store.get_outcome_stats()` from B-09. Compare current week vs previous week using `datetime('now', '-7 days')` filters.

---

## B-11: Level 10 Architecture Design — 4h

### Problem
The PRD correctly scopes out Level 10 ("Out of Scope" / "Correctly scoped out"). But there's no document explaining *why* or what the path looks like. This is needed for: (a) internal planning, (b) investor/team communication, (c) safety boundary definition.

### Deliverables

#### New document: `docs/ARCHITECTURE-L10.md`

Sections:

1. **What Level 10 Means** — honest definition: "An operations layer that can autonomously enter new markets, hire/fire subsystems, and restructure itself without human approval."
2. **Why It's Deferred** — concrete reasons:
   - Current system has no market-entry capability (it optimizes existing operations, doesn't discover new ones)
   - No financial authority (can't sign contracts, open bank accounts, or incur liabilities)
   - Safety: autonomous self-modification beyond parameter tuning is unbounded risk
   - No legal entity wrapper (AgencyOS is software, not a business)
3. **Prerequisite Capabilities** — what must exist before L10 is feasible:
   - L7 (Specialized Roles): Independent agent teams with bounded authority
   - L8 (Orchestrated Departments): Cross-functional coordination
   - L9 proven on real data: 6+ months of self-improvement outcomes
   - Financial integration: BTCPay pipeline, contract execution
   - Legal wrapper: LLC or similar with defined authority bounds
4. **The Path** — how each level builds on the previous:
   ```
   L9 (current) → Parameter tuning, threshold learning
   L7 (next)    → Role separation, bounded autonomy per role
   L8 (after)   → Department orchestration, cross-functional goals
   L10 (future) → Market discovery, self-restructuring
   ```
5. **Safety Boundaries** — what must NEVER be autonomous:
   - Spending money beyond approved budgets
   - Entering legal commitments
   - Modifying its own safety constraints
   - Hiring/firing humans
6. **Honest Assessment** — brutal-honest viability analysis per the PRD tone

#### Update `docs/ARCHITECTURE.md`
Add section reference to L10 doc. Update the "Honest Capability Map" to include the L10 path.

---

## Existing Code to Reuse

| Module | What to Reuse | What to Extend |
|--------|---------------|----------------|
| `auto_trigger.py` | AutoTriggerLoop class, signal→proposal→experiment pipeline | Wire to server, add outcome callback |
| `promotion.py` | PromotionEngine, TunerIncumbent, process_result() | Add outcome recording hook |
| `correlator.py` | RootCauseCorrelator, Insight generation | Use for proactive exploration hypotheses |
| `adversarial.py` | generate_adversarial_query() | Use for edge-case probing |
| `store.py` | All CRUD methods, get_or_create_properiment() | Add outcomes table + methods |
| `server.py` | Route registration, background thread pattern (B-05) | Start engine threads on boot |
| `weekly_review.py` | Aggregation pattern, WoW delta calculation | Mirror for self-improvement report |

## Testing Requirements

- **B-09**: Test BehaviorLearner adjusts thresholds correctly based on mock outcomes. Test ProactiveExplorer identifies stale incumbents. Test outcome recording fires on promotion/rollback. Test engine status endpoint.
- **B-10**: Test WoW delta calculation with data from two different weeks. Test condensed summary format.
- **B-11**: Documentation only — no code tests. Must be reviewed for accuracy against actual codebase.

## Acceptance Criteria

- [ ] Server starts AutoTriggerLoop + BehaviorLearner + ProactiveExplorer on boot
- [ ] Outcomes are recorded automatically after every experiment verdict
- [ ] Thresholds adjust based on rollback/promotion patterns (verifiable via /engine/parameters)
- [ ] Proactive exploration identifies stale incumbents and proposes experiments
- [ ] Weekly self-improvement report shows WoW deltas
- [ ] ARCHITECTURE-L10.md is complete and honest
- [ ] All existing 178 tests still pass + new tests for B-09/B-10

## Implementation Order

1. **Store layer** (outcomes table + methods) — foundation for everything
2. **Outcome recording hook** in promotion.py — closes the feedback loop
3. **BehaviorLearner** — consumes outcomes, adjusts parameters
4. **ProactiveExplorer** — identifies gaps, proposes experiments
5. **Server wiring** — background threads + HTTP endpoints
6. **Weekly self-improvement report** — uses outcomes data
7. **ARCHITECTURE-L10.md** — document the path
8. **Full test suite** — verify nothing regressed
