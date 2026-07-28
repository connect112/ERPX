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
import { Textarea } from "@/components/ui/textarea";
import type { AccountPublic } from "@/features/accounting/ledger/api/accounts-api";
import { useAccountsList, useCreateAccount, useUpdateAccount } from "@/features/accounting/ledger/api/accounts-hooks";
import {
  type AccountFormValues,
  accountFormSchema,
  accountTypeLabels,
  accountTypeValues,
} from "@/features/accounting/ledger/schemas/account-schemas";

interface AccountFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  account?: AccountPublic;
}

const emptyValues: AccountFormValues = {
  code: "",
  name: "",
  accountType: "asset",
  accountSubtype: "",
  parentAccountId: "",
  description: "",
  openingBalance: "0",
};

export function AccountFormDialog({ open, onOpenChange, account }: AccountFormDialogProps) {
  const isEditing = !!account;
  const { data: accounts } = useAccountsList({ limit: 500 });
  const createAccount = useCreateAccount();
  const updateAccount = useUpdateAccount(account?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AccountFormValues>({ resolver: zodResolver(accountFormSchema), defaultValues: emptyValues });

  useEffect(() => {
    if (open) {
      reset(
        account
          ? {
              code: account.code,
              name: account.name,
              accountType: account.account_type,
              accountSubtype: account.account_subtype ?? "",
              parentAccountId: account.parent_account_id ?? "",
              description: account.description ?? "",
              openingBalance: String(account.opening_balance),
            }
          : emptyValues
      );
    }
  }, [open, account, reset]);

  const onSubmit = (values: AccountFormValues) => {
    if (isEditing) {
      updateAccount.mutate(
        {
          name: values.name,
          account_subtype: values.accountSubtype || undefined,
          parent_account_id: values.parentAccountId || undefined,
          description: values.description || undefined,
        },
        { onSuccess: () => onOpenChange(false) }
      );
    } else {
      createAccount.mutate(
        {
          code: values.code,
          name: values.name,
          account_type: values.accountType,
          account_subtype: values.accountSubtype || undefined,
          parent_account_id: values.parentAccountId || undefined,
          description: values.description || undefined,
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
          <DialogTitle>{isEditing ? "Edit account" : "New account"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="code">Code</Label>
              <Input id="code" disabled={isEditing} {...register("code")} />
              {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="accountType">Type</Label>
              <Controller
                control={control}
                name="accountType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange} disabled={isEditing}>
                    <SelectTrigger id="accountType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {accountTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {accountTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="accountSubtype">Subtype</Label>
              <Input id="accountSubtype" {...register("accountSubtype")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="parentAccountId">Parent account</Label>
              <Controller
                control={control}
                name="parentAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="parentAccountId">
                      <SelectValue placeholder="None" />
                    </SelectTrigger>
                    <SelectContent>
                      {accounts?.items
                        .filter((a) => a.id !== account?.id)
                        .map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>
          {!isEditing && (
            <div className="space-y-2">
              <Label htmlFor="openingBalance">Opening balance</Label>
              <Input id="openingBalance" type="number" step="0.01" {...register("openingBalance")} />
            </div>
          )}
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create account"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
