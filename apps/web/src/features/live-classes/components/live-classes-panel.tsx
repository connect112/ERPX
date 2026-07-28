import { Plus, Video } from "lucide-react";
import { useState } from "react";

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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useChangeLiveClassStatus,
  useCreateLiveClass,
  useLiveClassesForBatch,
} from "@/features/live-classes/api/live-classes-hooks";
import { LiveClassStatusBadge } from "@/features/live-classes/components/live-class-status-badge";
import { useTrainersList } from "@/features/trainers/api/trainers-hooks";

const NEXT_STATUS: Record<string, { label: string; status: "live" | "completed" | "cancelled" }[]> = {
  scheduled: [
    { label: "Start", status: "live" },
    { label: "Cancel", status: "cancelled" },
  ],
  live: [{ label: "Complete", status: "completed" }],
  completed: [],
  cancelled: [],
};

export function LiveClassesPanel({ batchId }: { batchId: string }) {
  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [durationMinutes, setDurationMinutes] = useState("60");
  const [meetingLink, setMeetingLink] = useState("");
  const [trainerId, setTrainerId] = useState("");

  const { data, isLoading } = useLiveClassesForBatch(batchId);
  const { data: trainers } = useTrainersList({ limit: 200 });
  const createLiveClass = useCreateLiveClass(batchId);
  const changeStatus = useChangeLiveClassStatus(batchId);

  const reset = () => {
    setTitle("");
    setScheduledAt("");
    setDurationMinutes("60");
    setMeetingLink("");
    setTrainerId("");
  };

  const handleSubmit = () => {
    createLiveClass.mutate(
      {
        batch_id: batchId,
        title,
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_minutes: Number(durationMinutes),
        meeting_link: meetingLink,
        trainer_id: trainerId || undefined,
      },
      { onSuccess: () => { reset(); setFormOpen(false); } }
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Live classes</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Schedule session
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-24 w-full" />}
        {!isLoading && (data?.items.length ?? 0) === 0 && (
          <p className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
            <Video className="h-8 w-8 text-muted-foreground/50" />
            No live classes scheduled yet.
          </p>
        )}
        {!isLoading && (data?.items.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Scheduled</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((lc) => (
                <TableRow key={lc.id}>
                  <TableCell className="font-medium">
                    <a href={lc.meeting_link} target="_blank" rel="noreferrer" className="hover:underline">
                      {lc.title}
                    </a>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(lc.scheduled_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{lc.duration_minutes} min</TableCell>
                  <TableCell>
                    <LiveClassStatusBadge status={lc.status} />
                  </TableCell>
                  <TableCell className="flex justify-end gap-2">
                    {NEXT_STATUS[lc.status]?.map((action) => (
                      <Button
                        key={action.status}
                        variant="outline"
                        size="sm"
                        onClick={() => changeStatus.mutate({ id: lc.id, status: action.status })}
                      >
                        {action.label}
                      </Button>
                    ))}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule a live class</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="scheduledAt">Scheduled at</Label>
                <Input
                  id="scheduledAt"
                  type="datetime-local"
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="durationMinutes">Duration (min)</Label>
                <Input
                  id="durationMinutes"
                  type="number"
                  min={5}
                  max={480}
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="meetingLink">Meeting link</Label>
              <Input
                id="meetingLink"
                value={meetingLink}
                onChange={(e) => setMeetingLink(e.target.value)}
                placeholder="https://meet..."
              />
            </div>
            <div className="space-y-2">
              <Label>Trainer</Label>
              <Select value={trainerId} onValueChange={setTrainerId}>
                <SelectTrigger>
                  <SelectValue placeholder="No trainer" />
                </SelectTrigger>
                <SelectContent>
                  {trainers?.items.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.employee_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {createLiveClass.isError && (
              <p className="text-sm text-destructive">
                {(createLiveClass.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Could not schedule this session."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!title || !scheduledAt || !meetingLink || createLiveClass.isPending}
              onClick={handleSubmit}
            >
              {createLiveClass.isPending ? "Scheduling..." : "Schedule"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
