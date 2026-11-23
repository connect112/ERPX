import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { type TakeResult, courseLearningApi, courseLearningKeys } from "@/features/course-learning/api/course-learning-api";
import { errorMessage } from "@/features/my-internship/lib/format";

function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  return `${m}:${String(seconds % 60).padStart(2, "0")}`;
}

function Result({ result, courseId }: { result: TakeResult; courseId: string }) {
  return (
    <Card data-testid="assessment-result">
      <CardHeader>
        <CardTitle className="text-lg">Submitted</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {result.score != null ? (
          <p>
            Your score: <strong>{result.score}</strong> / {result.total_marks}{" "}
            {result.passed != null && <Badge variant={result.passed ? "success" : "destructive"}>{result.passed ? "Pass" : "Not passed"}</Badge>}
          </p>
        ) : (
          <p>Your answers were submitted. Your result will be shared by your instructor.</p>
        )}
        <Button asChild variant="outline">
          <Link to={`/courses/${courseId}`}>Back to the course</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

/**
 * Taking a quiz or mock test. Everything that matters is decided on the server: the questions arrive without their answers, the clock is the
 * server's, and the score is worked out there from the saved answers. This page only shows the questions, saves the choices and submits.
 */
export function AssessmentTakePage() {
  const { courseId = "", assessmentId = "" } = useParams<{ courseId: string; assessmentId: string }>();
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, number[]>>({});
  const [remaining, setRemaining] = useState<number | null>(null);
  const [done, setDone] = useState<TakeResult | null>(null);
  const saveTimer = useRef<number | undefined>(undefined);
  const latest = useRef(answers);
  latest.current = answers;

  const start = useQuery({
    queryKey: ["course-learning", courseId, "take", assessmentId],
    queryFn: () => courseLearningApi.start(courseId, assessmentId),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  });
  useEffect(() => {
    if (start.data) {
      setAnswers(start.data.saved_answers);
      setRemaining(start.data.remaining_seconds);
    }
  }, [start.data]);

  const submit = useMutation({
    mutationFn: () => courseLearningApi.submit(courseId, assessmentId, latest.current),
    onSuccess: (r) => {
      setDone(r);
      void queryClient.invalidateQueries({ queryKey: courseLearningKeys.course(courseId) });
    },
  });
  const submitRef = useRef(submit.mutate);
  submitRef.current = submit.mutate;

  // the countdown only reminds: the server's clock decides, and it submits what was saved when the time is up
  useEffect(() => {
    if (remaining === null || done) return;
    if (remaining <= 0) {
      submitRef.current();
      return;
    }
    const t = window.setTimeout(() => setRemaining((r) => (r === null ? r : r - 1)), 1000);
    return () => window.clearTimeout(t);
  }, [remaining, done]);

  const choose = (qid: string, index: number, multiple: boolean) => {
    setAnswers((cur) => {
      const picked = cur[qid] ?? [];
      const next = multiple ? (picked.includes(index) ? picked.filter((i) => i !== index) : [...picked, index]) : [index];
      return { ...cur, [qid]: next };
    });
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => void courseLearningApi.save(courseId, assessmentId, latest.current).catch(() => undefined), 600);
  };

  if (start.isLoading) return <div className="p-6"><Skeleton className="h-40 w-full" /></div>;
  if (done) return <div className="mx-auto max-w-2xl p-6"><Result result={done} courseId={courseId} /></div>;
  if (start.isError || !start.data) {
    const finished = errorMessage(start.error, "").includes("already submitted");
    return (
      <div className="mx-auto max-w-2xl space-y-3 p-6" data-testid="assessment-unavailable">
        <p className="text-sm">{finished ? "You have already submitted this assessment." : errorMessage(start.error, "This assessment is not available to you.")}</p>
        <Button asChild variant="outline">
          <Link to={`/courses/${courseId}`}>Back to the course</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6" data-testid="assessment-take">
      {remaining !== null && (
        <div className="sticky top-0 z-10 rounded-md border bg-card p-2 text-right text-sm font-medium" role="timer" aria-live="off">
          Time left: {clock(remaining)}
        </div>
      )}
      {start.data.questions.map((q, n) => (
        <Card key={q.id}>
          <CardHeader>
            <CardTitle className="text-base">
              {n + 1}. {q.text} <span className="text-xs font-normal text-muted-foreground">({q.marks} {q.marks === 1 ? "mark" : "marks"})</span>
            </CardTitle>
            {q.allow_multiple && <p className="text-xs text-muted-foreground">Choose every correct answer.</p>}
          </CardHeader>
          <CardContent className="space-y-2">
            {q.options.map((o) => (
              <label key={o.index} className="flex cursor-pointer items-center gap-2 rounded-md border p-2 text-sm hover:bg-muted/50">
                <input
                  type={q.allow_multiple ? "checkbox" : "radio"}
                  name={q.id}
                  checked={(answers[q.id] ?? []).includes(o.index)}
                  onChange={() => choose(q.id, o.index, q.allow_multiple)}
                />
                {o.text}
              </label>
            ))}
          </CardContent>
        </Card>
      ))}
      {submit.isError && <p className="text-sm text-destructive">{errorMessage(submit.error, "Could not submit. Please try again.")}</p>}
      <Button disabled={submit.isPending} onClick={() => window.confirm("Submit your answers? You cannot change them afterwards.") && submit.mutate()}>
        Submit answers
      </Button>
    </div>
  );
}
