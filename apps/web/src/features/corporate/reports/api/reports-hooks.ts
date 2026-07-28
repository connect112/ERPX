import { useQuery } from "@tanstack/react-query";

import { corporateReportsApi } from "@/features/corporate/reports/api/reports-api";

export function useClientSummary(clientId: string | undefined) {
  return useQuery({
    queryKey: ["corporate", "reports", "client-summary", clientId ?? ""],
    queryFn: () => corporateReportsApi.clientSummary(clientId as string),
    enabled: !!clientId,
  });
}

export function useVAPTPortfolioSummary(asOfDate?: string) {
  return useQuery({
    queryKey: ["corporate", "reports", "vapt-portfolio", asOfDate],
    queryFn: () => corporateReportsApi.vaptPortfolioSummary(asOfDate),
  });
}

export function useTicketSLASummary() {
  return useQuery({
    queryKey: ["corporate", "reports", "ticket-sla"],
    queryFn: () => corporateReportsApi.ticketSLASummary(),
  });
}
