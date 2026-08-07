# AgencyOS — Level 10 Architecture Design

**Version:** 1.0.0  
**Date:** 2026-08-08  
**Owner:** Darren Frost (Cheval-Volant, LLC)  
**Repo:** `/home/dtfrost/agencyOS/`

---

## 1. What Level 10 Means

Level 10 is an **autonomous business operations system** — software that can:

- **Enter new markets** autonomously: identify opportunities, configure outreach pipelines, adjust pricing, and begin customer acquisition without human direction
- **Hire/fire subsystems**: activate new monitoring roles, decommission underperforming ones, rebalance resource allocation across "departments"
- **Restructure itself**: reorganize its own module hierarchy, communication patterns, and data flows in response to changing business conditions
- **Negotiate and execute contracts** within bounded authority: engage vendors, renew service agreements, manage SLAs
- **Manage its own compliance posture**: maintain certifications, generate audit evidence, respond to regulatory changes proactively

In short: **AgencyOS becomes the business, not just a tool for the business.**

---

## 2. Why It's Deferred

Level 10 is **correctly scoped out of the current roadmap** for concrete reasons:

### 2.1 No Market-Entry Capability

Current AgencyOS **optimizes existing operations** — it detects anomalies in metrics you already track, proposes experiments on parameters you already have, and promotes changes within bounds you already set. It does not:

- Discover new market segments
- Generate new service offerings
- Identify or validate new customer personas
- Build new outreach channels from scratch

The system is fundamentally **reactive to the operational context humans provide**. Market entry is a human strategic decision.

### 2.2 No Financial Authority

AgencyOS has no ability to:

- Sign contracts or legally binding agreements
- Open bank accounts or manage payment instruments
- Incur liabilities or obligations on behalf of the business
- Execute financial transactions (even crypto) without human authorization

Current integration: **read-only financial tracking** (revenue/costs/invoices). The BTCPay pipeline is a separate system; AgencyOS ingests its webhook events but cannot initiate payments.

### 2.3 No Legal Entity

AgencyOS is **software, not a business**. It cannot:

- Be a party to contracts
- Hold intellectual property
- Be sued or held liable
- Obtain business licenses or insurance

Without an LLC or similar legal wrapper, autonomous business actions have no legal standing.

### 2.4 Safety: Unbounded Self-Modification

Level 10 implies the system can **modify its own constraints** — the safety boundaries themselves. Current L9 self-modification is bounded:

- **Parameter tuning only**: lambda thresholds, cooldown periods, auto-promote signal counts
- **Bounded by immutable constraints**: safety limits hardcoded, not learnable
- **No structural changes**: the system cannot rewrite its own module graph

Level 10 would require the system to:
- Modify its own safety constraints (unbounded risk)
- Rewrite its own module boundaries (architectural instability)
- Generate new code and deploy it (supply chain risk)

These are not bugs to fix — they're **categories of risk that require human governance**.

### 2.5 No Human Resources Capability

AgencyOS cannot:
- Hire or fire humans
- Negotiate employment contracts
- Manage payroll or benefits
- Resolve interpersonal conflicts

"Hiring subsystems" (L7-8) is metaphorical — it means activating new automated roles, not employing people.

---

## 3. Prerequisite Capabilities

Before L10 is feasible, these capabilities must exist and be proven:

### 3.1 L7 (Specialized Roles) — Independent Agent Teams

- **Message bus**: async communication between roles with topic-based routing
- **Role base class**: bounded autonomy per role (each role has defined permissions and scope)
- **Detector role**: autonomous signal detection with bounded authority
- **Correlator role**: autonomous root-cause analysis with bounded authority
- **Coordinator role**: arbitrates between conflicting role recommendations
- **Evolver role**: proposes structural modifications (bounded by governance)

**Current gap**: Single monolithic engine. No inter-role communication. No role-level permission boundaries.

### 3.2 L8 (Orchestrated Departments) — Cross-Functional Goals

