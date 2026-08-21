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
import { useIssueStock } from "@/features/inventory/stock/api/stock-hooks";
import {
  type IssueStockFormValues,
  issueStockFormSchema,
} from "@/features/inventory/stock/schemas/stock-schemas";
import { useItemsList } from "@/features/inventory/items/api/items-hooks";
import { useWarehouses } from "@/features/inventory/warehouses/api/warehouses-hooks";

interface IssueStockDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultItemId?: string;
}

const emptyValues: IssueStockFormValues = { itemId: "", warehouseId: "", quantity: 0, notes: "" };

export function IssueStockDialog({ open, onOpenChange, defaultItemId }: IssueStockDialogProps) {
  const issueStock = useIssueStock();
  const { data: items } = useItemsList({ limit: 200 });
  const { data: warehouses } = useWarehouses(true);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<IssueStockFormValues>({
    resolver: zodResolver(issueStockFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset({ ...emptyValues, itemId: defaultItemId ?? "" });
  }, [open, defaultItemId, reset]);

  const onSubmit = (values: IssueStockFormValues) => {
    issueStock.mutate(
      {
        item_id: values.itemId,
        warehouse_id: values.warehouseId,
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
          <DialogTitle>Issue stock</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="itemId" required>Item</Label>
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
            <Label htmlFor="warehouseId" required>Warehouse</Label>
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
            <Label htmlFor="quantity" required>Quantity</Label>
            <Input id="quantity" type="number" step="0.01" {...register("quantity")} />
            {errors.quantity && <p className="text-sm text-destructive">{errors.quantity.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {issueStock.isError && (
            <p className="text-sm text-destructive">
              {(issueStock.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={issueStock.isPending}>
              {issueStock.isPending ? "Saving..." : "Issue stock"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
