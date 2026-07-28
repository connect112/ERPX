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
import { useAdjustStock } from "@/features/inventory/stock/api/stock-hooks";
import {
  type AdjustStockFormValues,
  adjustStockFormSchema,
} from "@/features/inventory/stock/schemas/stock-schemas";
import { useItemsList } from "@/features/inventory/items/api/items-hooks";
import { useWarehouses } from "@/features/inventory/warehouses/api/warehouses-hooks";

interface AdjustStockDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultItemId?: string;
}

const emptyValues: AdjustStockFormValues = {
  itemId: "",
  warehouseId: "",
  quantityChange: 0,
  unitCost: 0,
  reason: "",
};

export function AdjustStockDialog({ open, onOpenChange, defaultItemId }: AdjustStockDialogProps) {
  const adjustStock = useAdjustStock();
  const { data: items } = useItemsList({ limit: 200 });
  const { data: warehouses } = useWarehouses(true);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AdjustStockFormValues>({
    resolver: zodResolver(adjustStockFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset({ ...emptyValues, itemId: defaultItemId ?? "" });
  }, [open, defaultItemId, reset]);

  const onSubmit = (values: AdjustStockFormValues) => {
    adjustStock.mutate(
      {
        item_id: values.itemId,
        warehouse_id: values.warehouseId,
        quantity_change: values.quantityChange,
        unit_cost: values.unitCost,
        reason: values.reason,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Adjust stock</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="itemId">Item</Label>
            <Controller
              control={control}
              name="itemId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange} disabled={!!defaultItemId}>
                  <SelectTrigger id="itemId">
                    <SelectValue placeholder="Select item" />
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
            {errors.itemId && <p className="text-sm text-destructive">{errors.itemId.message}</p>}
          </div>
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
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="quantityChange">Quantity change</Label>
              <Input id="quantityChange" type="number" step="0.01" {...register("quantityChange")} />
              <p className="text-xs text-muted-foreground">Positive to increase, negative to decrease.</p>
              {errors.quantityChange && (
                <p className="text-sm text-destructive">{errors.quantityChange.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="unitCost">Unit cost</Label>
              <Input id="unitCost" type="number" step="0.01" {...register("unitCost")} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="reason">Reason</Label>
            <Textarea id="reason" rows={2} {...register("reason")} />
            {errors.reason && <p className="text-sm text-destructive">{errors.reason.message}</p>}
          </div>

          {adjustStock.isError && (
            <p className="text-sm text-destructive">
              {(adjustStock.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={adjustStock.isPending}>
              {adjustStock.isPending ? "Saving..." : "Adjust stock"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
