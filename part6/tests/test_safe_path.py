"""Safe path: the refund is issued ONLY after cancellation is verified."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop
from tools import OrderStore, RefundStore, Tools

ORDER_ID = "TN-SAFE-1"


def _no_sleep(_seconds: float) -> None:
    pass


def _run():
    tools = Tools(
        order=OrderStore(ORDER_ID, settle_after_reads=3, settles_to="cancelled"),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )
    state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_safe",
        verify_enabled=True,
        budget=Budget(max_steps=20),
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )
    return tools, state, trace


def test_refund_issued_only_after_cancellation_verified():
    tools, state, trace = _run()

    actions = [r.decided_action for r in trace.records]
    refund_index = actions.index("issue_refund")

    # An independent re-read must have CONFIRMED "cancelled" before the refund.
    verified_before_refund = any(
        r.verification_read == "cancelled" for r in trace.records[:refund_index]
    )
    assert verified_before_refund, "refund issued without a verified cancellation"

    # And the run must finish successfully with a single, confirmed refund.
    assert trace.stop_reason == "completed_successfully"
    assert state.cancellation_status == "cancelled"
    assert state.refund_status == "completed"
    assert tools.refund.refund_effect_count == 1


def test_safe_run_waits_through_pending():
    _tools, _state, trace = _run()
    actions = [r.decided_action for r in trace.records]
    # The order is pending for a couple of reads, so the loop must adapt by
    # re-checking across turns rather than refunding immediately.
    assert actions.count("wait_and_recheck") >= 1
    assert actions.index("issue_refund") > actions.index("cancel_order")
