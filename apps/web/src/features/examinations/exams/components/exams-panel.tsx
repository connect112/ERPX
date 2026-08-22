import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
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
import { ExamAttemptSection } from "@/features/examinations/evaluation/components/exam-attempt-section";
import {
  useAddQuestionToExam,
  useCreateExam,
  useDeleteExam,
  useExamQuestions,
  useExams,
  useRemoveQuestionFromExam,
} from "@/features/examinations/exams/api/exams-hooks";
import { type ExamFormValues, examFormSchema } from "@/features/examinations/exams/schemas/exam-schemas";
import { useQuestions } from "@/features/examinations/question-bank/api/questions-hooks";

function ExamQuestionsSection({ courseId, examId }: { courseId: string; examId: string }) {
  const { data: examQuestions, isLoading } = useExamQuestions(courseId, examId);
  const { data: questions } = useQuestions(courseId);
  const addQuestion = useAddQuestionToExam(courseId, examId);
  const removeQuestion = useRemoveQuestionFromExam(courseId, examId);

  const [selectedQuestion, setSelectedQuestion] = useState("");
  const [marks, setMarks] = useState("1");

  const questionText = (id: string) => questions?.find((q) => q.id === id)?.question_text ?? id;
  const availableQuestions = questions?.filter(
    (q) => !examQuestions?.some((eq) => eq.question_id === q.id)
  );

  return (
    <div className="space-y-2 pl-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Questions
        </p>
        <div className="flex items-center gap-1">
          <Select value={selectedQuestion || undefined} onValueChange={setSelectedQuestion}>
            <SelectTrigger className="h-8 w-56 text-xs">
              <SelectValue placeholder="Select a question" />
            </SelectTrigger>
            <SelectContent>
              {availableQuestions?.map((q) => (
                <SelectItem key={q.id} value={q.id}>
                  {q.question_text.slice(0, 40)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            className="h-8 w-16 text-xs"
            type="number"
            value={marks}
            onChange={(e) => setMarks(e.target.value)}
          />
          <Button
            variant="ghost"
            size="sm"
            disabled={!selectedQuestion || addQuestion.isPending}
            onClick={() =>
              addQuestion.mutate(
                {
                  question_id: selectedQuestion,
                  marks_allocated: Number(marks),
                  order_index: examQuestions?.length ?? 0,
                },
                { onSuccess: () => setSelectedQuestion("") }
              )
            }
          >
            <Plus className="h-3 w-3" />
            Add
          </Button>
        </div>
      </div>
      {isLoading && <Skeleton className="h-8 w-full" />}
      {!isLoading && (examQuestions?.length ?? 0) === 0 && (
        <p className="text-xs text-muted-foreground">No questions attached yet.</p>
      )}
      {examQuestions?.map((eq) => (
        <div key={eq.id} className="flex items-center justify-between rounded border px-2 py-1.5">
          <span className="text-xs">{questionText(eq.question_id)}</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{eq.marks_allocated} marks</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => removeQuestion.mutate(eq.question_id)}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </div>
      ))}

      <ExamAttemptSection courseId={courseId} examId={examId} examQuestions={examQuestions ?? []} />
    </div>
  );
}

export function ExamsPanel({ courseId }: { courseId: string }) {
  const { data: exams, isLoading } = useExams(courseId);
  const createExam = useCreateExam(courseId);
  const deleteExam = useDeleteExam(courseId);
  const [formOpen, setFormOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ExamFormValues>({
    resolver: zodResolver(examFormSchema),
    defaultValues: { title: "", examDate: "", durationMinutes: "60", passingMarks: "40" },
  });

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = (values: ExamFormValues) => {
    createExam.mutate(
      {
        title: values.title,
        exam_date: new Date(values.examDate).toISOString(),
        duration_minutes: Number(values.durationMinutes),
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
        <CardTitle className="text-base">Exams</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add exam
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (exams?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No exams yet.</p>
        )}
        {exams?.map((exam) => (
          <div key={exam.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => toggle(exam.id)}
              >
                {expanded.has(exam.id) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">{exam.title}</span>
                <Badge variant="outline">{exam.status}</Badge>
                <span className="text-xs text-muted-foreground">
                  {new Date(exam.exam_date).toLocaleDateString()} · {exam.duration_minutes} min
                </span>
              </button>
              <Button variant="ghost" size="icon" onClick={() => deleteExam.mutate(exam.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            {expanded.has(exam.id) && (
              <div className="mt-3">
                <ExamQuestionsSection courseId={courseId} examId={exam.id} />
              </div>
            )}
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add exam</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title" required>Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="examDate" required>Exam date</Label>
              <Input id="examDate" type="datetime-local" {...register("examDate")} />
              {errors.examDate && (
                <p className="text-sm text-destructive">{errors.examDate.message}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="durationMinutes" required>Duration (min)</Label>
                <Input id="durationMinutes" type="number" {...register("durationMinutes")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="passingMarks" required>Passing marks</Label>
                <Input id="passingMarks" type="number" {...register("passingMarks")} />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createExam.isPending}>
                {createExam.isPending ? "Saving..." : "Add exam"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
