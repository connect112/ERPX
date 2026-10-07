import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import type { TemplateDetail, TemplatePreview, TemplateScope } from "@/features/email-templates/api/email-templates-api";
import {
  useEmailTemplate,
  usePreviewEmailTemplate,
  useResetEmailTemplate,
  useSaveEmailTemplate,
  useSendTestEmail,
} from "@/features/email-templates/api/email-templates-hooks";
import { useAuthStore } from "@/store/auth-store";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

type Field = "subject" | "body";

function EditorBody({ scope, detail }: { scope: TemplateScope; detail: TemplateDetail }) {
  const eventScope = Boolean(scope.hackathonId);
  const [subject, setSubject] = useState(detail.subject);
  const [body, setBody] = useState(detail.body);
  const [preview, setPreview] = useState<TemplatePreview | null>(null);
  const [testTo, setTestTo] = useState(useAuthStore.getState().user?.email ?? "");
  const [testResult, setTestResult] = useState<{ sent: boolean; message: string } | null>(null);
  const [saved, setSaved] = useState(false);
  const lastField = useRef<Field>("body");
  const subjectRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  const save = useSaveEmailTemplate(scope, detail.key);
  const reset = useResetEmailTemplate(scope, detail.key);
  const previewMutation = usePreviewEmailTemplate(scope, detail.key);
  const sendTest = useSendTestEmail(scope, detail.key);

  const dirty = subject !== detail.subject || body !== detail.body;
  const problems = preview?.errors ?? [];

  // Show what the email will look like (with sample values) as the wording is typed.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      previewMutation.mutate({ subject, body }, { onSuccess: setPreview });
    }, 400);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subject, body]);

  const insert = (name: string) => {
    const token = `{{${name}}}`;
    const field = lastField.current;
    const element = field === "subject" ? subjectRef.current : bodyRef.current;
    const value = field === "subject" ? subject : body;
    const start = element?.selectionStart ?? value.length;
    const end = element?.selectionEnd ?? value.length;
    const next = value.slice(0, start) + token + value.slice(end);
    if (field === "subject") setSubject(next);
    else setBody(next);
    window.setTimeout(() => {
      element?.focus();
      element?.setSelectionRange(start + token.length, start + token.length);
    }, 0);
  };

  const status = detail.customised
    ? eventScope
      ? "Edited for this event"
      : "Edited"
    : eventScope
      ? "Using the organisation's wording"
      : "Default wording";

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge variant={detail.customised ? "info" : "secondary"}>{status}</Badge>
          {detail.updated_at && (
            <span className="text-xs text-muted-foreground">
              Last edited {new Date(detail.updated_at).toLocaleString()}
              {detail.updated_by_name ? ` by ${detail.updated_by_name}` : ""}
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          <strong>Sent:</strong> {detail.when_sent}
          {detail.has_attachment && " The PDF attachment is added automatically."}
        </p>

        <div className="space-y-1">
          <Label htmlFor="tpl-subject">Subject</Label>
          <Input
            id="tpl-subject"
            ref={subjectRef}
            value={subject}
            maxLength={300}
            onFocus={() => (lastField.current = "subject")}
            onChange={(e) => setSubject(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="tpl-body">Message</Label>
          <Textarea
            id="tpl-body"
            ref={bodyRef}
            rows={14}
            className="font-mono text-sm"
            value={body}
            onFocus={() => (lastField.current = "body")}
            onChange={(e) => setBody(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <p className="text-xs font-medium">Click to insert a detail that is filled in for each person</p>
          <div className="flex flex-wrap gap-1.5">
            {detail.variables.map((v) => (
              <button
                key={v.name}
                type="button"
                title={`${v.description} (for example: ${v.sample})`}
                onClick={() => insert(v.name)}
                className="rounded-md border bg-muted/40 px-2 py-1 font-mono text-xs hover:bg-muted"
              >
                {`{{${v.name}}}`}
              </button>
            ))}
          </div>
        </div>

        <details className="rounded-md border p-3 text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium text-foreground">How to format the message</summary>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            <li>
              <code># Heading</code> on its own line makes a heading.
            </li>
            <li>A blank line starts a new paragraph.</li>
            <li>
              <code>**bold**</code> makes bold text; <code>[link text](https://example.com)</code> makes a link.
            </li>
            <li>
              A line with only a link, like <code>[Set my password]({"{{set_password_url}}"})</code>, becomes a button.
            </li>
            <li>
              <code>&gt; small note</code> makes small grey text.
            </li>
          </ul>
        </details>

        {problems.length > 0 && (
          <ul className="space-y-1 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            disabled={!dirty || problems.length > 0 || save.isPending}
            onClick={() => save.mutate({ subject, body }, { onSuccess: () => setSaved(true) })}
          >
            {save.isPending ? "Saving..." : "Save changes"}
          </Button>
          {dirty && (
            <Button
              variant="ghost"
              onClick={() => {
                setSubject(detail.subject);
                setBody(detail.body);
                setSaved(false);
              }}
            >
              Discard changes
            </Button>
          )}
          {detail.customised && (
            <Button
              variant="outline"
              disabled={reset.isPending}
              onClick={() => {
                const message = eventScope
                  ? "Go back to the organisation's wording for this email? This event's own version is deleted."
                  : "Go back to the default wording? Your edits to this email are deleted.";
                if (window.confirm(message)) reset.mutate(undefined, { onSuccess: () => setSaved(false) });
              }}
            >
              {eventScope ? "Use the organisation's wording" : "Reset to default"}
            </Button>
          )}
          {(subject !== detail.default_subject || body !== detail.default_body) && (
            <Button
              variant="ghost"
              title="Put the built-in wording into the editor (nothing is saved until you press Save)"
              onClick={() => {
                setSubject(detail.default_subject);
                setBody(detail.default_body);
                setSaved(false);
              }}
            >
              Load default text
            </Button>
          )}
          {saved && !dirty && <span className="text-sm text-emerald-700">Saved.</span>}
        </div>
        {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</p>}
        {reset.isError && <p className="text-sm text-destructive">{errorMessage(reset.error, "Could not reset.")}</p>}
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <p className="text-xs font-medium">Preview (with sample details)</p>
          <div className="rounded-md border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">Subject</p>
            <p className="text-sm font-medium">{preview?.subject ?? " "}</p>
          </div>
          <iframe
            title="Email preview"
            // No scripts, forms or popups are allowed in the preview; same-origin is only so it paints.
            sandbox="allow-same-origin"
            srcDoc={`<body style="margin:16px;background:#fff">${preview?.html ?? ""}</body>`}
            className="h-80 w-full rounded-md border bg-white"
          />
        </div>

        <div className="space-y-2 rounded-md border p-3">
          <p className="text-sm font-medium">Send a test email</p>
          <p className="text-xs text-muted-foreground">
            Sends what you see here (even if it isn't saved yet) with sample details, to one address only. It is marked
            [TEST], and it also tells you whether the mail server is working.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="email"
              aria-label="Send the test email to"
              placeholder="Email address to send the test to"
              className="min-w-[14rem] flex-1"
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && testTo.trim() && problems.length === 0) {
                  e.preventDefault();
                  sendTest.mutate({ to_email: testTo.trim(), subject, body }, { onSuccess: setTestResult, onError: () => setTestResult(null) });
                }
              }}
            />
            <Button
              variant="outline"
              disabled={!testTo.trim() || problems.length > 0 || sendTest.isPending}
              onClick={() =>
                sendTest.mutate(
                  { to_email: testTo.trim(), subject, body },
                  { onSuccess: setTestResult, onError: () => setTestResult(null) }
                )
              }
            >
              <Send className="h-4 w-4" />
              {sendTest.isPending ? "Sending..." : "Send test"}
            </Button>
          </div>
          {testResult && (
            <p className={`text-sm ${testResult.sent ? "text-emerald-700" : "text-destructive"}`}>{testResult.message}</p>
          )}
          {sendTest.isError && <p className="text-sm text-destructive">{errorMessage(sendTest.error, "Could not send the test.")}</p>}
        </div>
      </div>
    </div>
  );
}

/** The editor for one email, in a dialog. `scope` says whether it is the organisation's wording or one event's. */
export function TemplateEditorDialog({
  scope,
  templateKey,
  onClose,
}: {
  scope: TemplateScope;
  templateKey: string;
  onClose: () => void;
}) {
  const { data: detail, isLoading, isError } = useEmailTemplate(scope, templateKey);
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{detail?.name ?? "Email template"}</DialogTitle>
          <DialogDescription>{detail?.description ?? " "}</DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <Skeleton className="h-96 w-full" />
        ) : isError || !detail ? (
          <p className="text-sm text-destructive">Could not load this template.</p>
        ) : (
          // Keyed by what was saved, so the editor starts from the saved wording after a save or a reset.
          <EditorBody key={`${detail.key}:${detail.customised}:${detail.updated_at ?? ""}`} scope={scope} detail={detail} />
        )}
      </DialogContent>
    </Dialog>
  );
}
