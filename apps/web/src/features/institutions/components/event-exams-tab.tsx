import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Plus, Unlink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { type InstitutionEvent, institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { errorMessage } from "@/features/institutions/lib/format";
import { workshopExamsApi } from "@/features/workshop-exams/api/workshop-exams-api";

/**
 * The exams of an event. An exam is one record: linking an existing exam, or creating one here, puts it on this event and
 * it stays reachable from Workshop Exams too. Removing it from the event never deletes it.
 */
export function EventExamsTab({ event }: { event: InstitutionEvent }) {
  const queryClient = useQueryClient();
  const [linking, setLinking] = useState(false);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const exams = useQuery({ queryKey: institutionsKeys.eventExams(event.id), queryFn: () => institutionsApi.eventExams(event.id) });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
    void queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
  };
  const unlink = useMutation({ mutationFn: (examId: string) => institutionsApi.unlinkExam(event.id, examId), onSuccess: refresh });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">Workshop exams held as part of this event. Open one to manage its questions, attendees and certificates.</p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setLinking(true)}>
            <Link2 className="h-4 w-4" />
            Link existing exam
          </Button>
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New exam
          </Button>
        </div>
      </div>
      {notice && <p className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">{notice}</p>}
      <Card>
        <CardContent className="p-0">
          {exams.isLoading ? (
            <div className="p-6">
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (exams.data?.length ?? 0) === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">No exams on this event yet.</p>
          ) : (
            <ul className="divide-y">
              {exams.data?.map((x) => (
                <li key={x.id} className="flex items-center justify-between gap-3 p-4">
                  <div>
                    <Link to={`/workshop-exams/${x.id}`} className="font-medium hover:underline">
                      {x.title}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {x.question_count} question{x.question_count === 1 ? "" : "s"} · {x.attendee_count} attendee{x.attendee_count === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="capitalize">{x.status}</Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${x.title} from this event`}
                      onClick={() => {
                        if (window.confirm(`Remove "${x.title}" from this event? The exam itself is kept in Workshop Exams.`)) unlink.mutate(x.id);
                      }}
                    >
                      <Unlink className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      {unlink.isError && <p className="text-sm text-destructive">{errorMessage(unlink.error, "Could not remove the exam.")}</p>}
      {linking && (
        <LinkExamDialog
          event={event}
          onClose={() => setLinking(false)}
          onDone={(message) => {
            setNotice(message);
            refresh();
          }}
        />
      )}
      {creating && <NewExamDialog event={event} onClose={() => setCreating(false)} onDone={refresh} />}
    </div>
  );
}

function LinkExamDialog({ event, onClose, onDone }: { event: InstitutionEvent; onClose: () => void; onDone: (message: string) => void }) {
  const candidates = useQuery({ queryKey: ["institutions", "exam-candidates", event.id], queryFn: () => institutionsApi.examCandidates(event.id) });
  const link = useMutation({
    mutationFn: (examId: string) => institutionsApi.linkExam(event.id, examId),
    onSuccess: (result) => {
      onDone(result.message);
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Link an existing exam</DialogTitle>
          <DialogDescription>Exams that are not part of any event yet. Linking does not copy the exam; it is the same exam in both places. Its attendees are added to this event's students, so their marks show against them.</DialogDescription>
        </DialogHeader>
        {candidates.isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (candidates.data?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">Every exam already belongs to an event. Create a new one instead.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {candidates.data?.map((x) => (
              <li key={x.id} className="flex items-center justify-between gap-3 p-3">
                <div>
                  <p className="text-sm font-medium">{x.title}</p>
                  <p className="text-xs text-muted-foreground">{x.attendee_count} attendees · {x.status}</p>
                </div>
                <Button size="sm" disabled={link.isPending} onClick={() => link.mutate(x.id)}>
                  Link
                </Button>
              </li>
            ))}
          </ul>
        )}
        {link.isError && <p className="text-sm text-destructive">{errorMessage(link.error, "Could not link the exam.")}</p>}
      </DialogContent>
    </Dialog>
  );
}

function NewExamDialog({ event, onClose, onDone }: { event: InstitutionEvent; onClose: () => void; onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("30");
  const create = useMutation({
    mutationFn: () => workshopExamsApi.create({ title: title.trim(), duration_minutes: Number(duration), event_id: event.id }),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });
  const minutes = Number(duration);
  const valid = title.trim().length >= 2 && Number.isInteger(minutes) && minutes >= 1 && minutes <= 480;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New exam for {event.name}</DialogTitle>
          <DialogDescription>It is created on this event and also appears in Workshop Exams, where you add its questions and attendees.</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !create.isPending) create.mutate();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="new-exam-title">Title</Label>
            <Input id="new-exam-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="new-exam-duration">Time limit (minutes, from when each person starts)</Label>
            <Input id="new-exam-duration" inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value.replace(/\D/g, ""))} />
          </div>
          {create.isError && <p className="text-sm text-destructive">{errorMessage(create.error, "Could not create the exam.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || create.isPending}>
              {create.isPending ? "Creating..." : "Create exam"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
