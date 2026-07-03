"""Backend enforcement: the refund store is the FINAL boundary, not the loop."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop
from tools import OrderStore, RefundStore, Tools, UnsafeRefundStore

ORDER_ID = "TN-ENFORCE-1"


def _no_sleep(_seconds: float) -> None:
    pass


def _reader(order_store):
    return lambda: order_store.peek_order_status(order_store.order_id)


def test_refund_rejected_when_order_not_cancelled():
    order = OrderStore(ORDER_ID, settle_after_reads=3)
    order.cancel_order(ORDER_ID, f"cancel_order:{ORDER_ID}")  # accepted; world still pending
    refund = RefundStore(ORDER_ID, settle_after_reads=1, order_reader=_reader(order))

    resp = refund.issue_refund(ORDER_ID, f"issue_refund:{ORDER_ID}")

    assert resp["status"] == "rejected"
    assert resp["reason"] == "order_not_cancelled"
    assert refund.refund_effect_count == 0  # no side effect on rejection


def test_refund_succeeds_after_authoritative_cancellation():
    order = OrderStore(ORDER_ID, settle_after_reads=0)  # settles immediately
    order.cancel_order(ORDER_ID, f"cancel_order:{ORDER_ID}")
    refund = RefundStore(ORDER_ID, settle_after_reads=1, order_reader=_reader(order))

    resp = refund.issue_refund(ORDER_ID, f"issue_refund:{ORDER_ID}")

    assert resp["status"] == "accepted"
    assert refund.refund_effect_count == 1


def test_rejection_does_not_consume_the_idempotency_key():
    order = OrderStore(ORDER_ID, settle_after_reads=1)
    order.cancel_order(ORDER_ID, f"cancel_order:{ORDER_ID}")
    refund = RefundStore(ORDER_ID, settle_after_reads=1, order_reader=_reader(order))
    key = f"issue_refund:{ORDER_ID}"

    rejected = refund.issue_refund(ORDER_ID, key)
    assert rejected["status"] == "rejected"

    order.get_order_status(ORDER_ID)  # consuming read: the world settles to cancelled
    retried = refund.issue_refund(ORDER_ID, key)

    assert retried["status"] == "accepted"
    assert retried["idempotent_replay"] is False  # first APPLIED attempt
    assert refund.refund_effect_count == 1


def test_unsafe_store_pays_out_despite_pending_world():
    order = OrderStore(ORDER_ID, settle_after_reads=3)
    order.cancel_order(ORDER_ID, f"cancel_order:{ORDER_ID}")  # world still pending
    refund = UnsafeRefundStore(ORDER_ID, settle_after_reads=1, order_reader=_reader(order))

    resp = refund.issue_refund(ORDER_ID, f"issue_refund:{ORDER_ID}")

    assert resp["status"] == "accepted"  # the Part 1 world: nothing stops it
    assert refund.refund_effect_count == 1


def test_naive_loop_with_default_store_is_stopped_by_backend():
    """Gate OFF and default store: the backend still refuses to move money."""
    tools = Tools(
        order=OrderStore(ORDER_ID, settle_after_reads=3, settles_to="cancelled"),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )
    state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_backend_enforcement",
        verify_enabled=False,
        budget=Budget(max_steps=20),
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )

    assert trace.stop_reason == "refund_rejected_by_backend"
    assert tools.refund.refund_effect_count == 0
    last = trace.records[-1]
    assert last.decided_action == "issue_refund"
    assert last.tool_response["status"] == "rejected"
    assert last.resulting_state["world_order_status"] == "pending"
