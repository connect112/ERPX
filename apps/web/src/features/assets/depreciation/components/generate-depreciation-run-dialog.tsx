import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

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
import { useGenerateDepreciationRun } from "@/features/assets/depreciation/api/depreciation-hooks";
import {
  type GenerateDepreciationRunFormValues,
  generateDepreciationRunFormSchema,
} from "@/features/assets/depreciation/schemas/depreciation-schemas";

interface GenerateDepreciationRunDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function GenerateDepreciationRunDialog({ open, onOpenChange }: GenerateDepreciationRunDialogProps) {
  const generateRun = useGenerateDepreciationRun();
  const now = new Date();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<GenerateDepreciationRunFormValues>({
    resolver: zodResolver(generateDepreciationRunFormSchema),
    defaultValues: { periodYear: now.getFullYear(), periodMonth: now.getMonth() + 1, runDate: todayIso() },
  });

  useEffect(() => {
    if (open) {
      reset({ periodYear: now.getFullYear(), periodMonth: now.getMonth() + 1, runDate: todayIso() });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, reset]);

  const onSubmit = (values: GenerateDepreciationRunFormValues) => {
    generateRun.mutate(
      { period_year: values.periodYear, period_month: values.periodMonth, run_date: values.runDate },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate depreciation run</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="periodYear">Period year</Label>
              <Input id="periodYear" type="number" {...register("periodYear")} />
              {errors.periodYear && (
                <p className="text-sm text-destructive">{errors.periodYear.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="periodMonth">Period month</Label>
              <Input id="periodMonth" type="number" min={1} max={12} {...register("periodMonth")} />
              {errors.periodMonth && (
                <p className="text-sm text-destructive">{errors.periodMonth.message}</p>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="runDate">Run date</Label>
            <Input id="runDate" type="date" {...register("runDate")} />
            {errors.runDate && <p className="text-sm text-destructive">{errors.runDate.message}</p>}
          </div>

          {generateRun.isError && (
            <p className="text-sm text-destructive">
              {(generateRun.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          {generateRun.data && (
            <p className="text-sm text-muted-foreground">
              Processed {generateRun.data.assets_processed} asset(s).
              {generateRun.data.assets_fully_depreciated_skipped.length > 0 &&
                ` Skipped ${generateRun.data.assets_fully_depreciated_skipped.length} fully depreciated.`}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={generateRun.isPending}>
              {generateRun.isPending ? "Generating..." : "Generate"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
