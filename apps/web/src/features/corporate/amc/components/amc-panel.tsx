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
import { useAMCContractsList } from "@/features/corporate/amc/api/amc-hooks";
import { AMCFormDialog } from "@/features/corporate/amc/components/amc-form-dialog";
import { AMCStatusBadge } from "@/features/corporate/amc/components/amc-status-badge";
import { AMCVisitsDialog } from "@/features/corporate/amc/components/amc-visits-dialog";
import { billingFrequencyLabels } from "@/features/corporate/amc/schemas/amc-schemas";

export function AMCPanel({ clientId }: { clientId: string }) {
  const { data, isLoading } = useAMCContractsList({ client_id: clientId, limit: 50 });
  const [formOpen, setFormOpen] = useState(false);
  const [visitsTarget, setVisitsTarget] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">AMC contracts</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New AMC contract
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {!isLoading && (data?.items.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No AMC contracts yet.</p>
        )}
        {!isLoading && (data?.items.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Coverage</TableHead>
                <TableHead>Billing</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((contract) => (
                <TableRow key={contract.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {contract.amc_number}
                  </TableCell>
                  <TableCell className="max-w-[200px] truncate">{contract.coverage_description}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {billingFrequencyLabels[contract.billing_frequency]}
                  </TableCell>
                  <TableCell className="font-medium">{contract.amount.toLocaleString()}</TableCell>
                  <TableCell>
                    <AMCStatusBadge status={contract.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => setVisitsTarget(contract.id)}>
                      Visits
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <AMCFormDialog open={formOpen} onOpenChange={setFormOpen} clientId={clientId} />
      <AMCVisitsDialog
        open={!!visitsTarget}
        onOpenChange={(open) => !open && setVisitsTarget(null)}
        contractId={visitsTarget}
      />
    </Card>
  );
}
