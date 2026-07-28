import { apiClient } from "@/api/client";
import type { TicketPriority, TicketStatus } from "@/features/corporate/tickets/schemas/ticket-schemas";

export interface SupportTicketPublic {
  id: string;
  organization_id: string;
  client_id: string;
  project_id: string | null;
  assigned_to_employee_id: string | null;
  ticket_number: string;
  subject: string;
  description: string;
  priority: TicketPriority;
  status: TicketStatus;
  raised_by_contact_name: string | null;
  sla_due_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface TicketListResponse {
  items: SupportTicketPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface TicketListParams {
  client_id?: string;
  priority?: TicketPriority;
  status?: TicketStatus;
  assigned_to_employee_id?: string;
  skip?: number;
  limit?: number;
}

export interface TicketCreatePayload {
  client_id: string;
  project_id?: string;
  ticket_number: string;
  subject: string;
  description: string;
  priority?: TicketPriority;
  assigned_to_employee_id?: string;
  raised_by_contact_name?: string;
  sla_due_at?: string;
}

export interface TicketUpdatePayload {
  priority?: TicketPriority;
  assigned_to_employee_id?: string;
  sla_due_at?: string;
}

export interface TicketCommentPublic {
  id: string;
  ticket_id: string;
  created_by_user_id: string | null;
  comment_text: string;
  is_internal: boolean;
  created_at: string;
}

export interface TicketCommentCreatePayload {
  comment_text: string;
  is_internal?: boolean;
}

export const ticketsApi = {
  list: (params: TicketListParams) =>
    apiClient.get<TicketListResponse>("/corporate/tickets", { params }).then((r) => r.data),

  listOverdue: () =>
    apiClient.get<SupportTicketPublic[]>("/corporate/tickets/overdue").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<SupportTicketPublic>(`/corporate/tickets/${id}`).then((r) => r.data),

  create: (payload: TicketCreatePayload) =>
    apiClient.post<SupportTicketPublic>("/corporate/tickets", payload).then((r) => r.data),

  update: (id: string, payload: TicketUpdatePayload) =>
    apiClient.patch<SupportTicketPublic>(`/corporate/tickets/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, status: TicketStatus) =>
    apiClient.post<SupportTicketPublic>(`/corporate/tickets/${id}/status`, { status }).then((r) => r.data),

  addComment: (id: string, payload: TicketCommentCreatePayload) =>
    apiClient.post<TicketCommentPublic>(`/corporate/tickets/${id}/comments`, payload).then((r) => r.data),

  listComments: (id: string, includeInternal?: boolean) =>
    apiClient
      .get<TicketCommentPublic[]>(`/corporate/tickets/${id}/comments`, {
        params: { include_internal: includeInternal },
      })
      .then((r) => r.data),
};
