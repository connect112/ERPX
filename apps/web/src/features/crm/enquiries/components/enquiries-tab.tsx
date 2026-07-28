import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
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
  useCreateEnquiry,
  useDeleteEnquiry,
  useEnquiries,
  useUpdateEnquiry,
} from "@/features/crm/enquiries/api/enquiries-hooks";
import {
  type EnquiryFormValues,
  type EnquiryStatus,
  enquiryFormSchema,
  enquiryStatusLabels,
  enquiryStatusValues,
} from "@/features/crm/enquiries/schemas/enquiry-schemas";

const statusVariant = {
  open: "info",
  in_progress: "warning",
  closed: "secondary",
} as const;

export function EnquiriesTab({ leadId }: { leadId: string }) {
  const { data: enquiries, isLoading } = useEnquiries(leadId);
  const createEnquiry = useCreateEnquiry(leadId);
  const updateEnquiry = useUpdateEnquiry(leadId);
  const deleteEnquiry = useDeleteEnquiry(leadId);
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EnquiryFormValues>({ resolver: zodResolver(enquiryFormSchema) });

  const onSubmit = (values: EnquiryFormValues) => {
    createEnquiry.mutate(
      {
        course_interest: values.courseInterest,
        budget: values.budget ? Number(values.budget) : undefined,
        preferred_batch_timing: values.preferredBatchTiming || undefined,
        notes: values.notes || undefined,
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
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Enquiries</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add enquiry
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (enquiries?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No enquiries recorded yet.</p>
        )}
        {enquiries?.map((enquiry) => (
          <div key={enquiry.id} className="rounded-md border p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-medium">{enquiry.course_interest}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {enquiry.budget ? `Budget: ₹${enquiry.budget}` : "No budget specified"}
                  {enquiry.preferred_batch_timing ? ` · ${enquiry.preferred_batch_timing}` : ""}
                </p>
                {enquiry.notes && <p className="mt-1 text-xs text-muted-foreground">{enquiry.notes}</p>}
              </div>
              <div className="flex items-center gap-2">
                <Select
                  value={enquiry.status}
                  onValueChange={(status) =>
                    updateEnquiry.mutate({
                      enquiryId: enquiry.id,
                      payload: { status: status as EnquiryStatus },
                    })
                  }
                >
                  <SelectTrigger className="h-8 w-36 text-xs">
                    <SelectValue>
                      <Badge variant={statusVariant[enquiry.status]}>
                        {enquiryStatusLabels[enquiry.status]}
                      </Badge>
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {enquiryStatusValues.map((s) => (
                      <SelectItem key={s} value={s}>
                        {enquiryStatusLabels[s]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteEnquiry.mutate(enquiry.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New enquiry</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="courseInterest">Course interest</Label>
              <Input id="courseInterest" {...register("courseInterest")} />
              {errors.courseInterest && (
                <p className="text-sm text-destructive">{errors.courseInterest.message}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="budget">Budget</Label>
                <Input id="budget" type="number" step="0.01" {...register("budget")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="preferredBatchTiming">Preferred timing</Label>
                <Input id="preferredBatchTiming" {...register("preferredBatchTiming")} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea id="notes" rows={3} {...register("notes")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createEnquiry.isPending}>
                {createEnquiry.isPending ? "Saving..." : "Add enquiry"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
