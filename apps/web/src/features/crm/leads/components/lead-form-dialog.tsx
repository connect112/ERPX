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
import { useCreateLead, useUpdateLead } from "@/features/crm/leads/api/leads-hooks";
import type { LeadPublic } from "@/features/crm/leads/api/leads-api";
import {
  type LeadFormValues,
  leadFormSchema,
  leadSourceLabels,
  leadSourceValues,
} from "@/features/crm/leads/schemas/lead-schemas";

interface LeadFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lead?: LeadPublic;
}

export function LeadFormDialog({ open, onOpenChange, lead }: LeadFormDialogProps) {
  const isEditing = !!lead;
  const createLead = useCreateLead();
  const updateLead = useUpdateLead(lead?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LeadFormValues>({
    resolver: zodResolver(leadFormSchema),
    defaultValues: {
      fullName: "",
      email: "",
      phone: "",
      source: "website",
      assignedToUserId: "",
      notes: "",
    },
  });

  useEffect(() => {
    if (open) {
      reset({
        fullName: lead?.full_name ?? "",
        email: lead?.email ?? "",
        phone: lead?.phone ?? "",
        source: lead?.source ?? "website",
        assignedToUserId: lead?.assigned_to_user_id ?? "",
        notes: lead?.notes ?? "",
      });
    }
  }, [open, lead, reset]);

  const mutation = isEditing ? updateLead : createLead;

  const onSubmit = (values: LeadFormValues) => {
    const payload = {
      full_name: values.fullName,
      email: values.email || undefined,
      phone: values.phone || undefined,
      source: values.source,
      assigned_to_user_id: values.assignedToUserId || undefined,
      notes: values.notes || undefined,
    };

    mutation.mutate(payload, {
      onSuccess: () => onOpenChange(false),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit lead" : "New lead"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="fullName" required>Full name</Label>
            <Input id="fullName" {...register("fullName")} />
            {errors.fullName && (
              <p className="text-sm text-destructive">{errors.fullName.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" {...register("email")} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" {...register("phone")} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="source" required>Source</Label>
            <Controller
              control={control}
              name="source"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="source">
                    <SelectValue placeholder="Select a source" />
                  </SelectTrigger>
                  <SelectContent>
                    {leadSourceValues.map((source) => (
                      <SelectItem key={source} value={source}>
                        {leadSourceLabels[source]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={3} {...register("notes")} />
          </div>

          {mutation.isError && (
            <p className="text-sm text-destructive">
              {(mutation.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create lead"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
