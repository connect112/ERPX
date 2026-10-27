import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Mail, RotateCcw, Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { type OfferSettings, offerKeys, offersApi } from "@/features/our-internships/api/our-internships-api";
import { useAuthStore } from "@/store/auth-store";

/** The email that carries each letter: subject, wording with {{placeholders}}, and the date printed on the letters. */
export function OfferEmailCard({ internshipId, settings }: { internshipId: string; settings: OfferSettings }) {
  const queryClient = useQueryClient();
  const myEmail = useAuthStore((s) => s.user?.email ?? "");
  const body = useRef<HTMLTextAreaElement>(null);
  const [subject, setSubject] = useState(settings.email_subject);
  const [text, setText] = useState(settings.email_body);
  const [date, setDate] = useState(settings.offer_date ?? "");
  const [testTo, setTestTo] = useState(myEmail);

  useEffect(() => {
    setSubject(settings.email_subject);
    setText(settings.email_body);
    setDate(settings.offer_date ?? "");
  }, [settings.email_subject, settings.email_body, settings.offer_date]);

  const dirty = subject !== settings.email_subject || text !== settings.email_body || date !== (settings.offer_date ?? "");
  const store = (next: OfferSettings) => queryClient.setQueryData(offerKeys.settings(internshipId), next);
  const save = useMutation({
    mutationFn: (override?: { subject: null; body: null }) =>
      offersApi.saveEmail(internshipId, {
        subject: override ? null : subject.trim() || null,
        body: override ? null : text.trim() || null,
        offer_date: date || null,
      }),
    onSuccess: store,
  });
  const test = useMutation({ mutationFn: () => offersApi.sendTest(internshipId, testTo.trim()) });

  const insert = (name: string) => {
    const el = body.current;
    const token = `{{${name}}}`;
    if (!el) return setText((t) => t + token);
    const start = el.selectionStart ?? text.length;
    const end = el.selectionEnd ?? text.length;
    setText(text.slice(0, start) + token + text.slice(end));
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + token.length, start + token.length);
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">The email</CardTitle>
        <CardDescription>
          Each student gets this email with their own letter attached. The words in double braces are filled in for each student.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <Label htmlFor="offer-subject">Subject</Label>
          <Input id="offer-subject" value={subject} maxLength={255} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="offer-body">Message</Label>
          <Textarea id="offer-body" ref={body} rows={10} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-xs text-muted-foreground">Insert:</span>
            {Object.entries(settings.placeholders).map(([name, hint]) => (
              <Button key={name} type="button" size="sm" variant="outline" title={hint} onClick={() => insert(name)}>
                {`{{${name}}}`}
              </Button>
            ))}
          </div>
        </div>
        <div className="space-y-1">
          <Label htmlFor="offer-date">
            Date printed on the letters <span className="text-xs text-muted-foreground">(leave empty to use the day you release them)</span>
          </Label>
          <Input id="offer-date" type="date" className="w-48" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the email.")}</p>}
        <div className="flex flex-wrap gap-2">
          <Button type="button" disabled={!dirty || save.isPending} onClick={() => save.mutate(undefined)}>
            <Save className="h-4 w-4" />
            {save.isPending ? "Saving..." : dirty ? "Save email" : "Saved"}
          </Button>
          {!settings.email_is_default && (
            <Button
              type="button"
              variant="outline"
              disabled={save.isPending}
              onClick={() => {
                if (window.confirm("Go back to the standard wording? Your own subject and message are replaced.")) save.mutate({ subject: null, body: null });
              }}
            >
              <RotateCcw className="h-4 w-4" />
              Use the standard wording
            </Button>
          )}
        </div>
        {dirty && <p className="text-xs text-muted-foreground">Save before sending a test or releasing offers: they use the saved email.</p>}

        <div className="space-y-2 rounded-md border p-3">
          <p className="text-sm font-medium">Send yourself a test</p>
          <p className="text-xs text-muted-foreground">Sends this email with a sample letter, so you can see exactly what a student will receive.</p>
          <div className="flex flex-wrap gap-2">
            <Input aria-label="Send the test to" type="email" className="w-72" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
            <Button type="button" variant="outline" disabled={!settings.layout?.fields.length || !/^\S+@\S+\.\S+$/.test(testTo.trim()) || test.isPending} onClick={() => test.mutate()}>
              <Mail className="h-4 w-4" />
              {test.isPending ? "Sending..." : "Send test"}
            </Button>
          </div>
          {!settings.layout?.fields.length && <p className="text-xs text-muted-foreground">Place the details on the letter first.</p>}
          {test.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">{test.data.message}</p>}
          {test.isError && <p className="text-sm text-destructive">{errorMessage(test.error, "The test email could not be sent.")}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
