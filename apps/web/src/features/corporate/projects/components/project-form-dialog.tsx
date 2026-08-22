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
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import { useCreateProject } from "@/features/corporate/projects/api/projects-hooks";
import {
  type ProjectFormValues,
  projectFormSchema,
  projectTypeLabels,
  projectTypeValues,
} from "@/features/corporate/projects/schemas/project-schemas";

interface ProjectFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clientId: string;
}

const emptyValues: ProjectFormValues = {
  projectCode: "",
  name: "",
  description: "",
  projectType: "other",
  projectManagerEmployeeId: "",
  startDate: "",
  endDate: "",
  budgetAmount: undefined,
  notes: "",
};

export function ProjectFormDialog({ open, onOpenChange, clientId }: ProjectFormDialogProps) {
  const createProject = useCreateProject();
  const { data: employees } = useEmployeesList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: ProjectFormValues) => {
    createProject.mutate(
      {
        client_id: clientId,
        project_code: values.projectCode,
        name: values.name,
        description: values.description || undefined,
        project_type: values.projectType,
        project_manager_employee_id: values.projectManagerEmployeeId || undefined,
        start_date: values.startDate,
        end_date: values.endDate || undefined,
        budget_amount: values.budgetAmount,
        notes: values.notes || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="projectCode" required>Project code</Label>
              <Input id="projectCode" {...register("projectCode")} />
              {errors.projectCode && (
                <p className="text-sm text-destructive">{errors.projectCode.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="projectType" required>Type</Label>
              <Controller
                control={control}
                name="projectType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="projectType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {projectTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {projectTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="projectManagerEmployeeId">Project manager</Label>
              <Controller
                control={control}
                name="projectManagerEmployeeId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="projectManagerEmployeeId">
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
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="startDate" required>Start date</Label>
              <Input id="startDate" type="date" {...register("startDate")} />
              {errors.startDate && (
                <p className="text-sm text-destructive">{errors.startDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="endDate">End date</Label>
              <Input id="endDate" type="date" {...register("endDate")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="budgetAmount">Budget</Label>
              <Input id="budgetAmount" type="number" step="0.01" {...register("budgetAmount")} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {createProject.isError && (
            <p className="text-sm text-destructive">
              {(createProject.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createProject.isPending}>
              {createProject.isPending ? "Saving..." : "Create project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
