import { apiClient } from "@/api/client";
import type { StockTransactionType } from "@/features/inventory/stock/schemas/stock-schemas";

export interface StockTransactionPublic {
  id: string;
  organization_id: string;
  warehouse_id: string;
  item_id: string;
  transaction_type: StockTransactionType;
  quantity: number;
  unit_cost: number;
  transaction_date: string;
  reference_type: string | null;
  reference_id: string | null;
  notes: string | null;
  created_at: string;
}

export interface StockTransactionListResponse {
  items: StockTransactionPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface ItemTransactionListParams {
  warehouse_id?: string;
  skip?: number;
  limit?: number;
}

export interface ReceiveStockPayload {
  item_id: string;
  warehouse_id: string;
  quantity: number;
  unit_cost: number;
  notes?: string;
}

export interface IssueStockPayload {
  item_id: string;
  warehouse_id: string;
  quantity: number;
  notes?: string;
}

export interface AdjustStockPayload {
  item_id: string;
  warehouse_id: string;
  quantity_change: number;
  unit_cost?: number;
  reason: string;
}

export interface TransferStockPayload {
  item_id: string;
  from_warehouse_id: string;
  to_warehouse_id: string;
  quantity: number;
  notes?: string;
}

export const stockApi = {
  listItemTransactions: (itemId: string, params: ItemTransactionListParams) =>
    apiClient
      .get<StockTransactionListResponse>(`/inventory/items/${itemId}/transactions`, { params })
      .then((r) => r.data),

  receive: (payload: ReceiveStockPayload) =>
    apiClient.post<StockTransactionPublic>("/inventory/stock/receive", payload).then((r) => r.data),

  issue: (payload: IssueStockPayload) =>
    apiClient.post<StockTransactionPublic>("/inventory/stock/issue", payload).then((r) => r.data),

  adjust: (payload: AdjustStockPayload) =>
    apiClient.post<StockTransactionPublic>("/inventory/stock/adjust", payload).then((r) => r.data),

  transfer: (payload: TransferStockPayload) =>
    apiClient.post<StockTransactionPublic[]>("/inventory/stock/transfer", payload).then((r) => r.data),
};
