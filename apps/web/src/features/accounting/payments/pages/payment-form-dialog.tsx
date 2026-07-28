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
import { useBankAccounts } from "@/features/accounting/bank/api/bank-hooks";
import { useExpensesList } from "@/features/accounting/expenses/api/expenses-hooks";
import { useTDSSections } from "@/features/accounting/tds/api/tds-hooks";
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import { useCreatePayment } from "@/features/accounting/payments/api/payments-hooks";
import {
  type PaymentFormValues,
  apPaymentModeLabels,
  apPaymentModeValues,
  paymentFormSchema,
} from "@/features/accounting/payments/schemas/payment-schemas";

interface PaymentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PaymentFormDialog({ open, onOpenChange }: PaymentFormDialogProps) {
  const { data: vendors } = useVendorsList({ limit: 200 });
  const { data: expenses } = useExpensesList({ status: "approved", limit: 200 });
  const { data: bankAccounts } = useBankAccounts(true);
  const { data: accounts } = useAccountsList({ limit: 500, is_active: true });
  const { data: tdsSections } = useTDSSections(true);
  const createPayment = useCreatePayment();

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<PaymentFormValues>({
    resolver: zodResolver(paymentFormSchema),
    defaultValues: {
      vendorId: "",
      expenseId: "",
      paymentNumber: "",
      paymentDate: new Date().toISOString().slice(0, 10),
      grossAmount: "",
      paymentMode: "bank_transfer",
      bankAccountId: "",
      paymentAccountId: "",
      tdsSectionId: "",
      tdsPayableAccountId: "",
      referenceNumber: "",
      notes: "",
    },
  });

  const vendorId = watch("vendorId");
  const tdsSectionId = watch("tdsSectionId");
  const vendorExpenses = expenses?.items.filter((e) => e.vendor_id === vendorId);

  const onSubmit = (values: PaymentFormValues) => {
    createPayment.mutate(
      {
        vendor_id: values.vendorId,
        expense_id: values.expenseId,
        payment_number: values.paymentNumber,
        payment_date: new Date(values.paymentDate).toISOString(),
        gross_amount: Number(values.grossAmount),
        payment_mode: values.paymentMode,
        bank_account_id: values.bankAccountId || undefined,
        payment_account_id: values.paymentAccountId || undefined,
        tds_section_id: values.tdsSectionId || undefined,
        tds_payable_account_id: values.tdsPayableAccountId || undefined,
        reference_number: values.referenceNumber || undefined,
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
          <DialogTitle>New payment</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="vendorId">Vendor</Label>
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
              <Label htmlFor="expenseId">Expense</Label>
              <Controller
                control={control}
                name="expenseId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="expenseId">
                      <SelectValue placeholder="Select an approved expense" />
                    </SelectTrigger>
                    <SelectContent>
                      {vendorExpenses?.map((e) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.expense_number} (₹{e.total_amount})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.expenseId && (
                <p className="text-sm text-destructive">{errors.expenseId.message}</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="paymentNumber">Payment number</Label>
              <Input id="paymentNumber" {...register("paymentNumber")} />
              {errors.paymentNumber && (
                <p className="text-sm text-destructive">{errors.paymentNumber.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="paymentDate">Date</Label>
              <Input id="paymentDate" type="date" {...register("paymentDate")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="grossAmount">Gross amount</Label>
              <Input id="grossAmount" type="number" step="0.01" {...register("grossAmount")} />
              {errors.grossAmount && (
                <p className="text-sm text-destructive">{errors.grossAmount.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="paymentMode">Payment mode</Label>
              <Controller
                control={control}
                name="paymentMode"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="paymentMode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {apPaymentModeValues.map((m) => (
                        <SelectItem key={m} value={m}>
                          {apPaymentModeLabels[m]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="bankAccountId">Pay from bank account</Label>
            <Controller
              control={control}
              name="bankAccountId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="bankAccountId">
                    <SelectValue placeholder="Select bank account" />
                  </SelectTrigger>
                  <SelectContent>
                    {bankAccounts?.map((b) => (
                      <SelectItem key={b.id} value={b.id}>
                        {b.account_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.paymentAccountId && (
              <p className="text-sm text-destructive">{errors.paymentAccountId.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="tdsSectionId">TDS section (optional)</Label>
              <Controller
                control={control}
                name="tdsSectionId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="tdsSectionId">
                      <SelectValue placeholder="None" />
                    </SelectTrigger>
                    <SelectContent>
                      {tdsSections?.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.section_code} ({s.rate_percent}%)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            {tdsSectionId && (
              <div className="space-y-2">
                <Label htmlFor="tdsPayableAccountId">TDS payable account</Label>
                <Controller
                  control={control}
                  name="tdsPayableAccountId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="tdsPayableAccountId">
                        <SelectValue placeholder="Select account" />
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
                {errors.tdsPayableAccountId && (
                  <p className="text-sm text-destructive">{errors.tdsPayableAccountId.message}</p>
                )}
              </div>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="referenceNumber">Reference number</Label>
            <Input id="referenceNumber" {...register("referenceNumber")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>
          {createPayment.isError && (
            <p className="text-sm text-destructive">
              {(createPayment.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createPayment.isPending}>
              {createPayment.isPending ? "Saving..." : "Create payment"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
