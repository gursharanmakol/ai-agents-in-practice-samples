"""Tools available to the agent loop: fake order and refund stores + contracts.

The ``Tools`` container is the single object passed to the decider and loop, so
swapping the fake stores for real services later means changing only how
``Tools`` is constructed -- not the loop, decider, or trace.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CONTRACTS, ToolContract
from .order_tools import OrderStore
from .refund_tools import RefundStore


@dataclass
class Tools:
    """Bundles the order and refund tool-stores for one run."""

    order: OrderStore
    refund: RefundStore

    @property
    def contracts(self) -> dict[str, ToolContract]:
        """The declarative contract metadata for every tool."""
        return CONTRACTS


__all__ = ["OrderStore", "RefundStore", "Tools", "CONTRACTS", "ToolContract"]
