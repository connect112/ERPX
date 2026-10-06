import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  type PublicExamInfo,
  type PublicQuestion,
  publicExamApi,
} from "@/features/workshop-exams/api/workshop-exams-api";

type Phase =
  | { kind: "loading" }
  | { kind: "invalid" }
  | { kind: "info"; info: PublicExamInfo }
  | { kind: "taking" }
  | { kind: "done"; score: number | null; total: number | null };

function formatClock(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function errorText(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? fallback
  );
}

/**
 * The login-free exam page an attendee reaches from their emailed link.
 * Everything here is keyed off the token in the URL -- there is no
 * session, and (on purpose) none of the admin app's chrome.
 */
export function PublicExamPage() {
  const { token = "" } = useParams<{ token: string }>();
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [title, setTitle] = useState("");
  const [questions, setQuestions] = useState<PublicQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, number[]>>({});
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deadlineRef = useRef(0);
  const answersRef = useRef<Record<string, number[]>>({});
  const dirtyRef = useRef(false);
  const submittedRef = useRef(false);

  const begin = useCallback(
    async (examTitle: string) => {
      setBusy(true);
      setError(null);
      try {
        const started = await publicExamApi.start(token);
        setTitle(examTitle);
        setQuestions(started.questions);
        answersRef.current = started.saved_answers;
        setAnswers(started.saved_answers);
        deadlineRef.current = Date.now() + started.remaining_seconds * 1000;
        setSecondsLeft(started.remaining_seconds);
        setPhase({ kind: "taking" });
      } catch (e) {
        setError(errorText(e, "Could not start the exam. Please try again."));
      } finally {
        setBusy(false);
      }
    },
    [token]
  );

  // Initial load; someone reloading mid-exam goes straight back into it.
  useEffect(() => {
    let cancelled = false;
    publicExamApi
      .info(token)
      .then((info) => {
        if (cancelled) return;
        setTitle(info.title);
        if (info.state === "in_progress") {
          void begin(info.title);
        } else if (info.state === "submitted") {
          setPhase({ kind: "done", score: info.score, total: info.total_marks });
        } else {
          setPhase({ kind: "info", info });
        }
      })
      .catch(() => !cancelled && setPhase({ kind: "invalid" }));
    return () => {
      cancelled = true;
    };
  }, [token, begin]);

  const submit = useCallback(async () => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await publicExamApi.submit(token, answersRef.current);
      setPhase({ kind: "done", score: result.score, total: result.total_marks });
    } catch (e) {
      submittedRef.current = false;
      setError(errorText(e, "Could not submit - check your connection and press Submit again."));
    } finally {
      setBusy(false);
    }
  }, [token]);

  // Countdown; auto-submits at zero.
  useEffect(() => {
    if (phase.kind !== "taking") return;
    const timer = window.setInterval(() => {
      const left = Math.max(0, Math.round((deadlineRef.current - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left === 0) void submit();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [phase.kind, submit]);

  // Autosave every few seconds while there are unsaved changes, so a
  // dead battery or closed tab loses at most a moment of work.
  useEffect(() => {
    if (phase.kind !== "taking") return;
    const timer = window.setInterval(() => {
      if (!dirtyRef.current) return;
      dirtyRef.current = false;
      publicExamApi.saveAnswers(token, answersRef.current).catch(() => {
        dirtyRef.current = true;
      });
    }, 4000);
    return () => window.clearInterval(timer);
  }, [phase.kind, token]);

  useEffect(() => {
    if (phase.kind !== "taking") return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [phase.kind]);

  const choose = (question: PublicQuestion, optionIndex: number) => {
    const current = answersRef.current[question.id] ?? [];
    let next: number[];
    if (!question.allow_multiple) next = [optionIndex];
    else next = current.includes(optionIndex) ? current.filter((i) => i !== optionIndex) : [...current, optionIndex];
    answersRef.current = { ...answersRef.current, [question.id]: next };
    dirtyRef.current = true;
    setAnswers(answersRef.current);
  };

  const answered = questions.filter((q) => (answers[q.id]?.length ?? 0) > 0).length;

  const shell = (children: React.ReactNode) => (
    <div className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-2xl px-4 py-8">{children}</div>
    </div>
  );

  if (phase.kind === "loading") return shell(<p className="text-center text-muted-foreground">Loading...</p>);

  if (phase.kind === "invalid")
    return shell(
      <div className="rounded-lg border bg-card p-8 text-center">
        <h1 className="text-xl font-semibold">This link isn't valid</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Please use the exact link from your email. If you think this is a mistake, ask the organiser.
        </p>
      </div>
    );

  if (phase.kind === "done")
    return shell(
      <div className="rounded-lg border bg-card p-8 text-center">
        <h1 className="text-xl font-semibold">Thank you - your exam is submitted</h1>
        {phase.score != null && phase.total != null && (
          <p className="mt-3 text-2xl font-semibold">
            {phase.score} / {phase.total}
          </p>
        )}
        <p className="mt-3 text-sm text-muted-foreground">
          Your certificate will be emailed to the address this link was sent to. You can close this page.
        </p>
      </div>
    );

  if (phase.kind === "info") {
    const { info } = phase;
    return shell(
      <div className="rounded-lg border bg-card p-8">
        <h1 className="text-xl font-semibold">{info.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Hello {info.attendee_name}</p>
        {info.description && <p className="mt-4 whitespace-pre-wrap text-sm">{info.description}</p>}
        {info.state === "ready" && (
          <>
            <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              <li>{info.question_count} questions</li>
              <li>{info.duration_minutes} minutes - the timer starts when you press Start</li>
              <li>Your answers are saved as you go; the exam submits itself when time is up</li>
              <li>You can take it once</li>
            </ul>
            <Button className="mt-6 w-full" size="lg" disabled={busy} onClick={() => void begin(info.title)}>
              {busy ? "Starting..." : "Start exam"}
            </Button>
            {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
          </>
        )}
        {info.state === "not_open" && (
          <p className="mt-6 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
            The exam hasn't opened yet. Please wait for the organiser's go-ahead, then refresh this page.
          </p>
        )}
        {info.state === "closed" && (
          <p className="mt-6 rounded-md bg-muted p-3 text-sm">This exam is closed.</p>
        )}
      </div>
    );
  }

  return shell(
    <>
      <div className="sticky top-0 z-10 -mx-4 mb-4 border-b bg-background/95 px-4 py-3 backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-semibold">{title}</p>
            <p className="text-xs text-muted-foreground">
              {answered} of {questions.length} answered
            </p>
          </div>
          <div
            className={`rounded-md px-3 py-1 font-mono text-lg font-semibold ${
              secondsLeft <= 60 ? "bg-red-100 text-red-700" : "bg-muted"
            }`}
          >
            {formatClock(secondsLeft)}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {questions.map((q, i) => (
          <div key={q.id} className="rounded-lg border bg-card p-4">
            <p className="font-medium">
              {i + 1}. {q.text}
            </p>
            {q.allow_multiple && <p className="mt-1 text-xs text-muted-foreground">Select all that apply.</p>}
            <div className="mt-3 space-y-2">
              {q.options.map((o) => {
                const selected = answers[q.id]?.includes(o.index) ?? false;
                return (
                  <label
                    key={o.index}
                    className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm ${
                      selected ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                    }`}
                  >
                    <input
                      type={q.allow_multiple ? "checkbox" : "radio"}
                      className="mt-0.5"
                      name={q.id}
                      checked={selected}
                      onChange={() => choose(q, o.index)}
                    />
                    <span>{o.text}</span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 space-y-2 pb-10">
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button
          className="w-full"
          size="lg"
          disabled={busy}
          onClick={() => {
            const missing = questions.length - answered;
            if (missing > 0 && !window.confirm(`${missing} question(s) are unanswered. Submit anyway?`)) return;
            void submit();
          }}
        >
          {busy ? "Submitting..." : "Submit exam"}
        </Button>
      </div>
    </>
  );
}