- **Outreach department**: manages full lead-to-customer lifecycle autonomously
- **Engagement department**: manages full engagement lifecycle autonomously
- **Cross-department goals**: outreach feeds pipeline to engagement; engagement feeds feedback to outreach
- **Department-level KPIs**: measured and reported independently

**Current gap**: Extraction planned but not autonomous. Outreach/engagement modules are CRUD, not autonomous loops.

### 3.3 L9 Proven on Real Data — 6+ Months of Outcomes

- Self-improvement loop running continuously on production data
- **Measurable outcomes**: promotion rate > 50%, rollback rate < 20%, lambda adjustments converging
- **Stable behavior**: threshold adjustments plateau (system stops "learning" because it's converged)
- **Proven on real signals**: not synthetic data, not test fixtures

**Current gap**: Architecture-complete, signal-unproven. No production metrics yet.

### 3.4 Financial Integration

- **BTCPay pipeline**: full two-way integration (AgencyOS can initiate payments within bounds)
- **Contract execution**: smart contracts or legal wrappers for bounded authority
- **Budget enforcement**: spending limits enforced at the system level, not just UI warnings

### 3.5 Legal Wrapper

- **LLC formation**: AgencyOS operates as an LLC with defined operating agreement
- **Authority bounds**: operating agreement specifies what the system can/cannot do autonomously
- **Liability limits**: software errors don't cascade to personal liability
- **Human-in-the-loop**: certain actions (spending > $X, legal commitments) require human signature

### 3.6 Safety Architecture

- **Immutable safety layer**: hardcoded constraints the system cannot modify (even at L10)
- **Graduated autonomy**: actions ranked by risk level, each with appropriate oversight
- **Circuit breakers**: automatic pause on anomalous behavior patterns
- **Audit trail**: every autonomous action logged with rationale and evidence chain

---

## 4. The Path

```
L9 (current) → Parameter tuning, threshold learning
                ↓ (6+ months proven outcomes)
L7 (next)    → Role separation, bounded autonomy per role
                ↓ (roles stable, cross-role communication proven)
L8 (after)   → Department orchestration, cross-functional goals
                ↓ (departments autonomous on real data)
L10 (future) → Market discovery, self-restructuring
                (requires legal wrapper + financial authority + safety architecture)
```

### Phase 4.5: L7 Foundation (8h estimated)
- Message bus (agent_messages table + publish/subscribe)
- Role base class with permission boundaries
- Detector/Correlator/Evolver roles as background threads
- Coordinator as arbitration layer

### Phase 4.6: L8 Department Loops (6h estimated)
- Outreach department: autonomous lead-to-customer pipeline
- Engagement department: autonomous gap-assessment-to-delivery pipeline
- Cross-department signal routing

### Phase 4.7: L10 Safety Architecture (prerequisite)
- Immutable safety layer extraction
- Graduated autonomy framework
- Circuit breaker system
- Legal wrapper operating agreement

### Phase 4.8: L10 Capabilities (future, undefined scope)
- Market discovery engine
- Self-restructuring governance
- Contract execution within bounds
- Financial autonomy within approved budgets

---

## 5. Safety Boundaries — What Must NEVER Be Autonomous

These boundaries are **immutable** — they cannot be modified by the system at any level, including L10:

### 5.1 Spending Money Beyond Approved Budgets
- System can **recommend** budget changes
- Human must approve any expenditure outside current budget
- Hard ceiling: system cannot transfer funds without human signature

### 5.2 Entering Legal Commitments
- System can **draft** contract terms
- Human must sign/execute any binding agreement
- No smart contract can override this requirement

### 5.3 Modifying Its Own Safety Constraints
- Safety layer is **hardcoded**, not configurable
- System can propose safety changes (via audit trail)
- Human must approve and deploy safety modifications

### 5.4 Hiring/Firing Humans
- System can **recommend** hiring/firing decisions
- Human must execute any employment action
- No automated payroll changes without human approval

### 5.5 Accessing Data Without Tenant Isolation
- Row-level tenant isolation is **mandatory**
- System cannot cross tenant boundaries
- Aggregate analytics use anonymized data only

### 6. Honest Assessment

### 6.1 Current State
- **Architecture-complete**: Signal → Insight → Proposal → Experiment → Promote/Rollback loop is wired
- **Signal-unproven**: No production metrics yet; self-improvement engine has no data to learn from
- **L9-fragmentary**: Tuner incumbents and promotion engine exist but lack the feedback loop that makes them "self-improving"

### 6.2 L10 Viability
- **Technically achievable**: Yes, with sufficient engineering investment and the prerequisite capabilities listed above
- **Economically viable**: Uncertain. The market for autonomous business operations software is unproven. Most businesses want human oversight of strategic decisions.
- **Legally permissible**: Not without significant legal engineering (LLC wrapper, operating agreement, graduated autonomy)
- **Ethically defensible**: Only with robust safety architecture and human override capabilities

### 6.3 Pragmatic Recommendation
- **Do not build L10 now.** Focus on proving L9 on real data, then L7-L8.
- **Reassess after 6 months** of proven self-improvement outcomes on production signals.
- **L10 may never be needed.** L7-L8 (autonomous departments with bounded authority) may be sufficient for the target market.
- **The safety architecture is the product.** If you do pursue L10, the safety layer (immutable constraints, graduated autonomy, circuit breakers) is what makes it defensible — not the autonomous capabilities themselves.

---

## 7. What L10 Is NOT

- **NOT artificial general intelligence**: L10 is narrow AI operating within a specific business domain. It doesn't "think" — it optimizes within constraints.
- **NOT a replacement for human judgment**: L10 handles operational decisions within bounds. Strategic decisions (which markets to enter, which services to offer) remain human.
- **NOT a legal entity by itself**: Software cannot be a business. L10 requires a legal wrapper (LLC) with human directors.
- **NOT self-aware**: The system doesn't "know" it's optimizing. It runs algorithms. Anthropomorphizing leads to poor safety decisions.

---

## 8. Reference Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         L10 AGENCYOS                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    IMMUTABLE SAFETY LAYER                      │   │
│  │  - Budget ceilings        - Legal commitment boundaries        │   │
│  │  - Tenant isolation       - Human override requirements        │   │
│  │  - Circuit breakers       - Audit trail (append-only)          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   SELF-RESTRUCTURING LAYER                     │   │
│  │  - Module graph evolution  - Role rebalancing                  │   │
│  │  - Department reorg        - Communication pattern changes     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  │
│  │   MARKET    │  │  FINANCIAL  │  │  OPERATIONS │  │   LEGAL  │  │
│  │ DISCOVERY   │  │ AUTONOMY    │  │ AUTONOMY    │  │ WRAPPER  │  │
│  │             │  │             │  │             │  │          │  │
│  │ - Segment   │  │ - Budget    │  │ - Outreach  │  │ - LLC    │  │
│  │   ident     │  │   mgmt      │  │ - Engage    │  │ - Op     │  │
│  │ - Opportun  │  │ - Payment   │  │ - Signal    │  │   agree  │  │
│  │   ity eval  │  │   exec      │  │ - Experiment│  │ - Auth   │  │
│  │ - Competitor│  │ - Contract  │  │ - Promote   │  │   bounds │  │
│  │   tracking  │  │   payments  │  │             │  │          │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘  │
│         │                │               │                │         │
│         └────────────────┴───────────────┴────────────────┘         │
│                                   │                                  │
│                           ┌───────┴───────┐                         │
│                           │  MESSAGE BUS  │                         │
│                           │  (async,      │                         │
│                           │   topic-based)│                         │
│                           └───────────────┘                         │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              L7-L8 ROLES & DEPARTMENTS                         │   │
│  │  Detector → Correlator → Evolver → Coordinator                │   │
│  │  Outreach Dept ←→ Engagement Dept ←→ Feedback Dept            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    L9 SELF-IMPROVING CORE                      │   │
│  │  Signal Detection → Root Cause → Experiment → Promote/Rollback │   │
│  │  Behavior Learner → Proactive Explorer → Outcome Tracking      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

*This document is a planning artifact, not a commitment. L10 scope and timeline will be reassessed after L9 is proven on real production data.*
