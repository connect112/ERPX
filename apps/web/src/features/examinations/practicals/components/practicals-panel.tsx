import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

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
import { useStudentsList } from "@/features/students/api/students-hooks";
import {
  useCreatePractical,
  useDeletePractical,
  usePracticalResults,
  usePracticals,
  useRecordPracticalResult,
} from "@/features/examinations/practicals/api/practicals-hooks";
import {
  type PracticalFormValues,
  type RecordResultFormValues,
  practicalFormSchema,
  recordResultFormSchema,
} from "@/features/examinations/practicals/schemas/practical-schemas";

function ResultsSection({ courseId, practicalId }: { courseId: string; practicalId: string }) {
  const { data: results, isLoading } = usePracticalResults(courseId, practicalId);
  const { data: students } = useStudentsList({ limit: 200 });
  const recordResult = useRecordPracticalResult(courseId, practicalId);
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RecordResultFormValues>({ resolver: zodResolver(recordResultFormSchema) });

  const studentName = (id: string) => students?.items.find((s) => s.id === id)?.full_name ?? id;

  const onSubmit = (values: RecordResultFormValues) => {
    recordResult.mutate(
      { student_id: values.studentId, score: Number(values.score), remarks: values.remarks || undefined },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <div className="space-y-2 pl-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Results</p>
        <Button variant="ghost" size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-3 w-3" />
          Record result
        </Button>
      </div>
      {isLoading && <Skeleton className="h-8 w-full" />}
      {!isLoading && (results?.length ?? 0) === 0 && (
        <p className="text-xs text-muted-foreground">No results recorded yet.</p>
      )}
      {results?.map((result) => (
        <div key={result.id} className="flex items-center justify-between rounded border px-2 py-1.5">
          <span className="text-xs font-medium">{studentName(result.student_id)}</span>
          <span className="text-xs text-muted-foreground">Score: {result.score}</span>
        </div>
      ))}

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record result</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="studentId" required>Student</Label>
              <Controller
                control={control}
                name="studentId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="studentId">
                      <SelectValue placeholder="Select a student" />
                    </SelectTrigger>
                    <SelectContent>
                      {students?.items.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.studentId && (
                <p className="text-sm text-destructive">{errors.studentId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="score" required>Score</Label>
              <Input id="score" type="number" {...register("score")} />
              {errors.score && <p className="text-sm text-destructive">{errors.score.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="remarks">Remarks</Label>
              <Textarea id="remarks" rows={3} {...register("remarks")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={recordResult.isPending}>
                {recordResult.isPending ? "Saving..." : "Record"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function PracticalsPanel({ courseId }: { courseId: string }) {
  const { data: practicals, isLoading } = usePracticals(courseId);
  const createPractical = useCreatePractical(courseId);
  const deletePractical = useDeletePractical(courseId);
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PracticalFormValues>({
    resolver: zodResolver(practicalFormSchema),
    defaultValues: { title: "", examDate: "", rubric: "", totalMarks: "100", passingMarks: "40" },
  });

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: PracticalFormValues) => {
    createPractical.mutate(
      {
        title: values.title,
        exam_date: values.examDate,
        rubric: values.rubric || undefined,
        total_marks: Number(values.totalMarks),
        passing_marks: Number(values.passingMarks),
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
        <CardTitle className="text-base">Practicals</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add practical
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (practicals?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No practical exams yet.</p>
        )}
        {practicals?.map((practical) => (
          <div key={practical.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => toggle(practical.id)}
              >
                {expanded.has(practical.id) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">{practical.title}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(practical.exam_date).toLocaleDateString()} · {practical.passing_marks}/
                  {practical.total_marks} to pass
                </span>
              </button>
              <Button variant="ghost" size="icon" onClick={() => deletePractical.mutate(practical.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            {practical.rubric && (
              <p className="mt-1 pl-6 text-xs text-muted-foreground">{practical.rubric}</p>
            )}
            {expanded.has(practical.id) && (
              <div className="mt-3">
                <ResultsSection courseId={courseId} practicalId={practical.id} />
              </div>
            )}
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add practical exam</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title" required>Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="examDate" required>Exam date</Label>
              <Input id="examDate" type="date" {...register("examDate")} />
              {errors.examDate && (
                <p className="text-sm text-destructive">{errors.examDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="rubric">Rubric</Label>
              <Textarea id="rubric" rows={3} {...register("rubric")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="totalMarks" required>Total marks</Label>
                <Input id="totalMarks" type="number" {...register("totalMarks")} />
                {errors.totalMarks && (
                  <p className="text-sm text-destructive">{errors.totalMarks.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="passingMarks" required>Passing marks</Label>
                <Input id="passingMarks" type="number" {...register("passingMarks")} />
                {errors.passingMarks && (
                  <p className="text-sm text-destructive">{errors.passingMarks.message}</p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createPractical.isPending}>
                {createPractical.isPending ? "Saving..." : "Add practical"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
