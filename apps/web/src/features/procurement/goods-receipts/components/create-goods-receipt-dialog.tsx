import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";

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
import type { PurchaseOrderPublic } from "@/features/procurement/purchase-orders/api/purchase-orders-api";
import { useCreateGoodsReceipt } from "@/features/procurement/goods-receipts/api/goods-receipts-hooks";
import {
  type GoodsReceiptFormValues,
  goodsReceiptFormSchema,
} from "@/features/procurement/goods-receipts/schemas/goods-receipt-schemas";
import { useWarehouses } from "@/features/inventory/warehouses/api/warehouses-hooks";

interface CreateGoodsReceiptDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  po: PurchaseOrderPublic;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function CreateGoodsReceiptDialog({ open, onOpenChange, po }: CreateGoodsReceiptDialogProps) {
  const createGoodsReceipt = useCreateGoodsReceipt();
  const { data: warehouses } = useWarehouses(true);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<GoodsReceiptFormValues>({
    resolver: zodResolver(goodsReceiptFormSchema),
    defaultValues: { warehouseId: "", receiptNumber: "", receiptDate: todayIso(), notes: "", lines: [] },
  });

  const { fields } = useFieldArray({ control, name: "lines" });

  useEffect(() => {
    if (open) {
      reset({
        warehouseId: "",
        receiptNumber: "",
        receiptDate: todayIso(),
        notes: "",
        lines: po.lines
          .filter((line) => line.quantity_received < line.quantity_ordered)
          .map((line) => ({
            purchaseOrderLineId: line.id,
            description: line.description,
            quantityReceived: line.quantity_ordered - line.quantity_received,
            unitCost: line.unit_price,
          })),
      });
    }
  }, [open, po, reset]);

  const onSubmit = (values: GoodsReceiptFormValues) => {
    createGoodsReceipt.mutate(
      {
        purchase_order_id: po.id,
        warehouse_id: values.warehouseId,
        receipt_number: values.receiptNumber,
        receipt_date: new Date(values.receiptDate).toISOString(),
        notes: values.notes || undefined,
        lines: values.lines.map((l) => ({
          purchase_order_line_id: l.purchaseOrderLineId,
          quantity_received: l.quantityReceived,
          unit_cost: l.unitCost,
        })),
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Receive goods for {po.po_number}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="warehouseId">Warehouse</Label>
              <Controller
                control={control}
                name="warehouseId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="warehouseId">
                      <SelectValue placeholder="Select warehouse" />
                    </SelectTrigger>
                    <SelectContent>
                      {warehouses?.map((w) => (
                        <SelectItem key={w.id} value={w.id}>
                          {w.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.warehouseId && (
                <p className="text-sm text-destructive">{errors.warehouseId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="receiptNumber">Receipt number</Label>
              <Input id="receiptNumber" {...register("receiptNumber")} />
              {errors.receiptNumber && (
                <p className="text-sm text-destructive">{errors.receiptNumber.message}</p>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="receiptDate">Receipt date</Label>
            <Input id="receiptDate" type="date" {...register("receiptDate")} />
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Lines to receive
            </p>
            {fields.length === 0 && (
              <p className="text-sm text-muted-foreground">
                All lines on this purchase order have already been fully received.
              </p>
            )}
            {fields.map((field, index) => (
              <div key={field.id} className="grid grid-cols-12 items-center gap-2">
                <span className="col-span-5 truncate text-sm">{field.description}</span>
                <div className="col-span-3">
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="Qty received"
                    {...register(`lines.${index}.quantityReceived`)}
                  />
                </div>
                <div className="col-span-4">
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="Unit cost"
                    {...register(`lines.${index}.unitCost`)}
                  />
                </div>
              </div>
            ))}
            {errors.lines?.message && <p className="text-sm text-destructive">{errors.lines.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {createGoodsReceipt.isError && (
            <p className="text-sm text-destructive">
              {(createGoodsReceipt.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createGoodsReceipt.isPending || fields.length === 0}>
              {createGoodsReceipt.isPending ? "Saving..." : "Receive goods"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
