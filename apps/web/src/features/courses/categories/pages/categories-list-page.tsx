import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from "@/features/courses/categories/api/categories-hooks";
import type { CategoryPublic } from "@/features/courses/categories/api/categories-api";
import {
  type CategoryFormValues,
  categoryFormSchema,
} from "@/features/courses/categories/schemas/category-schemas";

export function CategoriesListPage() {
  const { data: categories, isLoading, isError } = useCategories();
  const createCategory = useCreateCategory();
  const updateCategory = useUpdateCategory();
  const deleteCategory = useDeleteCategory();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<CategoryPublic | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CategoryFormValues>({ resolver: zodResolver(categoryFormSchema) });

  useEffect(() => {
    if (formOpen) {
      reset(
        editing
          ? { name: editing.name, slug: editing.slug, description: editing.description ?? "" }
          : { name: "", slug: "", description: "" }
      );
    }
  }, [formOpen, editing, reset]);

  const onSubmit = (values: CategoryFormValues) => {
    if (editing) {
      updateCategory.mutate(
        { id: editing.id, payload: { name: values.name, description: values.description || undefined } },
        { onSuccess: () => setFormOpen(false) }
      );
    } else {
      createCategory.mutate(
        { name: values.name, slug: values.slug, description: values.description || undefined },
        { onSuccess: () => setFormOpen(false) }
      );
    }
  };

  const mutationPending = editing ? updateCategory.isPending : createCategory.isPending;
  const mutationError = editing ? updateCategory.error : createCategory.error;
  const mutationIsError = editing ? updateCategory.isError : createCategory.isError;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Course Categories</h1>
          <p className="mt-1 text-muted-foreground">Organize courses into browsable categories.</p>
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" />
          New Category
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-3 p-6">
          {isLoading && <Skeleton className="h-24 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load categories.</p>
          )}
          {!isLoading && !isError && (categories?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No categories yet. Create one to start organizing courses.
            </p>
          )}
          {categories?.map((category) => (
            <div
              key={category.id}
              className="flex items-center justify-between rounded-md border p-3"
            >
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium">{category.name}</p>
                  <Badge variant={category.is_active ? "success" : "secondary"}>
                    {category.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">{category.slug}</p>
                {category.description && (
                  <p className="mt-1 text-xs text-muted-foreground">{category.description}</p>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    updateCategory.mutate({
                      id: category.id,
                      payload: { is_active: !category.is_active },
                    })
                  }
                >
                  {category.is_active ? "Deactivate" : "Activate"}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    setEditing(category);
                    setFormOpen(true);
                  }}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteCategory.mutate(category.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit category" : "New category"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            {!editing && (
              <div className="space-y-2">
                <Label htmlFor="slug">Slug</Label>
                <Input id="slug" placeholder="e.g. web-development" {...register("slug")} />
                {errors.slug && <p className="text-sm text-destructive">{errors.slug.message}</p>}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={3} {...register("description")} />
            </div>
            {mutationIsError && (
              <p className="text-sm text-destructive">
                {(mutationError as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutationPending}>
                {mutationPending ? "Saving..." : editing ? "Save changes" : "Create category"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
