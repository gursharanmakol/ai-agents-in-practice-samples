"""In-memory fake order store and order tools for the agent loop.

The whole lesson of this lab lives here: ``cancel_order`` follows an
ACCEPT-THEN-SETTLE model. Calling it returns an immediate ``{"status":
"accepted"}`` acknowledgement (a 200-OK-style "we received your request"), but
the *readable* order status may stay ``"pending"`` (or ``"blocked"``) for a
configurable number of reads before it settles to its final value.

A tool response describes the REQUEST, not the WORLD. The agent must re-read
(verify) the world before trusting that the cancellation actually landed.
"""

from __future__ import annotations

from typing import Optional

# Readable world-statuses an order can report.
OPEN = "open"          # cancellation not requested yet
PENDING = "pending"    # cancel accepted, but not yet settled (the gap)
CANCELLED = "cancelled"  # terminal: cancellation confirmed
BLOCKED = "blocked"    # review-hold: will never settle to cancelled on its own


class OrderStore:
    """A fake, in-memory order whose cancellation settles lazily.

    Settle behavior is configurable per scenario so every run is deterministic.
    """

    def __init__(
        self,
        order_id: str,
        *,
        settle_after_reads: Optional[int] = 1,
        settles_to: str = CANCELLED,
    ) -> None:
        """
        Args:
            order_id: The order this store represents.
            settle_after_reads: How many *consuming* ``get_order_status`` reads
                must happen AFTER the cancel is accepted before the readable
                status leaves ``"pending"``. ``None`` means "never settles"
                (stays pending forever) -- this drives the budget-stop scenario.
            settles_to: The status the order settles to once
                ``settle_after_reads`` is reached. ``"cancelled"`` is the happy
                path; ``"blocked"`` is a review-hold that never becomes a clean
                cancellation (drives the escalation scenario).
        """
        self.order_id = order_id
        self.settle_after_reads = settle_after_reads
        self.settles_to = settles_to
        self._cancel_accepted = False
        self._reads_since_cancel = 0
        # Idempotency keys we have already applied, so a retry is a safe replay.
        self._applied_keys: set[str] = set()
        # How many times a cancel *actually* took effect (for idempotency tests).
        self.cancel_effect_count = 0

    def cancel_order(self, order_id: str, idempotency_key: str) -> dict:
        """Request cancellation. Returns an acceptance ack, NOT a confirmation.

        The idempotency key makes a retry safe: a repeated call with the same
        key is a replay that does not double-apply the cancellation.
        """
        if idempotency_key in self._applied_keys:
            # Same request, seen before: acknowledge again but do nothing new.
            return {"order_id": order_id, "status": "accepted", "idempotent_replay": True}
        self._applied_keys.add(idempotency_key)
        self._cancel_accepted = True
        self.cancel_effect_count += 1
        return {"order_id": order_id, "status": "accepted", "idempotent_replay": False}

    def _current_status(self) -> str:
        """Compute the readable status from the current settle clock."""
        if not self._cancel_accepted:
            return OPEN
        if self.settle_after_reads is None:
            return PENDING  # never settles
        if self._reads_since_cancel >= self.settle_after_reads:
            return self.settles_to
        return PENDING

    def get_order_status(self, order_id: str) -> dict:
        """Authoritative read of the order's current world status (consuming).

        Each call advances the settle clock once the cancel has been accepted.
        This is the read path the verification gate relies on; it never looks at
        ``cancel_order``'s return value.
        """
        if self._cancel_accepted:
            self._reads_since_cancel += 1
        return {"order_id": order_id, "status": self._current_status()}

    def peek_order_status(self, order_id: str) -> dict:
        """Non-consuming diagnostic peek (does NOT advance the settle clock).

        Used only to record the true world status in the trace, so the
        naive-vs-safe gap is visible to a reader. The decider never calls this.
        """
        return {"order_id": order_id, "status": self._current_status()}
