import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type LetterConfig,
  type LetterSettings,
  type ReleaseResult,
  letterKeys,
  lettersApi,
  useLetterStudents,
} from "@/features/our-internships/api/letters-api";
import { LettersEmail } from "@/features/our-internships/components/letters-email";
import { type ReleaseChoices, asksAboutLinks, releaseBlockedBy, releaseOptions } from "@/features/our-internships/lib/letters";

const DELIVERY = { none: "Not sent", queued: "Sending", sent: "Sent", failed: "Failed" } as const;

/**
 * Step 5: the email, who gets it, and the send. The email itself is an Email Studio template (see LettersEmail). Only letters an
 * administrator approved can be released, each student gets only their own PDF at their registered address, and every attempt (with
 * the reason for a failure) is kept in the history.
 */
export function LettersRelease({
  internshipId,
  settings,
  draft,
  onDraft,
  dirty,
}: {
  internshipId: string;
  settings: LetterSettings;
  draft: LetterConfig;
  onDraft: (next: LetterConfig) => void;
  dirty: boolean;
}) {
  const queryClient = useQueryClient();
  const students = useLetterStudents(internshipId);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [previewFor, setPreviewFor] = useState("");
  const [choices, setChoices] = useState<ReleaseChoices>({ linkPolicy: "keep_existing", useLegacy: false });
  const [result, setResult] = useState<ReleaseResult | null>(null);
  const permissions = useStudioPermissions();
  const refresh = () => queryClient.invalidateQueries({ queryKey: letterKeys.all(internshipId) });

  const preview = useQuery({
    queryKey: [...letterKeys.all(internshipId), "email-preview", previewFor, settings.config.email.subject, settings.config.email.body],
    queryFn: () => lettersApi.emailPreview(internshipId, previewFor || null),
  });
  const release = useMutation({
    mutationFn: (ids: string[]) => lettersApi.release(internshipId, ids, false, releaseOptions(preview.data, choices)),
    onSuccess: (r) => {
      setResult(r);
      setPicked(new Set());
      void refresh();
    },
  });
  // while letters are on their way, the history and the activity move on their own
  const sending = students.data?.students.some((r) => r.letter?.delivery_status === "queued") ?? false;
  const deliveries = useQuery({ queryKey: letterKeys.deliveries(internshipId), queryFn: () => lettersApi.deliveries(internshipId), refetchInterval: sending ? 3000 : false });
  const events = useQuery({ queryKey: letterKeys.events(internshipId), queryFn: () => lettersApi.events(internshipId), refetchInterval: sending ? 3000 : false });

  if (students.isLoading) return <Skeleton className="h-48 w-full" />;
  const rows = students.data?.students ?? [];
  // approved letters can be released (one whose email failed too, to try again), unless it is already on its way
  const releasable = rows.filter((r) => r.letter && !r.letter.outdated && r.letter.status === "approved" && r.letter.delivery_status !== "queued");
  const chosen = releasable.filter((r) => picked.has(r.student_id));
  const allPicked = releasable.length > 0 && chosen.length === releasable.length;
  const toggle = (id: string) =>
    setPicked((p) => {
      const next = new Set(p);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const blockedBy = releaseBlockedBy(preview.data, choices);

  return (
    <div className="space-y-6">
      <LettersEmail
        internshipId={internshipId}
        settings={settings}
        draft={draft}
        onDraft={onDraft}
        dirty={dirty}
        rows={rows}
        preview={preview}
        previewFor={previewFor}
        onPreviewFor={setPreviewFor}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Release the offer letters</CardTitle>
          <CardDescription>
            Choose who gets their letter. Only approved letters are listed; approve them on the Generated Letters tab. Nothing is sent until you confirm here.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {releasable.length === 0 ? (
            <p className="text-sm text-muted-foreground">No approved letters are waiting to be sent.</p>
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <input type="checkbox" aria-label="Select every approved letter" checked={allPicked} onChange={() => setPicked(allPicked ? new Set() : new Set(releasable.map((r) => r.student_id)))} />
                    </TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead>Will be sent to</TableHead>
                    <TableHead>Letter</TableHead>
                    <TableHead>Last send</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {releasable.map((r) => (
                    <TableRow key={r.student_id}>
                      <TableCell>
                        <input type="checkbox" aria-label={`Select ${r.name}`} checked={picked.has(r.student_id)} onChange={() => toggle(r.student_id)} />
                      </TableCell>
                      <TableCell className="font-medium">{r.name}</TableCell>
                      <TableCell>{r.email}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{r.letter?.reference} · v{r.letter?.version}</TableCell>
                      <TableCell>
                        {r.letter && r.letter.delivery_status !== "none" ? (
                          <Badge variant={r.letter.delivery_status === "failed" ? "destructive" : "info"}>{DELIVERY[r.letter.delivery_status]}</Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">Not sent</span>
                        )}
                        {r.letter?.delivery_error && <p className="mt-1 max-w-xs text-xs text-destructive">{r.letter.delivery_error}</p>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {asksAboutLinks(preview.data) && (
            <fieldset className="space-y-2 rounded-md border p-3 text-sm">
              <legend className="px-1 font-medium">Students' onboarding links</legend>
              <label className="flex items-start gap-2">
                <input type="radio" name="link-policy" className="mt-1" checked={choices.linkPolicy === "keep_existing"} onChange={() => setChoices({ ...choices, linkPolicy: "keep_existing" })} />
                <span>Keep the link a student already has (recommended). Students with no link get a new one in their email.</span>
              </label>
              <label className="flex items-start gap-2">
                <input type="radio" name="link-policy" className="mt-1" checked={choices.linkPolicy === "replace"} onChange={() => setChoices({ ...choices, linkPolicy: "replace" })} />
                <span>Give every student a new link. A student's earlier link stops working once their new email is accepted by the mail server.</span>
              </label>
            </fieldset>
          )}
          {preview.data?.problem && (
            <div role="alert" className="space-y-2 rounded-md border border-destructive/50 p-3 text-sm">
              <p className="text-destructive">The assigned email template cannot be used: {preview.data.problem}</p>
              <p className="text-muted-foreground">Fix it in Email Studio. Nothing is sent with other wording unless you choose the built-in email below.</p>
              {permissions.canPublish ? (
                <label className="flex items-start gap-2">
                  <input type="checkbox" className="mt-1" checked={choices.useLegacy} onChange={(e) => setChoices({ ...choices, useLegacy: e.target.checked })} />
                  <span>Send the built-in (legacy) email for this release instead. This is recorded on each letter.</span>
                </label>
              ) : (
                <p className="text-xs text-muted-foreground">Choosing the built-in email needs Email Studio publish access.</p>
              )}
            </div>
          )}
          {release.isError && <p className="text-sm text-destructive">{errorMessage(release.error, "Could not release the letters.")}</p>}
          {result && (
            <div className="space-y-1 text-sm">
              <p className="text-emerald-700 dark:text-emerald-400">{result.message}</p>
              {result.skipped.map((s) => (
                <p key={s.letter_id} className="text-amber-700 dark:text-amber-400">
                  {s.name}: {s.reason}
                </p>
              ))}
            </div>
          )}
          <Button
            disabled={chosen.length === 0 || release.isPending || dirty || !!blockedBy}
            onClick={() => {
              const links = asksAboutLinks(preview.data) && releaseOptions(preview.data, choices).link_policy === "replace" ? " Every student gets a NEW onboarding link, and their earlier link stops working once the email is accepted." : "";
              if (window.confirm(`Email an offer letter to ${chosen.length} student${chosen.length === 1 ? "" : "s"}? Each gets only their own letter. This cannot be undone.${links}`)) release.mutate(chosen.map((r) => (r.letter as { id: string }).id));
            }}
          >
            <Send className="h-4 w-4" />
            {release.isPending ? "Releasing..." : chosen.length ? `Confirm release to ${chosen.length}` : "Choose students to release"}
          </Button>
          {dirty && <p className="text-xs text-amber-700 dark:text-amber-400">Save or discard your unsaved settings before releasing.</p>}
          {blockedBy && <p className="text-xs text-destructive">{blockedBy}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Delivery history</CardTitle>
          <CardDescription>Every email attempt, including retries and the reason for any failure.</CardDescription>
        </CardHeader>
        <CardContent>
          {deliveries.data && deliveries.data.length > 0 ? (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead>Recipient</TableHead>
                    <TableHead>Result</TableHead>
                    <TableHead>Attempt</TableHead>
                    <TableHead>Reason</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deliveries.data.map((d) => (
                    <TableRow key={d.id}>
                      <TableCell className="whitespace-nowrap text-xs">{new Date(d.created_at).toLocaleString()}</TableCell>
                      <TableCell>{d.student_name}</TableCell>
                      <TableCell>{d.recipient_email}</TableCell>
                      <TableCell>
                        <Badge variant={d.status === "sent" ? "success" : "destructive"}>{d.status === "sent" ? "Sent" : "Failed"}</Badge>
                      </TableCell>
                      <TableCell className="tabular-nums">{d.attempt}</TableCell>
                      <TableCell className="max-w-xs text-xs text-destructive">{d.error}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Nothing has been sent yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Activity</CardTitle>
          <CardDescription>Who set up, approved, generated and released what.</CardDescription>
        </CardHeader>
        <CardContent>
          {events.data && events.data.length > 0 ? (
            <ul className="space-y-1 text-sm">
              {events.data.map((e) => (
                <li key={e.id} className="flex flex-wrap gap-x-3">
                  <span className="whitespace-nowrap text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString()}</span>
                  <span>{e.detail ?? e.action}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No activity yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
