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
import { useCreateContract } from "@/features/corporate/contracts/api/contracts-hooks";
import {
  type ContractFormValues,
  contractFormSchema,
  contractTypeLabels,
  contractTypeValues,
} from "@/features/corporate/contracts/schemas/contract-schemas";
import { useProjectsList } from "@/features/corporate/projects/api/projects-hooks";
import { useQuotationsList } from "@/features/corporate/quotations/api/quotations-hooks";

interface ContractFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clientId: string;
}

const emptyValues: ContractFormValues = {
  contractNumber: "",
  projectId: "",
  quotationId: "",
  contractType: "other",
  startDate: "",
  endDate: "",
  contractValue: 0,
  documentUrl: "",
  notes: "",
};

export function ContractFormDialog({ open, onOpenChange, clientId }: ContractFormDialogProps) {
  const createContract = useCreateContract();
  const { data: projects } = useProjectsList({ client_id: clientId, limit: 100 });
  const { data: quotations } = useQuotationsList({ client_id: clientId, limit: 100 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ContractFormValues>({
    resolver: zodResolver(contractFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: ContractFormValues) => {
    createContract.mutate(
      {
        client_id: clientId,
        project_id: values.projectId || undefined,
        quotation_id: values.quotationId || undefined,
        contract_number: values.contractNumber,
        contract_type: values.contractType,
        start_date: values.startDate,
        end_date: values.endDate || undefined,
        contract_value: values.contractValue,
        document_url: values.documentUrl || undefined,
        notes: values.notes || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New contract</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="contractNumber" required>Contract number</Label>
              <Input id="contractNumber" {...register("contractNumber")} />
              {errors.contractNumber && (
                <p className="text-sm text-destructive">{errors.contractNumber.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="contractType" required>Type</Label>
              <Controller
                control={control}
                name="contractType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="contractType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {contractTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {contractTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
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
              <Label htmlFor="quotationId">Quotation</Label>
              <Controller
                control={control}
                name="quotationId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="quotationId">
                      <SelectValue placeholder="Select quotation" />
                    </SelectTrigger>
                    <SelectContent>
                      {quotations?.items.map((q) => (
                        <SelectItem key={q.id} value={q.id}>
                          {q.quotation_number}
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
              <Label htmlFor="contractValue" required>Value</Label>
              <Input id="contractValue" type="number" step="0.01" {...register("contractValue")} />
              {errors.contractValue && (
                <p className="text-sm text-destructive">{errors.contractValue.message}</p>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="documentUrl">Document URL</Label>
            <Input id="documentUrl" {...register("documentUrl")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {createContract.isError && (
            <p className="text-sm text-destructive">
              {(createContract.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createContract.isPending}>
              {createContract.isPending ? "Saving..." : "Create contract"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
