"""Blocked path: a review-hold cancellation escalates and NEVER refunds."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop
from tools import OrderStore, RefundStore, Tools

ORDER_ID = "TN-BLOCKED-1"


def _no_sleep(_seconds: float) -> None:
    pass


def _run():
    tools = Tools(
        # Settles to "blocked" and never becomes a clean cancellation.
        order=OrderStore(ORDER_ID, settle_after_reads=1, settles_to="blocked"),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )
    state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_blocked",
        verify_enabled=True,
        budget=Budget(max_steps=20),
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )
    return tools, state, trace


def test_blocked_cancellation_escalates_without_refund():
    tools, state, trace = _run()

    actions = [r.decided_action for r in trace.records]
    assert "escalate_to_human" in actions
    assert trace.stop_reason == "escalated_to_human"

    # A blocked cancellation must NEVER lead to a refund.
    assert "issue_refund" not in actions
    assert tools.refund.refund_effect_count == 0
    assert state.refund_status == "not_started"
    assert state.cancellation_status == "blocked"
