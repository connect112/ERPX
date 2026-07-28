import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useSOCServicesByClient } from "@/features/corporate/soc/api/soc-hooks";
import { SOCServiceStatusBadge } from "@/features/corporate/soc/components/soc-badges";
import { SOCFormDialog } from "@/features/corporate/soc/components/soc-form-dialog";
import { SOCIncidentsDialog } from "@/features/corporate/soc/components/soc-incidents-dialog";
import { socServiceTypeLabels } from "@/features/corporate/soc/schemas/soc-schemas";

export function SOCPanel({ clientId }: { clientId: string }) {
  const { data: services, isLoading } = useSOCServicesByClient(clientId);
  const [formOpen, setFormOpen] = useState(false);
  const [incidentsTarget, setIncidentsTarget] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">SOC services</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New SOC service
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {!isLoading && (services?.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No SOC services yet.</p>
        )}
        {!isLoading && (services?.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>SLA</TableHead>
                <TableHead>Start date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {services?.map((service) => (
                <TableRow key={service.id}>
                  <TableCell className="font-medium">{socServiceTypeLabels[service.service_type]}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {service.sla_response_time_minutes ? `${service.sla_response_time_minutes} min` : "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(service.start_date).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <SOCServiceStatusBadge status={service.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => setIncidentsTarget(service.id)}>
                      Incidents
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <SOCFormDialog open={formOpen} onOpenChange={setFormOpen} clientId={clientId} />
      <SOCIncidentsDialog
        open={!!incidentsTarget}
        onOpenChange={(open) => !open && setIncidentsTarget(null)}
        serviceId={incidentsTarget}
      />
    </Card>
  );
}
