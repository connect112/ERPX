import { ArrowLeft, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useAccount, useAccountBalance, useUpdateAccount } from "@/features/accounting/ledger/api/accounts-hooks";
import { AccountFormDialog } from "@/features/accounting/ledger/pages/account-form-dialog";
import { accountTypeLabels } from "@/features/accounting/ledger/schemas/account-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function AccountDetailPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const navigate = useNavigate();
  const { data: account, isLoading } = useAccount(accountId);
  const updateAccount = useUpdateAccount(accountId ?? "");
  const [asOfDate, setAsOfDate] = useState(() => new Date().toISOString().slice(0, 10));
  const { data: balance, isLoading: balanceLoading } = useAccountBalance(accountId ?? "", asOfDate);

  const [editOpen, setEditOpen] = useState(false);

  if (isLoading || !account) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/accounting/ledger")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {account.code} — {account.name}
            </h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant="outline">{accountTypeLabels[account.account_type]}</Badge>
              <Badge variant={account.is_active ? "success" : "secondary"}>
                {account.is_active ? "Active" : "Inactive"}
              </Badge>
              {account.is_system_account && <Badge variant="info">System</Badge>}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => updateAccount.mutate({ is_active: !account.is_active })}
            disabled={updateAccount.isPending || account.is_system_account}
          >
            {account.is_active ? "Deactivate" : "Activate"}
          </Button>
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Account details</CardTitle>
          </CardHeader>
          <CardContent>
            {account.description && (
              <p className="pb-3 text-sm text-muted-foreground">{account.description}</p>
            )}
            <DetailRow label="Subtype" value={account.account_subtype || "—"} />
            <DetailRow label="Opening balance" value={`₹${account.opening_balance}`} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Balance</CardTitle>
            <div className="flex items-center gap-2">
              <Label htmlFor="asOfDate" className="text-xs text-muted-foreground">
                As of
              </Label>
              <Input
                id="asOfDate"
                type="date"
                className="h-8 w-40"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
              />
            </div>
          </CardHeader>
          <CardContent>
            {balanceLoading && <Skeleton className="h-24 w-full" />}
            {balance && (
              <>
                <DetailRow label="Opening balance" value={`₹${balance.opening_balance}`} />
                <DetailRow label="Total debit" value={`₹${balance.total_debit}`} />
                <DetailRow label="Total credit" value={`₹${balance.total_credit}`} />
                <DetailRow
                  label="Closing balance"
                  value={<span className="text-base font-semibold">₹{balance.closing_balance}</span>}
                />
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <AccountFormDialog open={editOpen} onOpenChange={setEditOpen} account={account} />
    </div>
  );
}
