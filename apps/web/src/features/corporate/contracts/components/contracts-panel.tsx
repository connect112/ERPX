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
import { ActivateContractDialog } from "@/features/corporate/contracts/components/activate-contract-dialog";
import { ContractFormDialog } from "@/features/corporate/contracts/components/contract-form-dialog";
import { ContractStatusBadge } from "@/features/corporate/contracts/components/contract-status-badge";
import { RenewContractDialog } from "@/features/corporate/contracts/components/renew-contract-dialog";
import type { ContractPublic } from "@/features/corporate/contracts/api/contracts-api";
import { useContractsList, useTerminateContract } from "@/features/corporate/contracts/api/contracts-hooks";
import { contractTypeLabels } from "@/features/corporate/contracts/schemas/contract-schemas";

function ContractRowActions({
  contract,
  onActivate,
  onRenew,
}: {
  contract: ContractPublic;
  onActivate: (id: string) => void;
  onRenew: (id: string) => void;
}) {
  const terminateContract = useTerminateContract(contract.id);

  if (contract.status === "draft") {
    return (
      <Button variant="ghost" size="sm" onClick={() => onActivate(contract.id)}>
        Activate
      </Button>
    );
  }
  if (contract.status === "active") {
    return (
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={() => onRenew(contract.id)}>
          Renew
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => terminateContract.mutate()}
          disabled={terminateContract.isPending}
        >
          Terminate
        </Button>
      </div>
    );
  }
  return null;
}

export function ContractsPanel({ clientId }: { clientId: string }) {
  const { data, isLoading } = useContractsList({ client_id: clientId, limit: 50 });
  const [formOpen, setFormOpen] = useState(false);
  const [activateTarget, setActivateTarget] = useState<string | null>(null);
  const [renewTarget, setRenewTarget] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Contracts</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New contract
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {!isLoading && (data?.items.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No contracts yet.</p>
        )}
        {!isLoading && (data?.items.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Start date</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((contract) => (
                <TableRow key={contract.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {contract.contract_number}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {contractTypeLabels[contract.contract_type]}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(contract.start_date).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="font-medium">{contract.contract_value.toLocaleString()}</TableCell>
                  <TableCell>
                    <ContractStatusBadge status={contract.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <ContractRowActions
                      contract={contract}
                      onActivate={setActivateTarget}
                      onRenew={setRenewTarget}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <ContractFormDialog open={formOpen} onOpenChange={setFormOpen} clientId={clientId} />
      <ActivateContractDialog
        open={!!activateTarget}
        onOpenChange={(open) => !open && setActivateTarget(null)}
        contractId={activateTarget}
      />
      <RenewContractDialog
        open={!!renewTarget}
        onOpenChange={(open) => !open && setRenewTarget(null)}
        contractId={renewTarget}
      />
    </Card>
  );
}
