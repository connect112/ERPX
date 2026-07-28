import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useClientsList } from "@/features/corporate/clients/api/clients-hooks";
import {
  useClientSummary,
  useTicketSLASummary,
  useVAPTPortfolioSummary,
} from "@/features/corporate/reports/api/reports-hooks";

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

export function CorporateReportsPage() {
  const { data: clients } = useClientsList({ limit: 200 });
  const [clientId, setClientId] = useState("");

  const { data: clientSummary, isLoading: clientSummaryLoading } = useClientSummary(clientId || undefined);
  const { data: vaptSummary, isLoading: vaptLoading } = useVAPTPortfolioSummary();
  const { data: slaSummary, isLoading: slaLoading } = useTicketSLASummary();

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Corporate Reports</h1>
        <p className="mt-1 text-muted-foreground">
          Portfolio-level insight across clients, VAPT engagements, and support SLAs.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Client summary</CardTitle>
          <Select value={clientId || undefined} onValueChange={setClientId}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Select a client" />
            </SelectTrigger>
            <SelectContent>
              {clients?.items.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          {!clientId && (
            <p className="py-4 text-center text-sm text-muted-foreground">
              Select a client to view their summary.
            </p>
          )}
          {clientId && clientSummaryLoading && <Skeleton className="h-16 w-full" />}
          {clientId && clientSummary && (
            <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
              <StatTile label="Projects" value={clientSummary.total_projects} />
              <StatTile label="Active projects" value={clientSummary.active_projects} />
              <StatTile label="Open tickets" value={clientSummary.open_tickets} />
              <StatTile label="Active AMC" value={clientSummary.active_amc_contracts} />
              <StatTile label="Active SOC" value={clientSummary.active_soc_services} />
              <StatTile
                label="Active contract value"
                value={clientSummary.active_contract_value.toLocaleString()}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">VAPT portfolio summary</CardTitle>
          </CardHeader>
          <CardContent>
            {vaptLoading && <Skeleton className="h-24 w-full" />}
            {vaptSummary && (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <StatTile label="Engagements" value={vaptSummary.total_engagements} />
                  <StatTile label="Total findings" value={vaptSummary.total_findings} />
                  <StatTile label="Open findings" value={vaptSummary.open_findings} />
                </div>
                <div className="grid grid-cols-3 gap-4 border-t pt-3">
                  {Object.entries(vaptSummary.findings_by_severity).map(([severity, count]) => (
                    <div key={severity}>
                      <p className="text-xs capitalize text-muted-foreground">{severity}</p>
                      <p className="font-semibold">{count}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Ticket SLA summary</CardTitle>
          </CardHeader>
          <CardContent>
            {slaLoading && <Skeleton className="h-24 w-full" />}
            {slaSummary && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <StatTile label="Open tickets" value={slaSummary.open_tickets} />
                  <StatTile label="Overdue tickets" value={slaSummary.overdue_tickets} />
                </div>
                <div className="grid grid-cols-4 gap-4 border-t pt-3">
                  {Object.entries(slaSummary.by_priority).map(([priority, count]) => (
                    <div key={priority}>
                      <p className="text-xs capitalize text-muted-foreground">{priority}</p>
                      <p className="font-semibold">{count}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
