import { CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useStudentsList } from "@/features/students/api/students-hooks";
import { useSetFlag, useSubmitFlag } from "@/features/pentrix/flags/api/flags-hooks";
import type { SubmissionResultResponse } from "@/features/pentrix/flags/api/flags-api";

export function FlagPanel({ challengeId }: { challengeId: string }) {
  const { data: students } = useStudentsList({ limit: 200 });
  const setFlag = useSetFlag(challengeId);
  const submitFlag = useSubmitFlag(challengeId);

  const [flagValue, setFlagValue] = useState("");
  const [studentId, setStudentId] = useState("");
  const [submitValue, setSubmitValue] = useState("");
  const [result, setResult] = useState<SubmissionResultResponse | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Flag</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="flagValue">Set / update flag</Label>
          <div className="flex gap-2">
            <Input
              id="flagValue"
              placeholder="flag{...}"
              value={flagValue}
              onChange={(e) => setFlagValue(e.target.value)}
            />
            <Button
              disabled={!flagValue || setFlag.isPending}
              onClick={() => setFlag.mutate(flagValue, { onSuccess: () => setFlagValue("") })}
            >
              {setFlag.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
          {setFlag.isSuccess && (
            <p className="text-xs text-emerald-600 dark:text-emerald-400">Flag updated.</p>
          )}
          <p className="text-xs text-muted-foreground">
            Stored as a hash — the plaintext is never shown back once saved.
          </p>
        </div>

        <div className="space-y-2 border-t pt-4">
          <Label htmlFor="submit-on-behalf">Submit on behalf of a student</Label>
          <div className="flex flex-wrap gap-2">
            <Select value={studentId || undefined} onValueChange={setStudentId}>
              <SelectTrigger id="submit-on-behalf" className="w-48">
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
            <Input
              className="flex-1"
              placeholder="Submitted flag value"
              value={submitValue}
              onChange={(e) => setSubmitValue(e.target.value)}
            />
            <Button
              disabled={!studentId || !submitValue || submitFlag.isPending}
              onClick={() =>
                submitFlag.mutate(
                  { studentId, flagValue: submitValue },
                  {
                    onSuccess: (data) => {
                      setResult(data);
                      setSubmitValue("");
                    },
                  }
                )
              }
            >
              {submitFlag.isPending ? "Checking..." : "Submit"}
            </Button>
          </div>
          {result && (
            <div className="flex items-center gap-2 rounded-md border p-2 text-sm">
              {result.correct ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              ) : (
                <XCircle className="h-4 w-4 text-destructive" />
              )}
              <span>
                {result.correct
                  ? result.already_solved
                    ? "Correct — already solved previously."
                    : `Correct! ${result.points_awarded} points awarded.`
                  : "Incorrect flag."}
              </span>
              {result.correct && !result.already_solved && (
                <Badge variant="success">+{result.points_awarded}</Badge>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
