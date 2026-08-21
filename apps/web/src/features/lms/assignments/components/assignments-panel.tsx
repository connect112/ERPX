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
import { Textarea } from "@/components/ui/textarea";
import { useStudentsList } from "@/features/students/api/students-hooks";
import type { SubmissionPublic } from "@/features/lms/assignments/api/assignments-api";
import {
  useAssignments,
  useCreateAssignment,
  useDeleteAssignment,
  useGradeSubmission,
  useSubmissions,
  useSubmitAssignment,
} from "@/features/lms/assignments/api/assignments-hooks";
import {
  type AssignmentFormValues,
  type GradeFormValues,
  type SubmissionFormValues,
  assignmentFormSchema,
  gradeFormSchema,
  submissionFormSchema,
  submissionStatusLabels,
} from "@/features/lms/assignments/schemas/assignment-schemas";

const statusVariant: Record<SubmissionPublic["status"], BadgeProps["variant"]> = {
  submitted: "info",
  graded: "success",
  late: "warning",
};

function SubmissionsSection({ courseId, assignmentId }: { courseId: string; assignmentId: string }) {
  const { data: submissions, isLoading } = useSubmissions(courseId, assignmentId);
  const { data: students } = useStudentsList({ limit: 200 });
  const submitAssignment = useSubmitAssignment(courseId, assignmentId);
  const gradeSubmission = useGradeSubmission(courseId, assignmentId);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [gradingId, setGradingId] = useState<string | null>(null);

  const studentName = (id: string) => students?.items.find((s) => s.id === id)?.full_name ?? id;

  const submitForm = useForm<SubmissionFormValues>({ resolver: zodResolver(submissionFormSchema) });
  const gradeForm = useForm<GradeFormValues>({ resolver: zodResolver(gradeFormSchema) });

  const onSubmit = (values: SubmissionFormValues) => {
    submitAssignment.mutate(
      {
        student_id: values.studentId,
        content_url: values.contentUrl || undefined,
        content_text: values.contentText || undefined,
      },
      {
        onSuccess: () => {
          setSubmitOpen(false);
          submitForm.reset();
        },
      }
    );
  };

  const onGrade = (values: GradeFormValues) => {
    if (!gradingId) return;
    gradeSubmission.mutate(
      { submissionId: gradingId, payload: { score: Number(values.score), feedback: values.feedback || undefined } },
      {
        onSuccess: () => {
          setGradingId(null);
          gradeForm.reset();
        },
      }
    );
  };

  return (
    <div className="space-y-2 pl-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Submissions
        </p>
        <Button variant="ghost" size="sm" onClick={() => setSubmitOpen(true)}>
          <Plus className="h-3 w-3" />
          Record submission
        </Button>
      </div>
      {isLoading && <Skeleton className="h-8 w-full" />}
      {!isLoading && (submissions?.length ?? 0) === 0 && (
        <p className="text-xs text-muted-foreground">No submissions yet.</p>
      )}
      {submissions?.map((submission) => (
        <div key={submission.id} className="flex items-center justify-between rounded border px-2 py-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium">{studentName(submission.student_id)}</span>
            <Badge variant={statusVariant[submission.status]}>
              {submissionStatusLabels[submission.status]}
            </Badge>
            {submission.score !== null && (
              <span className="text-xs text-muted-foreground">Score: {submission.score}</span>
            )}
          </div>
          {submission.status !== "graded" && (
            <Button variant="ghost" size="sm" onClick={() => setGradingId(submission.id)}>
              Grade
            </Button>
          )}
        </div>
      ))}

      <Dialog open={submitOpen} onOpenChange={setSubmitOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record submission</DialogTitle>
          </DialogHeader>
          <form onSubmit={submitForm.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="studentId" required>Student</Label>
              <Controller
                control={submitForm.control}
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
              {submitForm.formState.errors.studentId && (
                <p className="text-sm text-destructive">
                  {submitForm.formState.errors.studentId.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="contentUrl">Content URL</Label>
              <Input id="contentUrl" {...submitForm.register("contentUrl")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contentText">Content text</Label>
              <Textarea id="contentText" rows={3} {...submitForm.register("contentText")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setSubmitOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={submitAssignment.isPending}>
                {submitAssignment.isPending ? "Saving..." : "Record"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!gradingId} onOpenChange={(open) => !open && setGradingId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Grade submission</DialogTitle>
          </DialogHeader>
          <form onSubmit={gradeForm.handleSubmit(onGrade)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="score" required>Score</Label>
              <Input id="score" type="number" {...gradeForm.register("score")} />
              {gradeForm.formState.errors.score && (
                <p className="text-sm text-destructive">{gradeForm.formState.errors.score.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="feedback">Feedback</Label>
              <Textarea id="feedback" rows={3} {...gradeForm.register("feedback")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setGradingId(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={gradeSubmission.isPending}>
                {gradeSubmission.isPending ? "Saving..." : "Save grade"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function AssignmentsPanel({ courseId }: { courseId: string }) {
  const { data: assignments, isLoading } = useAssignments(courseId);
  const createAssignment = useCreateAssignment(courseId);
  const deleteAssignment = useDeleteAssignment(courseId);
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssignmentFormValues>({
    resolver: zodResolver(assignmentFormSchema),
    defaultValues: { title: "", description: "", dueDate: "", maxScore: "100" },
  });

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: AssignmentFormValues) => {
    createAssignment.mutate(
      {
        title: values.title,
        description: values.description || undefined,
        due_date: values.dueDate ? new Date(values.dueDate).toISOString() : undefined,
        max_score: Number(values.maxScore),
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
        <CardTitle className="text-base">Assignments</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add assignment
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (assignments?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No assignments yet.</p>
        )}
        {assignments?.map((assignment) => (
          <div key={assignment.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => toggle(assignment.id)}
              >
                {expanded.has(assignment.id) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">{assignment.title}</span>
                <span className="text-xs text-muted-foreground">Max {assignment.max_score}</span>
                {assignment.due_date && (
                  <span className="text-xs text-muted-foreground">
                    Due {new Date(assignment.due_date).toLocaleDateString()}
                  </span>
                )}
              </button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => deleteAssignment.mutate(assignment.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            {assignment.description && (
              <p className="mt-1 pl-6 text-xs text-muted-foreground">{assignment.description}</p>
            )}
            {expanded.has(assignment.id) && (
              <div className="mt-3">
                <SubmissionsSection courseId={courseId} assignmentId={assignment.id} />
              </div>
            )}
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add assignment</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title" required>Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={3} {...register("description")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="dueDate">Due date</Label>
                <Input id="dueDate" type="date" {...register("dueDate")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="maxScore" required>Max score</Label>
                <Input id="maxScore" type="number" {...register("maxScore")} />
                {errors.maxScore && (
                  <p className="text-sm text-destructive">{errors.maxScore.message}</p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createAssignment.isPending}>
                {createAssignment.isPending ? "Saving..." : "Add assignment"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
