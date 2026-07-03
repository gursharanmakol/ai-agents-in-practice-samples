"""Tools available to the agent loop: fake order and refund stores + contracts.

The ``Tools`` container is the single object passed to the decider and loop, so
swapping the fake stores for real services later means changing only how
``Tools`` is constructed -- not the loop, decider, or trace.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CONTRACTS, ToolContract
from .order_tools import OrderStore
from .refund_tools import RefundStore, UnsafeRefundStore


@dataclass
class Tools:
    """Bundles the order and refund tool-stores for one run."""

    order: OrderStore
    refund: RefundStore

    def __post_init__(self) -> None:
        # Default composition wires the refund store to the AUTHORITATIVE order
        # reader (non-consuming peek), making the store the final enforcement
        # boundary. UnsafeRefundStore ignores the check even when wired.
        if getattr(self.refund, "order_reader", None) is None:
            self.refund.order_reader = lambda: self.order.peek_order_status(self.order.order_id)

    @property
    def contracts(self) -> dict[str, ToolContract]:
        """The declarative contract metadata for every tool."""
        return CONTRACTS


__all__ = ["OrderStore", "RefundStore", "UnsafeRefundStore", "Tools", "CONTRACTS", "ToolContract"]
