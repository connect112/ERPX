import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge, type BadgeProps } from "@/components/ui/badge";
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
  useCompleteFollowUp,
  useCreateFollowUp,
  useDeleteFollowUp,
  useFollowUps,
} from "@/features/crm/followups/api/followups-hooks";
import type { FollowUpPublic } from "@/features/crm/followups/api/followups-api";
import {
  type FollowUpCompleteValues,
  type FollowUpFormValues,
  type FollowUpStatus,
  followUpCompleteSchema,
  followUpFormSchema,
  followUpStatusLabels,
  followUpTypeLabels,
  followUpTypeValues,
} from "@/features/crm/followups/schemas/followup-schemas";

const statusVariant: Record<FollowUpStatus, BadgeProps["variant"]> = {
  scheduled: "info",
  completed: "success",
  cancelled: "secondary",
  missed: "destructive",
};

export function FollowUpsTab({ leadId }: { leadId: string }) {
  const { data: followups, isLoading } = useFollowUps(leadId);
  const createFollowUp = useCreateFollowUp(leadId);
  const completeFollowUp = useCompleteFollowUp(leadId);
  const deleteFollowUp = useDeleteFollowUp(leadId);
  const [formOpen, setFormOpen] = useState(false);
  const [completingId, setCompletingId] = useState<string | null>(null);

  const createForm = useForm<FollowUpFormValues>({
    resolver: zodResolver(followUpFormSchema),
    defaultValues: { followUpType: "call", scheduledAt: "", notes: "" },
  });

  const completeForm = useForm<FollowUpCompleteValues>({
    resolver: zodResolver(followUpCompleteSchema),
    defaultValues: { outcome: "", notes: "" },
  });

  const onCreate = (values: FollowUpFormValues) => {
    createFollowUp.mutate(
      {
        follow_up_type: values.followUpType,
        scheduled_at: new Date(values.scheduledAt).toISOString(),
        notes: values.notes || undefined,
      },
      {
        onSuccess: () => {
          setFormOpen(false);
          createForm.reset();
        },
      }
    );
  };

  const onComplete = (values: FollowUpCompleteValues) => {
    if (!completingId) return;
    completeFollowUp.mutate(
      { followupId: completingId, payload: { outcome: values.outcome, notes: values.notes || undefined } },
      {
        onSuccess: () => {
          setCompletingId(null);
          completeForm.reset();
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Follow-ups</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Schedule follow-up
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (followups?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No follow-ups scheduled yet.</p>
        )}
        {followups?.map((followup: FollowUpPublic) => (
          <div key={followup.id} className="rounded-md border p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium">{followUpTypeLabels[followup.follow_up_type]}</p>
                  <Badge variant={statusVariant[followup.status]}>
                    {followUpStatusLabels[followup.status]}
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {new Date(followup.scheduled_at).toLocaleString()}
                </p>
                {followup.outcome && (
                  <p className="mt-1 text-xs text-muted-foreground">Outcome: {followup.outcome}</p>
                )}
                {followup.notes && <p className="mt-1 text-xs text-muted-foreground">{followup.notes}</p>}
              </div>
              <div className="flex items-center gap-1">
                {followup.status === "scheduled" && (
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Mark complete"
                    onClick={() => setCompletingId(followup.id)}
                  >
                    <CheckCircle2 className="h-4 w-4" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteFollowUp.mutate(followup.id)}
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
            <DialogTitle>Schedule follow-up</DialogTitle>
          </DialogHeader>
          <form onSubmit={createForm.handleSubmit(onCreate)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="followUpType">Type</Label>
              <Controller
                control={createForm.control}
                name="followUpType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="followUpType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {followUpTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {followUpTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="scheduledAt">Scheduled at</Label>
              <Input
                id="scheduledAt"
                type="datetime-local"
                {...createForm.register("scheduledAt")}
              />
              {createForm.formState.errors.scheduledAt && (
                <p className="text-sm text-destructive">
                  {createForm.formState.errors.scheduledAt.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea id="notes" rows={3} {...createForm.register("notes")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createFollowUp.isPending}>
                {createFollowUp.isPending ? "Saving..." : "Schedule"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!completingId} onOpenChange={(open) => !open && setCompletingId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Complete follow-up</DialogTitle>
          </DialogHeader>
          <form onSubmit={completeForm.handleSubmit(onComplete)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="outcome">Outcome</Label>
              <Input id="outcome" {...completeForm.register("outcome")} />
              {completeForm.formState.errors.outcome && (
                <p className="text-sm text-destructive">
                  {completeForm.formState.errors.outcome.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="completeNotes">Notes</Label>
              <Textarea id="completeNotes" rows={3} {...completeForm.register("notes")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCompletingId(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={completeFollowUp.isPending}>
                {completeFollowUp.isPending ? "Saving..." : "Mark complete"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
