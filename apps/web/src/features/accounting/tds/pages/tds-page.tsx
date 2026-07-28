import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateTDSSection, useTDSSections } from "@/features/accounting/tds/api/tds-hooks";
import { type TDSSectionFormValues, tdsSectionFormSchema } from "@/features/accounting/tds/schemas/tds-schemas";

export function TDSPage() {
  const { data: sections, isLoading, isError } = useTDSSections();
  const createSection = useCreateTDSSection();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TDSSectionFormValues>({ resolver: zodResolver(tdsSectionFormSchema) });

  const onSubmit = (values: TDSSectionFormValues) => {
    createSection.mutate(
      {
        section_code: values.sectionCode,
        description: values.description,
        rate_percent: Number(values.ratePercent),
        threshold_amount: values.thresholdAmount ? Number(values.thresholdAmount) : undefined,
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
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">TDS</h1>
          <p className="mt-1 text-muted-foreground">
            Tax deducted at source sections applied when paying vendors.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Section
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">TDS sections</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {isLoading && <Skeleton className="h-16 w-full" />}
          {isError && <p className="text-sm text-destructive">Failed to load TDS sections.</p>}
          {!isLoading && !isError && (sections?.length ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground">No TDS sections configured yet.</p>
          )}
          {sections?.map((section) => (
            <div key={section.id} className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">
                  {section.section_code} — {section.description}
                </p>
                <p className="text-xs text-muted-foreground">
                  {section.rate_percent}% · Threshold ₹{section.threshold_amount}
                </p>
              </div>
              <Badge variant={section.is_active ? "success" : "secondary"}>
                {section.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      <p className="text-sm text-muted-foreground">
        Deduction history for a specific vendor is available on that vendor's detail page.
      </p>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New TDS section</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sectionCode">Section code</Label>
                <Input id="sectionCode" placeholder="e.g. 194C" {...register("sectionCode")} />
                {errors.sectionCode && (
                  <p className="text-sm text-destructive">{errors.sectionCode.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="ratePercent">Rate %</Label>
                <Input id="ratePercent" type="number" step="0.01" {...register("ratePercent")} />
                {errors.ratePercent && (
                  <p className="text-sm text-destructive">{errors.ratePercent.message}</p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input id="description" {...register("description")} />
              {errors.description && (
                <p className="text-sm text-destructive">{errors.description.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="thresholdAmount">Threshold amount</Label>
              <Input id="thresholdAmount" type="number" step="0.01" {...register("thresholdAmount")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createSection.isPending}>
                {createSection.isPending ? "Saving..." : "Create section"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
