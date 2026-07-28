import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Pencil, Plus } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import {
  useBankAccount,
  useBankAccountBalance,
  useBankTransactions,
  useCreateBankTransaction,
  useReconcileTransaction,
  useUpdateBankAccount,
} from "@/features/accounting/bank/api/bank-hooks";
import { BankAccountFormDialog } from "@/features/accounting/bank/pages/bank-account-form-dialog";
import {
  type BankTransactionFormValues,
  bankAccountTypeLabels,
  bankTransactionFormSchema,
} from "@/features/accounting/bank/schemas/bank-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function BankAccountDetailPage() {
  const { bankAccountId } = useParams<{ bankAccountId: string }>();
  const navigate = useNavigate();
  const { data: account, isLoading } = useBankAccount(bankAccountId);
  const updateAccount = useUpdateBankAccount(bankAccountId ?? "");
  const { data: balance, isLoading: balanceLoading } = useBankAccountBalance(bankAccountId ?? "");
  const { data: transactions, isLoading: txnsLoading } = useBankTransactions(bankAccountId ?? "");
  const { data: glAccounts } = useAccountsList({ limit: 500 });
  const createTransaction = useCreateBankTransaction(bankAccountId ?? "");
  const reconcileTransaction = useReconcileTransaction(bankAccountId ?? "");

  const [editOpen, setEditOpen] = useState(false);
  const [txnFormOpen, setTxnFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BankTransactionFormValues>({
    resolver: zodResolver(bankTransactionFormSchema),
    defaultValues: {
      transactionDate: new Date().toISOString().slice(0, 16),
      description: "",
      debitAmount: "",
      creditAmount: "",
      referenceNumber: "",
      contraAccountId: "",
    },
  });

  const accountLabel = (id: string) => {
    const a = glAccounts?.items.find((x) => x.id === id);
    return a ? `${a.code} — ${a.name}` : id;
  };

  const onSubmit = (values: BankTransactionFormValues) => {
    createTransaction.mutate(
      {
        transaction_date: new Date(values.transactionDate).toISOString(),
        description: values.description,
        debit_amount: values.debitAmount ? Number(values.debitAmount) : undefined,
        credit_amount: values.creditAmount ? Number(values.creditAmount) : undefined,
        reference_number: values.referenceNumber || undefined,
        contra_account_id: values.contraAccountId,
      },
      {
        onSuccess: () => {
          setTxnFormOpen(false);
          reset();
        },
      }
    );
  };

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
          <Button variant="ghost" size="icon" onClick={() => navigate("/accounting/bank")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{account.account_name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant="outline">{bankAccountTypeLabels[account.account_type]}</Badge>
              <Badge variant={account.is_active ? "success" : "secondary"}>
                {account.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => updateAccount.mutate({ is_active: !account.is_active })}
            disabled={updateAccount.isPending}
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
            <DetailRow label="Bank" value={account.bank_name || "—"} />
            <DetailRow label="Account number" value={account.account_number || "—"} />
            <DetailRow label="IFSC" value={account.ifsc_code || "—"} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Balance</CardTitle>
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

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Transactions</CardTitle>
          <Button size="sm" onClick={() => setTxnFormOpen(true)}>
            <Plus className="h-4 w-4" />
            Record transaction
          </Button>
        </CardHeader>
        <CardContent>
          {txnsLoading && <Skeleton className="h-32 w-full" />}
          {!txnsLoading && (transactions?.items.length ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground">No transactions recorded yet.</p>
          )}
          {!txnsLoading && (transactions?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Debit</TableHead>
                  <TableHead className="text-right">Credit</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions?.items.map((txn) => (
                  <TableRow key={txn.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(txn.transaction_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell>{txn.description}</TableCell>
                    <TableCell className="text-right">
                      {txn.debit_amount > 0 ? txn.debit_amount.toFixed(2) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      {txn.credit_amount > 0 ? txn.credit_amount.toFixed(2) : "—"}
                    </TableCell>
                    <TableCell>
                      {txn.is_reconciled ? (
                        <Badge variant="success">Reconciled</Badge>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={reconcileTransaction.isPending}
                          onClick={() => reconcileTransaction.mutate(txn.id)}
                        >
                          Reconcile
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <BankAccountFormDialog open={editOpen} onOpenChange={setEditOpen} bankAccount={account} />

      <Dialog open={txnFormOpen} onOpenChange={setTxnFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record bank transaction</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="transactionDate">Date</Label>
              <Input id="transactionDate" type="datetime-local" {...register("transactionDate")} />
              {errors.transactionDate && (
                <p className="text-sm text-destructive">{errors.transactionDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input id="description" {...register("description")} />
              {errors.description && (
                <p className="text-sm text-destructive">{errors.description.message}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="debitAmount">Debit</Label>
                <Input id="debitAmount" type="number" step="0.01" {...register("debitAmount")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="creditAmount">Credit</Label>
                <Input id="creditAmount" type="number" step="0.01" {...register("creditAmount")} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="contraAccountId">Contra account</Label>
              <Controller
                control={control}
                name="contraAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="contraAccountId">
                      <SelectValue placeholder="e.g. Bank Charges" />
                    </SelectTrigger>
                    <SelectContent>
                      {glAccounts?.items.map((a) => (
                        <SelectItem key={a.id} value={a.id}>
                          {accountLabel(a.id)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.contraAccountId && (
                <p className="text-sm text-destructive">{errors.contraAccountId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="referenceNumber">Reference number</Label>
              <Input id="referenceNumber" {...register("referenceNumber")} />
            </div>
            {createTransaction.isError && (
              <p className="text-sm text-destructive">
                {(createTransaction.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setTxnFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createTransaction.isPending}>
                {createTransaction.isPending ? "Saving..." : "Record transaction"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
