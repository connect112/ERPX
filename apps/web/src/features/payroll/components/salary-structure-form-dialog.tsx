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
import { useCreateSalaryStructure, useSalaryComponents } from "@/features/payroll/api/payroll-hooks";
import {
  type SalaryStructureFormValues,
  salaryStructureFormSchema,
} from "@/features/payroll/schemas/payroll-schemas";

interface SalaryStructureFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeId: string;
}

const emptyValues: SalaryStructureFormValues = {
  effectiveFrom: "",
  notes: "",
  lines: [{ salaryComponentId: "", amount: 0 }],
};

export function SalaryStructureFormDialog({
  open,
  onOpenChange,
  employeeId,
}: SalaryStructureFormDialogProps) {
  const createStructure = useCreateSalaryStructure();
  const { data: components } = useSalaryComponents(true);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SalaryStructureFormValues>({
    resolver: zodResolver(salaryStructureFormSchema),
    defaultValues: emptyValues,
  });

  const { fields, append, remove } = useFieldArray({ control, name: "lines" });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: SalaryStructureFormValues) => {
    createStructure.mutate(
      {
        employee_id: employeeId,
        effective_from: values.effectiveFrom,
        notes: values.notes || undefined,
        lines: values.lines.map((line) => ({
          salary_component_id: line.salaryComponentId,
          amount: line.amount,
        })),
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New salary structure</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="effectiveFrom">Effective from</Label>
            <Input id="effectiveFrom" type="date" {...register("effectiveFrom")} />
            {errors.effectiveFrom && (
              <p className="text-sm text-destructive">{errors.effectiveFrom.message}</p>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Components
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => append({ salaryComponentId: "", amount: 0 })}
              >
                <Plus className="h-4 w-4" />
                Add line
              </Button>
            </div>
            {fields.map((field, index) => (
              <div key={field.id} className="flex items-end gap-2">
                <div className="flex-1 space-y-2">
                  <Label htmlFor={`lines.${index}.salaryComponentId`}>Component</Label>
                  <Controller
                    control={control}
                    name={`lines.${index}.salaryComponentId`}
                    render={({ field: selectField }) => (
                      <Select value={selectField.value || undefined} onValueChange={selectField.onChange}>
                        <SelectTrigger id={`lines.${index}.salaryComponentId`}>
                          <SelectValue placeholder="Select component" />
                        </SelectTrigger>
                        <SelectContent>
                          {components?.map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                              {c.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
                <div className="w-32 space-y-2">
                  <Label htmlFor={`lines.${index}.amount`}>Amount</Label>
                  <Input
                    id={`lines.${index}.amount`}
                    type="number"
                    step="0.01"
                    {...register(`lines.${index}.amount`)}
                  />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  disabled={fields.length === 1}
                  onClick={() => remove(index)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {errors.lines?.message && (
              <p className="text-sm text-destructive">{errors.lines.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {createStructure.isError && (
            <p className="text-sm text-destructive">
              {(createStructure.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createStructure.isPending}>
              {createStructure.isPending ? "Saving..." : "Create structure"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
