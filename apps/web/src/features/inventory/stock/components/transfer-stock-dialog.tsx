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
import { useTransferStock } from "@/features/inventory/stock/api/stock-hooks";
import {
  type TransferStockFormValues,
  transferStockFormSchema,
} from "@/features/inventory/stock/schemas/stock-schemas";
import { useItemsList } from "@/features/inventory/items/api/items-hooks";
import { useWarehouses } from "@/features/inventory/warehouses/api/warehouses-hooks";

interface TransferStockDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultItemId?: string;
}

const emptyValues: TransferStockFormValues = {
  itemId: "",
  fromWarehouseId: "",
  toWarehouseId: "",
  quantity: 0,
  notes: "",
};

export function TransferStockDialog({ open, onOpenChange, defaultItemId }: TransferStockDialogProps) {
  const transferStock = useTransferStock();
  const { data: items } = useItemsList({ limit: 200 });
  const { data: warehouses } = useWarehouses(true);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TransferStockFormValues>({
    resolver: zodResolver(transferStockFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset({ ...emptyValues, itemId: defaultItemId ?? "" });
  }, [open, defaultItemId, reset]);

  const onSubmit = (values: TransferStockFormValues) => {
    transferStock.mutate(
      {
        item_id: values.itemId,
        from_warehouse_id: values.fromWarehouseId,
        to_warehouse_id: values.toWarehouseId,
        quantity: values.quantity,
        notes: values.notes || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Transfer stock</DialogTitle>
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
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="fromWarehouseId">From warehouse</Label>
              <Controller
                control={control}
                name="fromWarehouseId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="fromWarehouseId">
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
              {errors.fromWarehouseId && (
                <p className="text-sm text-destructive">{errors.fromWarehouseId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="toWarehouseId">To warehouse</Label>
              <Controller
                control={control}
                name="toWarehouseId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="toWarehouseId">
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
              {errors.toWarehouseId && (
                <p className="text-sm text-destructive">{errors.toWarehouseId.message}</p>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="quantity">Quantity</Label>
            <Input id="quantity" type="number" step="0.01" {...register("quantity")} />
            {errors.quantity && <p className="text-sm text-destructive">{errors.quantity.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {transferStock.isError && (
            <p className="text-sm text-destructive">
              {(transferStock.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={transferStock.isPending}>
              {transferStock.isPending ? "Transferring..." : "Transfer stock"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
