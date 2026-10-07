import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { workshopExamsApi } from "@/features/workshop-exams/api/workshop-exams-api";

/** The special parts an ID format can contain; each button adds one to the end of the format. */
const TOKENS: { token: string; label: string; hint: string }[] = [
  { token: "{YYYY}", label: "Year", hint: "2026" },
  { token: "{YY}", label: "Year (2 digits)", hint: "26" },
  { token: "{MM}", label: "Month", hint: "10" },
  { token: "{#4}", label: "Numbers in order", hint: "0001, 0002, 0003 ... (4 digits)" },
  { token: "{D4}", label: "Random digits", hint: "4 random digits, e.g. 7305" },
  { token: "{L3}", label: "Random letters", hint: "3 random letters, e.g. XQP" },
  { token: "{A6}", label: "Random letters + digits", hint: "6 random letters/digits, e.g. K7M4QX" },
  { token: "{1000-9999}", label: "Number in a range", hint: "a random number from 1000 to 9999" },
];

/** The server's own wording: format problems come back as validation details ("Value error, <what to change>"). */
function errorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string; details?: { msg?: string }[] } } } })
    ?.response?.data?.error;
  const detail = Array.isArray(data?.details) ? data?.details[0]?.msg : undefined;
  if (detail) return detail.replace(/^Value error,\s*/, "");
  return data?.message ?? fallback;
}

/**
 * The "box" that decides what every certificate ID looks like: fixed text plus special parts that change per
 * certificate (numbers in order that start where you say, random letters/digits, a number in a range).
 */
export function CertificateIdFormat({
  examId,
  savedPattern,
  savedStart,
  pattern,
  start,
  onPattern,
  onStart,
  locked,
}: {
  examId: string;
  savedPattern: string | null;
  savedStart: number;
  pattern: string;
  start: number;
  onPattern: (value: string) => void;
  onStart: (value: number) => void;
  locked: boolean;
}) {
  const queryClient = useQueryClient();
  const [examples, setExamples] = useState<string[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [shuffle, setShuffle] = useState(0);

  // Ask the server what the format would produce, once the admin pauses typing.
  useEffect(() => {
    if (!pattern.trim()) {
      setExamples(null);
      setProblem(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      workshopExamsApi
        .certificateIdExamples(examId, pattern, start)
        .then((rows) => {
          if (cancelled) return;
          setExamples(rows);
          setProblem(null);
        })
        .catch((error) => {
          if (cancelled) return;
          setExamples(null);
          setProblem(errorMessage(error, "That format can't be used."));
        });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [examId, pattern, start, shuffle]);

  const save = useMutation({
    mutationFn: () =>
      workshopExamsApi.update(examId, { certificate_id_pattern: pattern.trim(), certificate_id_start: start }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workshop-exams"] }),
  });

  const dirty = pattern.trim() !== (savedPattern ?? "") || start !== savedStart;
  const usesNumbers = pattern.includes("{#");

  return (
    <div className="space-y-3 rounded-md border p-3">
      <div>
        <p className="font-medium">Certificate ID format</p>
        <p className="text-sm text-muted-foreground">
          Type the fixed text you want, and add the special parts below for whatever should change on every
          certificate. Leave it empty to keep the automatic style (WS-2026-3F9A12C4).
        </p>
      </div>

      <div className="space-y-1">
        <Label htmlFor="cid-pattern">Format</Label>
        <Input
          id="cid-pattern"
          value={pattern}
          disabled={locked}
          maxLength={80}
          spellCheck={false}
          placeholder="GIR-DSO-{YYYY}-{#4}"
          onChange={(e) => onPattern(e.target.value)}
          className="font-mono"
        />
        <p className="text-xs text-muted-foreground">
          Fixed text can use letters, digits, - and _ (no spaces). Special parts go in braces.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {TOKENS.map(({ token, label, hint }) => (
          <Button
            key={token}
            type="button"
            size="sm"
            variant="outline"
            disabled={locked}
            title={hint}
            onClick={() => onPattern(`${pattern}${token}`)}
          >
            + {label}
          </Button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Change the numbers inside a part to suit: <code>{"{#5}"}</code> = 5 digits in order, <code>{"{A8}"}</code> = 8
        random letters/digits, <code>{"{L2}"}</code> = 2 random letters, <code>{"{D6}"}</code> = 6 random digits,{" "}
        <code>{"{500-999}"}</code> = a random number between 500 and 999.
      </p>

      {usesNumbers && (
        <div className="space-y-1">
          <Label htmlFor="cid-start">Numbers in order start from</Label>
          <Input
            id="cid-start"
            type="number"
            min={0}
            max={999999999}
            className="w-40"
            disabled={locked}
            value={start}
            onChange={(e) => onStart(Math.max(0, Math.floor(Number(e.target.value) || 0)))}
          />
          <p className="text-xs text-muted-foreground">
            The first certificate gets this number, the next one more, and so on.
          </p>
        </div>
      )}

      <div className="rounded-md bg-muted/60 p-2 text-sm">
        {problem ? (
          <p className="text-destructive">{problem}</p>
        ) : examples ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-muted-foreground">Examples:</span>
            {examples.map((id) => (
              <code key={id} className="rounded bg-background px-1.5 py-0.5">
                {id}
              </code>
            ))}
            {/\{[ADLadl]\d|\{\d+-\d+\}/.test(pattern) && (
              <button type="button" className="text-xs text-primary underline" onClick={() => setShuffle((n) => n + 1)}>
                show others
              </button>
            )}
          </div>
        ) : (
          <p className="text-muted-foreground">Examples appear here once you enter a format.</p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={!dirty || !!problem || save.isPending || locked} onClick={() => save.mutate()}>
          {save.isPending ? "Saving..." : "Save ID format"}
        </Button>
        {dirty && !locked && <span className="text-sm text-amber-700">Not saved yet.</span>}
        {save.isSuccess && !dirty && <span className="text-sm text-muted-foreground">Saved.</span>}
        {locked && (
          <span className="text-sm text-muted-foreground">Certificates have been sent, so the format is locked.</span>
        )}
      </div>
      {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</p>}
    </div>
  );
}
