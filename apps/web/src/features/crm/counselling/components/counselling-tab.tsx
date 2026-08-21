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
  useCompleteCounsellingSession,
  useCounsellingSessions,
  useCreateCounsellingSession,
  useDeleteCounsellingSession,
} from "@/features/crm/counselling/api/counselling-hooks";
import {
  type CounsellingCompleteValues,
  type CounsellingFormValues,
  type CounsellingStatus,
  counsellingCompleteSchema,
  counsellingFormSchema,
  counsellingModeLabels,
  counsellingModeValues,
  counsellingStatusLabels,
} from "@/features/crm/counselling/schemas/counselling-schemas";

const statusVariant: Record<CounsellingStatus, BadgeProps["variant"]> = {
  scheduled: "info",
  completed: "success",
  cancelled: "secondary",
  no_show: "destructive",
};

export function CounsellingTab({ leadId }: { leadId: string }) {
  const { data: sessions, isLoading } = useCounsellingSessions(leadId);
  const createSession = useCreateCounsellingSession(leadId);
  const completeSession = useCompleteCounsellingSession(leadId);
  const deleteSession = useDeleteCounsellingSession(leadId);
  const [formOpen, setFormOpen] = useState(false);
  const [completingId, setCompletingId] = useState<string | null>(null);

  const createForm = useForm<CounsellingFormValues>({
    resolver: zodResolver(counsellingFormSchema),
    defaultValues: { mode: "phone", scheduledAt: "", notes: "" },
  });

  const completeForm = useForm<CounsellingCompleteValues>({
    resolver: zodResolver(counsellingCompleteSchema),
    defaultValues: { recommendedCourse: "", notes: "" },
  });

  const onCreate = (values: CounsellingFormValues) => {
    createSession.mutate(
      {
        mode: values.mode,
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

  const onComplete = (values: CounsellingCompleteValues) => {
    if (!completingId) return;
    completeSession.mutate(
      {
        sessionId: completingId,
        payload: {
          recommended_course: values.recommendedCourse || undefined,
          notes: values.notes || undefined,
        },
      },
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
        <CardTitle className="text-base">Counselling</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Schedule session
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (sessions?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No counselling sessions yet.</p>
        )}
        {sessions?.map((session) => (
          <div key={session.id} className="rounded-md border p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium">{counsellingModeLabels[session.mode]}</p>
                  <Badge variant={statusVariant[session.status]}>
                    {counsellingStatusLabels[session.status]}
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {new Date(session.scheduled_at).toLocaleString()}
                </p>
                {session.recommended_course && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Recommended: {session.recommended_course}
                  </p>
                )}
                {session.notes && <p className="mt-1 text-xs text-muted-foreground">{session.notes}</p>}
              </div>
              <div className="flex items-center gap-1">
                {session.status === "scheduled" && (
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Mark complete"
                    onClick={() => setCompletingId(session.id)}
                  >
                    <CheckCircle2 className="h-4 w-4" />
                  </Button>
                )}
                <Button variant="ghost" size="icon" onClick={() => deleteSession.mutate(session.id)}>
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
            <DialogTitle>Schedule counselling session</DialogTitle>
          </DialogHeader>
          <form onSubmit={createForm.handleSubmit(onCreate)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mode" required>Mode</Label>
              <Controller
                control={createForm.control}
                name="mode"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="mode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {counsellingModeValues.map((m) => (
                        <SelectItem key={m} value={m}>
                          {counsellingModeLabels[m]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="scheduledAt" required>Scheduled at</Label>
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
              <Button type="submit" disabled={createSession.isPending}>
                {createSession.isPending ? "Saving..." : "Schedule"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!completingId} onOpenChange={(open) => !open && setCompletingId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Complete counselling session</DialogTitle>
          </DialogHeader>
          <form onSubmit={completeForm.handleSubmit(onComplete)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="recommendedCourse">Recommended course</Label>
              <Input id="recommendedCourse" {...completeForm.register("recommendedCourse")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="completeNotes">Notes</Label>
              <Textarea id="completeNotes" rows={3} {...completeForm.register("notes")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCompletingId(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={completeSession.isPending}>
                {completeSession.isPending ? "Saving..." : "Mark complete"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
