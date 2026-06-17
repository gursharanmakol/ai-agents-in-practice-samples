"""Non-tool actions the loop can take.

These are the moves that are not a single tool call:

- ``wait_and_recheck``: back off, then independently re-read the order status to
  confirm a pending cancellation (the cancellation verification gate).
- ``escalate_to_human``: terminal hand-off; records a reason and issues NO refund.
- ``final_response``: terminal success.
"""

from __future__ import annotations

from typing import Callable, Tuple

from tools.order_tools import CANCELLED

from .verify import verify_action_landed


def wait_and_recheck(
    order_id: str,
    order_store,
    *,
    retries: int,
    backoff: float,
    sleep_fn: Callable[[float], None],
) -> Tuple[dict, str, str]:
    """Wait (with backoff) then independently re-read the order status.

    The re-read goes through ``get_order_status`` -- a path independent of
    ``cancel_order``'s acknowledgement -- which is what makes it a real
    verification rather than wishful thinking.

    Returns ``(raw_read, status_string, outcome)`` so the loop can record the
    raw tool response and the verification outcome as separate trace fields.
    """
    outcome, last_read = verify_action_landed(
        read=lambda: order_store.get_order_status(order_id),
        expected=CANCELLED,
        retries=retries,
        backoff=backoff,
        sleep_fn=sleep_fn,
    )
    return last_read, last_read["status"], outcome


def escalate_to_human(*, reason: str) -> dict:
    """Terminal hand-off to a human. No refund is ever issued from here."""
    return {"action": "escalate_to_human", "reason": reason, "refund_issued": False}


def final_response(order_id: str) -> dict:
    """Terminal success: cancellation and refund both confirmed."""
    return {
        "action": "final_response",
        "status": "completed",
        "summary": f"Order {order_id} cancelled and refund completed (both verified).",
        "refund_issued": True,
    }
