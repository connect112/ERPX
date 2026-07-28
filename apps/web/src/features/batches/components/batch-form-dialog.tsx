import { useState } from "react";

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
import { useCreateBatch } from "@/features/batches/api/batches-hooks";
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import { useTrainersList } from "@/features/trainers/api/trainers-hooks";

interface BatchFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BatchFormDialog({ open, onOpenChange }: BatchFormDialogProps) {
  const [courseId, setCourseId] = useState("");
  const [trainerId, setTrainerId] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [capacity, setCapacity] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const { data: courses } = useCoursesList({ limit: 200 });
  const { data: trainers } = useTrainersList({ limit: 200 });
  const createBatch = useCreateBatch();

  const reset = () => {
    setCourseId("");
    setTrainerId("");
    setName("");
    setCode("");
    setCapacity("");
    setStartDate("");
    setEndDate("");
  };

  const handleSubmit = () => {
    createBatch.mutate(
      {
        course_id: courseId,
        trainer_id: trainerId || undefined,
        name,
        code,
        capacity: capacity ? Number(capacity) : undefined,
        start_date: startDate,
        end_date: endDate || undefined,
      },
      {
        onSuccess: () => {
          reset();
          onOpenChange(false);
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New batch</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="courseId">Course</Label>
            <Select value={courseId} onValueChange={setCourseId}>
              <SelectTrigger id="courseId">
                <SelectValue placeholder="Select a course" />
              </SelectTrigger>
              <SelectContent>
                {courses?.items.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Batch name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="code">Code</Label>
              <Input id="code" value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="trainerId">Trainer</Label>
            <Select value={trainerId} onValueChange={setTrainerId}>
              <SelectTrigger id="trainerId">
                <SelectValue placeholder="No trainer assigned yet" />
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

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="startDate">Start date</Label>
              <Input
                id="startDate"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="endDate">End date</Label>
              <Input id="endDate" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="capacity">Capacity</Label>
            <Input
              id="capacity"
              type="number"
              min={1}
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
            />
          </div>

          {createBatch.isError && (
            <p className="text-sm text-destructive">
              {(createBatch.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not create batch."}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!courseId || !name || !code || !startDate || createBatch.isPending}
            onClick={handleSubmit}
          >
            {createBatch.isPending ? "Creating..." : "Create batch"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
