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
import { useItemCategories } from "@/features/inventory/categories/api/item-categories-hooks";
import type { InventoryItemPublic } from "@/features/inventory/items/api/items-api";
import { useCreateItem, useUpdateItem } from "@/features/inventory/items/api/items-hooks";
import { type ItemFormValues, itemFormSchema } from "@/features/inventory/items/schemas/item-schemas";

interface ItemFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item?: InventoryItemPublic;
}

const emptyValues: ItemFormValues = {
  sku: "",
  name: "",
  categoryId: "",
  description: "",
  unitOfMeasure: "",
  reorderLevel: 0,
  reorderQuantity: 0,
  standardCost: 0,
};

export function ItemFormDialog({ open, onOpenChange, item }: ItemFormDialogProps) {
  const isEditing = !!item;
  const createItem = useCreateItem();
  const updateItem = useUpdateItem(item?.id ?? "");
  const { data: categories } = useItemCategories(true);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ItemFormValues>({
    resolver: zodResolver(itemFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        item
          ? {
              sku: item.sku,
              name: item.name,
              categoryId: item.category_id ?? "",
              description: item.description ?? "",
              unitOfMeasure: item.unit_of_measure,
              reorderLevel: item.reorder_level,
              reorderQuantity: item.reorder_quantity,
              standardCost: item.standard_cost,
            }
          : emptyValues
      );
    }
  }, [open, item, reset]);

  const mutation = isEditing ? updateItem : createItem;

  const onSubmit = (values: ItemFormValues) => {
    const shared = {
      name: values.name,
      category_id: values.categoryId || undefined,
      description: values.description || undefined,
      unit_of_measure: values.unitOfMeasure,
      reorder_level: values.reorderLevel,
      reorder_quantity: values.reorderQuantity,
      standard_cost: values.standardCost,
    };

    if (isEditing) {
      updateItem.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createItem.mutate({ ...shared, sku: values.sku }, { onSuccess: () => onOpenChange(false) });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit item" : "New item"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="sku">SKU</Label>
              <Input id="sku" disabled={isEditing} {...register("sku")} />
              {errors.sku && <p className="text-sm text-destructive">{errors.sku.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="categoryId">Category</Label>
              <Controller
                control={control}
                name="categoryId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="categoryId">
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                    <SelectContent>
                      {categories?.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="unitOfMeasure">Unit of measure</Label>
              <Input id="unitOfMeasure" placeholder="e.g. pcs, kg, box" {...register("unitOfMeasure")} />
              {errors.unitOfMeasure && (
                <p className="text-sm text-destructive">{errors.unitOfMeasure.message}</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="reorderLevel">Reorder level</Label>
              <Input id="reorderLevel" type="number" step="0.01" {...register("reorderLevel")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reorderQuantity">Reorder qty</Label>
              <Input id="reorderQuantity" type="number" step="0.01" {...register("reorderQuantity")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="standardCost">Standard cost</Label>
              <Input id="standardCost" type="number" step="0.01" {...register("standardCost")} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>

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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create item"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
