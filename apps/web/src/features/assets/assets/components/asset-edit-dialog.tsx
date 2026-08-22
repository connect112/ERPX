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
import { useAssetCategories } from "@/features/assets/categories/api/asset-categories-hooks";
import type { AssetPublic } from "@/features/assets/assets/api/assets-api";
import { useUpdateAsset } from "@/features/assets/assets/api/assets-hooks";
import {
  type AssetEditFormValues,
  assetEditFormSchema,
  assetStatusLabels,
  assetStatusValues,
} from "@/features/assets/assets/schemas/asset-schemas";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";

interface AssetEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  asset: AssetPublic;
}

export function AssetEditDialog({ open, onOpenChange, asset }: AssetEditDialogProps) {
  const updateAsset = useUpdateAsset(asset.id);
  const { data: categories } = useAssetCategories(true);
  const { data: employees } = useEmployeesList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssetEditFormValues>({ resolver: zodResolver(assetEditFormSchema) });

  useEffect(() => {
    if (open) {
      reset({
        name: asset.name,
        categoryId: asset.category_id ?? "",
        assignedToEmployeeId: asset.assigned_to_employee_id ?? "",
        description: asset.description ?? "",
        location: asset.location ?? "",
        status: asset.status,
        notes: asset.notes ?? "",
      });
    }
  }, [open, asset, reset]);

  const onSubmit = (values: AssetEditFormValues) => {
    updateAsset.mutate(
      {
        name: values.name,
        category_id: values.categoryId || undefined,
        assigned_to_employee_id: values.assignedToEmployeeId || undefined,
        description: values.description || undefined,
        location: values.location || undefined,
        status: values.status,
        notes: values.notes || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit asset</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name" required>Name</Label>
            <Input id="name" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
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
              <Label htmlFor="assignedToEmployeeId">Assigned to</Label>
              <Controller
                control={control}
                name="assignedToEmployeeId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="assignedToEmployeeId">
                      <SelectValue placeholder="Select employee" />
                    </SelectTrigger>
                    <SelectContent>
                      {employees?.items.map((e) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input placeholder="Location" {...register("location")} />
            <Controller
              control={control}
              name="status"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {assetStatusValues.map((s) => (
                      <SelectItem key={s} value={s}>
                        {assetStatusLabels[s]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {updateAsset.isError && (
            <p className="text-sm text-destructive">
              {(updateAsset.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateAsset.isPending}>
              {updateAsset.isPending ? "Saving..." : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
