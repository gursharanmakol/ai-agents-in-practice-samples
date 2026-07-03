"""Idempotency: a repeated call with the same key does not double-apply."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop
from tools import OrderStore, RefundStore, Tools

ORDER_ID = "TN-IDEM-1"


def _no_sleep(_seconds: float) -> None:
    pass


def test_repeated_cancel_with_same_key_does_not_double_apply():
    store = OrderStore(ORDER_ID, settle_after_reads=1)
    key = f"cancel_order:{ORDER_ID}"

    first = store.cancel_order(ORDER_ID, key)
    second = store.cancel_order(ORDER_ID, key)

    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert store.cancel_effect_count == 1  # applied exactly once


def test_repeated_refund_with_same_key_does_not_double_pay():
    order = OrderStore(ORDER_ID, settle_after_reads=0)
    order.cancel_order(ORDER_ID, f"cancel_order:{ORDER_ID}")
    store = RefundStore(ORDER_ID, settle_after_reads=1,
                        order_reader=lambda: order.peek_order_status(ORDER_ID))
    key = f"issue_refund:{ORDER_ID}"

    first = store.issue_refund(ORDER_ID, key)
    second = store.issue_refund(ORDER_ID, key)

    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert store.refund_effect_count == 1  # paid out exactly once


def test_full_safe_run_applies_each_mutation_once():
    tools = Tools(
        order=OrderStore(ORDER_ID, settle_after_reads=2, settles_to="cancelled"),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )
    run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_idempotency",
        verify_enabled=True,
        budget=Budget(max_steps=20),
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )
    assert tools.order.cancel_effect_count == 1
    assert tools.refund.refund_effect_count == 1
