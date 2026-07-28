import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { useCustomersList } from "@/features/accounting/customers/api/customers-hooks";
import { useGSTRates } from "@/features/accounting/gst/api/gst-hooks";
import { useCreateInvoice } from "@/features/accounting/invoices/api/invoices-hooks";
import { type InvoiceFormValues, invoiceFormSchema } from "@/features/accounting/invoices/schemas/invoice-schemas";

export function InvoiceCreatePage() {
  const navigate = useNavigate();
  const { data: customers } = useCustomersList({ limit: 200 });
  const { data: accounts } = useAccountsList({ limit: 500, is_active: true });
  const { data: gstRates } = useGSTRates(true);
  const createInvoice = useCreateInvoice();

  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<InvoiceFormValues>({
    resolver: zodResolver(invoiceFormSchema),
    defaultValues: {
      customerId: "",
      invoiceNumber: "",
      invoiceDate: new Date().toISOString().slice(0, 10),
      dueDate: new Date().toISOString().slice(0, 10),
      receivableAccountId: "",
      taxPayableAccountId: "",
      discountAccountId: "",
      isInterstate: false,
      discountAmount: "",
      notes: "",
      lines: [{ revenueAccountId: "", description: "", quantity: "1", unitPrice: "", gstRateId: "" }],
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "lines" });
  const lines = watch("lines");

  const revenueAccounts = accounts?.items.filter((a) => a.account_type === "income");

  const subtotal = lines.reduce((sum, l) => sum + (Number(l.quantity) || 0) * (Number(l.unitPrice) || 0), 0);

  const onSubmit = (values: InvoiceFormValues) => {
    createInvoice.mutate(
      {
        customer_id: values.customerId,
        invoice_number: values.invoiceNumber,
        invoice_date: new Date(values.invoiceDate).toISOString(),
        due_date: new Date(values.dueDate).toISOString(),
        receivable_account_id: values.receivableAccountId,
        tax_payable_account_id: values.taxPayableAccountId || undefined,
        discount_account_id: values.discountAccountId || undefined,
        is_interstate: values.isInterstate,
        discount_amount: values.discountAmount ? Number(values.discountAmount) : undefined,
        notes: values.notes || undefined,
        lines: values.lines.map((l) => ({
          revenue_account_id: l.revenueAccountId,
          description: l.description,
          quantity: Number(l.quantity),
          unit_price: Number(l.unitPrice),
          gst_rate_id: l.gstRateId || undefined,
        })),
      },
      {
        onSuccess: (invoice) => navigate(`/accounting/invoices/${invoice.id}`),
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/accounting/invoices")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">New invoice</h1>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Invoice details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="customerId">Customer</Label>
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
                <Label htmlFor="invoiceNumber">Invoice number</Label>
                <Input id="invoiceNumber" {...register("invoiceNumber")} />
                {errors.invoiceNumber && (
                  <p className="text-sm text-destructive">{errors.invoiceNumber.message}</p>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="invoiceDate">Invoice date</Label>
                <Input id="invoiceDate" type="date" {...register("invoiceDate")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dueDate">Due date</Label>
                <Input id="dueDate" type="date" {...register("dueDate")} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="receivableAccountId">Receivable account</Label>
                <Controller
                  control={control}
                  name="receivableAccountId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="receivableAccountId">
                        <SelectValue placeholder="e.g. Accounts Receivable" />
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
                {errors.receivableAccountId && (
                  <p className="text-sm text-destructive">{errors.receivableAccountId.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="taxPayableAccountId">Tax payable account</Label>
                <Controller
                  control={control}
                  name="taxPayableAccountId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="taxPayableAccountId">
                        <SelectValue placeholder="Optional" />
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
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 rounded border-input" {...register("isInterstate")} />
              Interstate transaction (IGST)
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Line items</CardTitle>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() =>
                append({ revenueAccountId: "", description: "", quantity: "1", unitPrice: "", gstRateId: "" })
              }
            >
              <Plus className="h-3 w-3" />
              Add line
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {errors.lines?.message && (
              <p className="text-sm text-destructive">{errors.lines.message}</p>
            )}
            {fields.map((field, index) => (
              <div key={field.id} className="grid grid-cols-12 items-start gap-2">
                <div className="col-span-3">
                  <Controller
                    control={control}
                    name={`lines.${index}.revenueAccountId`}
                    render={({ field: selectField }) => (
                      <Select value={selectField.value || undefined} onValueChange={selectField.onChange}>
                        <SelectTrigger>
                          <SelectValue placeholder="Revenue account" />
                        </SelectTrigger>
                        <SelectContent>
                          {revenueAccounts?.map((a) => (
                            <SelectItem key={a.id} value={a.id}>
                              {a.code} — {a.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
                <div className="col-span-3">
                  <Input placeholder="Description" {...register(`lines.${index}.description`)} />
                </div>
                <div className="col-span-1">
                  <Input type="number" step="0.01" placeholder="Qty" {...register(`lines.${index}.quantity`)} />
                </div>
                <div className="col-span-2">
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="Unit price"
                    {...register(`lines.${index}.unitPrice`)}
                  />
                </div>
                <div className="col-span-2">
                  <Controller
                    control={control}
                    name={`lines.${index}.gstRateId`}
                    render={({ field: selectField }) => (
                      <Select
                        value={selectField.value || undefined}
                        onValueChange={selectField.onChange}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="GST rate" />
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
                <div className="col-span-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    disabled={fields.length <= 1}
                    onClick={() => remove(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
            <div className="flex justify-end gap-4 border-t pt-2 text-sm">
              <span className="text-muted-foreground">
                Subtotal: <span className="font-medium text-foreground">₹{subtotal.toFixed(2)}</span>
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 p-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="discountAccountId">Discount account</Label>
                <Controller
                  control={control}
                  name="discountAccountId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="discountAccountId">
                        <SelectValue placeholder="Optional" />
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
              </div>
              <div className="space-y-2">
                <Label htmlFor="discountAmount">Discount amount</Label>
                <Input id="discountAmount" type="number" step="0.01" {...register("discountAmount")} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea id="notes" rows={2} {...register("notes")} />
            </div>
          </CardContent>
        </Card>

        {createInvoice.isError && (
          <p className="text-sm text-destructive">
            {(createInvoice.error as { response?: { data?: { error?: { message?: string } } } })
              ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate("/accounting/invoices")}>
            Cancel
          </Button>
          <Button type="submit" disabled={createInvoice.isPending}>
            {createInvoice.isPending ? "Saving..." : "Create invoice"}
          </Button>
        </div>
      </form>
    </div>
  );
}
