import { useState } from "react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useStudentsList } from "@/features/students/api/students-hooks";
import { useQuestions } from "@/features/examinations/question-bank/api/questions-hooks";
import type { ExamQuestionPublic } from "@/features/examinations/exams/api/exams-api";
import type { ExamAttemptPublic, AttemptStatus } from "@/features/examinations/evaluation/api/evaluation-api";
import {
  useAnswers,
  useFinalizeEvaluation,
  useGradeAnswer,
  useStartExamAttempt,
  useSubmitAnswer,
  useSubmitAttempt,
} from "@/features/examinations/evaluation/api/evaluation-hooks";

const statusVariant: Record<AttemptStatus, BadgeProps["variant"]> = {
  in_progress: "info",
  submitted: "warning",
  evaluated: "success",
};

function AnswerRow({
  attemptId,
  examQuestion,
  questionText,
}: {
  attemptId: string;
  examQuestion: ExamQuestionPublic;
  questionText: string;
}) {
  const { data: answers } = useAnswers(attemptId);
  const submitAnswer = useSubmitAnswer(attemptId);
  const gradeAnswer = useGradeAnswer(attemptId);
  const [answerText, setAnswerText] = useState("");
  const [gradeInput, setGradeInput] = useState("");

  const existingAnswer = answers?.find((a) => a.question_id === examQuestion.question_id);

  return (
    <div className="rounded border p-2">
      <p className="text-xs font-medium">
        {questionText} <span className="text-muted-foreground">({examQuestion.marks_allocated} marks)</span>
      </p>
      {existingAnswer ? (
        <div className="mt-1 flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">{existingAnswer.answer_text || "No answer text"}</p>
          {existingAnswer.marks_awarded !== null ? (
            <span className="text-xs font-medium">Awarded: {existingAnswer.marks_awarded}</span>
          ) : (
            <div className="flex items-center gap-1">
              <Input
                className="h-7 w-16 text-xs"
                type="number"
                value={gradeInput}
                onChange={(e) => setGradeInput(e.target.value)}
              />
              <Button
                size="sm"
                className="h-7"
                disabled={gradeAnswer.isPending}
                onClick={() =>
                  gradeAnswer.mutate({ answerId: existingAnswer.id, marksAwarded: Number(gradeInput) })
                }
              >
                Grade
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="mt-1 flex items-center gap-1">
          <Input
            className="h-7 flex-1 text-xs"
            placeholder="Answer text"
            value={answerText}
            onChange={(e) => setAnswerText(e.target.value)}
          />
          <Button
            size="sm"
            className="h-7"
            disabled={submitAnswer.isPending}
            onClick={() =>
              submitAnswer.mutate(
                { questionId: examQuestion.question_id, answerText },
                { onSuccess: () => setAnswerText("") }
              )
            }
          >
            Submit
          </Button>
        </div>
      )}
    </div>
  );
}

export function ExamAttemptSection({
  courseId,
  examId,
  examQuestions,
}: {
  courseId: string;
  examId: string;
  examQuestions: ExamQuestionPublic[];
}) {
  const { data: students } = useStudentsList({ limit: 200 });
  const { data: questions } = useQuestions(courseId);
  const [selectedStudent, setSelectedStudent] = useState("");
  const [attempt, setAttempt] = useState<ExamAttemptPublic | null>(null);

  const startAttempt = useStartExamAttempt(examId);
  const submitAttempt = useSubmitAttempt();
  const finalizeEvaluation = useFinalizeEvaluation();

  const questionText = (id: string) => questions?.find((q) => q.id === id)?.question_text ?? id;

  return (
    <div className="space-y-3 pl-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Evaluation
      </p>

      {!attempt && (
        <div className="flex items-center gap-2">
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
            onClick={() =>
              startAttempt.mutate(selectedStudent, {
                onSuccess: (result) => {
                  setAttempt(result);
                  setSelectedStudent("");
                },
              })
            }
          >
            Start attempt
          </Button>
        </div>
      )}

      {attempt && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant={statusVariant[attempt.status]}>{attempt.status}</Badge>
            {attempt.total_score !== null && (
              <span className="text-xs text-muted-foreground">Score: {attempt.total_score}</span>
            )}
            {attempt.status === "in_progress" && (
              <Button
                size="sm"
                variant="ghost"
                disabled={submitAttempt.isPending}
                onClick={() =>
                  submitAttempt.mutate(attempt.id, {
                    onSuccess: (updated) => setAttempt(updated),
                  })
                }
              >
                Submit attempt
              </Button>
            )}
            {attempt.status === "submitted" && (
              <Button
                size="sm"
                variant="ghost"
                disabled={finalizeEvaluation.isPending}
                onClick={() =>
                  finalizeEvaluation.mutate(attempt.id, {
                    onSuccess: (updated) => setAttempt(updated),
                  })
                }
              >
                Finalize evaluation
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => setAttempt(null)}>
              Close
            </Button>
          </div>

          {examQuestions.length === 0 && (
            <p className="text-xs text-muted-foreground">
              This exam has no questions attached yet.
            </p>
          )}
          {!questions && <Skeleton className="h-8 w-full" />}
          <div className="space-y-2">
            {examQuestions.map((eq) => (
              <AnswerRow
                key={eq.id}
                attemptId={attempt.id}
                examQuestion={eq}
                questionText={questionText(eq.question_id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
