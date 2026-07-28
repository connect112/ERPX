import { apiClient } from "@/api/client";

export interface WarehousePublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  name: string;
  code: string;
  address_line1: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  is_active: boolean;
  created_at: string;
}

export interface WarehouseCreatePayload {
  name: string;
  code: string;
  branch_id?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
}

export interface WarehouseUpdatePayload {
  name?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  is_active?: boolean;
}

export const warehousesApi = {
  list: (isActive?: boolean) =>
    apiClient
      .get<WarehousePublic[]>("/inventory/warehouses", { params: { is_active: isActive } })
      .then((r) => r.data),

  create: (payload: WarehouseCreatePayload) =>
    apiClient.post<WarehousePublic>("/inventory/warehouses", payload).then((r) => r.data),

  update: (id: string, payload: WarehouseUpdatePayload) =>
    apiClient.patch<WarehousePublic>(`/inventory/warehouses/${id}`, payload).then((r) => r.data),
};
