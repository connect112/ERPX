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
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import { useAssetCategories } from "@/features/assets/categories/api/asset-categories-hooks";
import {
  depreciationMethodLabels,
  depreciationMethodValues,
} from "@/features/assets/categories/schemas/asset-category-schemas";
import { useCreateAsset } from "@/features/assets/assets/api/assets-hooks";
import { type AssetFormValues, assetFormSchema } from "@/features/assets/assets/schemas/asset-schemas";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";

interface AssetCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const emptyValues: AssetFormValues = {
  assetCode: "",
  name: "",
  categoryId: "",
  assignedToEmployeeId: "",
  assetAccountId: "",
  accumulatedDepreciationAccountId: "",
  depreciationExpenseAccountId: "",
  description: "",
  location: "",
  purchaseDate: "",
  purchaseCost: 0,
  salvageValue: 0,
  usefulLifeYears: 5,
  depreciationMethod: "straight_line",
  notes: "",
};

export function AssetCreateDialog({ open, onOpenChange }: AssetCreateDialogProps) {
  const createAsset = useCreateAsset();
  const { data: categories } = useAssetCategories(true);
  const { data: accounts } = useAccountsList({ limit: 200 });
  const { data: employees } = useEmployeesList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssetFormValues>({
    resolver: zodResolver(assetFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: AssetFormValues) => {
    createAsset.mutate(
      {
        asset_code: values.assetCode,
        name: values.name,
        category_id: values.categoryId || undefined,
        assigned_to_employee_id: values.assignedToEmployeeId || undefined,
        asset_account_id: values.assetAccountId,
        accumulated_depreciation_account_id: values.accumulatedDepreciationAccountId,
        depreciation_expense_account_id: values.depreciationExpenseAccountId,
        description: values.description || undefined,
        location: values.location || undefined,
        purchase_date: values.purchaseDate,
        purchase_cost: values.purchaseCost,
        salvage_value: values.salvageValue,
        useful_life_years: values.usefulLifeYears,
        depreciation_method: values.depreciationMethod,
        notes: values.notes || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New asset</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="assetCode" required>Asset code</Label>
              <Input id="assetCode" {...register("assetCode")} />
              {errors.assetCode && <p className="text-sm text-destructive">{errors.assetCode.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
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

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              GL accounts
            </p>
            <div className="space-y-2">
              <Label htmlFor="assetAccountId" required>Fixed asset account</Label>
              <Controller
                control={control}
                name="assetAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="assetAccountId">
                      <SelectValue placeholder="Select GL account" />
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
              {errors.assetAccountId && (
                <p className="text-sm text-destructive">{errors.assetAccountId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="accumulatedDepreciationAccountId" required>Accumulated depreciation account</Label>
              <Controller
                control={control}
                name="accumulatedDepreciationAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="accumulatedDepreciationAccountId">
                      <SelectValue placeholder="Select GL account" />
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
              {errors.accumulatedDepreciationAccountId && (
                <p className="text-sm text-destructive">
                  {errors.accumulatedDepreciationAccountId.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="depreciationExpenseAccountId" required>Depreciation expense account</Label>
              <Controller
                control={control}
                name="depreciationExpenseAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="depreciationExpenseAccountId">
                      <SelectValue placeholder="Select GL account" />
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
              {errors.depreciationExpenseAccountId && (
                <p className="text-sm text-destructive">
                  {errors.depreciationExpenseAccountId.message}
                </p>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Purchase &amp; depreciation
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="purchaseDate" required>Purchase date</Label>
                <Input id="purchaseDate" type="date" {...register("purchaseDate")} />
                {errors.purchaseDate && (
                  <p className="text-sm text-destructive">{errors.purchaseDate.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="purchaseCost" required>Purchase cost</Label>
                <Input id="purchaseCost" type="number" step="0.01" {...register("purchaseCost")} />
                {errors.purchaseCost && (
                  <p className="text-sm text-destructive">{errors.purchaseCost.message}</p>
                )}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="salvageValue">Salvage value</Label>
                <Input id="salvageValue" type="number" step="0.01" {...register("salvageValue")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="usefulLifeYears" required>Useful life (years)</Label>
                <Input id="usefulLifeYears" type="number" {...register("usefulLifeYears")} />
                {errors.usefulLifeYears && (
                  <p className="text-sm text-destructive">{errors.usefulLifeYears.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="depreciationMethod" required>Method</Label>
                <Controller
                  control={control}
                  name="depreciationMethod"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="depreciationMethod">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {depreciationMethodValues.map((m) => (
                          <SelectItem key={m} value={m}>
                            {depreciationMethodLabels[m]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input placeholder="Location" {...register("location")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {createAsset.isError && (
            <p className="text-sm text-destructive">
              {(createAsset.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createAsset.isPending}>
              {createAsset.isPending ? "Saving..." : "Create asset"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
