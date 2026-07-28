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
import {
  useCreateDepartment,
  useCreateDesignation,
  useDepartments,
  useDesignations,
} from "@/features/hr/api/hr-hooks";
import {
  type DepartmentFormValues,
  type DesignationFormValues,
  departmentFormSchema,
  designationFormSchema,
} from "@/features/hr/schemas/hr-schemas";

function DepartmentsCard() {
  const { data: departments, isLoading, isError } = useDepartments();
  const createDepartment = useCreateDepartment();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<DepartmentFormValues>({ resolver: zodResolver(departmentFormSchema) });

  const onSubmit = (values: DepartmentFormValues) => {
    createDepartment.mutate(
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
        <CardTitle className="text-base">Departments</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New department
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {isError && <p className="text-sm text-destructive">Failed to load departments.</p>}
        {!isLoading && !isError && (departments?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No departments yet.</p>
        )}
        {departments?.map((department) => (
          <div key={department.id} className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">
                {department.code} — {department.name}
              </p>
              {department.description && (
                <p className="text-xs text-muted-foreground">{department.description}</p>
              )}
            </div>
            <Badge variant={department.is_active ? "success" : "secondary"}>
              {department.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New department</DialogTitle>
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
              <Button type="submit" disabled={createDepartment.isPending}>
                {createDepartment.isPending ? "Saving..." : "Create department"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function DesignationsCard() {
  const { data: designations, isLoading, isError } = useDesignations();
  const createDesignation = useCreateDesignation();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<DesignationFormValues>({ resolver: zodResolver(designationFormSchema) });

  const onSubmit = (values: DesignationFormValues) => {
    createDesignation.mutate(
      {
        title: values.title,
        code: values.code,
        grade_level: values.gradeLevel ? Number(values.gradeLevel) : undefined,
        description: values.description || undefined,
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
        <CardTitle className="text-base">Designations</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New designation
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {isError && <p className="text-sm text-destructive">Failed to load designations.</p>}
        {!isLoading && !isError && (designations?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No designations yet.</p>
        )}
        {designations?.map((designation) => (
          <div key={designation.id} className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">
                {designation.code} — {designation.title}
              </p>
              {designation.grade_level && (
                <p className="text-xs text-muted-foreground">Grade {designation.grade_level}</p>
              )}
            </div>
            <Badge variant={designation.is_active ? "success" : "secondary"}>
              {designation.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New designation</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input id="title" {...register("title")} />
                {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="code">Code</Label>
                <Input id="code" {...register("code")} />
                {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="gradeLevel">Grade level</Label>
              <Input id="gradeLevel" type="number" {...register("gradeLevel")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={2} {...register("description")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createDesignation.isPending}>
                {createDesignation.isPending ? "Saving..." : "Create designation"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export function HRSettingsPage() {
  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Departments &amp; Designations</h1>
        <p className="mt-1 text-muted-foreground">
          The organizational structure employees are assigned into.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <DepartmentsCard />
        <DesignationsCard />
      </div>
    </div>
  );
}
