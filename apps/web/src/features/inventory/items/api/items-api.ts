import { apiClient } from "@/api/client";

export interface InventoryItemPublic {
  id: string;
  organization_id: string;
  category_id: string | null;
  sku: string;
  name: string;
  description: string | null;
  unit_of_measure: string;
  reorder_level: number;
  reorder_quantity: number;
  standard_cost: number;
  is_active: boolean;
  created_at: string;
}

export interface ItemListResponse {
  items: InventoryItemPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface ItemListParams {
  category_id?: string;
  is_active?: boolean;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface ItemCreatePayload {
  sku: string;
  name: string;
  category_id?: string;
  description?: string;
  unit_of_measure: string;
  reorder_level?: number;
  reorder_quantity?: number;
  standard_cost?: number;
}

export type ItemUpdatePayload = Partial<Omit<ItemCreatePayload, "sku">> & { is_active?: boolean };

export interface StockLevel {
  item_id: string;
  warehouse_id: string | null;
  quantity_on_hand: number;
  average_unit_cost: number;
  stock_value: number;
}

export interface LowStockItem {
  item_id: string;
  sku: string;
  name: string;
  reorder_level: number;
  quantity_on_hand: number;
}

export const itemsApi = {
  list: (params: ItemListParams) =>
    apiClient.get<ItemListResponse>("/inventory/items", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<InventoryItemPublic>(`/inventory/items/${id}`).then((r) => r.data),

  create: (payload: ItemCreatePayload) =>
    apiClient.post<InventoryItemPublic>("/inventory/items", payload).then((r) => r.data),

  update: (id: string, payload: ItemUpdatePayload) =>
    apiClient.patch<InventoryItemPublic>(`/inventory/items/${id}`, payload).then((r) => r.data),

  stockLevel: (id: string, warehouseId?: string) =>
    apiClient
      .get<StockLevel>(`/inventory/items/${id}/stock-level`, { params: { warehouse_id: warehouseId } })
      .then((r) => r.data),

  lowStock: (warehouseId?: string) =>
    apiClient
      .get<LowStockItem[]>("/inventory/low-stock", { params: { warehouse_id: warehouseId } })
      .then((r) => r.data),
};
