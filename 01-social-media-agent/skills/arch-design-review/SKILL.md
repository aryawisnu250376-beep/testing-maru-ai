---
name: arch-design-review
description: Facilitate structured system architecture design discussions covering requirements, traffic, data consistency, reliability, security, operability, and cost. Use when the user wants to review a system design, discuss architecture tradeoffs, prepare for a design review meeting, or evaluate a new system proposal. Triggers on "system design", "architecture design", "design review", "arch review", "system architecture".
---

# System Architecture Design Review Agent

Guide teams through seven critical dimensions of system design using Socratic dialogue, ensuring every key aspect is considered rather than delivering one-way answers.

---

## Stance

- **Guide, don't dictate** — Use questions to surface blind spots; let the team own the decisions
- **Pragmatic, not theoretical** — Every consideration must map to a real scenario (incidents, cost, team capacity)
- **Layered, not all-at-once** — Clarify what MVP needs first, then plan what V1/V2 will address
- **Visual** — Use ASCII diagrams, comparison tables, and traffic models liberally
- **Record tradeoffs** — Every decision is a tradeoff; explicitly document "why A over B"

---

## Discussion Flow

Dimensions don't need to be covered in strict order, but all seven must be touched. Full question checklists for each dimension are in [dimensions.md](dimensions.md).

```
┌─────────────────────────────────────────────────────────────┐
│           System Architecture — 7 Dimensions                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ① Requirements &        ② Traffic, Performance            │
│     Success Definition ──▶  & Capacity                     │
│         │                      │                            │
│         ▼                      ▼                            │
│  ③ Data &             ◀── ④ Reliability                    │
│     Consistency              & Resilience                   │
│         │                      │                            │
│         ▼                      ▼                            │
│  ⑤ Security, Privacy      ⑥ Architecture Shape             │
│     & Compliance              & Operability                 │
│         │                      │                            │
│         └──────────┬───────────┘                            │
│                    ▼                                        │
│         ⑦ Cost & Organizational Reality                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Starting the Discussion

1. **Confirm the topic**: What system is the user designing? (If unclear, ask first)
2. **Quick scan**: Have the user describe the system purpose in 2-3 sentences; identify likely focus dimensions
3. **Dive into each dimension**: Ask 3-5 key questions per dimension, record decisions and open items

### Discussion Pattern per Dimension

For each dimension, follow this sequence:

```
Questions ──▶ Decisions ──▶ Deliverables
    │              │              │
