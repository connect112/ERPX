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
import { useCreateVAPTEngagement } from "@/features/corporate/vapt/api/vapt-hooks";
import {
  type VAPTEngagementFormValues,
  vaptEngagementFormSchema,
  vaptEngagementTypeLabels,
  vaptEngagementTypeValues,
} from "@/features/corporate/vapt/schemas/vapt-schemas";

interface VAPTEngagementFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
}

const emptyValues: VAPTEngagementFormValues = {
  scopeDescription: "",
  engagementType: "web_app",
  methodology: "",
  leadTesterEmployeeId: "",
  startDate: "",
  endDate: "",
};

export function VAPTEngagementFormDialog({ open, onOpenChange, projectId }: VAPTEngagementFormDialogProps) {
  const createEngagement = useCreateVAPTEngagement();
  const { data: employees } = useEmployeesList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<VAPTEngagementFormValues>({
    resolver: zodResolver(vaptEngagementFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: VAPTEngagementFormValues) => {
    createEngagement.mutate(
      {
        project_id: projectId,
        scope_description: values.scopeDescription,
        engagement_type: values.engagementType,
        methodology: values.methodology || undefined,
        lead_tester_employee_id: values.leadTesterEmployeeId || undefined,
        start_date: values.startDate,
        end_date: values.endDate || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New VAPT engagement</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="scopeDescription" required>Scope description</Label>
            <Textarea id="scopeDescription" rows={2} {...register("scopeDescription")} />
            {errors.scopeDescription && (
              <p className="text-sm text-destructive">{errors.scopeDescription.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="engagementType" required>Type</Label>
              <Controller
                control={control}
                name="engagementType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="engagementType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {vaptEngagementTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {vaptEngagementTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="leadTesterEmployeeId">Lead tester</Label>
              <Controller
                control={control}
                name="leadTesterEmployeeId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="leadTesterEmployeeId">
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
          <div className="space-y-2">
            <Label htmlFor="methodology">Methodology</Label>
            <Input id="methodology" {...register("methodology")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
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
          </div>

          {createEngagement.isError && (
            <p className="text-sm text-destructive">
              {(createEngagement.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createEngagement.isPending}>
              {createEngagement.isPending ? "Saving..." : "Create engagement"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
