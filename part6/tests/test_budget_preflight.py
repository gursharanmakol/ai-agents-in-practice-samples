"""Budget preflight: the ceiling is checked BEFORE an action runs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop
from tools import OrderStore, RefundStore, Tools

ORDER_ID = "TN-PREFLIGHT-1"


def _no_sleep(_seconds: float) -> None:
    pass


def test_unaffordable_action_is_never_executed():
    tools = Tools(
        order=OrderStore(ORDER_ID, settle_after_reads=3, settles_to="cancelled"),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )
    # get_order_status costs 0.5; cancel_order costs 1.0. With max_cost=1.4 the
    # loop can afford the read but NOT the cancel: preflight must stop it
    # before the tool runs, not reconcile after.
    budget = Budget(max_steps=20, max_cost=1.4)
    state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_budget_preflight",
        verify_enabled=True,
        budget=budget,
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )

    assert trace.stop_reason == "cost_budget_exhausted"
    assert tools.order.cancel_effect_count == 0  # the tool was never called
    assert state.step_count == 1  # only the affordable read ran
    assert budget.spent_cost == 0.5  # nothing was charged for the stopped action