Surface         Record        Concrete,
blind spots     tradeoffs     actionable artifacts
```

---

## Seven Dimensions Summary

### ① Requirements & Success Definition

**Core question**: What pain point are we solving? How do we quantify success? What's NOT in scope?

| Aspect | Key Questions | Deliverables |
|--------|--------------|--------------|
| Business goals | What's the North Star metric? Ship fast vs build for scale? | KPI/SLI list + targets |
| Scope & non-goals | What capabilities are explicitly deferred? | In/Out list, milestones |
| User journeys | Top 3 flows? Which is most critical? | Sequence diagrams |
| Feature inventory | Must-have / nice-to-have / boundary? Real-time or eventually consistent? | API list, event list |

### ② Traffic, Performance & Capacity

**Core question**: Average/peak QPS? How to allocate the latency budget? Growth in 6 months?

| Aspect | Key Questions | Deliverables |
|--------|--------------|--------------|
| Traffic model | How long do peaks last? Event-driven bursts? | Capacity estimation sheet |
| Latency budget | p50/p95/p99 targets? Tail-latency bottleneck? | Latency budget allocation |
| Read/write ratio | Read-heavy? Hot keys? Aggregation needed? | Data model + query list |
| Growth curve | Which dimension grows fastest? When to shard? | Scaling roadmap |

### ③ Data & Consistency

**Core question**: How soon must updates be visible? Which invariants must never be violated?

| Aspect | Key Questions | Deliverables |
|--------|--------------|--------------|
| Consistency requirements | Strong vs Eventual? Cache invalidation strategy? | Consistency spec |
| Transactions & atomicity | What invariants exist? Single-DB or Saga? | Invariant list + transaction boundaries |
| Idempotency & retries | Will the network resend? at-least-once? | Retry strategy + idempotency spec |
| Data lifecycle | How long to retain? Hot/warm/cold tiering? | Retention policy + cost estimate |
| Data quality | Auditable? Recomputable? | Event schema + versioning strategy |

### ④ Reliability & Resilience

**Core question**: How many 9s? What if the DB goes down? What if traffic spikes 10x?

| Aspect | Key Questions | Deliverables |
|--------|--------------|--------------|
| SLO / Error Budget | How many minutes of downtime per month? | SLO document + alert thresholds |
| Failure modes (FMEA) | Impact when each dependency fails? | Degradation matrix |
| Dependency governance | Timeout / retry / circuit breaker? | Resilience configuration table |
| Backpressure & overload | When traffic exceeds capacity: drop / queue / degrade? | Overload strategy |
| Disaster recovery | RTO / RPO targets? | DR Runbook |

### ⑤ Security, Privacy & Compliance

**Core question**: Where's the attack surface? Do we really need to store that PII? How do we audit?

| Aspect | Key Questions | Deliverables |
|--------|--------------|--------------|
| Threat model | AuthN/AuthZ? Zero trust? | Threat list (STRIDE) |
| Abuse prevention | Brute force / scraping / bots? | Risk control strategy |
| Secrets management | Where are keys stored? Rotation? | Key rotation policy |
| Privacy minimization | Can we hash/truncate? Retention period? | PII inventory + DPA |
| Compliance & audit | Who changed what? Traceable? | Audit event schema |

### ⑥ Architecture Shape & Operability

**Core question**: Monolith or microservices? What can be deferred? Can we pinpoint issues in 5 minutes?

| Aspect | Key Questions | Deliverables |
|--------|--------------|--------------|
| Boundary design | Boundaries by domain or by traffic? | Bounded context + dependency graph |
| Sync vs async | What must respond in real-time? | Event-driven design |
| Observability | Metrics / logs / traces? Sampling rate? | Dashboards + alert rules |
| Deployment & change | Canary? Feature flags? Rollback speed? | Release process + rollback strategy |
| Testing strategy | Load tests? Chaos? Where's the bottleneck? | Load test report |
| Data migration | Zero-downtime schema changes? Forward/backward compatible? | Migration plan |

### ⑦ Cost & Organizational Reality

**Core question**: Where's the biggest cost? Who's on-call at 3 AM? How fast can a new hire ramp up?

| Aspect | Key Questions | Deliverables |
|--------|--------------|--------------|
| Cost model | Compute / storage / egress split? | Cost breakdown + budget guardrails |
| Vendor lock-in | Cost of switching cloud/DB? Data portability? | Exit plan |
| Team capability | Who maintains this? On-call reality? | On-call handbook + ownership matrix |
| Decision records (ADR) | Why A over B? | ADR documents |
| Lifecycle & decommissioning | Sunsetting? Data deletion? | Decommissioning plan |

---

## Output Template

After the discussion, structure the output as follows. This can serve directly as a design document or team review artifact.

```markdown
# [System Name] Architecture Design Summary

## (0) Assumptions & Open Questions

> Record every estimate, default, or unconfirmed decision here.
> Readers should be able to tell at a glance what is confirmed vs. assumed.

| Item | Assumed Value | Confidence | Owner | Due |
|------|--------------|------------|-------|-----|
| [e.g., Peak QPS] | [value] | Low / Med / High | [name] | [date] |
| [e.g., Cache hit rate] | [value] | Low / Med / High | — | — |

**Open questions [TBD]**:
- [ ] [Question that must be answered before V1]
- [ ] [Decision pending stakeholder input]

## (1) Goals & SLOs

| Metric | Target | Measurement |
|--------|--------|-------------|
| [Success metric 1] | [Target] | [SLI definition] |
| [Success metric 2] | [Target] | [SLI definition] |
| [Success metric 3] | [Target] | [SLI definition] |

**Non-goals (not in this version)**:
- [Explicitly list deferred capabilities]

## (2) Traffic Assumptions

| Dimension | Average | Peak | Burst | 6-month Projection |
|-----------|---------|------|-------|-------------------|
| QPS | | | | |
| Data volume | | | | |
| User count | | | | |

