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
  useCreateViva,
  useDeleteViva,
  useRecordVivaResult,
  useVivaResults,
  useVivas,
} from "@/features/examinations/viva/api/viva-hooks";
import {
  type RecordVivaResultFormValues,
  type VivaFormValues,
  recordVivaResultFormSchema,
  vivaFormSchema,
} from "@/features/examinations/viva/schemas/viva-schemas";

function VivaResultsSection({ courseId, vivaId }: { courseId: string; vivaId: string }) {
  const { data: results, isLoading } = useVivaResults(courseId, vivaId);
  const { data: students } = useStudentsList({ limit: 200 });
  const recordResult = useRecordVivaResult(courseId, vivaId);
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RecordVivaResultFormValues>({ resolver: zodResolver(recordVivaResultFormSchema) });

  const studentName = (id: string) => students?.items.find((s) => s.id === id)?.full_name ?? id;

  const onSubmit = (values: RecordVivaResultFormValues) => {
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

export function VivaPanel({ courseId }: { courseId: string }) {
  const { data: vivas, isLoading } = useVivas(courseId);
  const createViva = useCreateViva(courseId);
  const deleteViva = useDeleteViva(courseId);
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<VivaFormValues>({
    resolver: zodResolver(vivaFormSchema),
    defaultValues: { title: "", examDate: "", panelMembers: "", totalMarks: "50", passingMarks: "20" },
  });

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: VivaFormValues) => {
    createViva.mutate(
      {
        title: values.title,
        exam_date: values.examDate,
        panel_members: values.panelMembers || undefined,
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
        <CardTitle className="text-base">Viva</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add viva
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (vivas?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No viva exams yet.</p>
        )}
        {vivas?.map((viva) => (
          <div key={viva.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => toggle(viva.id)}
              >
                {expanded.has(viva.id) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">{viva.title}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(viva.exam_date).toLocaleDateString()} · {viva.passing_marks}/
                  {viva.total_marks} to pass
                </span>
              </button>
              <Button variant="ghost" size="icon" onClick={() => deleteViva.mutate(viva.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            {viva.panel_members && (
              <p className="mt-1 pl-6 text-xs text-muted-foreground">Panel: {viva.panel_members}</p>
            )}
            {expanded.has(viva.id) && (
              <div className="mt-3">
                <VivaResultsSection courseId={courseId} vivaId={viva.id} />
              </div>
            )}
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add viva exam</DialogTitle>
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
              <Label htmlFor="panelMembers">Panel members</Label>
              <Textarea id="panelMembers" rows={2} {...register("panelMembers")} />
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
              <Button type="submit" disabled={createViva.isPending}>
                {createViva.isPending ? "Saving..." : "Add viva"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
