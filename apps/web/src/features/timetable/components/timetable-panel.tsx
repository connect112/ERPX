import { Plus, Trash2 } from "lucide-react";
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
import { useClassroomsList } from "@/features/classrooms/api/classrooms-hooks";
import { type DayOfWeek } from "@/features/timetable/api/timetable-api";
import {
  useCreateTimetableEntry,
  useDeleteTimetableEntry,
  useTimetableForBatch,
} from "@/features/timetable/api/timetable-hooks";
import { useTrainersList } from "@/features/trainers/api/trainers-hooks";

const dayLabels: Record<DayOfWeek, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday",
};
const dayValues = Object.keys(dayLabels) as DayOfWeek[];

export function TimetablePanel({ batchId }: { batchId: string }) {
  const [formOpen, setFormOpen] = useState(false);
  const [dayOfWeek, setDayOfWeek] = useState<DayOfWeek>("monday");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [classroomId, setClassroomId] = useState("");
  const [trainerId, setTrainerId] = useState("");
  const [subject, setSubject] = useState("");

  const { data: entries, isLoading } = useTimetableForBatch(batchId);
  const { data: classrooms } = useClassroomsList({ limit: 200 });
  const { data: trainers } = useTrainersList({ limit: 200 });
  const createEntry = useCreateTimetableEntry(batchId);
  const deleteEntry = useDeleteTimetableEntry(batchId);

  const reset = () => {
    setDayOfWeek("monday");
    setStartTime("");
    setEndTime("");
    setClassroomId("");
    setTrainerId("");
    setSubject("");
  };

  const handleSubmit = () => {
    createEntry.mutate(
      {
        batch_id: batchId,
        day_of_week: dayOfWeek,
        start_time: startTime,
        end_time: endTime,
        classroom_id: classroomId || undefined,
        trainer_id: trainerId || undefined,
        subject: subject || undefined,
      },
      { onSuccess: () => { reset(); setFormOpen(false); } }
    );
  };

  const classroomName = (id: string | null) => classrooms?.items.find((c) => c.id === id)?.name ?? "—";
  const trainerName = (id: string | null) => trainers?.items.find((t) => t.id === id)?.employee_name ?? "—";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Weekly timetable</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add slot
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-24 w-full" />}
        {!isLoading && (entries?.length ?? 0) === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">No recurring slots scheduled yet.</p>
        )}
        {!isLoading && (entries?.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Day</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Classroom</TableHead>
                <TableHead>Trainer</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries?.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="font-medium">{dayLabels[entry.day_of_week]}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {entry.start_time.slice(0, 5)} – {entry.end_time.slice(0, 5)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{entry.subject ?? "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{classroomName(entry.classroom_id)}</TableCell>
                  <TableCell className="text-muted-foreground">{trainerName(entry.trainer_id)}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" onClick={() => deleteEntry.mutate(entry.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
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
            <DialogTitle>Add timetable slot</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Day of week</Label>
              <Select value={dayOfWeek} onValueChange={(v) => setDayOfWeek(v as DayOfWeek)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {dayValues.map((d) => (
                    <SelectItem key={d} value={d}>
                      {dayLabels[d]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="startTime">Start time</Label>
                <Input id="startTime" type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="endTime">End time</Label>
                <Input id="endTime" type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="subject">Subject</Label>
              <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Classroom</Label>
              <Select value={classroomId} onValueChange={setClassroomId}>
                <SelectTrigger>
                  <SelectValue placeholder="No classroom" />
                </SelectTrigger>
                <SelectContent>
                  {classrooms?.items.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
            {createEntry.isError && (
              <p className="text-sm text-destructive">
                {(createEntry.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Could not add this slot."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!startTime || !endTime || createEntry.isPending}
              onClick={handleSubmit}
            >
              {createEntry.isPending ? "Adding..." : "Add slot"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
