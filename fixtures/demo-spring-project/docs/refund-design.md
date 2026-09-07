# Refund module design (demo fixture)

## Overview

The refund module centers on `RefundService.apply(RefundRequest)`.

## Flow

1. Validate order status and payment capture.
2. Create refund record in `PENDING`.
3. Call payment gateway; on success set `COMPLETED`.

## Idempotency

Same `orderId` + `refundReason` must return the same refund id without double charge.

## Testing

Use fixture tests under `src/test` — do not hit production payment URLs.
