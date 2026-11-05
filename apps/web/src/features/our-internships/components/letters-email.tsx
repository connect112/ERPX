import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { ExternalLink, Mail, Monitor, RefreshCw, Smartphone } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type EmailPreview,
  type LetterConfig,
  type LetterSettings,
  type LetterStudent,
  letterKeys,
  lettersApi,
} from "@/features/our-internships/api/letters-api";
import { AreaField, TextField, selectClass } from "@/features/our-internships/components/letter-fields";
import { setPath } from "@/features/our-internships/lib/letters";

const STUDIO = "/administration/email-templates";

/**
 * The email that goes with each offer letter. It is written in Email Studio: this card shows which published template is assigned
 * to it, draws the email exactly as the server will send it (for a sample student or a chosen one) and sends a test. Nothing here
 * issues, changes or reveals a real onboarding link: the link shown is a sample that opens nothing.
 *
 * With no template assigned the letter settings' own wording (the legacy email) is used, and stays editable here.
 */
export function LettersEmail({
  internshipId,
  settings,
  draft,
  onDraft,
  dirty,
  rows,
  preview,
  previewFor,
  onPreviewFor,
}: {
  internshipId: string;
  settings: LetterSettings;
  draft: LetterConfig;
  onDraft: (next: LetterConfig) => void;
  dirty: boolean;
  rows: LetterStudent[];
  preview: UseQueryResult<EmailPreview>;
  previewFor: string;
  onPreviewFor: (studentId: string) => void;
}) {
  const queryClient = useQueryClient();
  const permissions = useStudioPermissions();
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [testTo, setTestTo] = useState("");
  const test = useMutation({ mutationFn: () => lettersApi.testEmail(internshipId, testTo.trim()) });
  const saveEmail = useMutation({
    mutationFn: () => lettersApi.saveConfig(internshipId, draft, "internship"),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: letterKeys.all(internshipId) }),
  });
  const email = preview.data;
  const emailDirty = dirty && (draft.email.subject !== settings.config.email.subject || draft.email.body !== settings.config.email.body);
  const canOpenStudio = permissions.canManage || permissions.canPublish;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Email template</CardTitle>
          <CardDescription>Sent with the student's own letter attached. The wording and design are managed in Email Studio.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!email ? (
            <Skeleton className="h-16 w-full" />
          ) : email.source === "studio" ? (
            <div className="space-y-2 rounded-md border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{email.template?.name ?? "Assigned template"}</span>
                {email.template?.version_number != null && <Badge variant="success">Published v{email.template.version_number}</Badge>}
                {email.uses_link && email.link_available && <Badge variant="info">Includes the student's onboarding link</Badge>}
                {email.uses_link && !email.link_available && <Badge variant="outline">Link left out (manual onboarding)</Badge>}
              </div>
              {email.template?.published_at && <p className="text-xs text-muted-foreground">Published {new Date(email.template.published_at).toLocaleString()}.</p>}
              {email.problem && (
                <p role="alert" className="text-destructive">
                  This template cannot be used right now: {email.problem}
                </p>
              )}
              <div className="flex flex-wrap items-center gap-3">
                {canOpenStudio && email.template?.id ? (
                  <Button asChild size="sm" variant="outline">
                    <Link to={`${STUDIO}/studio/${email.template.id}`}>
                      <ExternalLink className="h-4 w-4" /> Edit in Email Studio
                    </Link>
                  </Button>
                ) : null}
                {canOpenStudio && (
                  <Link className="text-sm underline" to={STUDIO}>
                    Email Studio library
                  </Link>
                )}
                {!canOpenStudio && <span className="text-xs text-muted-foreground">Ask an administrator with Email Studio access to change it.</span>}
              </div>
              <p className="text-xs text-muted-foreground">
                A release uses the version published now and keeps using it for that whole batch, even if a newer version is published while it is being sent.
              </p>
            </div>
          ) : (
            <div className="space-y-2 rounded-md border border-dashed p-3 text-sm">
              <p>
                <span className="font-medium">No Email Studio template is assigned.</span> The built-in wording below is used. For a branded email (and an optional personal onboarding
                link), publish a template in Email Studio and assign it to <em>Internship offer letter</em>.
              </p>
              {canOpenStudio ? (
                <div className="flex flex-wrap gap-3">
                  <Button asChild size="sm" variant="outline">
                    <Link to={`${STUDIO}/create`}>
                      <ExternalLink className="h-4 w-4" /> Create an email in Email Studio
                    </Link>
                  </Button>
                  <Link className="self-center text-sm underline" to={STUDIO}>
                    Email Studio library
                  </Link>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Ask an administrator with Email Studio access to set one up.</p>
              )}
              <details className="pt-1">
                <summary className="cursor-pointer text-sm font-medium">Built-in wording (used only until a template is assigned)</summary>
                <div className="space-y-3 pt-3">
                  <p className="text-xs text-muted-foreground">
                    Placeholders: {Object.keys(settings.placeholders).map((k) => `{{${k}}}`).join(", ")}.
                  </p>
                  <TextField id="em-subject" label="Subject" value={draft.email.subject} onChange={(v) => onDraft(setPath(draft, ["email", "subject"], v))} />
                  <AreaField id="em-body" label="Message" rows={9} value={draft.email.body} onChange={(v) => onDraft(setPath(draft, ["email", "body"], v))} />
                  <div className="flex flex-wrap items-center gap-3">
                    <Button size="sm" disabled={!dirty || saveEmail.isPending} onClick={() => saveEmail.mutate()}>
                      {saveEmail.isPending ? "Saving..." : "Save the email"}
                    </Button>
                    {emailDirty && <span className="text-sm text-amber-700 dark:text-amber-400">Save to see the preview below change.</span>}
                    {saveEmail.isError && <span className="text-sm text-destructive">{errorMessage(saveEmail.error, "Could not save.")}</span>}
                  </div>
                </div>
              </details>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Review the email and attachment</CardTitle>
          <CardDescription>Drawn by the server exactly as it will be sent. A preview or a test never creates or changes a student's real onboarding link.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <label htmlFor="em-student" className="text-sm font-medium">
                Show it for
              </label>
              <select id="em-student" className={`${selectClass} max-w-sm`} value={previewFor} onChange={(e) => onPreviewFor(e.target.value)}>
                <option value="">A sample student</option>
                {rows.map((r) => (
                  <option key={r.student_id} value={r.student_id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="inline-flex rounded-md border p-0.5" role="group" aria-label="Preview size">
              <Button size="sm" variant={device === "desktop" ? "default" : "ghost"} onClick={() => setDevice("desktop")} aria-pressed={device === "desktop"}>
                <Monitor className="h-4 w-4" /> Desktop
              </Button>
              <Button size="sm" variant={device === "mobile" ? "default" : "ghost"} onClick={() => setDevice("mobile")} aria-pressed={device === "mobile"}>
                <Smartphone className="h-4 w-4" /> Mobile
              </Button>
            </div>
            <Button size="sm" variant="outline" disabled={preview.isFetching} onClick={() => void preview.refetch()}>
              <RefreshCw className={`h-4 w-4 ${preview.isFetching ? "animate-spin" : ""}`} /> Refresh
            </Button>
          </div>
          {preview.isError && <p className="text-sm text-destructive">{errorMessage(preview.error, "Could not draw the preview.")}</p>}
          {email && (
            <div className="space-y-2">
              <div className="space-y-1 rounded-md border bg-muted/30 p-3 text-sm">
                <p>
                  <span className="text-muted-foreground">To:</span> {email.to || "(a sample address)"}
                </p>
                <p>
                  <span className="text-muted-foreground">Subject:</span> {email.subject}
                </p>
                <p>
                  <span className="text-muted-foreground">Attachment:</span> {email.attachment}
                </p>
                {email.uses_link && email.link_available && <p className="text-xs text-muted-foreground">The link in this preview is a sample that opens nothing.</p>}
              </div>
              {email.html ? (
                <div className="overflow-x-auto rounded-md border bg-muted/40 p-3">
                  <iframe
                    title="Email preview"
                    sandbox=""
                    srcDoc={email.html}
                    style={{ width: device === "mobile" ? 375 : 680, maxWidth: "100%" }}
                    className="mx-auto block h-[60vh] rounded border bg-white"
                  />
                </div>
              ) : (
                <pre className="whitespace-pre-wrap rounded-md border bg-muted/40 p-3 font-sans text-sm">{email.body}</pre>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Input aria-label="Send a test email to" type="email" placeholder="you@example.com" className="max-w-xs" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
            <Button size="sm" variant="outline" disabled={!testTo.trim() || test.isPending || !!email?.problem} onClick={() => test.mutate()}>
              <Mail className="h-4 w-4" />
              {test.isPending ? "Sending..." : "Send a test with a sample letter"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">The test uses sample details and a sample letter, is marked as a test, and goes only to the address above.</p>
          {test.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">{test.data.message}</p>}
          {test.isError && <p className="text-sm text-destructive">{errorMessage(test.error, "Could not send the test.")}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
