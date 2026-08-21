import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
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
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import type { BankAccountPublic } from "@/features/accounting/bank/api/bank-api";
import { useCreateBankAccount, useUpdateBankAccount } from "@/features/accounting/bank/api/bank-hooks";
import {
  type BankAccountFormValues,
  bankAccountFormSchema,
  bankAccountTypeLabels,
  bankAccountTypeValues,
} from "@/features/accounting/bank/schemas/bank-schemas";

interface BankAccountFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  bankAccount?: BankAccountPublic;
}

const emptyValues: BankAccountFormValues = {
  glAccountId: "",
  accountName: "",
  accountType: "current",
  bankName: "",
  accountNumber: "",
  ifscCode: "",
  openingBalance: "0",
};

export function BankAccountFormDialog({ open, onOpenChange, bankAccount }: BankAccountFormDialogProps) {
  const isEditing = !!bankAccount;
  const { data: glAccounts } = useAccountsList({ limit: 500, account_type: "asset" });
  const createAccount = useCreateBankAccount();
  const updateAccount = useUpdateBankAccount(bankAccount?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BankAccountFormValues>({
    resolver: zodResolver(bankAccountFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        bankAccount
          ? {
              glAccountId: bankAccount.gl_account_id,
              accountName: bankAccount.account_name,
              accountType: bankAccount.account_type,
              bankName: bankAccount.bank_name ?? "",
              accountNumber: bankAccount.account_number ?? "",
              ifscCode: bankAccount.ifsc_code ?? "",
              openingBalance: String(bankAccount.opening_balance),
            }
          : emptyValues
      );
    }
  }, [open, bankAccount, reset]);

  const onSubmit = (values: BankAccountFormValues) => {
    if (isEditing) {
      updateAccount.mutate(
        {
          account_name: values.accountName,
          bank_name: values.bankName || undefined,
          account_number: values.accountNumber || undefined,
          ifsc_code: values.ifscCode || undefined,
        },
        { onSuccess: () => onOpenChange(false) }
      );
    } else {
      createAccount.mutate(
        {
          gl_account_id: values.glAccountId,
          account_name: values.accountName,
          account_type: values.accountType,
          bank_name: values.bankName || undefined,
          account_number: values.accountNumber || undefined,
          ifsc_code: values.ifscCode || undefined,
          opening_balance: values.openingBalance ? Number(values.openingBalance) : undefined,
        },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  const mutation = isEditing ? updateAccount : createAccount;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit bank account" : "New bank account"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="accountName" required>Account name</Label>
            <Input id="accountName" {...register("accountName")} />
            {errors.accountName && (
              <p className="text-sm text-destructive">{errors.accountName.message}</p>
            )}
          </div>
          {!isEditing && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="glAccountId" required>GL account</Label>
                <Controller
                  control={control}
                  name="glAccountId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="glAccountId">
                        <SelectValue placeholder="Select GL account" />
                      </SelectTrigger>
                      <SelectContent>
                        {glAccounts?.items.map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                {errors.glAccountId && (
                  <p className="text-sm text-destructive">{errors.glAccountId.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="accountType" required>Type</Label>
                <Controller
                  control={control}
                  name="accountType"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="accountType">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {bankAccountTypeValues.map((t) => (
                          <SelectItem key={t} value={t}>
                            {bankAccountTypeLabels[t]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="bankName">Bank name</Label>
              <Input id="bankName" {...register("bankName")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="accountNumber">Account number</Label>
              <Input id="accountNumber" {...register("accountNumber")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="ifscCode">IFSC code</Label>
              <Input id="ifscCode" {...register("ifscCode")} />
            </div>
            {!isEditing && (
              <div className="space-y-2">
                <Label htmlFor="openingBalance">Opening balance</Label>
                <Input id="openingBalance" type="number" step="0.01" {...register("openingBalance")} />
              </div>
            )}
          </div>
          {mutation.isError && (
            <p className="text-sm text-destructive">
              {(mutation.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create bank account"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
