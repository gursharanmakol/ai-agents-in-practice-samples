"""Runtime validation: malformed tool responses never enter working state."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop import ToolResponseInvalid, validate_tool_response


def test_valid_response_is_returned_unchanged():
    resp = {"order_id": "TN-1", "status": "pending"}
    assert validate_tool_response("get_order_status", resp) is resp


def test_missing_required_field_is_rejected():
    try:
        validate_tool_response("get_order_status", {"order_id": "TN-1"})
    except ToolResponseInvalid as err:
        assert "status" in str(err)
    else:
        raise AssertionError("missing field passed validation")


def test_wrong_type_is_rejected():
    try:
        validate_tool_response("get_order_status", {"order_id": "TN-1", "status": 5})
    except ToolResponseInvalid as err:
        assert "must be str" in str(err)
    else:
        raise AssertionError("wrong type passed validation")


def test_unrecognized_status_is_rejected():
    try:
        validate_tool_response("issue_refund", {"order_id": "TN-1", "status": "exploded"})
    except ToolResponseInvalid as err:
        assert "unrecognized status" in str(err)
    else:
        raise AssertionError("unknown status passed validation")


def test_accepted_cancel_missing_replay_flag_is_rejected():
    try:
        validate_tool_response("cancel_order", {"order_id": "TN-1", "status": "accepted"})
    except ToolResponseInvalid as err:
        assert "idempotent_replay" in str(err)
    else:
        raise AssertionError("accepted response missing replay flag passed validation")


def test_accepted_refund_missing_replay_flag_is_rejected():
    try:
        validate_tool_response("issue_refund", {"order_id": "TN-1", "status": "accepted"})
    except ToolResponseInvalid as err:
        assert "idempotent_replay" in str(err)
    else:
        raise AssertionError("accepted response missing replay flag passed validation")


def test_rejected_refund_missing_reason_is_rejected():
    try:
        validate_tool_response("issue_refund", {"order_id": "TN-1", "status": "rejected"})
    except ToolResponseInvalid as err:
        assert "reason" in str(err)
    else:
        raise AssertionError("rejected response missing reason passed validation")
