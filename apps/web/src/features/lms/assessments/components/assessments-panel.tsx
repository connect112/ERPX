import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
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
import { useStudentsList } from "@/features/students/api/students-hooks";
import {
  useAssessments,
  useAttempts,
  useCreateAssessment,
  useDeleteAssessment,
  useStartAttempt,
  useSubmitAttempt,
  useUpdateAssessment,
} from "@/features/lms/assessments/api/assessments-hooks";
import {
  type AssessmentFormValues,
  type AttemptStatus,
  assessmentFormSchema,
  assessmentTypeLabels,
  assessmentTypeValues,
  attemptStatusLabels,
} from "@/features/lms/assessments/schemas/assessment-schemas";

const attemptStatusVariant: Record<AttemptStatus, BadgeProps["variant"]> = {
  in_progress: "info",
  submitted: "warning",
  evaluated: "success",
};

function AttemptsSection({ courseId, assessmentId }: { courseId: string; assessmentId: string }) {
  const { data: attempts, isLoading } = useAttempts(courseId, assessmentId);
  const { data: students } = useStudentsList({ limit: 200 });
  const startAttempt = useStartAttempt(courseId, assessmentId);
  const submitAttempt = useSubmitAttempt(courseId, assessmentId);
  const [selectedStudent, setSelectedStudent] = useState("");
  const [scoringId, setScoringId] = useState<string | null>(null);
  const [scoreInput, setScoreInput] = useState("");

  const studentName = (id: string) => students?.items.find((s) => s.id === id)?.full_name ?? id;

  return (
    <div className="space-y-2 pl-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Attempts
        </p>
        <div className="flex items-center gap-1">
          <Select value={selectedStudent || undefined} onValueChange={setSelectedStudent}>
            <SelectTrigger className="h-8 w-44 text-xs">
              <SelectValue placeholder="Select student" />
            </SelectTrigger>
            <SelectContent>
              {students?.items.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.full_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="ghost"
            size="sm"
            disabled={!selectedStudent || startAttempt.isPending}
            onClick={() => startAttempt.mutate(selectedStudent, { onSuccess: () => setSelectedStudent("") })}
          >
            Start attempt
          </Button>
        </div>
      </div>
      {isLoading && <Skeleton className="h-8 w-full" />}
      {!isLoading && (attempts?.length ?? 0) === 0 && (
        <p className="text-xs text-muted-foreground">No attempts yet.</p>
      )}
      {attempts?.map((attempt) => (
        <div key={attempt.id} className="flex items-center justify-between rounded border px-2 py-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium">{studentName(attempt.student_id)}</span>
            <Badge variant={attemptStatusVariant[attempt.status]}>
              {attemptStatusLabels[attempt.status]}
            </Badge>
            {attempt.score !== null && (
              <span className="text-xs text-muted-foreground">Score: {attempt.score}</span>
            )}
          </div>
          {attempt.status === "in_progress" &&
            (scoringId === attempt.id ? (
              <div className="flex items-center gap-1">
                <Input
                  className="h-7 w-20 text-xs"
                  type="number"
                  value={scoreInput}
                  onChange={(e) => setScoreInput(e.target.value)}
                />
                <Button
                  size="sm"
                  className="h-7"
                  disabled={submitAttempt.isPending}
                  onClick={() =>
                    submitAttempt.mutate(
                      { attemptId: attempt.id, score: Number(scoreInput) },
                      { onSuccess: () => setScoringId(null) }
                    )
                  }
                >
                  Save
                </Button>
              </div>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => setScoringId(attempt.id)}>
                Submit score
              </Button>
            ))}
        </div>
      ))}
    </div>
  );
}

export function AssessmentsPanel({ courseId }: { courseId: string }) {
  const { data: assessments, isLoading } = useAssessments(courseId);
  const createAssessment = useCreateAssessment(courseId);
  const updateAssessment = useUpdateAssessment(courseId);
  const deleteAssessment = useDeleteAssessment(courseId);
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssessmentFormValues>({
    resolver: zodResolver(assessmentFormSchema),
    defaultValues: { title: "", assessmentType: "quiz", totalMarks: "100", passingMarks: "40", durationMinutes: "" },
  });

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: AssessmentFormValues) => {
    createAssessment.mutate(
      {
        title: values.title,
        assessment_type: values.assessmentType,
        total_marks: Number(values.totalMarks),
        passing_marks: Number(values.passingMarks),
        duration_minutes: values.durationMinutes ? Number(values.durationMinutes) : undefined,
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
        <CardTitle className="text-base">Assessments</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add assessment
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (assessments?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No assessments yet.</p>
        )}
        {assessments?.map((assessment) => (
          <div key={assessment.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => toggle(assessment.id)}
              >
                {expanded.has(assessment.id) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">{assessment.title}</span>
                <Badge variant="outline">{assessmentTypeLabels[assessment.assessment_type]}</Badge>
                <span className="text-xs text-muted-foreground">
                  {assessment.passing_marks}/{assessment.total_marks} to pass
                </span>
                <Badge variant={assessment.is_published ? "success" : "secondary"}>
                  {assessment.is_published ? "Published" : "Draft"}
                </Badge>
              </button>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    updateAssessment.mutate({
                      assessmentId: assessment.id,
                      payload: { is_published: !assessment.is_published },
                    })
                  }
                >
                  {assessment.is_published ? "Unpublish" : "Publish"}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteAssessment.mutate(assessment.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
            {expanded.has(assessment.id) && (
              <div className="mt-3">
                <AttemptsSection courseId={courseId} assessmentId={assessment.id} />
              </div>
            )}
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add assessment</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="assessmentType">Type</Label>
              <Controller
                control={control}
                name="assessmentType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="assessmentType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {assessmentTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {assessmentTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="totalMarks">Total marks</Label>
                <Input id="totalMarks" type="number" {...register("totalMarks")} />
                {errors.totalMarks && (
                  <p className="text-sm text-destructive">{errors.totalMarks.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="passingMarks">Passing marks</Label>
                <Input id="passingMarks" type="number" {...register("passingMarks")} />
                {errors.passingMarks && (
                  <p className="text-sm text-destructive">{errors.passingMarks.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="durationMinutes">Duration (min)</Label>
                <Input id="durationMinutes" type="number" {...register("durationMinutes")} />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createAssessment.isPending}>
                {createAssessment.isPending ? "Saving..." : "Add assessment"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
