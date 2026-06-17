"""Declarative tool contracts.

This is metadata the decider and loop can reference: for each tool, what it
takes, what it returns, how it can fail, whether it needs an idempotency key,
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
    input_shape: dict
    output_shape: dict
    failure_modes: List[str]
    idempotency: str
    verification_method: str


CONTRACTS: dict[str, ToolContract] = {
    "get_order_status": ToolContract(
        name="get_order_status",
        input_shape={"order_id": "str"},
        output_shape={"order_id": "str", "status": "open|pending|cancelled|blocked"},
        failure_modes=["transient read error", "stale read"],
        idempotency="not applicable (read-only)",
        verification_method="n/a (this IS the read used to verify other actions)",
    ),
    "cancel_order": ToolContract(
        name="cancel_order",
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
        input_shape={"order_id": "str", "idempotency_key": "str"},
        output_shape={"order_id": "str", "status": "accepted", "idempotent_replay": "bool"},
        failure_modes=[
            "accepted-but-not-settled (status still pending)",
            "double refund if called without a key",
        ],
        idempotency="key required (state-mutating)",
        verification_method="re-read refund status; expect 'completed'",
    ),
    "get_refund_status": ToolContract(
        name="get_refund_status",
        input_shape={"order_id": "str"},
        output_shape={"order_id": "str", "status": "none|pending|completed"},
        failure_modes=["transient read error", "stale read"],
        idempotency="not applicable (read-only)",
        verification_method="n/a (this IS the read used to verify the refund)",
    ),
}
