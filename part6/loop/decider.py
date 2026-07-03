"""Deciders: how the loop chooses the next action.

The next action is chosen at RUNTIME from the current STATE -- never from a
step counter. Terminology note (Part 5): because DeterministicDecider is code
choosing the action, code owns the control policy, so v1 is workflow-shaped.
LLMDeciderStub marks the seam where that choice becomes agentic. There is deliberately no
``if step == 1 ... elif step == 2`` anywhere here. ``step_count`` exists only
for the budget stop, never for choosing what to do next.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .state import CancellationStatus as C
from .state import RefundStatus as R


class BaseDecider(ABC):
    """A decider maps the current state to the next action name."""

    @abstractmethod
    def decide_next_action(self, state, tools, skill) -> str:
        """Return the name of the single next action to take."""
        raise NotImplementedError


class DeterministicDecider(BaseDecider):
    """Branches purely on confirmed state fields -- no API keys, stable traces.

    This preserves the loop shape without an LLM: observe state, choose the
    next action from that state, and let the loop act, verify, and update.
    Code makes the choice, so this controller is workflow-shaped (Part 5).
    """

    def decide_next_action(self, state, tools, skill) -> str:
        # We have never looked at the order -> find out where it stands.
        if state.cancellation_status == C.UNKNOWN:
            return "get_order_status"
        # Order is open and cancellation was never requested -> request it.
        if state.cancellation_status == C.NOT_REQUESTED:
            return "cancel_order"
        # Cancel accepted but not confirmed -> wait and re-read the world.
        if state.cancellation_status == C.PENDING:
            return "wait_and_recheck"
        # Review-hold: cannot auto-cancel -> hand off to a human (no refund).
        if state.cancellation_status == C.BLOCKED:
            return "escalate_to_human"
        # Cancellation confirmed -> drive the refund, also verify-before-trust.
        if state.cancellation_status == C.CANCELLED:
            if state.refund_status == R.NOT_STARTED:
                return "issue_refund"
            if state.refund_status == R.PENDING:
                return "get_refund_status"
            if state.refund_status == R.COMPLETED:
                return "final_response"
        # Defensive default: anything unexpected goes to a human, never a refund.
        return "escalate_to_human"


class LLMDeciderStub(BaseDecider):
    """Boundary for a real model-driven decider. Intentionally not implemented."""

    def decide_next_action(self, state, tools, skill) -> str:
        raise NotImplementedError(
            "Swap a real model in here. The loop, tools, state, contracts, "
            "verification gate, and trace do not change."
        )
