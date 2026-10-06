import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { HackathonPublic } from "@/features/hackathons/api/hackathons-api";
import { useUpdateHackathon } from "@/features/hackathons/api/hackathons-hooks";

const MAX_LIMIT = 50;

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

/**
 * Whether teams may change a task submission after making it, and how many times. The
 * limit box only appears while resubmission is on; the first submission never counts.
 */
export function ResubmissionCard({ hackathon }: { hackathon: HackathonPublic }) {
  const update = useUpdateHackathon(hackathon.id);
  const [limit, setLimit] = useState(String(hackathon.max_resubmissions));

  useEffect(() => {
    setLimit(String(hackathon.max_resubmissions));
  }, [hackathon.max_resubmissions]);

  const parsed = Number(limit);
  const valid = limit.trim() !== "" && Number.isInteger(parsed) && parsed >= 0 && parsed <= MAX_LIMIT;
  const changed = valid && parsed !== hackathon.max_resubmissions;
  const saveLimit = () => {
    if (changed && !update.isPending) update.mutate({ max_resubmissions: parsed });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Resubmission</CardTitle>
        <CardDescription>
          {hackathon.resubmission_enabled
            ? "Teams can change a task submission after making it, up to the limit below."
            : "Submissions are final once a team has made them."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={hackathon.resubmission_enabled}
            disabled={update.isPending}
            onChange={(e) => update.mutate({ resubmission_enabled: e.target.checked })}
          />
          <span>Allow teams to resubmit a task</span>
        </label>

        {hackathon.resubmission_enabled && (
          <div className="space-y-1.5">
            <label htmlFor="max-resubmissions" className="text-sm font-medium">
              Resubmissions allowed per task
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="max-resubmissions"
                type="number"
                min={0}
                max={MAX_LIMIT}
                step={1}
                inputMode="numeric"
                className={`w-24 ${limit.trim() !== "" && !valid ? "border-destructive" : ""}`}
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    saveLimit();
                  }
                }}
              />
              <Button size="sm" disabled={!changed || update.isPending} onClick={saveLimit}>
                Save
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {valid && parsed === 0
                ? "0 means a team can only submit each task once."
                : `A team's first submission doesn't count, so each team can submit a task ${valid ? parsed + 1 : "…"} times in all.`}{" "}
              A resubmitted task shows as unreviewed again until you re-score it.
            </p>
          </div>
        )}
        {update.isError && <p className="text-sm text-destructive">{errorMessage(update.error, "Could not save.")}</p>}
      </CardContent>
    </Card>
  );
}
