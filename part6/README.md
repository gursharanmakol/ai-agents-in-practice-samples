# Part 6 — Building the Production Agent Loop

A deterministic, runnable production-loop lab for TechNova's "cancel an order, then refund what's
owed" flow. It demonstrates one core principle: **a tool response describes the REQUEST, not
the WORLD.** An `accepted` acknowledgement from `cancel_order` is not proof the order is
cancelled. For irreversible actions (like issuing a refund), the system must **verify the world
changed before committing** to the next consequential action.

## Workflow-shaped controller with an agentic seam

The default lab uses a deterministic decision function so it runs without API
keys and produces stable traces. Each turn observes state, chooses the next
action from the current state (never from a step counter), acts through one
allowed tool, checks the result, updates state, and repeats. Under Part 5's
definition, this v1 controller is workflow-shaped: code owns the next-action
choice. A real LLM decider can replace this function later, making the choice
genuinely agentic, without changing the tools, state, contracts, verification
gate, or trace.

## Why the default decider is deterministic

You might be wondering: where is the actual LLM deciding what to do?

There isn't one in v1, by design — and that is the point of this lab.

Part 6 is about the production structure *around* an agent loop, not about model
intelligence: working state, scoped tools, tool contracts, idempotency keys,
verify-before-commit, budget and stop rules, and a trace. Those are the parts that decide
whether an agent survives production, and they are identical whether the next action is
chosen by a deterministic function or by a model.

A real LLM decider would replace exactly one thing — the `decide_next_action()` function in
`loop/decider.py`, where `LLMDeciderStub` marks the seam. State, tools, contracts, the
verification gate, idempotency, budgets, stop rules, and the trace would not change. That is
why the default decider is deterministic: it runs with no API key, produces stable and
reviewable traces, and keeps the focus on the structure rather than on a model's output.

One definition note, to stay consistent with Part 5: v1 is not an agent. The
next action is chosen at runtime, but it is chosen by code, and code owning the
control policy is what makes a system workflow-shaped. That is deliberate. A
hardcoded `cancel → verify → refund` sequence would hide the structure this lab
exists to show; a state-driven controller keeps the real shape of the
`observe → decide → act → check → repeat` loop, with verification implemented
inside `check`, while staying deterministic. Swap a model in behind the same
seam and the choice becomes agentic; nothing else about the loop changes.

So the lab is not demonstrating model intelligence. It is demonstrating the control structure
a production agent needs around the model — the part that is hard to get right and easy to
skip in a demo.

## Note on the skill file

The skill in `skills/cancel_order_skill.md` is the packaged procedure for the task, loaded as
text. In this deterministic v1 lab, the decider encodes the same logic in code (branching on
state) rather than parsing the markdown at runtime — so the file travels with the lab as the
human-readable procedure, but it does not drive control flow. A live LLM decider could read
this same skill text when choosing the next action, and the rest of the loop — state, tools,
contracts, verification, idempotency, budget, stop rules, trace — would stay the same.

## Requirements

- Python 3.10+

## Run it

### macOS / Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python examples/run_safe.py
python examples/run_naive.py
pytest
```

### Windows (PowerShell)

```powershell
py -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python examples\run_safe.py
python examples\run_naive.py
pytest
```

Both example scripts write a pretty-printed JSON trace into `traces/`
(`safe_trace.json` and `naive_trace.json`).

## What to look for in the traces

Every step record keeps `tool_response` and `verification_read` as **separate fields**, even
when they agree. That gap is the whole lesson:

- `tool_response` is what the tool *said* (e.g. `cancel_order` -> `{"status": "accepted"}`).
- `verification_read` is what an **authoritative re-read** of the business state *confirmed*
  (e.g. `get_order_status` -> `"cancelled"`, or still `"pending"`).

Compare the two runs:

- **`safe_trace.json`** — after `cancel_order` is accepted, the cancellation status is held at
  `pending` until an authoritative re-read confirms `cancelled`. Only then is the refund issued,
  and the refund is itself verified before the loop finishes.
- **`naive_trace.json`** — the verification gate is removed, and the example wires the
  explicitly labeled, teaching-only `UnsafeRefundStore`, which models Part 1's world: a backend
  with no enforcement boundary of its own. The loop trusts the `accepted` acknowledgement and
  issues the refund immediately. Look at the `issue_refund` step: the
  loop state treats the order as `cancelled`, but `world_order_status` in `resulting_state` is
  still `pending`. The refund went out before the world was confirmed — the exact bug this
  lab warns about.

## The backend is the final enforcement boundary

The loop's verification gate prevents bad sequencing. The refund store enforces the actual
rule. The default `RefundStore` is wired (by the `Tools` container) to an authoritative order
reader and revalidates the cancellation precondition at execution time: if the order is not
`cancelled`, the refund is **rejected** with `order_not_cancelled`, no money moves, and the
idempotency key is not consumed, so a retry is allowed once the world settles. Run the naive
loop against the default store and the backend stops it — `refund_rejected_by_backend` — even
with the verification gate switched off. See `tests/test_backend_enforcement.py`.

Three more production behaviors are implemented, not planned:

- **Budget preflight**: the ceiling is checked *before* an action runs (`Budget.can_spend`);
  an unaffordable action is never executed. See `tests/test_budget_preflight.py`.
- **Six-question tool contracts**: every contract carries `description` and `when_to_use`
  alongside shapes, failure modes, idempotency, and verification method (`tools/contracts.py`).
- **Runtime response validation**: tool responses are checked against their contract before
  they enter working state; malformed or unrecognized responses are rejected
  (`loop/validate.py`, `tests/test_validation.py`).

## What this is NOT

This is **not** a framework or a platform. There is no MCP, no RAG, no real LLM, no real
payments, and no multi-agent orchestration. It is one bounded production-loop scaffold with
a deterministic controller and two fake, in-memory tools. MCP and a real LLM decider are possible later additions *around the same
tools and loop* — the loop, state, contracts, verification gate, and trace would not change.

TechNova is a fictional company. All orders, refunds, and policies here are made up for
teaching.

## Roadmap

This is v1 — the deterministic, workflow-shaped production scaffold. A later version swaps in a real LLM decider
behind the same seam (`decide_next_action`), and the surrounding structure — state, tools,
contracts, verification, idempotency, budgets, stop rules, and trace — stays the same. That
stability is the point: the model is the part that changes, the production structure is not.

## Read the article

[AI Agents in Practice — Part 6: Building the Production Agent Loop](https://dev.to/gursharansingh/ai-agents-in-practice-part-6-building-the-production-agent-loop-2lfi)
