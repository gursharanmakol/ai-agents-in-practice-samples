---
name: cancel-and-refund
description: >
  Cancel an order and issue any refund owed, when cancellation is legitimate.
  Use when a customer asks to cancel an order and get their money back.
---

1. Confirm the cancellation is allowed:
   order not yet shipped; request is legitimate.
2. Call `cancel_order` with an idempotency key.
3. Verify the cancellation landed:
   re-read order status; proceed only if terminal-cancelled.
4. Get human approval for the refund amount
   if it crosses the approval threshold.
5. Issue the refund with an idempotency key.
6. Verify the refund landed:
   re-read refund status.
7. If verification fails, do not continue.
   Wait and re-read with backoff, or escalate.
