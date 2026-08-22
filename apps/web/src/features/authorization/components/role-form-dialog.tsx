import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

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
import { Textarea } from "@/components/ui/textarea";
import { useCreateRole } from "@/features/authorization/api/authorization-hooks";
import { type RoleFormValues, roleFormSchema } from "@/features/authorization/schemas/role-schemas";

interface RoleFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RoleFormDialog({ open, onOpenChange }: RoleFormDialogProps) {
  const createRole = useCreateRole();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RoleFormValues>({
    resolver: zodResolver(roleFormSchema),
    defaultValues: { name: "", slug: "", description: "" },
  });

  const onSubmit = (values: RoleFormValues) => {
    createRole.mutate(
      { name: values.name, slug: values.slug, description: values.description || undefined },
      {
        onSuccess: () => {
          onOpenChange(false);
          reset();
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New role</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="slug" required>Slug</Label>
              <Input id="slug" placeholder="e.g. finance_manager" {...register("slug")} />
              {errors.slug && <p className="text-sm text-destructive">{errors.slug.message}</p>}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>

          {createRole.isError && (
            <p className="text-sm text-destructive">
              {(createRole.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createRole.isPending}>
              {createRole.isPending ? "Saving..." : "Create role"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
