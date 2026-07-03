"""Declarative tool contracts.

This is metadata the decider and loop can reference: for each tool, when to
use it, what it takes, what it returns, how it can fail, whether it needs an
idempotency key,
and -- crucially -- how to *verify* that a state-mutating call actually landed.

Keep this declarative. It documents the verification method; it does not
execute it. The loop's verification gate is what acts on these expectations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ToolContract:
    """A single tool's contract: shape, failure modes, and how to verify it."""

    name: str
    description: str
    when_to_use: str
    input_shape: dict
    output_shape: dict
    failure_modes: List[str]
    idempotency: str
    verification_method: str


CONTRACTS: dict[str, ToolContract] = {
    "get_order_status": ToolContract(
        name="get_order_status",
        description="Read the authoritative status of an order.",
        when_to_use=(
            "Use to establish or re-confirm order state before and after "
            "mutations. Read-only; safe at any time."
        ),
        input_shape={"order_id": "str"},
        output_shape={"order_id": "str", "status": "open|pending|cancelled|blocked"},
        failure_modes=["transient read error", "stale read"],
        idempotency="not applicable (read-only)",
        verification_method="n/a (this IS the read used to verify other actions)",
    ),
    "cancel_order": ToolContract(
        name="cancel_order",
        description="Request cancellation of an order (accept-then-settle).",
        when_to_use=(
            "Use only when the order is open and cancellation has not been "
            "requested. Do not use it to check status, and do not retry with "
            "a new key."
        ),
        input_shape={"order_id": "str", "idempotency_key": "str"},
        output_shape={"order_id": "str", "status": "accepted", "idempotent_replay": "bool"},
        failure_modes=[
            "accepted-but-not-settled (status still pending)",
            "blocked by review-hold",
            "order already shipped (not cancellable)",
        ],
        idempotency="key required (state-mutating)",
        verification_method="re-read order status; expect terminal 'cancelled'",
    ),
    "issue_refund": ToolContract(
        name="issue_refund",
        description="Issue the refund owed on a cancelled order.",
        when_to_use=(
            "Use only after the cancellation has been confirmed by an "
            "authoritative re-read. Never on an acknowledgement alone."
        ),
        input_shape={"order_id": "str", "idempotency_key": "str"},
        output_shape={
            "order_id": "str",
            "status": "accepted|rejected",
            "idempotent_replay": "bool (accepted only)",
            "reason": "str (rejected only)",
        },
        failure_modes=[
            "accepted-but-not-settled (status still pending)",
            "rejected: order_not_cancelled (precondition enforced by the store)",
            "double refund if called without a key",
        ],
        idempotency="key required (state-mutating)",
        verification_method="re-read refund status; expect 'completed'",
    ),
    "get_refund_status": ToolContract(
        name="get_refund_status",
        description="Read the authoritative status of a refund.",
        when_to_use="Use to verify a refund actually landed after issuing it.",
        input_shape={"order_id": "str"},
        output_shape={"order_id": "str", "status": "none|pending|completed"},
        failure_modes=["transient read error", "stale read"],
        idempotency="not applicable (read-only)",
        verification_method="n/a (this IS the read used to verify the refund)",
    ),
}
