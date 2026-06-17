"""Trace shape: tool_response and verification_read are always SEPARATE fields."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop
from tools import OrderStore, RefundStore, Tools

ORDER_ID = "TN-TRACE-1"

REQUIRED_FIELDS = {
    "step",
    "observed_state",
    "decided_action",
    "tool_called",
    "tool_response",
    "verification_read",
    "resulting_state",
    "cost",
    "latency_ms",
}


def _no_sleep(_seconds: float) -> None:
    pass


def _run():
    tools = Tools(
        order=OrderStore(ORDER_ID, settle_after_reads=2, settles_to="cancelled"),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )
    _state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="test_trace_shape",
        verify_enabled=True,
        budget=Budget(max_steps=20),
        retries=1,
        backoff=0.0,
        sleep_fn=_no_sleep,
    )
    return trace


def test_every_record_has_the_required_distinct_fields():
    trace = _run()
    data = trace.to_dict()

    assert data["steps"], "trace should contain at least one step"
    for record in data["steps"]:
        # Both fields exist on every record, even when they would agree.
        assert "tool_response" in record
        assert "verification_read" in record
        assert REQUIRED_FIELDS.issubset(record.keys())


def test_final_record_carries_stop_reason():
    trace = _run()
    data = trace.to_dict()
    assert data["stop_reason"] is not None
    assert data["final_state"] is not None
