import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";

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
import { useDeleteRole, useRole, useUpdateRole } from "@/features/authorization/api/authorization-hooks";
import { RolePermissionsEditor } from "@/features/authorization/components/role-permissions-editor";
import { type RoleUpdateFormValues, roleUpdateFormSchema } from "@/features/authorization/schemas/role-schemas";

export function RoleDetailPage() {
  const { roleId } = useParams<{ roleId: string }>();
  const navigate = useNavigate();
  const { data: role, isLoading } = useRole(roleId);
  const updateRole = useUpdateRole(roleId ?? "");
  const deleteRole = useDeleteRole();

  const [deleteOpen, setDeleteOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RoleUpdateFormValues>({ resolver: zodResolver(roleUpdateFormSchema) });

  useEffect(() => {
    if (role) reset({ name: role.name, description: role.description ?? "" });
  }, [role, reset]);

  if (isLoading || !role) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const onSubmit = (values: RoleUpdateFormValues) => {
    updateRole.mutate({ name: values.name, description: values.description || undefined });
  };

  const handleDelete = () => {
    deleteRole.mutate(role.id, { onSuccess: () => navigate("/administration/roles") });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/administration/roles")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{role.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{role.slug}</span>
              <Badge variant={role.is_system ? "secondary" : "info"}>
                {role.is_system ? "System" : "Custom"}
              </Badge>
            </div>
          </div>
        </div>
        {!role.is_system && (
          <Button variant="outline" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Role details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
              <Input id="name" disabled={role.is_system} {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={2} disabled={role.is_system} {...register("description")} />
            </div>
            {!role.is_system && (
              <div className="flex justify-end">
                <Button type="submit" disabled={updateRole.isPending}>
                  {updateRole.isPending ? "Saving..." : "Save changes"}
                </Button>
              </div>
            )}
          </form>
        </CardContent>
      </Card>

      <RolePermissionsEditor role={role} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete role</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{role.name}</span>? This action
            cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteRole.isPending}>
              {deleteRole.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
