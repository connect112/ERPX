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
import { useCreateTicket } from "@/features/corporate/tickets/api/tickets-hooks";
import {
  type TicketFormValues,
  ticketFormSchema,
  ticketPriorityLabels,
  ticketPriorityValues,
} from "@/features/corporate/tickets/schemas/ticket-schemas";
import { useProjectsList } from "@/features/corporate/projects/api/projects-hooks";

interface TicketFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clientId: string;
}

const emptyValues: TicketFormValues = {
  ticketNumber: "",
  projectId: "",
  subject: "",
  description: "",
  priority: "medium",
  assignedToEmployeeId: "",
  raisedByContactName: "",
  slaDueAt: "",
};

export function TicketFormDialog({ open, onOpenChange, clientId }: TicketFormDialogProps) {
  const createTicket = useCreateTicket();
  const { data: projects } = useProjectsList({ client_id: clientId, limit: 100 });
  const { data: employees } = useEmployeesList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TicketFormValues>({
    resolver: zodResolver(ticketFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: TicketFormValues) => {
    createTicket.mutate(
      {
        client_id: clientId,
        project_id: values.projectId || undefined,
        ticket_number: values.ticketNumber,
        subject: values.subject,
        description: values.description,
        priority: values.priority,
        assigned_to_employee_id: values.assignedToEmployeeId || undefined,
        raised_by_contact_name: values.raisedByContactName || undefined,
        sla_due_at: values.slaDueAt ? new Date(values.slaDueAt).toISOString() : undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New ticket</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="ticketNumber" required>Ticket number</Label>
              <Input id="ticketNumber" {...register("ticketNumber")} />
              {errors.ticketNumber && (
                <p className="text-sm text-destructive">{errors.ticketNumber.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="priority" required>Priority</Label>
              <Controller
                control={control}
                name="priority"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="priority">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ticketPriorityValues.map((p) => (
                        <SelectItem key={p} value={p}>
                          {ticketPriorityLabels[p]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="subject" required>Subject</Label>
            <Input id="subject" {...register("subject")} />
            {errors.subject && <p className="text-sm text-destructive">{errors.subject.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="description" required>Description</Label>
            <Textarea id="description" rows={3} {...register("description")} />
            {errors.description && (
              <p className="text-sm text-destructive">{errors.description.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
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
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input placeholder="Raised by (contact name)" {...register("raisedByContactName")} />
            <Input type="datetime-local" placeholder="SLA due at" {...register("slaDueAt")} />
          </div>

          {createTicket.isError && (
            <p className="text-sm text-destructive">
              {(createTicket.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createTicket.isPending}>
              {createTicket.isPending ? "Saving..." : "Create ticket"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
