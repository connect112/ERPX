import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";

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
import { useRolesList } from "@/features/authorization/api/authorization-hooks";
import { useCreateWorkflow } from "@/features/workflow/api/workflow-hooks";
import {
  type WorkflowFormValues,
  workflowFormSchema,
} from "@/features/workflow/schemas/workflow-schemas";

interface WorkflowFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const emptyValues: WorkflowFormValues = {
  entityType: "",
  name: "",
  description: "",
  steps: [{ stepOrder: 1, approverRoleId: "", name: "" }],
};

export function WorkflowFormDialog({ open, onOpenChange }: WorkflowFormDialogProps) {
  const createWorkflow = useCreateWorkflow();
  const { data: roles } = useRolesList();

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<WorkflowFormValues>({
    resolver: zodResolver(workflowFormSchema),
    defaultValues: emptyValues,
  });

  const { fields, append, remove } = useFieldArray({ control, name: "steps" });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: WorkflowFormValues) => {
    createWorkflow.mutate(
      {
        entity_type: values.entityType,
        name: values.name,
        description: values.description || undefined,
        steps: values.steps.map((s, index) => ({
          step_order: index + 1,
          approver_role_id: s.approverRoleId,
          name: s.name || undefined,
        })),
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New approval workflow</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="entityType">Entity type</Label>
              <Input id="entityType" placeholder="e.g. leave_application" {...register("entityType")} />
              {errors.entityType && (
                <p className="text-sm text-destructive">{errors.entityType.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Approval steps (in order)
              </p>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() =>
                  append({ stepOrder: fields.length + 1, approverRoleId: "", name: "" })
                }
              >
                <Plus className="h-3 w-3" />
                Add step
              </Button>
            </div>
            {errors.steps?.message && (
              <p className="text-sm text-destructive">{errors.steps.message}</p>
            )}
            {fields.map((field, index) => (
              <div key={field.id} className="grid grid-cols-12 items-start gap-2">
                <div className="col-span-1 flex h-10 items-center justify-center text-sm font-medium text-muted-foreground">
                  {index + 1}
                </div>
                <div className="col-span-5">
                  <Controller
                    control={control}
                    name={`steps.${index}.approverRoleId`}
                    render={({ field: roleField }) => (
                      <Select value={roleField.value} onValueChange={roleField.onChange}>
                        <SelectTrigger>
                          <SelectValue placeholder="Approver role" />
                        </SelectTrigger>
                        <SelectContent>
                          {roles?.map((r) => (
                            <SelectItem key={r.id} value={r.id}>
                              {r.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                  {errors.steps?.[index]?.approverRoleId && (
                    <p className="pt-1 text-xs text-destructive">
                      {errors.steps[index]?.approverRoleId?.message}
                    </p>
                  )}
                </div>
                <div className="col-span-5">
                  <Input placeholder="Step name (optional)" {...register(`steps.${index}.name`)} />
                </div>
                <div className="col-span-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    disabled={fields.length <= 1}
                    onClick={() => remove(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>

          {createWorkflow.isError && (
            <p className="text-sm text-destructive">
              {(createWorkflow.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createWorkflow.isPending}>
              {createWorkflow.isPending ? "Saving..." : "Create workflow"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
