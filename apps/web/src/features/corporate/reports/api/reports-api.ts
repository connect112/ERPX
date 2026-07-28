import { apiClient } from "@/api/client";

export interface ClientSummary {
  client_id: string;
  total_projects: number;
  active_projects: number;
  open_tickets: number;
  active_amc_contracts: number;
  active_soc_services: number;
  active_contract_value: number;
}

export interface VAPTPortfolioSummary {
  as_of_date: string;
  total_engagements: number;
  total_findings: number;
  open_findings: number;
  findings_by_severity: Record<string, number>;
}

export interface TicketSLASummary {
  open_tickets: number;
  overdue_tickets: number;
  by_priority: Record<string, number>;
}

export const corporateReportsApi = {
  clientSummary: (clientId: string) =>
    apiClient
      .get<ClientSummary>(`/corporate/reports/clients/${clientId}/summary`)
      .then((r) => r.data),

  vaptPortfolioSummary: (asOfDate?: string) =>
    apiClient
      .get<VAPTPortfolioSummary>("/corporate/reports/vapt/portfolio-summary", {
        params: { as_of_date: asOfDate },
      })
      .then((r) => r.data),

  ticketSLASummary: () =>
    apiClient.get<TicketSLASummary>("/corporate/reports/tickets/sla-summary").then((r) => r.data),
};
