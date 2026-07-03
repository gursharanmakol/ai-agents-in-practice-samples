"""Run the SAFE agent loop and write traces/safe_trace.json.

This is the full, verify-before-commit loop. The order takes a few reads to
settle, so the agent observes the pending state, waits and re-reads until an
AUTHORITATIVE re-read confirms the cancellation, and only THEN issues the refund --
which it also verifies before declaring success.

TechNova is a fictional company; all data here is made up for teaching.

Run from the part6 directory:
    python examples/run_safe.py     (macOS / Linux)
    python examples\\run_safe.py    (Windows)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the part6 packages importable no matter where this is launched from.
PART6 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PART6))

from loop import Budget, DeterministicDecider, load_skill, run_agent_loop  # noqa: E402
from tools import OrderStore, RefundStore, Tools  # noqa: E402

ORDER_ID = "TN-100457"


def main() -> None:
    # Pending-then-resolves: the order stays "pending" for a couple of reads,
    # then settles to "cancelled". The refund settles on the first re-read.
    tools = Tools(
        order=OrderStore(ORDER_ID, settle_after_reads=3, settles_to="cancelled"),
        refund=RefundStore(ORDER_ID, settle_after_reads=1),
    )

    state, trace = run_agent_loop(
        tools,
        DeterministicDecider(),
        order_id=ORDER_ID,
        skill=load_skill(),
        scenario="safe_verify_before_commit",
        verify_enabled=True,
        budget=Budget(max_steps=12),
        retries=1,
        backoff=0.0,  # zero backoff keeps the demo fast and deterministic
    )

    out = PART6 / "traces" / "safe_trace.json"
    trace.write(out)

    print("SAFE run complete.")
    print(f"  stop_reason       : {trace.stop_reason}")
    print(f"  cancellation      : {state.cancellation_status}")
    print(f"  refund            : {state.refund_status}")
    print(f"  refund applied x  : {tools.refund.refund_effect_count}")
    print(f"  steps             : {state.step_count}")
    print(f"  trace written to  : {out}")


if __name__ == "__main__":
    main()
