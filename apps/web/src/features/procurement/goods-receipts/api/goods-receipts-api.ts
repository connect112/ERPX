import { apiClient } from "@/api/client";

export interface GoodsReceiptLinePublic {
  id: string;
  purchase_order_line_id: string;
  quantity_received: number;
  unit_cost: number;
}

export interface GoodsReceiptPublic {
  id: string;
  organization_id: string;
  purchase_order_id: string;
  warehouse_id: string;
  received_by_user_id: string | null;
  receipt_number: string;
  receipt_date: string;
  notes: string | null;
  created_at: string;
  lines: GoodsReceiptLinePublic[];
}

export interface GoodsReceiptLinePayload {
  purchase_order_line_id: string;
  quantity_received: number;
  unit_cost: number;
}

export interface GoodsReceiptCreatePayload {
  purchase_order_id: string;
  warehouse_id: string;
  receipt_number: string;
  receipt_date: string;
  notes?: string;
  lines: GoodsReceiptLinePayload[];
}

export const goodsReceiptsApi = {
  get: (id: string) => apiClient.get<GoodsReceiptPublic>(`/procurement/goods-receipts/${id}`).then((r) => r.data),

  listByPurchaseOrder: (poId: string) =>
    apiClient
      .get<GoodsReceiptPublic[]>(`/procurement/purchase-orders/${poId}/goods-receipts`)
      .then((r) => r.data),

  create: (payload: GoodsReceiptCreatePayload) =>
    apiClient.post<GoodsReceiptPublic>("/procurement/goods-receipts", payload).then((r) => r.data),
};
