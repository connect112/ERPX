import { apiClient } from "@/api/client";
import type { PurchaseOrderStatus } from "@/features/procurement/purchase-orders/schemas/purchase-order-schemas";

export interface PurchaseOrderLinePublic {
  id: string;
  item_id: string;
  gst_rate_id: string | null;
  description: string;
  quantity_ordered: number;
  quantity_received: number;
  unit_price: number;
  line_subtotal: number;
  tax_amount: number;
  line_total: number;
}

export interface PurchaseOrderPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  vendor_id: string;
  po_number: string;
  order_date: string;
  expected_delivery_date: string | null;
  status: PurchaseOrderStatus;
  subtotal_amount: number;
  tax_amount: number;
  total_amount: number;
  notes: string | null;
  created_at: string;
  lines: PurchaseOrderLinePublic[];
}

export interface PurchaseOrderListResponse {
  items: PurchaseOrderPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface PurchaseOrderListParams {
  vendor_id?: string;
  status?: PurchaseOrderStatus;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}

export interface PurchaseOrderLinePayload {
  item_id: string;
  description: string;
  quantity_ordered: number;
  unit_price: number;
  gst_rate_id?: string;
}

export interface PurchaseOrderCreatePayload {
  vendor_id: string;
  po_number: string;
  order_date: string;
  expected_delivery_date?: string;
  notes?: string;
  lines: PurchaseOrderLinePayload[];
}

export interface PurchaseOrderUpdatePayload {
  expected_delivery_date?: string;
  notes?: string;
  lines?: PurchaseOrderLinePayload[];
}

export const purchaseOrdersApi = {
  list: (params: PurchaseOrderListParams) =>
    apiClient.get<PurchaseOrderListResponse>("/procurement/purchase-orders", { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<PurchaseOrderPublic>(`/procurement/purchase-orders/${id}`).then((r) => r.data),

  create: (payload: PurchaseOrderCreatePayload) =>
    apiClient.post<PurchaseOrderPublic>("/procurement/purchase-orders", payload).then((r) => r.data),

  update: (id: string, payload: PurchaseOrderUpdatePayload) =>
    apiClient.patch<PurchaseOrderPublic>(`/procurement/purchase-orders/${id}`, payload).then((r) => r.data),

  send: (id: string) =>
    apiClient.post<PurchaseOrderPublic>(`/procurement/purchase-orders/${id}/send`).then((r) => r.data),

  cancel: (id: string) =>
    apiClient.post<PurchaseOrderPublic>(`/procurement/purchase-orders/${id}/cancel`).then((r) => r.data),
};
