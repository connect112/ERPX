import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useCreateItemCategory, useItemCategories } from "@/features/inventory/categories/api/item-categories-hooks";
import {
  type ItemCategoryFormValues,
  itemCategoryFormSchema,
} from "@/features/inventory/categories/schemas/item-category-schemas";
import { useCreateWarehouse, useWarehouses } from "@/features/inventory/warehouses/api/warehouses-hooks";
import {
  type WarehouseFormValues,
  warehouseFormSchema,
} from "@/features/inventory/warehouses/schemas/warehouse-schemas";

function ItemCategoriesCard() {
  const { data: categories, isLoading, isError } = useItemCategories();
  const createCategory = useCreateItemCategory();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ItemCategoryFormValues>({ resolver: zodResolver(itemCategoryFormSchema) });

  const onSubmit = (values: ItemCategoryFormValues) => {
    createCategory.mutate(
      { name: values.name, code: values.code, description: values.description || undefined },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Item Categories</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New category
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {isError && <p className="text-sm text-destructive">Failed to load item categories.</p>}
        {!isLoading && !isError && (categories?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No item categories yet.</p>
        )}
        {categories?.map((category) => (
          <div key={category.id} className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">
                {category.code} — {category.name}
              </p>
              {category.description && (
                <p className="text-xs text-muted-foreground">{category.description}</p>
              )}
            </div>
            <Badge variant={category.is_active ? "success" : "secondary"}>
              {category.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New item category</DialogTitle>
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
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={2} {...register("description")} />
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
    </Card>
  );
}

function WarehousesCard() {
  const { data: warehouses, isLoading, isError } = useWarehouses();
  const createWarehouse = useCreateWarehouse();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<WarehouseFormValues>({ resolver: zodResolver(warehouseFormSchema) });

  const onSubmit = (values: WarehouseFormValues) => {
    createWarehouse.mutate(
      {
        name: values.name,
        code: values.code,
        address_line1: values.addressLine1 || undefined,
        city: values.city || undefined,
        state: values.state || undefined,
        country: values.country || undefined,
        postal_code: values.postalCode || undefined,
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
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Warehouses</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New warehouse
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {isError && <p className="text-sm text-destructive">Failed to load warehouses.</p>}
        {!isLoading && !isError && (warehouses?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No warehouses yet.</p>
        )}
        {warehouses?.map((warehouse) => (
          <div key={warehouse.id} className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">
                {warehouse.code} — {warehouse.name}
              </p>
              <p className="text-xs text-muted-foreground">
                {[warehouse.city, warehouse.state, warehouse.country].filter(Boolean).join(", ") || "—"}
              </p>
            </div>
            <Badge variant={warehouse.is_active ? "success" : "secondary"}>
              {warehouse.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New warehouse</DialogTitle>
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
            <div className="space-y-2">
              <Input placeholder="Address line 1" {...register("addressLine1")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="City" {...register("city")} />
              <Input placeholder="State" {...register("state")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="Country" {...register("country")} />
              <Input placeholder="Postal code" {...register("postalCode")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createWarehouse.isPending}>
                {createWarehouse.isPending ? "Saving..." : "Create warehouse"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export function InventorySettingsPage() {
  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Item Categories &amp; Warehouses</h1>
        <p className="mt-1 text-muted-foreground">
          Configure the catalog structure used across inventory items and stock.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ItemCategoriesCard />
        <WarehousesCard />
      </div>
    </div>
  );
}
