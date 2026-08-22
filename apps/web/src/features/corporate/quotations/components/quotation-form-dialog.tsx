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
import { useGSTRates } from "@/features/accounting/gst/api/gst-hooks";
import { useCreateQuotation } from "@/features/corporate/quotations/api/quotations-hooks";
import {
  type QuotationFormValues,
  quotationFormSchema,
} from "@/features/corporate/quotations/schemas/quotation-schemas";
import { useProjectsList } from "@/features/corporate/projects/api/projects-hooks";

interface QuotationFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clientId: string;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

const emptyValues: QuotationFormValues = {
  quotationNumber: "",
  projectId: "",
  quotationDate: todayIso(),
  validUntil: "",
  notes: "",
  lines: [{ description: "", quantity: 1, unitPrice: 0, gstRateId: "" }],
};

export function QuotationFormDialog({ open, onOpenChange, clientId }: QuotationFormDialogProps) {
  const createQuotation = useCreateQuotation();
  const { data: projects } = useProjectsList({ client_id: clientId, limit: 100 });
  const { data: gstRates } = useGSTRates(true);

  const {
    register,
    control,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<QuotationFormValues>({
    resolver: zodResolver(quotationFormSchema),
    defaultValues: emptyValues,
  });

  const { fields, append, remove } = useFieldArray({ control, name: "lines" });
  const lines = watch("lines");
  const subtotal = lines.reduce((sum, l) => sum + (Number(l.quantity) || 0) * (Number(l.unitPrice) || 0), 0);

  useEffect(() => {
    if (open) reset({ ...emptyValues, quotationDate: todayIso() });
  }, [open, reset]);

  const onSubmit = (values: QuotationFormValues) => {
    createQuotation.mutate(
      {
        client_id: clientId,
        project_id: values.projectId || undefined,
        quotation_number: values.quotationNumber,
        quotation_date: values.quotationDate,
        valid_until: values.validUntil,
        notes: values.notes || undefined,
        lines: values.lines.map((l) => ({
          description: l.description,
          quantity: l.quantity,
          unit_price: l.unitPrice,
          gst_rate_id: l.gstRateId || undefined,
        })),
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New quotation</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="quotationNumber" required>Quotation number</Label>
              <Input id="quotationNumber" {...register("quotationNumber")} />
              {errors.quotationNumber && (
                <p className="text-sm text-destructive">{errors.quotationNumber.message}</p>
              )}
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
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="quotationDate" required>Quotation date</Label>
              <Input id="quotationDate" type="date" {...register("quotationDate")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="validUntil" required>Valid until</Label>
              <Input id="validUntil" type="date" {...register("validUntil")} />
              {errors.validUntil && (
                <p className="text-sm text-destructive">{errors.validUntil.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Line items
              </p>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => append({ description: "", quantity: 1, unitPrice: 0, gstRateId: "" })}
              >
                <Plus className="h-3 w-3" />
                Add line
              </Button>
            </div>
            {errors.lines?.message && <p className="text-sm text-destructive">{errors.lines.message}</p>}
            {fields.map((field, index) => (
              <div key={field.id} className="grid grid-cols-12 items-start gap-2">
                <div className="col-span-4">
                  <Input placeholder="Description" {...register(`lines.${index}.description`)} />
                </div>
                <div className="col-span-2">
                  <Input type="number" step="0.01" placeholder="Qty" {...register(`lines.${index}.quantity`)} />
                </div>
                <div className="col-span-2">
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="Unit price"
                    {...register(`lines.${index}.unitPrice`)}
                  />
                </div>
                <div className="col-span-3">
                  <Controller
                    control={control}
                    name={`lines.${index}.gstRateId`}
                    render={({ field: selectField }) => (
                      <Select value={selectField.value || undefined} onValueChange={selectField.onChange}>
                        <SelectTrigger>
                          <SelectValue placeholder="GST rate" />
                        </SelectTrigger>
                        <SelectContent>
                          {gstRates?.map((r) => (
                            <SelectItem key={r.id} value={r.id}>
                              {r.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
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
            <div className="flex justify-end border-t pt-2 text-sm">
              <span className="text-muted-foreground">
                Subtotal: <span className="font-medium text-foreground">{subtotal.toFixed(2)}</span>
              </span>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          {createQuotation.isError && (
            <p className="text-sm text-destructive">
              {(createQuotation.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createQuotation.isPending}>
              {createQuotation.isPending ? "Saving..." : "Create quotation"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
