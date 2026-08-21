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


class ConcurrentReopenOrderStore(OrderStore):
    """Test-only: after cancel settles, later peeks report a concurrent reopen.

    Models another actor changing the world between verify-before-commit and the
    refund write. Counting starts only after a consuming read has observed
    ``cancelled``, so the cancel-step diagnostic peek is ignored. The first
    cancelled peek after that (end of ``wait_and_recheck``) still reports
    ``cancelled``; subsequent peeks — including the refund store's authoritative
    reader — report ``reopen_as``.
    """

    def __init__(self, order_id: str, *, reopen_as: str = "open", **kwargs) -> None:
        super().__init__(order_id, **kwargs)
        self.reopen_as = reopen_as
        self._seen_cancelled_read = False
        self._cancelled_peeks = 0

    def get_order_status(self, order_id: str) -> dict:
        result = super().get_order_status(order_id)
        if result["status"] == "cancelled":
            self._seen_cancelled_read = True
        return result

    def peek_order_status(self, order_id: str) -> dict:
        base = super().peek_order_status(order_id)
        if self._seen_cancelled_read and base["status"] == "cancelled":
            self._cancelled_peeks += 1
            if self._cancelled_peeks > 1:
                return {"order_id": order_id, "status": self.reopen_as}
        return base


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


def test_unwired_store_fails_closed():
    refund = RefundStore(ORDER_ID, settle_after_reads=1)  # no reader
    resp = refund.issue_refund(ORDER_ID, f"issue_refund:{ORDER_ID}")
    assert resp["status"] == "rejected"
    assert resp["reason"] == "authoritative_order_reader_unavailable"
    assert refund.refund_effect_count == 0


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


def test_verified_then_concurrent_reopen_rejects_refund():
    """Verification succeeds, then another actor reopens the order before the write.

    Shows verify-before-commit is necessary for sequencing but insufficient for
    transactional correctness: RefundStore revalidates at write time and refuses
    to move money on the stale observation. The concurrent reopen is simulated by
    a deterministic test-local store subclass, not real concurrency.
    """
    tools = Tools(
        order=ConcurrentReopenOrderStore(
            ORDER_ID, settle_after_reads=0, settles_to="cancelled", reopen_as="open"
        ),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )
    _state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_toctou_reopen",
        verify_enabled=True,
        budget=Budget(max_steps=20),
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )

    verified = next(
        r
        for r in trace.records
        if r.decided_action == "wait_and_recheck" and r.verification_read == "cancelled"
    )
    assert verified.resulting_state["verification_status"] == "verified"
    assert verified.resulting_state["cancellation_status"] == "cancelled"
    assert verified.resulting_state["world_order_status"] == "cancelled"

    last = trace.records[-1]
    assert last.decided_action == "issue_refund"
    assert last.tool_response["status"] == "rejected"
    assert last.tool_response["reason"] == "order_not_cancelled"
    assert last.resulting_state["world_order_status"] == "open"
    assert last.resulting_state["world_refund_status"] == "none"
    assert "refund rejected by backend" in last.resulting_state["note"]

    assert trace.stop_reason == "refund_rejected_by_backend"
    assert tools.refund.refund_effect_count == 0
