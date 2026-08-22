import { zodResolver } from "@hookform/resolvers/zod";
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
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import { useGSTRates } from "@/features/accounting/gst/api/gst-hooks";
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import { useCreateExpense } from "@/features/accounting/expenses/api/expenses-hooks";
import { type ExpenseFormValues, expenseFormSchema } from "@/features/accounting/expenses/schemas/expense-schemas";

interface ExpenseFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ExpenseFormDialog({ open, onOpenChange }: ExpenseFormDialogProps) {
  const { data: vendors } = useVendorsList({ limit: 200 });
  const { data: accounts } = useAccountsList({ limit: 500, is_active: true });
  const { data: gstRates } = useGSTRates(true);
  const createExpense = useCreateExpense();

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<ExpenseFormValues>({
    resolver: zodResolver(expenseFormSchema),
    defaultValues: {
      vendorId: "",
      expenseAccountId: "",
      payableAccountId: "",
      expenseNumber: "",
      expenseDate: new Date().toISOString().slice(0, 10),
      category: "",
      description: "",
      subtotalAmount: "",
      gstRateId: "",
      inputTaxCreditAccountId: "",
      isInterstate: false,
      attachmentUrl: "",
      notes: "",
    },
  });

  const gstRateId = watch("gstRateId");

  const onSubmit = (values: ExpenseFormValues) => {
    createExpense.mutate(
      {
        vendor_id: values.vendorId,
        expense_account_id: values.expenseAccountId,
        payable_account_id: values.payableAccountId,
        expense_number: values.expenseNumber,
        expense_date: new Date(values.expenseDate).toISOString(),
        category: values.category,
        description: values.description,
        subtotal_amount: Number(values.subtotalAmount),
        gst_rate_id: values.gstRateId || undefined,
        input_tax_credit_account_id: values.inputTaxCreditAccountId || undefined,
        is_interstate: values.isInterstate,
        attachment_url: values.attachmentUrl || undefined,
        notes: values.notes || undefined,
      },
      {
        onSuccess: () => {
          onOpenChange(false);
          reset();
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New expense</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="vendorId" required>Vendor</Label>
              <Controller
                control={control}
                name="vendorId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="vendorId">
                      <SelectValue placeholder="Select a vendor" />
                    </SelectTrigger>
                    <SelectContent>
                      {vendors?.items.map((v) => (
                        <SelectItem key={v.id} value={v.id}>
                          {v.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.vendorId && <p className="text-sm text-destructive">{errors.vendorId.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="expenseNumber" required>Expense number</Label>
              <Input id="expenseNumber" {...register("expenseNumber")} />
              {errors.expenseNumber && (
                <p className="text-sm text-destructive">{errors.expenseNumber.message}</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="category" required>Category</Label>
              <Input id="category" {...register("category")} />
              {errors.category && <p className="text-sm text-destructive">{errors.category.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="expenseDate" required>Date</Label>
              <Input id="expenseDate" type="date" {...register("expenseDate")} />
              {errors.expenseDate && (
                <p className="text-sm text-destructive">{errors.expenseDate.message}</p>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="description" required>Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
            {errors.description && (
              <p className="text-sm text-destructive">{errors.description.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="expenseAccountId" required>Expense account</Label>
              <Controller
                control={control}
                name="expenseAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="expenseAccountId">
                      <SelectValue placeholder="Select account" />
                    </SelectTrigger>
                    <SelectContent>
                      {accounts?.items
                        .filter((a) => a.account_type === "expense")
                        .map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.expenseAccountId && (
                <p className="text-sm text-destructive">{errors.expenseAccountId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="payableAccountId" required>Payable account</Label>
              <Controller
                control={control}
                name="payableAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="payableAccountId">
                      <SelectValue placeholder="e.g. Accounts Payable" />
                    </SelectTrigger>
                    <SelectContent>
                      {accounts?.items
                        .filter((a) => a.account_type === "liability")
                        .map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.payableAccountId && (
                <p className="text-sm text-destructive">{errors.payableAccountId.message}</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="subtotalAmount" required>Amount</Label>
              <Input id="subtotalAmount" type="number" step="0.01" {...register("subtotalAmount")} />
              {errors.subtotalAmount && (
                <p className="text-sm text-destructive">{errors.subtotalAmount.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="gstRateId">GST rate</Label>
              <Controller
                control={control}
                name="gstRateId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="gstRateId">
                      <SelectValue placeholder="None" />
                    </SelectTrigger>
                    <SelectContent>
                      {gstRates?.map((r) => (
                        <SelectItem key={r.id} value={r.id}>
                          {r.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          {gstRateId && (
            <div className="space-y-2">
              <Label htmlFor="inputTaxCreditAccountId">Input tax credit account</Label>
              <Controller
                control={control}
                name="inputTaxCreditAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="inputTaxCreditAccountId">
                      <SelectValue placeholder="Select account" />
                    </SelectTrigger>
                    <SelectContent>
                      {accounts?.items
                        .filter((a) => a.account_type === "asset")
                        .map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.inputTaxCreditAccountId && (
                <p className="text-sm text-destructive">{errors.inputTaxCreditAccountId.message}</p>
              )}
            </div>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 rounded border-input" {...register("isInterstate")} />
            Interstate transaction (IGST)
          </label>
          <div className="space-y-2">
            <Label htmlFor="attachmentUrl">Attachment URL</Label>
            <Input id="attachmentUrl" {...register("attachmentUrl")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>
          {createExpense.isError && (
            <p className="text-sm text-destructive">
              {(createExpense.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createExpense.isPending}>
              {createExpense.isPending ? "Saving..." : "Create expense"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
