import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useBankAccounts } from "@/features/accounting/bank/api/bank-hooks";
import { BankAccountFormDialog } from "@/features/accounting/bank/pages/bank-account-form-dialog";
import { bankAccountTypeLabels } from "@/features/accounting/bank/schemas/bank-schemas";

export function BankAccountsListPage() {
  const navigate = useNavigate();
  const { data: accounts, isLoading, isError } = useBankAccounts();
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Bank Accounts</h1>
          <p className="mt-1 text-muted-foreground">
            Cash and bank accounts, each mapped to a general ledger account.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Bank Account
        </Button>
      </div>

      <Card>
        <CardContent className="p-6">
          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load bank accounts.</p>
          )}
          {!isLoading && !isError && (accounts?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No bank accounts yet.</p>
          )}
          {!isLoading && !isError && (accounts?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Account name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Bank</TableHead>
                  <TableHead>Account number</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts?.map((account) => (
                  <TableRow
                    key={account.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/accounting/bank/${account.id}`)}
                  >
                    <TableCell className="font-medium">{account.account_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {bankAccountTypeLabels[account.account_type]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{account.bank_name || "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {account.account_number || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={account.is_active ? "success" : "secondary"}>
                        {account.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <BankAccountFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
