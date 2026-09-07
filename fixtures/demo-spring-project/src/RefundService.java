package com.demo.refund;

import java.math.BigDecimal;

public class RefundService {

    public RefundResult apply(RefundRequest request) {
        // TODO: idempotent apply
        return new RefundResult("demo-id", request.getOrderId(), BigDecimal.ZERO);
    }
}
