"""Runtime validation of tool responses against their contracts.

A typed output shape becomes a control surface only when it is CHECKED at
runtime. This validator rejects malformed or unrecognized responses before
they enter trusted working state. It is deliberately lightweight: required
keys, basic types, and the status vocabulary declared in the contract.
"""

from __future__ import annotations

from tools.contracts import CONTRACTS


class ToolResponseInvalid(ValueError):
    """A tool response failed contract validation and must not enter state."""


def _allowed_statuses(contract) -> set[str]:
    spec = contract.output_shape.get("status", "")
    return {part.strip() for part in spec.split("|") if part.strip()}


def validate_tool_response(tool_name: str, response, contracts=None) -> dict:
    """Validate ``response`` against the tool's contract. Returns it unchanged.

    Raises ToolResponseInvalid on a missing required field, a wrong type, or a
    status outside the contract's declared vocabulary.
    """
    contracts = CONTRACTS if contracts is None else contracts
    contract = contracts.get(tool_name)
    if contract is None:
        raise ToolResponseInvalid(f"no contract registered for tool {tool_name!r}")
    if not isinstance(response, dict):
        raise ToolResponseInvalid(
            f"{tool_name}: expected a structured dict response, got {type(response).__name__}"
        )
    for field in ("order_id", "status"):
        if field not in response:
            raise ToolResponseInvalid(f"{tool_name}: missing required field {field!r}")
        if not isinstance(response[field], str):
            raise ToolResponseInvalid(
                f"{tool_name}: field {field!r} must be str, got {type(response[field]).__name__}"
            )
    allowed = _allowed_statuses(contract)
    if allowed and response["status"] not in allowed:
        raise ToolResponseInvalid(
            f"{tool_name}: unrecognized status {response['status']!r} (allowed: {sorted(allowed)})"
        )
    if tool_name in ("cancel_order", "issue_refund") and response["status"] == "accepted":
        if "idempotent_replay" not in response:
            raise ToolResponseInvalid(
                f"{tool_name}: accepted response missing required field 'idempotent_replay'"
            )
    if response["status"] == "rejected":
        if "reason" not in response or not isinstance(response.get("reason"), str):
            raise ToolResponseInvalid(
                f"{tool_name}: rejected response requires a string 'reason'"
            )
    if "idempotent_replay" in response and not isinstance(response["idempotent_replay"], bool):
        raise ToolResponseInvalid(f"{tool_name}: idempotent_replay must be bool")
    return response
