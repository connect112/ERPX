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
import { useCreateAMCContract } from "@/features/corporate/amc/api/amc-hooks";
import {
  type AMCContractFormValues,
  amcContractFormSchema,
  billingFrequencyLabels,
  billingFrequencyValues,
} from "@/features/corporate/amc/schemas/amc-schemas";

interface AMCFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clientId: string;
}

const emptyValues: AMCContractFormValues = {
  amcNumber: "",
  coverageDescription: "",
  startDate: "",
  endDate: "",
  renewalReminderDays: 30,
  amount: 0,
  billingFrequency: "annually",
};

export function AMCFormDialog({ open, onOpenChange, clientId }: AMCFormDialogProps) {
  const createAMC = useCreateAMCContract();

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AMCContractFormValues>({
    resolver: zodResolver(amcContractFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: AMCContractFormValues) => {
    createAMC.mutate(
      {
        client_id: clientId,
        amc_number: values.amcNumber,
        coverage_description: values.coverageDescription,
        start_date: values.startDate,
        end_date: values.endDate,
        renewal_reminder_days: values.renewalReminderDays,
        amount: values.amount,
        billing_frequency: values.billingFrequency,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New AMC contract</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="amcNumber" required>AMC number</Label>
            <Input id="amcNumber" {...register("amcNumber")} />
            {errors.amcNumber && <p className="text-sm text-destructive">{errors.amcNumber.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="coverageDescription" required>Coverage description</Label>
            <Textarea id="coverageDescription" rows={2} {...register("coverageDescription")} />
            {errors.coverageDescription && (
              <p className="text-sm text-destructive">{errors.coverageDescription.message}</p>
            )}
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
              <Label htmlFor="endDate" required>End date</Label>
              <Input id="endDate" type="date" {...register("endDate")} />
              {errors.endDate && <p className="text-sm text-destructive">{errors.endDate.message}</p>}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="amount" required>Amount</Label>
              <Input id="amount" type="number" step="0.01" {...register("amount")} />
              {errors.amount && <p className="text-sm text-destructive">{errors.amount.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="billingFrequency" required>Billing</Label>
              <Controller
                control={control}
                name="billingFrequency"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="billingFrequency">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {billingFrequencyValues.map((f) => (
                        <SelectItem key={f} value={f}>
                          {billingFrequencyLabels[f]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="renewalReminderDays">Reminder (days)</Label>
              <Input id="renewalReminderDays" type="number" {...register("renewalReminderDays")} />
            </div>
          </div>

          {createAMC.isError && (
            <p className="text-sm text-destructive">
              {(createAMC.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createAMC.isPending}>
              {createAMC.isPending ? "Saving..." : "Create AMC contract"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
