"""The agent loop package: state, decider, verification gate, actions, and trace.

Public surface kept small on purpose -- two example scripts and pytest are the
whole interface.
"""

from __future__ import annotations

from .agent_loop import PRINCIPLE, load_skill, run_agent_loop
from .budget import Budget
from .decider import BaseDecider, DeterministicDecider, LLMDeciderStub
from .state import CancellationStatus, RefundStatus, State, VerificationStatus
from .trace import StepRecord, Trace
from .verify import verify_action_landed

__all__ = [
    "run_agent_loop",
    "load_skill",
    "PRINCIPLE",
    "Budget",
    "BaseDecider",
    "DeterministicDecider",
    "LLMDeciderStub",
    "State",
    "CancellationStatus",
    "RefundStatus",
    "VerificationStatus",
    "Trace",
    "StepRecord",
    "verify_action_landed",
]
