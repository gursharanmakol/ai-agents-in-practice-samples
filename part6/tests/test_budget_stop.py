"""Budget stop: an order that never settles ends in a clean, recorded stop."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop
from tools import OrderStore, RefundStore, Tools

ORDER_ID = "TN-BUDGET-1"


def _no_sleep(_seconds: float) -> None:
    pass


def test_step_cap_triggers_clean_stop():
    tools = Tools(
        # settle_after_reads=None -> the order stays "pending" forever, so the
        # loop keeps waiting/re-checking until the budget stops it.
        order=OrderStore(ORDER_ID, settle_after_reads=None),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )
    state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_budget",
        verify_enabled=True,
        budget=Budget(max_steps=5),
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )

    assert trace.stop_reason == "step_cap_reached"
    assert state.step_count == 5

    # A permanent stall must never result in a refund.
    assert tools.refund.refund_effect_count == 0
    assert state.refund_status != "completed"
