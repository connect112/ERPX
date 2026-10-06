import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { hackathonsApi } from "@/features/hackathons/api/hackathons-api";
import { parseAttendees } from "@/features/workshop-exams/lib/parsers";

const MAX_PER_REQUEST = 300;

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

/**
 * Paste "Name, email" lines to create a student login for each person and
 * email them a link to set their password. Students then sign in to the
 * student portal and create or join a team themselves.
 */
export function ParticipantsCard({ hackathonId }: { hackathonId: string }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [resend, setResend] = useState(false);
  const parsed = parseAttendees(text);

  const add = useMutation({
    mutationFn: () => hackathonsApi.addParticipants(hackathonId, parsed.rows, resend),
    onSuccess: (result) => {
      // Keep failed rows in the box so they can be fixed and retried; clear it
      // only when everything went through.
      if (result.errors.length === 0) setText("");
      else {
        const failed = new Set(result.errors.map((e) => e.email));
        setText(
          parsed.rows
            .filter((r) => failed.has(r.email))
            .map((r) => `${r.name}, ${r.email}`)
            .join("\n")
        );
      }
      queryClient.invalidateQueries({ queryKey: ["hackathons"] });
      queryClient.invalidateQueries({ queryKey: ["students"] });
    },
  });

  const tooMany = parsed.rows.length > MAX_PER_REQUEST;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add participants</CardTitle>
        <CardDescription>
          Paste one person per line as "Name, email" (or two columns from a spreadsheet). Each person gets an ERPX
          student login and an email to set their password; then they sign in to the student portal and create or
          join a team. People who already have a login are left alone.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          rows={8}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={"Asha Rao, asha@example.com\nRavi Kumar, ravi@example.com"}
        />
        <p className="text-sm text-muted-foreground">{parsed.rows.length} valid</p>
        {parsed.errors.length > 0 && (
          <ul className="max-h-24 overflow-auto text-sm text-destructive">
            {parsed.errors.slice(0, 8).map((e) => (
              <li key={e}>{e}</li>
            ))}
            {parsed.errors.length > 8 && <li>...and {parsed.errors.length - 8} more</li>}
          </ul>
        )}
        {tooMany && (
          <p className="text-sm text-destructive">Add at most {MAX_PER_REQUEST} people at a time - split the list.</p>
        )}
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={resend} onChange={(e) => setResend(e.target.checked)} />
          <span>Also email a fresh set-password link to people who already have a login (e.g. they lost the email).</span>
        </label>
        <Button disabled={parsed.rows.length === 0 || tooMany || add.isPending} onClick={() => add.mutate()}>
          {add.isPending ? "Creating accounts..." : `Create ${parsed.rows.length || ""} login${parsed.rows.length === 1 ? "" : "s"}`}
        </Button>

        {add.isSuccess && (
          <div className="space-y-1 text-sm">
            <p className="text-emerald-700">
              Created {add.data.created} login(s) and queued their emails
              {add.data.resent > 0 && `; re-sent a link to ${add.data.resent}`}
              {add.data.already_have_login > 0 && `; ${add.data.already_have_login} already had a login`}.
            </p>
            {add.data.errors.length > 0 && (
              <div className="text-destructive">
                <p>{add.data.errors.length} could not be created (left in the box above):</p>
                <ul className="list-disc pl-5">
                  {add.data.errors.slice(0, 10).map((e) => (
                    <li key={e.email}>
                      {e.email}: {e.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {add.isError && <p className="text-sm text-destructive">{errorMessage(add.error, "Could not create the logins.")}</p>}
      </CardContent>
    </Card>
  );
}
