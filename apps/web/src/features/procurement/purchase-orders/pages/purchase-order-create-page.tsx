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
import { useGSTRates } from "@/features/accounting/gst/api/gst-hooks";
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import { useItemsList } from "@/features/inventory/items/api/items-hooks";
import { useCreatePurchaseOrder } from "@/features/procurement/purchase-orders/api/purchase-orders-hooks";
import {
  type PurchaseOrderFormValues,
  purchaseOrderFormSchema,
} from "@/features/procurement/purchase-orders/schemas/purchase-order-schemas";

export function PurchaseOrderCreatePage() {
  const navigate = useNavigate();
  const { data: vendors } = useVendorsList({ limit: 200 });
  const { data: items } = useItemsList({ limit: 200 });
  const { data: gstRates } = useGSTRates(true);
  const createPurchaseOrder = useCreatePurchaseOrder();

  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<PurchaseOrderFormValues>({
    resolver: zodResolver(purchaseOrderFormSchema),
    defaultValues: {
      vendorId: "",
      poNumber: "",
      orderDate: new Date().toISOString().slice(0, 10),
      expectedDeliveryDate: "",
      notes: "",
      lines: [{ itemId: "", description: "", quantityOrdered: 1, unitPrice: 0, gstRateId: "" }],
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "lines" });
  const lines = watch("lines");

  const subtotal = lines.reduce(
    (sum, l) => sum + (Number(l.quantityOrdered) || 0) * (Number(l.unitPrice) || 0),
    0
  );

  const onSubmit = (values: PurchaseOrderFormValues) => {
    createPurchaseOrder.mutate(
      {
        vendor_id: values.vendorId,
        po_number: values.poNumber,
        order_date: new Date(values.orderDate).toISOString(),
        expected_delivery_date: values.expectedDeliveryDate
          ? new Date(values.expectedDeliveryDate).toISOString()
          : undefined,
        notes: values.notes || undefined,
        lines: values.lines.map((l) => ({
          item_id: l.itemId,
          description: l.description,
          quantity_ordered: l.quantityOrdered,
          unit_price: l.unitPrice,
          gst_rate_id: l.gstRateId || undefined,
        })),
      },
      { onSuccess: (po) => navigate(`/procurement/purchase-orders/${po.id}`) }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/procurement/purchase-orders")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">New purchase order</h1>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Order details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
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
                <Label htmlFor="poNumber">PO number</Label>
                <Input id="poNumber" {...register("poNumber")} />
                {errors.poNumber && <p className="text-sm text-destructive">{errors.poNumber.message}</p>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="orderDate">Order date</Label>
                <Input id="orderDate" type="date" {...register("orderDate")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expectedDeliveryDate">Expected delivery date</Label>
                <Input id="expectedDeliveryDate" type="date" {...register("expectedDeliveryDate")} />
              </div>
            </div>
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
                append({ itemId: "", description: "", quantityOrdered: 1, unitPrice: 0, gstRateId: "" })
              }
            >
              <Plus className="h-3 w-3" />
              Add line
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {errors.lines?.message && <p className="text-sm text-destructive">{errors.lines.message}</p>}
            {fields.map((field, index) => (
              <div key={field.id} className="grid grid-cols-12 items-start gap-2">
                <div className="col-span-3">
                  <Controller
                    control={control}
                    name={`lines.${index}.itemId`}
                    render={({ field: selectField }) => (
                      <Select value={selectField.value || undefined} onValueChange={selectField.onChange}>
                        <SelectTrigger>
                          <SelectValue placeholder="Item" />
                        </SelectTrigger>
                        <SelectContent>
                          {items?.items.map((i) => (
                            <SelectItem key={i.id} value={i.id}>
                              {i.sku} — {i.name}
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
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="Qty"
                    {...register(`lines.${index}.quantityOrdered`)}
                  />
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
                      <Select value={selectField.value || undefined} onValueChange={selectField.onChange}>
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
                Subtotal: <span className="font-medium text-foreground">{subtotal.toFixed(2)}</span>
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea id="notes" rows={2} {...register("notes")} />
            </div>
          </CardContent>
        </Card>

        {createPurchaseOrder.isError && (
          <p className="text-sm text-destructive">
            {(createPurchaseOrder.error as { response?: { data?: { error?: { message?: string } } } })
              ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate("/procurement/purchase-orders")}>
            Cancel
          </Button>
          <Button type="submit" disabled={createPurchaseOrder.isPending}>
            {createPurchaseOrder.isPending ? "Saving..." : "Create purchase order"}
          </Button>
        </div>
      </form>
    </div>
  );
}
