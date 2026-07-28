import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAssetCategories, useCreateAssetCategory } from "@/features/assets/categories/api/asset-categories-hooks";
import {
  type AssetCategoryFormValues,
  assetCategoryFormSchema,
  depreciationMethodLabels,
  depreciationMethodValues,
} from "@/features/assets/categories/schemas/asset-category-schemas";

export function AssetCategoriesPage() {
  const { data: categories, isLoading, isError } = useAssetCategories();
  const createCategory = useCreateAssetCategory();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssetCategoryFormValues>({
    resolver: zodResolver(assetCategoryFormSchema),
    defaultValues: { name: "", code: "", defaultUsefulLifeYears: 5, defaultDepreciationMethod: "straight_line" },
  });

  const onSubmit = (values: AssetCategoryFormValues) => {
    createCategory.mutate(
      {
        name: values.name,
        code: values.code,
        default_useful_life_years: values.defaultUsefulLifeYears,
        default_depreciation_method: values.defaultDepreciationMethod,
      },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Asset Categories</h1>
          <p className="mt-1 text-muted-foreground">
            Configure default useful life and depreciation method for asset groups.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New category
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All categories</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && <p className="text-sm text-destructive">Failed to load asset categories.</p>}
          {!isLoading && !isError && (categories?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No asset categories yet.</p>
          )}
          {!isLoading && !isError && (categories?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Useful life</TableHead>
                  <TableHead>Depreciation method</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {categories?.map((category) => (
                  <TableRow key={category.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">{category.code}</TableCell>
                    <TableCell className="font-medium">{category.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {category.default_useful_life_years} years
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {depreciationMethodLabels[category.default_depreciation_method]}
                    </TableCell>
                    <TableCell>
                      <Badge variant={category.is_active ? "success" : "secondary"}>
                        {category.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New asset category</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" {...register("name")} />
                {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="code">Code</Label>
                <Input id="code" {...register("code")} />
                {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="defaultUsefulLifeYears">Useful life (years)</Label>
                <Input id="defaultUsefulLifeYears" type="number" {...register("defaultUsefulLifeYears")} />
                {errors.defaultUsefulLifeYears && (
                  <p className="text-sm text-destructive">{errors.defaultUsefulLifeYears.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="defaultDepreciationMethod">Depreciation method</Label>
                <Controller
                  control={control}
                  name="defaultDepreciationMethod"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="defaultDepreciationMethod">
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
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createCategory.isPending}>
                {createCategory.isPending ? "Saving..." : "Create category"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
