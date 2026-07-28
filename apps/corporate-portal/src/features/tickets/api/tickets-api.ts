import { apiClient } from "@/api/client";

export interface SupportTicketPublic {
  id: string;
  organization_id: string;
  client_id: string;
  project_id: string | null;
  assigned_to_employee_id: string | null;
  ticket_number: string;
  subject: string;
  description: string;
  priority: "low" | "medium" | "high" | "urgent";
  status: "open" | "in_progress" | "on_hold" | "resolved" | "closed";
  raised_by_contact_name: string | null;
  sla_due_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface TicketCommentPublic {
  id: string;
  ticket_id: string;
  created_by_user_id: string | null;
  comment_text: string;
  is_internal: boolean;
  created_at: string;
}

export interface CreateTicketPayload {
  subject: string;
  description: string;
  priority: SupportTicketPublic["priority"];
  project_id?: string;
}

export const ticketsApi = {
  myTickets: () => apiClient.get<SupportTicketPublic[]>("/corporate/tickets/me").then((r) => r.data),

  createTicket: (payload: CreateTicketPayload) =>
    apiClient.post<SupportTicketPublic>("/corporate/tickets/me", payload).then((r) => r.data),

  getTicket: (ticketId: string) =>
    apiClient.get<SupportTicketPublic>(`/corporate/tickets/me/${ticketId}`).then((r) => r.data),

  listComments: (ticketId: string) =>
    apiClient
      .get<TicketCommentPublic[]>(`/corporate/tickets/me/${ticketId}/comments`)
      .then((r) => r.data),

  addComment: (ticketId: string, commentText: string) =>
    apiClient
      .post<TicketCommentPublic>(`/corporate/tickets/me/${ticketId}/comments`, {
        comment_text: commentText,
      })
      .then((r) => r.data),
};
