import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Send } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type LetterConfig,
  type LetterSettings,
  type ReleaseResult,
  letterKeys,
  lettersApi,
  useLetterStudents,
} from "@/features/our-internships/api/letters-api";
import { AreaField, TextField, selectClass } from "@/features/our-internships/components/letter-fields";
import { setPath } from "@/features/our-internships/lib/letters";

const DELIVERY = { none: "Not sent", queued: "Sending", sent: "Sent", failed: "Failed" } as const;

/**
 * Step 5: the email, who gets it, and the send. Only letters an administrator approved can be released, each student gets only
 * their own PDF at their registered address, and every attempt (with the reason for a failure) is kept in the history.
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
  const [testTo, setTestTo] = useState("");
  const [result, setResult] = useState<ReleaseResult | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: letterKeys.all(internshipId) });

  const saveEmail = useMutation({ mutationFn: () => lettersApi.saveConfig(internshipId, draft, "internship"), onSuccess: () => void refresh() });
  const preview = useQuery({
    queryKey: [...letterKeys.all(internshipId), "email-preview", previewFor, settings.config.email.subject, settings.config.email.body],
    queryFn: () => lettersApi.emailPreview(internshipId, previewFor || null),
  });
  const test = useMutation({ mutationFn: () => lettersApi.testEmail(internshipId, testTo.trim()) });
  const release = useMutation({
    mutationFn: (ids: string[]) => lettersApi.release(internshipId, ids, false),
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
  const emailDirty = dirty && (draft.email.subject !== settings.config.email.subject || draft.email.body !== settings.config.email.body);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Email template</CardTitle>
          <CardDescription>
            Sent with the student's own letter attached. Placeholders: {Object.keys(settings.placeholders).map((k) => `{{${k}}}`).join(", ")}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <TextField id="em-subject" label="Subject" value={draft.email.subject} onChange={(v) => onDraft(setPath(draft, ["email", "subject"], v))} />
          <AreaField id="em-body" label="Message" rows={9} value={draft.email.body} onChange={(v) => onDraft(setPath(draft, ["email", "body"], v))} />
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" disabled={!dirty || saveEmail.isPending} onClick={() => saveEmail.mutate()}>
              {saveEmail.isPending ? "Saving..." : "Save the email"}
            </Button>
            {emailDirty && <span className="text-sm text-amber-700 dark:text-amber-400">Save to see the preview below change.</span>}
            {saveEmail.isError && <span className="text-sm text-destructive">{errorMessage(saveEmail.error, "Could not save.")}</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Review the email and attachment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <label htmlFor="em-student" className="text-sm font-medium">
              Show it for
            </label>
            <select id="em-student" className={`${selectClass} max-w-sm`} value={previewFor} onChange={(e) => setPreviewFor(e.target.value)}>
              <option value="">A sample student</option>
              {rows.map((r) => (
                <option key={r.student_id} value={r.student_id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
          {preview.data && (
            <div className="space-y-1 rounded-md border bg-muted/30 p-3 text-sm">
              <p>
                <span className="text-muted-foreground">To:</span> {preview.data.to || "(a sample address)"}
              </p>
              <p>
                <span className="text-muted-foreground">Subject:</span> {preview.data.subject}
              </p>
              <p>
                <span className="text-muted-foreground">Attachment:</span> {preview.data.attachment}
              </p>
              <pre className="mt-2 whitespace-pre-wrap font-sans">{preview.data.body}</pre>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Input aria-label="Send a test email to" type="email" placeholder="you@example.com" className="max-w-xs" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
            <Button size="sm" variant="outline" disabled={!testTo.trim() || test.isPending} onClick={() => test.mutate()}>
              <Mail className="h-4 w-4" />
              {test.isPending ? "Sending..." : "Send a test with a sample letter"}
            </Button>
          </div>
          {test.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">{test.data.message}</p>}
          {test.isError && <p className="text-sm text-destructive">{errorMessage(test.error, "Could not send the test.")}</p>}
        </CardContent>
      </Card>

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
            disabled={chosen.length === 0 || release.isPending || dirty}
            onClick={() => {
              if (window.confirm(`Email an offer letter to ${chosen.length} student${chosen.length === 1 ? "" : "s"}? Each gets only their own letter. This cannot be undone.`)) release.mutate(chosen.map((r) => (r.letter as { id: string }).id));
            }}
          >
            <Send className="h-4 w-4" />
            {release.isPending ? "Releasing..." : chosen.length ? `Confirm release to ${chosen.length}` : "Choose students to release"}
          </Button>
          {dirty && <p className="text-xs text-amber-700 dark:text-amber-400">Save or discard your unsaved settings before releasing.</p>}
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
