# NeuralMind Agent OS

Multi-tenant, self-improving product operations layer for NeuralMind.
**Internal operator tooling — NOT distributed to end users.**

## What this is

Agent OS implements the signal → insight → proposal → experiment → promote/rollback loop that makes NeuralMind self-improving. It detects metric anomalies, correlates them with code/config changes, auto-creates proposals, runs experiments, and updates tuner incumbents — all behind a tenant-scoped daemon with SQLite persistence and a PostgreSQL migration path for multi-business agency operations.

**This repository contains the operator tooling extracted from the public NeuralMind codebase (`dfrostar/neuralmind`).** It is the private counterpart that houses the self-improving loop, the daemon agent-os routes, the CLI subcommands, and the agency operations architecture — everything that makes NeuralMind better, without being part of the public PyPI package.

## Architecture

```
SignalDetector (Page-Hinkley anomaly detection)
    ↓ signal fires
RootCauseCorrelator (git/config correlation)
    ↓ insight generated
AutoTriggerLoop (proposal auto-creation + experiment auto-run)
    ↓ signal_count ≥ MIN_SIGNALS
PromotionEngine (ExperimentRunner + TunerIncumbent)
    ↓ verdict = PROMOTED / ROLLED_BACK
TunerIncumbent (updates best-known value per metric)
```

## Why private

- No end-user needs to see the self-improving plumbing
- Keeps the public NeuralMind package clean and focused
- Separates operator concerns (tenants, signals, promotions) from client-facing features (code search, synapse queries)
- Prevents competitors from copying the operations model without doing the work

## Built from public NeuralMind

The code here was extracted from the public repo at `dfrostar/neuralmind` (directory `neuralmind/agent_os/`). The public repo retains zero agent-os code after extraction — clean separation.

## Development

### Editable install
```bash
pip install -e .
```

### Tests
```bash
pytest tests/ -q
```

### Daemon (developer)
```bash
NEURALMIND_AGENTOS_DIR=/tmp/agentos neuralmind serve
```

### API endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | /api/agent-os/tenants | Create tenant |
| GET | /api/agent-os/tenants | List tenants |
| DELETE | /api/agent-os/tenants/{id} | Delete tenant |
| POST | /api/agent-os/tenants/{id}/rbac | Assign role |
| GET | /api/agent-os/signals | List tracked metrics |
| POST | /api/agent-os/signals | Push metric value |
| POST | /api/agent-os/experiments | Run A/B experiment |
| GET | /api/agent-os/experiments | List experiment history |
| POST | /api/agent-os/proposals | Create proposal |
| GET | /api/agent-os/proposals | List proposals |
| POST | /api/agent-os/proposals/{id}/run | Run proposal experiment |

## Data model

All state is persisted via SQLite (AgentOSStore) with WAL mode. Tenants, signals, proposals, experiments, promotions, incumbents, and adversarials each own a table with per-tenant indexes.

## Known adversarial findings (2026-08-03)

As of extraction, 5 of 6 loop breakpoints are fixed and end-to-end verified:

| # | Severity | Status | Summary |
|---|----------|--------|---------|
| S1 | CRITICAL | ✅ Fixed | update_signal now passes project_path → correlator fires | 
| S2 | CRITICAL | ✅ Fixed | AutoTriggerLoop daemon wiring includes store + tenant |
| S3 | CRITICAL | ✅ Fixed | TunerIncumbent ship callable rewired on | | S4 | CRITICAL | ✅ Fixed | increment_signal_count deadlock resolved (742bd9) |
| S5 | HIGH | ⚠️ Open | Page-Hinkley constant-baseline non-firing |
| S6 | MEDIUM | ✅ Fixed | higher_is_better=True in auto-experiment trigger |
| S7 | HIGH | ✅ Fixed | get_or_create_proposal atomic across lock |

## Deployment target

Runs as a sidecar to the NeuralMind daemon. Development: `neuralmind serve`. Production: `supervisord` on the same tin (Ubuntu LLM or Agency OS rig). Evolution roadmap: PostgreSQL + pgvector for multi-business agency operations.

## Hands-on operations

| Task | Command |
|------|---------|
| Health snapshot | `neuralmind agent-os health-snapshot` |
| Push a signal | `neuralmind agent-os signals push --metric latency_ms --value 142 --tenant-id prod` |
| Create a proposal | `neuralmind agent-os proposals create --tenant-id prod --title "..." --baseline-tag v1 --candidate-tag v2 --metric-name latency_ms --baseline-value 100 --candidate-value 85` |
| Run experiment | `neuralmind agent-os experiments run --tenant-id prod --proposal-id prop_xxxxx` |
| List tenants | `neuralmind agent-os tenants list` |
| Schema migration | `neuralmind agent-os migrate` |

## Related docs (public repo)

- `dfrostar/neuralmind/docs/wiki/CLI-Reference.md` — the neuralmind CLI reference
- `dfrostar/neuralmind/docs/AGENT-OS-V2.0.2-ADVERSARIAL-REVIEW-RESULTS.md` — full adversarial review
- `dfrostar/neuralmind-agentos/` — private repo