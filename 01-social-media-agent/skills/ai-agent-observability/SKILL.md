---
name: ai-agent-observability
description: Guide for building observable, evaluable AI Agent systems. Covers trace design (Run/Trace/Thread), non-determinism management, structured error handling, evaluation strategies (unit/trace/thread), production-to-offline feedback loops, and guardrails. Use when developing AI agents, adding observability to LLM pipelines, designing agent evaluation, or debugging non-deterministic agent behavior.
---

# AI Agent Observability & Evaluation

Operational guide for making AI agents **observable, evaluable, and iteratively improvable**. Treats agents as non-deterministic systems where traces (not code) are the source of truth.

## Core Mental Model

```
Code defines prompts + tools → Agent produces behavior distributions
Traces capture what actually happened → Evals measure reasoning quality
Production failures → become offline test cases → close the loop
```

**Key difference from traditional software**: You manage *behavior distributions*, not deterministic code paths. Same input can yield different outputs; correctness is revealed at runtime by user inputs you can't fully anticipate.

## When to Apply This Skill

- Building or improving an AI agent / LLM pipeline
- Adding observability (tracing, logging, metrics) to agent systems
- Designing evaluation strategies for non-deterministic behavior
- Debugging "it works sometimes" or "it forgot what I said" issues
- Preparing an agent for production (from demo to reliable)

---

## 1. Guardrails First

Before any observability, define **what must never happen**:

1. List 3+ forbidden actions (e.g., delete data, make purchases, leak PII)
2. Add confirmation/approval gates for high-risk tool calls
3. Set hard limits: `max_steps`, `max_tool_calls`, `timeout`
4. Route known input patterns to rules/forms; only unknown goes to LLM
5. Deploy with traffic splitting (shadow/canary) before full rollout

```python
# Example guardrail config
GUARDRAILS = {
    "max_steps": 15,
    "max_tool_calls": 30,
    "timeout_seconds": 120,
    "forbidden_tools": ["delete_record", "send_payment"],
    "require_approval": ["update_database", "send_email"],
}
```

## 2. Trace Design — The Three Primitives

### Run (single LLM call)
The atomic unit. Record for every LLM invocation:

| Field | What | Why |
|-------|------|-----|
| `run_id` | Unique ID | Link to parent trace |
| `run_type` | planner / tool-selector / summarizer / critic | Different eval criteria per type |
| `prompt_preview` | First 500 chars of formatted prompt | Reproduce non-determinism |
| `response_preview` | First 500 chars of raw response | Spot hallucinations |
| `messages` | Full message array | Complete context reconstruction |
| `tools_available` | Tool definitions passed | Understand tool selection |
| `tool_calls` | Name, args, return value, error, latency | Debug tool misuse |
| `tokens` | prompt / completion / total | Cost tracking |
| `latency_ms` | Wall-clock time | Performance regression |
| `decision_context` | Key factors influencing this call | Understand *why* |
| `context_length` | Token count of input context | Detect truncation |
| `truncated` | Whether context was cut | Explains "sudden amnesia" |

### Trace (one task execution)
A directed graph of Runs for a single user request:

```
User Request → [Run: parse] → [Run: plan] → [Run: tool_select] → [Run: tool_execute] → [Run: summarize]
```

Trace-level checks:
- Total steps (detect loops: same tool + same args >= 3 consecutive times)
- Total cost and latency
- Error propagation (which step caused downstream failure)
- "Not-allowed" conditions: loops, tool errors, timeouts

### Thread (multi-turn conversation)
Links multiple Traces across turns with one `thread_id`:

```
Turn 1: User asks → Trace A (3 runs)
Turn 2: User follows up → Trace B (5 runs) — should remember Turn 1 context
Turn 3: User corrects → Trace C (2 runs) — should apply correction
```

Thread-level checks:
- Memory retention: does agent remember key preferences/constraints?
- Self-contradiction across turns
- Re-ask rate (user repeating themselves = context loss)

## 3. What Signals to Capture

### Efficiency Metrics (no ground truth needed)
```
latency_total, latency_per_step, latency_per_tool
token_usage, model_call_count, tool_call_count
retry_count, loop_count, rewrite_count
error_code_rate, tool_failure_rate, parse_failure_rate, format_violation_rate
```

### User Behavior Signals
```
abandon_rate, re_ask_rate, edit_rate, cancel_rate
satisfaction_score, escalation_rate
```

