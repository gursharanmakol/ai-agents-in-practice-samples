"""Structured execution trace.

Every turn appends one ``StepRecord``. Each record keeps ``tool_response`` and
``verification_read`` as SEPARATE fields, even when they agree. That separation
is the lesson of this lab and is consumed by later diagnostics (Part 7):

- ``tool_response`` -- what the tool *said* (e.g. ``{"status": "accepted"}``).
- ``verification_read`` -- what an *independent re-read* of the world confirmed
  (e.g. ``"cancelled"``), or ``None`` when no verification was performed.

Traces are written as pretty-printed JSON so they are easy to diff and read.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class StepRecord:
    """One turn of the loop. The nine fields below are always present."""

    step: int
    observed_state: dict
    decided_action: str
    tool_called: Optional[str]
    tool_response: Any
    verification_read: Any
    resulting_state: dict
    cost: float
    latency_ms: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Trace:
    """A full run: ordered step records plus a terminal stop reason."""

    scenario: str
    principle: str
    records: List[StepRecord] = field(default_factory=list)
    stop_reason: Optional[str] = None
    final_state: Optional[dict] = None

    def add(self, record: StepRecord) -> None:
        self.records.append(record)

    def finish(self, stop_reason: Optional[str], final_state: dict) -> None:
        """Record why the loop stopped and the final confirmed state."""
        self.stop_reason = stop_reason
        self.final_state = final_state

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "principle": self.principle,
            "steps": [r.to_dict() for r in self.records],
            "stop_reason": self.stop_reason,
            "final_state": self.final_state,
        }

    def write(self, path) -> None:
        """Write pretty-printed JSON, creating the parent directory if needed."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
