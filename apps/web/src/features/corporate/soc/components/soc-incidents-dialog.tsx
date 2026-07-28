import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useState } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import { useCreateSOCIncident, useSOCIncidents, useUpdateSOCIncident } from "@/features/corporate/soc/api/soc-hooks";
import { IncidentSeverityBadge, IncidentStatusBadge } from "@/features/corporate/soc/components/soc-badges";
import {
  type SOCIncidentFormValues,
  incidentSeverityLabels,
  incidentSeverityValues,
  incidentStatusValues,
  socIncidentFormSchema,
} from "@/features/corporate/soc/schemas/soc-schemas";

interface SOCIncidentsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serviceId: string | null;
}

export function SOCIncidentsDialog({ open, onOpenChange, serviceId }: SOCIncidentsDialogProps) {
  const { data: incidents, isLoading } = useSOCIncidents(serviceId ?? undefined);
  const { data: employees } = useEmployeesList({ limit: 200 });
  const createIncident = useCreateSOCIncident(serviceId ?? "");
  const updateIncident = useUpdateSOCIncident();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SOCIncidentFormValues>({
    resolver: zodResolver(socIncidentFormSchema),
    defaultValues: { title: "", severity: "medium", description: "", detectedAt: "", assignedToEmployeeId: "" },
  });

  const onSubmit = (values: SOCIncidentFormValues) => {
    createIncident.mutate(
      {
        title: values.title,
        severity: values.severity,
        description: values.description,
        detected_at: new Date(values.detectedAt).toISOString(),
        assigned_to_employee_id: values.assignedToEmployeeId || undefined,
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>SOC incidents</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setFormOpen(true)}>
              <Plus className="h-4 w-4" />
              Report incident
            </Button>
          </div>
          {isLoading && <Skeleton className="h-24 w-full" />}
          {!isLoading && (incidents?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No incidents reported.</p>
          )}
          {!isLoading && (incidents?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {incidents?.map((incident) => (
                  <TableRow key={incident.id}>
                    <TableCell className="max-w-[160px] truncate font-medium">{incident.title}</TableCell>
                    <TableCell>
                      <IncidentSeverityBadge severity={incident.severity} />
                    </TableCell>
                    <TableCell>
                      <Select
                        value={incident.status}
                        onValueChange={(value) =>
                          updateIncident.mutate({ incidentId: incident.id, payload: { status: value as typeof incident.status } })
                        }
                      >
                        <SelectTrigger className="h-8 w-36">
                          <SelectValue>
                            <IncidentStatusBadge status={incident.status} />
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          {incidentStatusValues.map((s) => (
                            <SelectItem key={s} value={s}>
                              {s}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </DialogContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Report SOC incident</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="severity">Severity</Label>
                <Controller
                  control={control}
                  name="severity"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="severity">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {incidentSeverityValues.map((s) => (
                          <SelectItem key={s} value={s}>
                            {incidentSeverityLabels[s]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="detectedAt">Detected at</Label>
                <Input id="detectedAt" type="datetime-local" {...register("detectedAt")} />
                {errors.detectedAt && (
                  <p className="text-sm text-destructive">{errors.detectedAt.message}</p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={2} {...register("description")} />
              {errors.description && (
                <p className="text-sm text-destructive">{errors.description.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="assignedToEmployeeId">Assigned to</Label>
              <Controller
                control={control}
                name="assignedToEmployeeId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="assignedToEmployeeId">
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
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createIncident.isPending}>
                {createIncident.isPending ? "Saving..." : "Report incident"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Dialog>
  );
}
