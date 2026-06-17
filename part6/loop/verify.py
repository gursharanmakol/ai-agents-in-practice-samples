"""The verification gate: confirm the world actually changed.

``verify_action_landed`` re-reads the world (with real exponential backoff
between attempts) until it observes the expected state or runs out of retries.

The single most important property: the READ path is INDEPENDENT of the WRITE
path. We pass a ``read`` callable that re-queries the world (e.g.
``get_order_status``); we never inspect the return value of the write that we
are trying to confirm (e.g. ``cancel_order``'s ``accepted`` ack). An ack means
"request received", not "world changed" -- only an independent read can confirm
the latter.
"""

from __future__ import annotations

import time
from typing import Callable, Tuple


def verify_action_landed(
    read: Callable[[], dict],
    expected: str,
    retries: int,
    backoff: float,
    sleep_fn: Callable[[float], None] = time.sleep,
    key: str = "status",
) -> Tuple[str, dict]:
    """Re-read until ``read()[key] == expected`` or retries are exhausted.

    Args:
        read: Independent read of the world. Returns a dict like
            ``{"status": "pending"}``. Called once per attempt.
        expected: The value of ``read()[key]`` that counts as confirmation.
        retries: Number of *additional* attempts after the first read. With
            ``retries=1`` the world is read up to twice.
        backoff: Base backoff in seconds. The wait before attempt ``n`` is
            ``backoff * (2 ** n)`` (exponential). Set to ``0`` for fast runs.
        sleep_fn: Injectable sleep so tests can pass a no-op and stay fast and
            deterministic.
        key: Which field of the read result to compare against ``expected``.

    Returns:
        A ``(outcome, last_read)`` tuple where ``outcome`` is ``"verified"`` if
        the expected value was observed, otherwise ``"unverified"``, and
        ``last_read`` is the final raw read dict (so callers can see what the
        world actually reported, e.g. ``"blocked"``).
    """
    last_read: dict = {}
    for attempt in range(retries + 1):
        last_read = read()
        if last_read.get(key) == expected:
            return "verified", last_read
        # Don't sleep after the final attempt -- we're about to give up.
        if attempt < retries:
            sleep_fn(backoff * (2 ** attempt))
    return "unverified", last_read
