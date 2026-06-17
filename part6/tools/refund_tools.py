"""In-memory fake refund store and refund tools for the agent loop.

Refunds use the same ACCEPT-THEN-SETTLE model as cancellations:
``issue_refund`` returns ``{"status": "accepted"}`` immediately, but
``get_refund_status`` reports ``"pending"`` for a configurable number of reads
before it settles to ``"completed"``. The agent must re-read to confirm the
refund actually landed.
"""

from __future__ import annotations

from typing import Optional

# Readable world-statuses a refund can report.
NONE = "none"            # no refund issued yet
PENDING = "pending"      # refund accepted, not yet settled
COMPLETED = "completed"  # terminal: refund confirmed


class RefundStore:
    """A fake, in-memory refund whose settlement is lazy and deterministic."""

    def __init__(self, order_id: str, *, settle_after_reads: Optional[int] = 1) -> None:
        """
        Args:
            order_id: The order this refund belongs to.
            settle_after_reads: How many *consuming* ``get_refund_status`` reads
                must happen AFTER the refund is accepted before the status leaves
                ``"pending"`` and becomes ``"completed"``. ``None`` means it
                never settles.
        """
        self.order_id = order_id
        self.settle_after_reads = settle_after_reads
        self._issued = False
        self._reads_since_issue = 0
        self._applied_keys: set[str] = set()
        # How many times a refund *actually* took effect (for idempotency tests).
        self.refund_effect_count = 0

    def issue_refund(self, order_id: str, idempotency_key: str) -> dict:
        """Request a refund. Returns an acceptance ack, NOT a confirmation.

        The idempotency key makes a retry safe: a repeated call with the same
        key is a replay and does not pay out twice.
        """
        if idempotency_key in self._applied_keys:
            return {"order_id": order_id, "status": "accepted", "idempotent_replay": True}
        self._applied_keys.add(idempotency_key)
        self._issued = True
        self.refund_effect_count += 1
        return {"order_id": order_id, "status": "accepted", "idempotent_replay": False}

    def _current_status(self) -> str:
        if not self._issued:
            return NONE
        if self.settle_after_reads is None:
            return PENDING
        if self._reads_since_issue >= self.settle_after_reads:
            return COMPLETED
        return PENDING

    def get_refund_status(self, order_id: str) -> dict:
        """Independent read of the refund's current world status (consuming).

        Advances the settle clock once the refund has been accepted. This is the
        read path the verification gate uses; it never trusts the issue ack.
        """
        if self._issued:
            self._reads_since_issue += 1
        return {"order_id": order_id, "status": self._current_status()}

    def peek_refund_status(self, order_id: str) -> dict:
        """Non-consuming diagnostic peek (does NOT advance the settle clock)."""
        return {"order_id": order_id, "status": self._current_status()}
