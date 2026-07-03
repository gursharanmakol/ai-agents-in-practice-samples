"""Budget and stop rules.

A real agent must always be able to stop. This module enforces three limits:

- a step cap (don't loop forever),
- a simple accumulated cost budget, and
- a silence/timeout guard, modeled deterministically: it flags a step whose
  recorded latency exceeded the guard. A real integration must enforce
  wall-clock deadlines around external calls; this lab cannot preempt a
  function that never returns.

Whichever trips first ends the loop cleanly with a recorded ``stop_reason``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Per-action cost, accumulated into the budget. Reads are cheaper than writes.
ACTION_COST: dict[str, float] = {
    "get_order_status": 0.5,
    "cancel_order": 1.0,
    "wait_and_recheck": 0.5,
    "issue_refund": 1.0,
    "get_refund_status": 0.5,
    "escalate_to_human": 0.0,
    "final_response": 0.0,
}


@dataclass
class Budget:
    """Tracks spend and decides when the loop must stop."""

    max_steps: int = 12
    max_cost: float = 100.0
    step_timeout_ms: float = 5000.0
    spent_cost: float = 0.0

    def can_spend(self, cost: float) -> bool:
        """Preflight: True if charging ``cost`` would stay within ``max_cost``.

        Checked BEFORE an action runs, so the worst case is a clean stop, not
        a runaway that is reconciled after the money was spent.
        """
        return self.spent_cost + cost <= self.max_cost

    def charge(self, cost: float) -> None:
        self.spent_cost += cost

    def step_cap_reached(self, step_count: int) -> bool:
        return step_count >= self.max_steps

    def cost_exhausted(self) -> bool:
        return self.spent_cost >= self.max_cost

    def timed_out(self, latency_ms: float) -> bool:
        """A step that takes longer than the guard is treated as silence/hang."""
        return latency_ms > self.step_timeout_ms

    def check(self, step_count: int, last_latency_ms: float) -> Optional[str]:
        """Return a ``stop_reason`` if any limit is hit, else ``None``."""
        if self.timed_out(last_latency_ms):
            return "timeout_silence_guard"
        if self.cost_exhausted():
            return "cost_budget_exhausted"
        if self.step_cap_reached(step_count):
            return "step_cap_reached"
        return None
