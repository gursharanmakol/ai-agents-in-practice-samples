# cancel_order_skill
name: cancel_order
description: Cancel an order and issue any refund owed, safely, when cancellation is legitimate.
procedure:
  1. Confirm the cancellation is allowed (order not yet shipped; request is legitimate).
  2. Get human approval for the refund amount if it crosses the approval threshold.
  3. Call cancel_order with an idempotency key.
  4. Verify the cancellation landed: re-read order status; proceed only if terminal-cancelled.
  5. Issue the refund with an idempotency key — only after step 4 confirms.
  6. Verify the refund landed: re-read refund status.
  7. If any verification fails: do not continue. Wait, retry with backoff, or escalate.
