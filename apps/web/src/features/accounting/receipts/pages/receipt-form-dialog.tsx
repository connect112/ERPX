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
import { useCustomersList } from "@/features/accounting/customers/api/customers-hooks";
import { useInvoicesList } from "@/features/accounting/invoices/api/invoices-hooks";
import { useCreateReceipt } from "@/features/accounting/receipts/api/receipts-hooks";
import {
  type ReceiptFormValues,
  paymentModeLabels,
  paymentModeValues,
  receiptFormSchema,
} from "@/features/accounting/receipts/schemas/receipt-schemas";

interface ReceiptFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ReceiptFormDialog({ open, onOpenChange }: ReceiptFormDialogProps) {
  const { data: customers } = useCustomersList({ limit: 200 });
  const { data: invoices } = useInvoicesList({ limit: 200 });
  const { data: bankAccounts } = useBankAccounts(true);
  const { data: accounts } = useAccountsList({ limit: 500, account_type: "asset" });
  const createReceipt = useCreateReceipt();

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<ReceiptFormValues>({
    resolver: zodResolver(receiptFormSchema),
    defaultValues: {
      customerId: "",
      invoiceId: "",
      receivableAccountId: "",
      receiptNumber: "",
      receiptDate: new Date().toISOString().slice(0, 10),
      amount: "",
      paymentMode: "bank_transfer",
      bankAccountId: "",
      depositAccountId: "",
      referenceNumber: "",
      notes: "",
    },
  });

  const customerId = watch("customerId");
  const customerInvoices = invoices?.items.filter((i) => i.customer_id === customerId);

  const onSubmit = (values: ReceiptFormValues) => {
    createReceipt.mutate(
      {
        customer_id: values.customerId,
        invoice_id: values.invoiceId || undefined,
        receivable_account_id: values.receivableAccountId || undefined,
        receipt_number: values.receiptNumber,
        receipt_date: new Date(values.receiptDate).toISOString(),
        amount: Number(values.amount),
        payment_mode: values.paymentMode,
        bank_account_id: values.bankAccountId || undefined,
        deposit_account_id: values.depositAccountId || undefined,
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
          <DialogTitle>New receipt</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="customerId" required>Customer</Label>
              <Controller
                control={control}
                name="customerId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="customerId">
                      <SelectValue placeholder="Select a customer" />
                    </SelectTrigger>
                    <SelectContent>
                      {customers?.items.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.customerId && (
                <p className="text-sm text-destructive">{errors.customerId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="invoiceId">Invoice (optional)</Label>
              <Controller
                control={control}
                name="invoiceId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="invoiceId">
                      <SelectValue placeholder="On-account" />
                    </SelectTrigger>
                    <SelectContent>
                      {customerInvoices?.map((i) => (
                        <SelectItem key={i.id} value={i.id}>
                          {i.invoice_number}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="receivableAccountId">Receivable account (if on-account)</Label>
            <Controller
              control={control}
              name="receivableAccountId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="receivableAccountId">
                    <SelectValue placeholder="Required if no invoice selected" />
                  </SelectTrigger>
                  <SelectContent>
                    {accounts?.items.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.code} — {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.receivableAccountId && (
              <p className="text-sm text-destructive">{errors.receivableAccountId.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="receiptNumber" required>Receipt number</Label>
              <Input id="receiptNumber" {...register("receiptNumber")} />
              {errors.receiptNumber && (
                <p className="text-sm text-destructive">{errors.receiptNumber.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="receiptDate" required>Date</Label>
              <Input id="receiptDate" type="date" {...register("receiptDate")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="amount" required>Amount</Label>
              <Input id="amount" type="number" step="0.01" {...register("amount")} />
              {errors.amount && <p className="text-sm text-destructive">{errors.amount.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="paymentMode" required>Payment mode</Label>
              <Controller
                control={control}
                name="paymentMode"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="paymentMode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {paymentModeValues.map((m) => (
                        <SelectItem key={m} value={m}>
                          {paymentModeLabels[m]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="bankAccountId">Deposit into bank account</Label>
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
            {errors.depositAccountId && (
              <p className="text-sm text-destructive">{errors.depositAccountId.message}</p>
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
          {createReceipt.isError && (
            <p className="text-sm text-destructive">
              {(createReceipt.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createReceipt.isPending}>
              {createReceipt.isPending ? "Saving..." : "Create receipt"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
