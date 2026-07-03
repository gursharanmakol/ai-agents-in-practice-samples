"""Run the NAIVE agent loop and write traces/naive_trace.json.

This is the SAME loop and order store as the safe run -- with the verification
gate REMOVED (``verify_enabled=False``) AND the refund store swapped for the
explicitly labeled, teaching-only ``UnsafeRefundStore``, which models Part 1's
world: a backend with no enforcement boundary of its own. The loop trusts
``cancel_order``'s ``accepted`` acknowledgement as if it were the world, so it
issues the refund immediately, BEFORE the order has settled to "cancelled".

Look at the ``issue_refund`` step in the trace: the loop state treats the order
as ``cancelled``, but ``world_order_status`` is still ``pending``. That is the
bug this lab warns about: a tool response describes the request, not the world.
(With the default, production-shaped ``RefundStore``, this premature attempt is
rejected with ``order_not_cancelled`` -- see tests/test_backend_enforcement.py.)

TechNova is a fictional company; all data here is made up for teaching.

Run from the part6 directory:
    python examples/run_naive.py     (macOS / Linux)
    python examples\\run_naive.py    (Windows)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the part6 packages importable no matter where this is launched from.
PART6 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PART6))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop  # noqa: E402
from tools import OrderStore, Tools, UnsafeRefundStore  # noqa: E402

ORDER_ID = "TN-100457"


def main() -> None:
    # Same order store as run_safe.py; the gate is off and the refund store is
    # the teaching-only UnsafeRefundStore (no backend enforcement, like Part 1).
    tools = Tools(
        order=OrderStore(ORDER_ID, settle_after_reads=3, settles_to="cancelled"),
        refund=UnsafeRefundStore(ORDER_ID, settle_after_reads=1),
    )

    state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="naive_no_verification",
        verify_enabled=False,  # the only difference from run_safe.py
        budget=Budget(max_steps=12),
        retries=1,
        backoff=0.0,
    )

    out = PART6 / "traces" / "naive_trace.json"
    trace.write(out)

    # Find the refund step and show how early the refund went out.
    refund_step = next(
        (r for r in trace.records if r.decided_action == "issue_refund"), None
    )

    print("NAIVE run complete.")
    print(f"  stop_reason       : {trace.stop_reason}")
    print(f"  cancellation      : {state.cancellation_status} (loop-state belief)")
    print(f"  refund            : {state.refund_status}")
    print(f"  refund applied x  : {tools.refund.refund_effect_count}")
    if refund_step is not None:
        print(
            "  at refund time, the TRUE world order status was: "
            f"{refund_step.resulting_state['world_order_status']} "
            "(refund issued before the world was confirmed!)"
        )
    print(f"  trace written to  : {out}")


if __name__ == "__main__":
    main()
