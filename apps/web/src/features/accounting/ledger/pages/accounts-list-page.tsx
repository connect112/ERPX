import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import { AccountFormDialog } from "@/features/accounting/ledger/pages/account-form-dialog";
import {
  type AccountType,
  accountTypeLabels,
  accountTypeValues,
} from "@/features/accounting/ledger/schemas/account-schemas";

export function AccountsListPage() {
  const navigate = useNavigate();
  const [accountType, setAccountType] = useState<AccountType | "all">("all");
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useAccountsList({
    account_type: accountType === "all" ? undefined : accountType,
    limit: 200,
  });

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Chart of Accounts</h1>
          <p className="mt-1 text-muted-foreground">
            The general ledger's account hierarchy — every journal posting references one of these.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Account
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select value={accountType} onValueChange={(v) => setAccountType(v as AccountType | "all")}>
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              {accountTypeValues.map((t) => (
                <SelectItem key={t} value={t}>
                  {accountTypeLabels[t]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load accounts.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No accounts yet. Create one to start building your chart of accounts.
            </p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Subtype</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((account) => (
                  <TableRow
                    key={account.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/accounting/ledger/${account.id}`)}
                  >
                    <TableCell className="font-mono text-xs">{account.code}</TableCell>
                    <TableCell className="font-medium">{account.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {accountTypeLabels[account.account_type]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {account.account_subtype || "—"}
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

      <AccountFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
