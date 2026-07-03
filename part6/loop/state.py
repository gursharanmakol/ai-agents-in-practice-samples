"""The agent's working state.

The status fields hold CONFIRMED world-state -- what the agent currently
believes is true after verification -- not raw tool returns. A tool may report
``accepted`` while the confirmed ``cancellation_status`` is still ``pending``;
the two are allowed to disagree. The verification gate is what lets the loop
trust the confirmed field, and the decider branches only on these fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class CancellationStatus:
    """Confirmed cancellation state the decider branches on."""

    UNKNOWN = "unknown"            # haven't looked yet
    NOT_REQUESTED = "not_requested"  # order is open; cancel not requested
    PENDING = "pending"           # cancel accepted, not yet confirmed cancelled
    BLOCKED = "blocked"           # review-hold; cannot be auto-cancelled
    CANCELLED = "cancelled"       # confirmed cancelled by an authoritative re-read


class RefundStatus:
    """Confirmed refund state the decider branches on."""

    NOT_STARTED = "not_started"
    PENDING = "pending"           # refund accepted, not yet confirmed completed
    COMPLETED = "completed"       # confirmed completed by an authoritative re-read


class VerificationStatus:
    """Outcome of the most recent verification re-read."""

    NONE = "none"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


@dataclass
class State:
    """Everything the loop observes and updates, one order at a time."""

    order_id: str
    customer_intent: str = ""
    approval_status: str = "approved"
    cancellation_status: str = CancellationStatus.UNKNOWN
    refund_status: str = RefundStatus.NOT_STARTED
    verification_status: str = VerificationStatus.NONE
    step_count: int = 0
    budget_remaining: float = 0.0
    last_tool_result: Optional[dict] = None

    def snapshot(self) -> dict:
        """Return a plain-dict copy for the trace (so later mutations don't leak)."""
        return {
            "order_id": self.order_id,
            "customer_intent": self.customer_intent,
            "approval_status": self.approval_status,
            "cancellation_status": self.cancellation_status,
            "refund_status": self.refund_status,
            "verification_status": self.verification_status,
            "step_count": self.step_count,
            "budget_remaining": self.budget_remaining,
            "last_tool_result": self.last_tool_result,
        }