### Anomaly Detection
Compare metrics against a **baseline**. Alert when:
- Tool call count spikes → likely looping or thrashing
- Latency increases without success rate change → unnecessary steps
- Format violation rate increases → prompt/model/parser change
- Re-ask rate increases → answers becoming unclear
- Specific tool failure rate spikes → external API issue

## 4. Evaluation Strategy — Three Layers

### Layer 1: Run-Level (Unit Tests for Decisions)

Fast, deterministic-ish, runs in CI.

```python
# Example: tool selection eval
test_cases = [
    {"input": "What's the weather?", "expected_tool": "get_weather"},
    {"input": "Book a flight", "expected_tool": "search_flights"},
    {"input": "Tell me a joke", "expected_tool": None},  # no tool needed
]

def eval_tool_selection(agent, cases):
    results = []
    for case in cases:
        run = agent.plan(case["input"])
        passed = run.selected_tool == case["expected_tool"]
        results.append({"input": case["input"], "passed": passed})
    return results
# Target: >= 90% pass rate
```

**Build 10+ cases per critical run type.** Focus on:
- Tool selection accuracy
- Query generation quality
- Summary completeness
- When to ask clarification vs. proceed

### Layer 2: Trace-Level (End-to-End Task Tests)

Slower, more realistic. Define **minimum acceptance criteria**, not perfect answers:

```python
trace_eval = {
    "input": "Find flights from NYC to London under $500",
    "must_happen": ["search_flights called", "price_filter applied"],
    "must_not_happen": ["loop detected", "timeout", "tool_error"],
    "max_steps": 8,
    "max_cost_usd": 0.05,
}
```

### Layer 3: Thread-Level (Multi-Turn Consistency)

Define 3+ memory points that must persist across turns:

```python
thread_eval = {
    "setup_turns": [
        {"user": "I'm vegetarian", "check": "acknowledged"},
        {"user": "Find me restaurants", "check": "only_vegetarian_results"},
        {"user": "What about Italian?", "check": "still_vegetarian_filter"},
    ],
    "memory_points": ["vegetarian", "preference for Italian"],
}
```

## 5. Production → Offline Feedback Loop

This is the core iteration cycle:

```
Production trace (failure) 
  → Find trace_id 
  → Locate failing step 
  → Extract state snapshot (messages + tools + context)
  → Anonymize/mask PII 
  → Create offline test case (input + expected)
  → Fix prompt/tool 
  → Verify: fail before fix, pass after 
  → Add to CI regression suite
```

### Online Evaluators (no ground truth)
Deploy at minimum:
1. **Loop detector**: same tool + same args >= 3 consecutive → alert
2. **Tool error rate**: per-tool failure rate, alert if > threshold
3. **Timeout rate**: traces exceeding time limit
4. **Refusal rate**: agent declining to act when it should

### Weekly Rhythm
1. Review Top 3 failure modes from online evaluators
2. Triage: fix prompt / tool interface / guardrail
3. Convert failures → offline test cases
4. Re-run offline benchmark
5. Update alert thresholds based on new baseline

## 6. Implementation Checklist

Quick self-assessment — see [checklist.md](checklist.md) for the full version:

- [ ] Forbidden actions listed + enforcement mechanism
- [ ] `max_steps`, `max_tool_calls`, `timeout` enforced
- [ ] Every LLM call recorded as a Run with full context
- [ ] Tool calls recorded (args, return, error, latency)
- [ ] Traces replayable in time-order
- [ ] `trace_id` attached to all bug reports
- [ ] `thread_id` linking multi-turn conversations
- [ ] At least 1 run-level eval suite (auto pass/fail)
- [ ] At least 1 trace-level eval (end-to-end with must-not-happen)
- [ ] At least 2 online evaluators running (loop + tool error)
- [ ] Production trace → offline test case pipeline exists
- [ ] Weekly failure mode review process established

## Additional Resources

- Detailed checklist: [checklist.md](checklist.md)
- Evaluation playbook & strategies: [playbook.md](playbook.md)
- English overview: [README.md](README.md)
- 中文版說明: [README_TW.md](README_TW.md)

<!-- maru-imported-from: https://raw.githubusercontent.com/DavisChang/antigravity-skills/main/.agent/skills/ai-agent-observability/SKILL.md -->
