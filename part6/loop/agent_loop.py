"""The agent loop: observe -> decide -> act -> check -> update -> repeat.

The loop calls the decider every turn to choose ONE action from the current
state, acts through at most one tool, checks the result (verifying when the
gate is enabled), updates state, and appends a trace record. It stops on a
terminal action, an escalation, or any budget rule.

The verification gate is the difference between the safe and naive runs:

- ``verify_enabled=True`` (safe): an ``accepted`` ack only moves status to
  ``pending``. Status is promoted to ``cancelled`` / ``completed`` ONLY by an
  independent re-read (``wait_and_recheck`` / ``get_refund_status``).
- ``verify_enabled=False`` (naive): the ack is trusted as if it were the world,
  so status jumps straight to ``cancelled`` / ``completed`` and the refund can
  go out before the world is confirmed. Same loop, same tools -- gate removed.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from . import actions
from .budget import ACTION_COST, Budget
from .decider import BaseDecider
from .state import CancellationStatus as C
from .state import RefundStatus as R
from .state import State, VerificationStatus
from .trace import StepRecord, Trace
from .verify import verify_action_landed

# Deterministic, recorded-only latencies (NOT wall-clock; keeps traces stable).
ACTION_LATENCY_MS: dict[str, float] = {
    "get_order_status": 40.0,
    "cancel_order": 60.0,
    "wait_and_recheck": 30.0,
    "issue_refund": 60.0,
    "get_refund_status": 40.0,
    "escalate_to_human": 10.0,
    "final_response": 10.0,
}

TERMINAL_ACTIONS = {"escalate_to_human", "final_response"}

PRINCIPLE = (
    "A tool response describes the REQUEST, not the WORLD. For irreversible "
    "actions, verify the world changed before committing the next consequential action."
)


def load_skill(name: str = "cancel_order_skill") -> str:
    """Load a skill file as TEXT.

    The decider does NOT parse this for control flow; the skill is the
    human-readable procedure that travels with the code. The path is built
    relative to this file so it works no matter where python/pytest is run from.
    """
    path = Path(__file__).resolve().parent.parent / "skills" / f"{name}.md"
    return path.read_text(encoding="utf-8")


def _map_order_read(status: str) -> str:
    """Map a raw order read to a confirmed cancellation_status."""
    return {
        "open": C.NOT_REQUESTED,
        "pending": C.PENDING,
        "cancelled": C.CANCELLED,
        "blocked": C.BLOCKED,
    }.get(status, C.PENDING)


def _map_refund_read(status: str) -> str:
    """Map a raw refund read to a confirmed refund_status."""
    return {
        "none": R.NOT_STARTED,
        "pending": R.PENDING,
        "completed": R.COMPLETED,
    }.get(status, R.PENDING)


def run_agent_loop(
    tools,
    decider: BaseDecider,
    *,
    order_id: str,
    skill: str = "",
    scenario: str = "",
    verify_enabled: bool = True,
    budget: Optional[Budget] = None,
    retries: int = 1,
    backoff: float = 0.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Tuple[State, Trace]:
    """Run the loop to a terminal state, escalation, or budget stop.

    Returns the final ``State`` and the ``Trace``.
    """
    if budget is None:
        budget = Budget()

    state = State(
        order_id=order_id,
        customer_intent="cancel order and refund what is owed",
    )
    state.budget_remaining = budget.max_cost
    trace = Trace(scenario=scenario, principle=PRINCIPLE)
    stop_reason: Optional[str] = None

    while True:
        observed_state = state.snapshot()
        action = decider.decide_next_action(state, tools, skill)

        tool_called: Optional[str] = None
        tool_response = None
        verification_read = None
        note: Optional[str] = None

        if action == "get_order_status":
            # Plain observation read: learn where the order stands. Nothing to
            # verify here -- this read IS how we observe the world.
            tool_called = "get_order_status"
            tool_response = tools.order.get_order_status(order_id)
            state.last_tool_result = tool_response
            state.cancellation_status = _map_order_read(tool_response["status"])

        elif action == "cancel_order":
            tool_called = "cancel_order"
            key = f"cancel_order:{order_id}"  # deterministic per (action, order)
            tool_response = tools.order.cancel_order(order_id, key)
            state.last_tool_result = tool_response
            # VERIFICATION GATE: an "accepted" ack is not proof the world changed.
            if verify_enabled:
                state.cancellation_status = C.PENDING  # await an independent re-read
            else:
                # NAIVE: trust the request as if it were the world (the bug).
                state.cancellation_status = C.CANCELLED

        elif action == "wait_and_recheck":
            # The re-read IS the verification, so tool_response (raw read) and
            # verification_read (outcome status) are recorded separately.
            tool_called = "get_order_status"
            raw, vstatus, outcome = actions.wait_and_recheck(
                order_id, tools.order, retries=retries, backoff=backoff, sleep_fn=sleep_fn
            )
            tool_response = raw
            verification_read = vstatus
            state.verification_status = (
                VerificationStatus.VERIFIED if outcome == "verified" else VerificationStatus.UNVERIFIED
            )
            state.last_tool_result = raw
            state.cancellation_status = _map_order_read(vstatus)

        elif action == "issue_refund":
            tool_called = "issue_refund"
            key = f"issue_refund:{order_id}"
            tool_response = tools.refund.issue_refund(order_id, key)
            state.last_tool_result = tool_response
            # Same gate as cancellation: don't trust the ack as completion.
            if verify_enabled:
                state.refund_status = R.PENDING
            else:
                state.refund_status = R.COMPLETED

        elif action == "get_refund_status":
            tool_called = "get_refund_status"
            outcome, raw = verify_action_landed(
                read=lambda: tools.refund.get_refund_status(order_id),
                expected="completed",
                retries=retries,
                backoff=backoff,
                sleep_fn=sleep_fn,
            )
            tool_response = raw
            verification_read = raw["status"]
            state.verification_status = (
                VerificationStatus.VERIFIED if outcome == "verified" else VerificationStatus.UNVERIFIED
            )
            state.last_tool_result = raw
            state.refund_status = _map_refund_read(raw["status"])

        elif action == "escalate_to_human":
            result = actions.escalate_to_human(
                reason="cancellation blocked / on review-hold; not auto-cancellable"
            )
            note = result["reason"]

        elif action == "final_response":
            result = actions.final_response(order_id)
            note = result["summary"]

        else:  # pragma: no cover - guards against a decider returning garbage
            raise ValueError(f"Unknown action from decider: {action!r}")

        # --- check + update: charge budget, advance counters, record the turn ---
        cost = ACTION_COST.get(action, 0.0)
        budget.charge(cost)
        state.budget_remaining = max(budget.max_cost - budget.spent_cost, 0.0)
        latency = ACTION_LATENCY_MS.get(action, 0.0)
        state.step_count += 1

        resulting_state = state.snapshot()
        # Diagnostic peeks (non-consuming): the TRUE world, so a reader can see
        # the gap between what the agent believes and what is actually settled.
        resulting_state["world_order_status"] = tools.order.peek_order_status(order_id)["status"]
        resulting_state["world_refund_status"] = tools.refund.peek_refund_status(order_id)["status"]
        if note:
            resulting_state["note"] = note

        trace.add(
            StepRecord(
                step=state.step_count,
                observed_state=observed_state,
                decided_action=action,
                tool_called=tool_called,
                tool_response=tool_response,
                verification_read=verification_read,
                resulting_state=resulting_state,
                cost=cost,
                latency_ms=latency,
            )
        )

        # --- stop conditions ---
        if action in TERMINAL_ACTIONS:
            stop_reason = (
                "escalated_to_human" if action == "escalate_to_human" else "completed_successfully"
            )
            break

        budget_stop = budget.check(state.step_count, latency)
        if budget_stop:
            stop_reason = budget_stop
            break

    trace.finish(stop_reason=stop_reason, final_state=state.snapshot())
    return state, trace
