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
import { useCreateSOCService } from "@/features/corporate/soc/api/soc-hooks";
import {
  type SOCServiceFormValues,
  socServiceFormSchema,
  socServiceTypeLabels,
  socServiceTypeValues,
} from "@/features/corporate/soc/schemas/soc-schemas";
import { useProjectsList } from "@/features/corporate/projects/api/projects-hooks";

interface SOCFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clientId: string;
}

const emptyValues: SOCServiceFormValues = {
  projectId: "",
  serviceType: "monitoring",
  slaResponseTimeMinutes: undefined,
  startDate: "",
  endDate: "",
  notes: "",
};

export function SOCFormDialog({ open, onOpenChange, clientId }: SOCFormDialogProps) {
  const createService = useCreateSOCService();
  const { data: projects } = useProjectsList({ client_id: clientId, limit: 100 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SOCServiceFormValues>({
    resolver: zodResolver(socServiceFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: SOCServiceFormValues) => {
    createService.mutate(
      {
        client_id: clientId,
        project_id: values.projectId || undefined,
        service_type: values.serviceType,
        sla_response_time_minutes: values.slaResponseTimeMinutes,
        start_date: values.startDate,
        end_date: values.endDate || undefined,
        notes: values.notes || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New SOC service</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="serviceType">Service type</Label>
              <Controller
                control={control}
                name="serviceType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="serviceType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {socServiceTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {socServiceTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="projectId">Project</Label>
              <Controller
                control={control}
                name="projectId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="projectId">
                      <SelectValue placeholder="Select project" />
                    </SelectTrigger>
                    <SelectContent>
                      {projects?.items.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.name}
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
              <Label htmlFor="startDate">Start date</Label>
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
              <Label htmlFor="slaResponseTimeMinutes">SLA (min)</Label>
              <Input id="slaResponseTimeMinutes" type="number" {...register("slaResponseTimeMinutes")} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {createService.isError && (
            <p className="text-sm text-destructive">
              {(createService.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createService.isPending}>
              {createService.isPending ? "Saving..." : "Create service"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