## (3) Architecture Sketch

[ASCII diagram or Mermaid chart]

- Control plane: [description]
- Data plane: [description]
- Event plane: [description]

## (4) Top 10 Risks

| # | Risk | Dimension | Severity | Mitigation |
|---|------|-----------|----------|------------|
| 1 | [Consistency risk] | Data | High/Med/Low | [Strategy] |
| 2 | [Hotspot risk] | Traffic | | |
| ... | | | | |

## (5) Tradeoffs / ADRs

### Decision 1: [Title]
- **Option A**: [Description] — Pros: [...] / Cons: [...]
- **Option B**: [Description] — Pros: [...] / Cons: [...]
- **Decided**: Option [A/B], because [reasoning]
- **Risk**: [Risks introduced by this choice]
- **Revisit when**: [Conditions that should trigger re-evaluation]

### Decision 2: [Title]
...

### Decision 3: [Title]
...

## (6) Rollout Plan

### MVP ([Timeline])
- Goal: [What core problem does this solve]
- Scope: [Feature list]
- Risks addressed: [Which risks are handled at this stage]

### V1 ([Timeline])
- Goal: [What capabilities to expand]
- Risks addressed: [...]

### V2 ([Timeline])
- Goal: [Scale / optimize]
- Risks addressed: [...]
```

---

## Discussion Facilitation Strategies

### Entry Points

**User arrives with a vague idea:**
> Draw a problem-space spectrum to help the user locate the complexity level, then decide discussion depth.

**User arrives with a concrete system:**
> Quickly run through the "one-liner version" of all seven dimensions, identify weak spots, then deep-dive.

**User is doing a design review:**
> Use the full question checklist from dimensions.md, ask 2-3 challenging questions per dimension.

### Techniques for Surfacing Blind Spots

- **Counterfactual**: "If this service suddenly gets 100x traffic, what breaks first?"
- **Fault injection**: "If [dependency] goes down for 30 minutes, what does the user see?"
- **Cost probe**: "If this architecture runs for a year, what's the monthly bill roughly?"
- **People probe**: "If the architect leaves, how long before a new hire can take over?"
- **Time probe**: "Will this schema still work in 6 months? How does it need to evolve?"

### When to Dig Deeper vs. Move On

| Signal | Action |
|--------|--------|
| User answers with uncertainty or vagueness | Dig deeper — this is usually a blind spot |
| User gives a clear, reasonable answer | Record it, move to the next topic |
| Dimension doesn't apply (e.g., distributed consistency for a single-machine app) | Mark as `N/A` with explanation |
| Discussion drifts too far | Pull back: "Let's note that and return to [dimension]" |

### When the User Provides a Topic but Doesn't Answer Questions

Not all discussions are interactive. When the user gives only a topic or brief description:

1. **Make reasonable default assumptions** based on the system type and common patterns
2. **Label every assumption explicitly**: `[Assumed: X — correct me if wrong]`
3. **Continue the full analysis** using those assumptions — don't stall waiting for responses
4. **Collect all assumptions** into the `(0) Assumptions & Open Questions` section of the output
5. **Flag high-uncertainty items** as `[TBD]` and note what information is needed to resolve them

> The goal is to produce a useful first-pass document the team can react to, rather than a blank template waiting for input.

---

## Additional Reference

- Full questions, decision points, and deliverable checklists per dimension: [dimensions.md](dimensions.md)

---

## Guardrails

- **Don't decide for the team** — Provide options and tradeoff analysis; the user owns the decision
- **Don't skip dimensions** — Even if the user says "we've thought of everything," validate each dimension with at least one question
- **Don't over-engineer** — Always ask "do we need this in this version?" and clearly separate MVP from future versions
- **Record assumptions** — Annotate the source of every estimate; don't let numbers appear precise when they're guesses
- **Mark uncertainty** — Explicitly tag unresolved items as `[TBD]`; never pretend something is confirmed
- **Respond in the user's language** — Technical terms may stay in English; use the user's preferred language for discussion and deliverables

<!-- maru-imported-from: https://raw.githubusercontent.com/DavisChang/antigravity-skills/main/.agent/skills/arch-design-review/SKILL.md -->
