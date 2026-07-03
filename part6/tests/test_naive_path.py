"""Naive path: the refund is issued BEFORE verification -- the bug we warn about."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop
from tools import OrderStore, Tools, UnsafeRefundStore

ORDER_ID = "TN-NAIVE-1"


def _no_sleep(_seconds: float) -> None:
    pass


def _run():
    # Same store config as the safe test; the gate is removed AND the refund
    # store is the explicitly labeled UnsafeRefundStore, modeling Part 1's
    # unenforced backend so the money can actually move (the bug on display).
    tools = Tools(
        order=OrderStore(ORDER_ID, settle_after_reads=3, settles_to="cancelled"),
        refund=UnsafeRefundStore(ORDER_ID, settle_after_reads=1),
    )
    state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_naive",
        verify_enabled=False,
        budget=Budget(max_steps=20),
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )
    return tools, state, trace


def test_refund_issued_before_any_verification():
    tools, _state, trace = _run()

    actions = [r.decided_action for r in trace.records]
    assert "issue_refund" in actions, "naive run should still issue a refund"

    # No step ever confirmed the cancellation by an authoritative re-read.
    assert all(r.verification_read != "cancelled" for r in trace.records)

    # At the moment of the refund, the TRUE world order status was still pending:
    # the refund went out before the cancellation was actually confirmed.
    refund_step = trace.records[actions.index("issue_refund")]
    assert refund_step.resulting_state["world_order_status"] == "pending"
    assert refund_step.resulting_state["cancellation_status"] == "cancelled"  # belief only

    # The refund really did pay out (the dangerous part).
    assert tools.refund.refund_effect_count == 1
