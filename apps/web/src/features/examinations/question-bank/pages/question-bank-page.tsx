import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import {
  useCreateQuestion,
  useDeleteQuestion,
  useQuestions,
} from "@/features/examinations/question-bank/api/questions-hooks";
import {
  type QuestionFormValues,
  autoGradableTypes,
  difficultyLabels,
  difficultyValues,
  optionsBasedTypes,
  questionFormSchema,
  questionTypeLabels,
  questionTypeValues,
} from "@/features/examinations/question-bank/schemas/question-schemas";

export function QuestionBankPage() {
  const { data: courses } = useCoursesList({ limit: 200 });
  const [courseFilter, setCourseFilter] = useState("all");
  const { data: questions, isLoading, isError } = useQuestions(
    courseFilter === "all" ? undefined : courseFilter
  );
  const createQuestion = useCreateQuestion();
  const deleteQuestion = useDeleteQuestion();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<QuestionFormValues>({
    resolver: zodResolver(questionFormSchema),
    defaultValues: {
      courseId: "",
      questionText: "",
      questionType: "mcq",
      options: "",
      correctAnswer: "",
      defaultMarks: "1",
      difficulty: "medium",
    },
  });

  const questionType = watch("questionType");
  const showOptions = optionsBasedTypes.includes(questionType);
  const showCorrectAnswer = autoGradableTypes.includes(questionType);

  const courseTitle = (id: string | null) =>
    id ? (courses?.items.find((c) => c.id === id)?.title ?? id) : "General";

  const onSubmit = (values: QuestionFormValues) => {
    createQuestion.mutate(
      {
        course_id: values.courseId || undefined,
        question_text: values.questionText,
        question_type: values.questionType,
        options: values.options
          ? values.options.split("\n").map((o) => o.trim()).filter(Boolean)
          : undefined,
        correct_answer: values.correctAnswer || undefined,
        default_marks: Number(values.defaultMarks),
        difficulty: values.difficulty,
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
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Question Bank</h1>
          <p className="mt-1 text-muted-foreground">
            Build a reusable pool of questions for exams across your courses.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Question
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select value={courseFilter} onValueChange={setCourseFilter}>
            <SelectTrigger className="sm:w-56">
              <SelectValue placeholder="All courses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All courses</SelectItem>
              {courses?.items.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && <Skeleton className="h-24 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load questions.</p>
          )}
          {!isLoading && !isError && (questions?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No questions yet. Add one to start building your bank.
            </p>
          )}
          {questions?.map((question) => (
            <div key={question.id} className="rounded-md border p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">{question.question_text}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{questionTypeLabels[question.question_type]}</Badge>
                    <Badge variant="secondary">{difficultyLabels[question.difficulty]}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {question.default_marks} marks · {courseTitle(question.course_id)}
                    </span>
                  </div>
                  {question.options && question.options.length > 0 && (
                    <ul className="mt-2 list-inside list-disc text-xs text-muted-foreground">
                      {question.options.map((option, i) => (
                        <li key={i}>{option}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteQuestion.mutate(question.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>New question</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="questionText">Question text</Label>
              <Textarea id="questionText" rows={3} {...register("questionText")} />
              {errors.questionText && (
                <p className="text-sm text-destructive">{errors.questionText.message}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="courseId">Course (optional)</Label>
                <Controller
                  control={control}
                  name="courseId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="courseId">
                        <SelectValue placeholder="General" />
                      </SelectTrigger>
                      <SelectContent>
                        {courses?.items.map((c) => (
                          <SelectItem key={c.id} value={c.id}>
                            {c.title}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="questionType">Type</Label>
                <Controller
                  control={control}
                  name="questionType"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="questionType">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {questionTypeValues.map((t) => (
                          <SelectItem key={t} value={t}>
                            {questionTypeLabels[t]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>
            {showOptions && (
              <div className="space-y-2">
                <Label htmlFor="options">Options (one per line)</Label>
                <Textarea id="options" rows={3} {...register("options")} />
              </div>
            )}
            {showCorrectAnswer && (
              <div className="space-y-2">
                <Label htmlFor="correctAnswer">Correct answer</Label>
                <Input id="correctAnswer" {...register("correctAnswer")} />
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="defaultMarks">Default marks</Label>
                <Input id="defaultMarks" type="number" {...register("defaultMarks")} />
                {errors.defaultMarks && (
                  <p className="text-sm text-destructive">{errors.defaultMarks.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="difficulty">Difficulty</Label>
                <Controller
                  control={control}
                  name="difficulty"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="difficulty">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {difficultyValues.map((d) => (
                          <SelectItem key={d} value={d}>
                            {difficultyLabels[d]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>
            {createQuestion.isError && (
              <p className="text-sm text-destructive">
                {(createQuestion.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createQuestion.isPending}>
                {createQuestion.isPending ? "Saving..." : "Add question"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
