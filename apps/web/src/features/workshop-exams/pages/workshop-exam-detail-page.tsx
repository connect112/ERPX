import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Award, Check, Copy, Download, Plus, Send, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { CertificateDesigner } from "@/features/workshop-exams/components/certificate-designer";
import { CodeTextarea } from "@/features/workshop-exams/components/code-textarea";
import { HackathonCertificatesDialog } from "@/features/workshop-exams/components/hackathon-certificates-dialog";
import { RichText } from "@/features/workshop-exams/components/rich-text";
import { QuestionEditor } from "@/features/workshop-exams/components/question-editor";
import { BLANK_QUESTION } from "@/features/workshop-exams/lib/question-draft";
import {
  type Attendee,
  type ExamStatus,
  type InfoField,
  type Question,
  type WorkshopExam,
  workshopExamsApi,
} from "@/features/workshop-exams/api/workshop-exams-api";
import { parseAttendees, parseQuestions } from "@/features/workshop-exams/lib/parsers";
import { examStatusBadge } from "@/features/workshop-exams/lib/status";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function WorkshopExamDetailPage() {
  const { examId } = useParams<{ examId: string }>();
  const id = examId as string;
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: exam, isLoading } = useQuery({
    queryKey: ["workshop-exams", id],
    queryFn: () => workshopExamsApi.get(id),
    enabled: !!id,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });

  const setStatus = useMutation({
    mutationFn: (status: ExamStatus) => workshopExamsApi.setStatus(id, status),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => workshopExamsApi.remove(id),
    onSuccess: () => {
      refresh();
      navigate("/workshop-exams");
    },
  });

  if (isLoading || !exam) {
    return (
      <div className="p-6">
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const badge = examStatusBadge[exam.status];

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link to="/workshop-exams" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground">
          <ArrowLeft className="h-4 w-4" />
          All workshop exams
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold">{exam.title}</h1>
            <Badge variant={badge.variant}>{badge.label}</Badge>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {exam.status === "draft" && (
              <Button disabled={setStatus.isPending} onClick={() => setStatus.mutate("open")}>
                Open exam
              </Button>
            )}
            {exam.status === "open" && (
              <Button variant="outline" disabled={setStatus.isPending} onClick={() => setStatus.mutate("closed")}>
                Close exam
              </Button>
            )}
            {exam.status === "closed" && (
              <Button variant="outline" disabled={setStatus.isPending} onClick={() => setStatus.mutate("open")}>
                Re-open
              </Button>
            )}
            <Button
              variant="ghost"
              className="text-destructive"
              disabled={remove.isPending}
              onClick={() => {
                if (window.confirm("Delete this exam and all its attendees and results?")) remove.mutate();
              }}
            >
              Delete
            </Button>
          </div>
        </div>
        {setStatus.isError && (
          <p className="mt-2 text-sm text-destructive">
            {errorMessage(setStatus.error, "Could not change the exam status.")}
          </p>
        )}
      </div>

      <Tabs defaultValue="live">
        <TabsList>
          <TabsTrigger value="live">Live</TabsTrigger>
          <TabsTrigger value="attendees">Attendees</TabsTrigger>
          <TabsTrigger value="questions">Questions</TabsTrigger>
          <TabsTrigger value="setup">Setup &amp; certificates</TabsTrigger>
        </TabsList>
        <TabsContent value="live">
          <LiveTab exam={exam} />
        </TabsContent>
        <TabsContent value="attendees">
          <AttendeesTab exam={exam} />
        </TabsContent>
        <TabsContent value="questions">
          <QuestionsTab exam={exam} />
        </TabsContent>
        <TabsContent value="setup">
          <SetupTab exam={exam} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------- Live ----------------

function attendeeStatus(a: Attendee): { label: string; variant: "secondary" | "info" | "success" } {
  if (a.certificate_only) return { label: "Certificate only", variant: "secondary" };
  if (a.submitted_at) return { label: "Submitted", variant: "success" };
  if (a.started_at) return { label: "Writing", variant: "info" };
  return { label: "Not started", variant: "secondary" };
}

function LiveTab({ exam }: { exam: WorkshopExam }) {
  const queryClient = useQueryClient();
  const [hackathonCertificatesOpen, setHackathonCertificatesOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ["workshop-exams", exam.id, "dashboard"],
    queryFn: () => workshopExamsApi.dashboard(exam.id),
    // Live while people are writing; no need to hammer it otherwise.
    refetchInterval: exam.status === "open" ? 5000 : false,
  });
  const sendNow = useMutation({
    mutationFn: (includeInProgress: boolean) => workshopExamsApi.sendCertificatesNow(exam.id, includeInProgress),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workshop-exams"] }),
    onError: (error) => {
      // 409 = some students are still inside their time limit. Never cut them
      // off silently: let the admin decide.
      if ((error as { response?: { status?: number } })?.response?.status !== 409) return;
      const reason = errorMessage(error, "Some students are still writing.");
      if (window.confirm(`${reason}\n\nSend now anyway? Their exams will be submitted as they stand.`)) {
        sendNow.mutate(true);
      }
    },
  });

  const stats = [
    { label: "Attendees", value: data?.total_attendees },
    { label: "Not started", value: data?.not_started },
    { label: "Writing now", value: data?.in_progress },
    { label: "Submitted", value: data?.submitted },
    { label: "Avg score", value: data?.average_score_percent != null ? `${data.average_score_percent}%` : "-" },
    { label: "Certificates sent", value: data?.certificates_sent },
    { label: "Certificate only", value: data?.certificate_only },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-7">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p className="text-2xl font-semibold">{s.value ?? "-"}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => workshopExamsApi.downloadResults(exam.id)}>
          <Download className="h-4 w-4" />
          Download results (CSV)
        </Button>
        <Button
          variant="outline"
          disabled={sendNow.isPending || (data?.submitted ?? 0) + (data?.in_progress ?? 0) === 0}
          onClick={() => {
            if (
              window.confirm(
                "Send certificates now to everyone who has written the exam? This also closes the exam, so nobody can start it afterwards."
              )
            )
              sendNow.mutate(false);
          }}
        >
          <Send className="h-4 w-4" />
          Send certificates now
        </Button>
        <Button variant="outline" onClick={() => setHackathonCertificatesOpen(true)}>
          <Award className="h-4 w-4" />
          Certificates for a hackathon
        </Button>
        {sendNow.isSuccess && <span className="self-center text-sm text-muted-foreground">{sendNow.data.message}</span>}
        {sendNow.isError && (sendNow.error as { response?: { status?: number } })?.response?.status !== 409 && (
          <span className="self-center text-sm text-destructive">
            {errorMessage(sendNow.error, "Could not send certificates.")}
          </span>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                {exam.info_fields.map((f) => (
                  <TableHead key={f.key}>{f.label}</TableHead>
                ))}
                <TableHead>Status</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Certificate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.attendees.map((a) => {
                const s = attendeeStatus(a);
                return (
                  <TableRow key={a.id}>
                    <TableCell className="font-medium">{a.name}</TableCell>
                    <TableCell className="text-muted-foreground">{a.email}</TableCell>
                    {exam.info_fields.map((f) => (
                      <TableCell key={f.key} className="text-muted-foreground">
                        {a.info?.[f.key] ?? "-"}
                      </TableCell>
                    ))}
                    <TableCell>
                      <Badge variant={s.variant}>{s.label}</Badge>
                    </TableCell>
                    <TableCell>{a.score != null ? `${a.score} / ${a.total_marks}` : "-"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {a.certificate_sent_at ? "Sent" : a.certificate_number ? "Queued" : "-"}
                    </TableCell>
                  </TableRow>
                );
              })}
              {(data?.attendees.length ?? 0) === 0 && (
                <TableRow>
                  <TableCell colSpan={5 + exam.info_fields.length} className="py-8 text-center text-muted-foreground">
                    Nobody has registered yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      {hackathonCertificatesOpen && (
        <HackathonCertificatesDialog exam={exam} onClose={() => setHackathonCertificatesOpen(false)} />
      )}
    </div>
  );
}

// ---------------- Attendees ----------------

function AttendeesTab({ exam }: { exam: WorkshopExam }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const parsed = parseAttendees(text);

  const { data: attendees } = useQuery({
    queryKey: ["workshop-exams", exam.id, "attendees"],
    queryFn: () => workshopExamsApi.attendees(exam.id),
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });

  const importMutation = useMutation({
    mutationFn: () => workshopExamsApi.importAttendees(exam.id, parsed.rows),
    onSuccess: () => {
      setText("");
      invalidate();
    },
  });
  const invite = useMutation({
    mutationFn: (resendAll: boolean) => workshopExamsApi.sendInvites(exam.id, resendAll),
    onSuccess: invalidate,
  });

  // People given a certificate only (e.g. hackathon participants) are not part of the exam: no link, no count.
  const examAttendees = (attendees ?? []).filter((a) => !a.certificate_only);
  const notInvited = examAttendees.filter((a) => !a.invited_at && !a.submitted_at).length;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">Registration link</CardTitle>
          <CardDescription>
            Share this one link (WhatsApp, screen, QR). Students fill in the details you asked for, and get their
            own private exam link on screen and by email. Nobody needs a login.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CopyLink url={`${window.location.origin}/workshop-exam/join/${exam.public_code}`} />
          {exam.status !== "open" && (
            <p className="mt-2 text-sm text-muted-foreground">
              The link starts working once you open the exam.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Or add attendees yourself (optional)</CardTitle>
          <CardDescription>
            Paste one person per line - "Name, email", or two columns copied from a spreadsheet. Each person gets
            their own private exam link by email.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            rows={10}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"Asha Rao, asha@example.com\nRavi Kumar, ravi@example.com"}
          />
          <p className="text-sm text-muted-foreground">{parsed.rows.length} valid</p>
          {parsed.errors.length > 0 && (
            <ul className="max-h-24 overflow-auto text-sm text-destructive">
              {parsed.errors.slice(0, 10).map((e) => (
                <li key={e}>{e}</li>
              ))}
              {parsed.errors.length > 10 && <li>...and {parsed.errors.length - 10} more</li>}
            </ul>
          )}
          <Button disabled={parsed.rows.length === 0 || importMutation.isPending} onClick={() => importMutation.mutate()}>
            Add {parsed.rows.length || ""} attendee{parsed.rows.length === 1 ? "" : "s"}
          </Button>
          {importMutation.isSuccess && (
            <p className="text-sm text-muted-foreground">
              Added {importMutation.data.added}
              {importMutation.data.skipped_duplicates > 0 &&
                `, skipped ${importMutation.data.skipped_duplicates} duplicate email(s)`}
              .
            </p>
          )}
          {importMutation.isError && (
            <p className="text-sm text-destructive">{errorMessage(importMutation.error, "Import failed.")}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Exam links</CardTitle>
          <CardDescription>
            Emails the personal link to everyone who hasn't been sent one yet. Open the exam first so the link works.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button disabled={notInvited === 0 || invite.isPending} onClick={() => invite.mutate(false)}>
              <Send className="h-4 w-4" />
              Email links to {notInvited} not yet invited
            </Button>
            <Button
              variant="outline"
              disabled={examAttendees.length === 0 || invite.isPending}
              onClick={() => {
                if (window.confirm("Re-send the link to everyone who hasn't submitted yet?")) invite.mutate(true);
              }}
            >
              Re-send to all
            </Button>
          </div>
          {invite.isSuccess && <p className="text-sm text-muted-foreground">Queued {invite.data.queued} email(s).</p>}
          <p className="text-sm text-muted-foreground">
            {examAttendees.length} attendee(s) in total, {examAttendees.filter((a) => a.invited_at).length} invited.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------- Shared bits ----------------

function CopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-2">
      <Input readOnly value={url} onFocus={(e) => e.currentTarget.select()} aria-label="Registration link" />
      <Button
        variant="outline"
        onClick={() => {
          void navigator.clipboard?.writeText(url);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        {copied ? "Copied" : "Copy"}
      </Button>
    </div>
  );
}

// ---------------- Questions ----------------

function QuestionsTab({ exam }: { exam: WorkshopExam }) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showBulk, setShowBulk] = useState(false);
  const [bulkText, setBulkText] = useState("");
  const parsed = parseQuestions(bulkText);

  const { data: questions } = useQuery({
    queryKey: ["workshop-exams", exam.id, "questions"],
    queryFn: () => workshopExamsApi.questions(exam.id),
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });

  // The server is the real gate (questions lock once anyone has started);
  // its message is shown if an edit is refused.
  const add = useMutation({
    mutationFn: (rows: Parameters<typeof workshopExamsApi.addQuestions>[1]) =>
      workshopExamsApi.addQuestions(exam.id, rows),
    onSuccess: () => {
      setAdding(false);
      setBulkText("");
      setShowBulk(false);
      invalidate();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, q }: { id: string; q: Parameters<typeof workshopExamsApi.updateQuestion>[2] }) =>
      workshopExamsApi.updateQuestion(exam.id, id, q),
    onSuccess: () => {
      setEditingId(null);
      invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (questionId: string) => workshopExamsApi.deleteQuestion(exam.id, questionId),
    onSuccess: invalidate,
  });

  const locked = exam.status === "closed";

  return (
    <div className="max-w-3xl space-y-4">
      {locked && (
        <p className="text-sm text-muted-foreground">
          This exam is closed, so its questions can no longer be changed.
        </p>
      )}

      {questions?.map((q: Question, i) =>
        editingId === q.id ? (
          <QuestionEditor
            key={q.id}
            initial={q}
            saveLabel="Save question"
            busy={update.isPending}
            error={update.isError ? errorMessage(update.error, "Could not save.") : null}
            onSave={(draft) => update.mutate({ id: q.id, q: draft })}
            onCancel={() => setEditingId(null)}
          />
        ) : (
          <Card key={q.id}>
            <CardContent className="space-y-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex gap-1.5 font-medium">
                    <span className="shrink-0">{i + 1}.</span>
                    <RichText text={q.text} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {q.marks} mark{q.marks === 1 ? "" : "s"}
                    {q.allow_multiple && " · several correct"}
                  </p>
                </div>
                {!locked && (
                  <div className="flex shrink-0 gap-1">
                    <Button size="sm" variant="ghost" onClick={() => setEditingId(q.id)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(q.id)}
                    >
                      Remove
                    </Button>
                  </div>
                )}
              </div>
              <ul className="space-y-1 text-sm">
                {q.options.map((o, oi) => {
                  const correct = q.correct_indices.includes(oi);
                  return (
                    <li
                      key={oi}
                      className={`flex items-start gap-2 ${correct ? "font-medium text-emerald-700" : "text-muted-foreground"}`}
                    >
                      {correct ? <Check className="mt-0.5 h-4 w-4 shrink-0" /> : <X className="mt-0.5 h-4 w-4 shrink-0 opacity-30" />}
                      <RichText text={o} />
                    </li>
                  );
                })}
              </ul>
            </CardContent>
          </Card>
        )
      )}
      {(remove.isError || update.isError) && editingId === null && (
        <p className="text-sm text-destructive">
          {errorMessage(remove.error ?? update.error, "Could not change the question.")}
        </p>
      )}

      {adding ? (
        <QuestionEditor
          initial={BLANK_QUESTION}
          saveLabel="Add question"
          busy={add.isPending}
          error={add.isError && !showBulk ? errorMessage(add.error, "Could not add.") : null}
          onSave={(draft) => add.mutate([draft])}
          onCancel={() => setAdding(false)}
        />
      ) : (
        !locked && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" />
              Add question
            </Button>
            <Button variant="outline" onClick={() => setShowBulk((v) => !v)}>
              Paste many at once
            </Button>
          </div>
        )
      )}
      {(questions?.length ?? 0) === 0 && !adding && (
        <p className="text-sm text-muted-foreground">No questions yet.</p>
      )}

      {showBulk && !locked && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Paste many questions</CardTitle>
            <CardDescription>
              Paste your questions as they are. Number each one (Q1., 2.), write the options as A. B. C. D. (the
              question or an option can run over several lines, e.g. code), and say which is right with a line like{" "}
              <code>Answer: C</code> (<code>Answer: A, C</code> if several) or a * in front of the option. To colour
              code, select its lines and press <em>Code block</em> (or write ```dockerfile before and ``` after the
              code). The preview below shows exactly how each question was understood. The simple format also works: question on the
              first line, one option per line, * on the correct ones, blank line between questions.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <CodeTextarea
              rows={12}
              value={bulkText}
              onChange={setBulkText}
              className="font-mono text-xs"
              ariaLabel="Questions to add"
              placeholder={"Q1. What does this print?\nprint(1 + 1)\nA. 11\nB. 2\nAnswer: B\n\nQ2. Which are primes?\nA. 2\nB. 3\nC. 4\nAnswer: A, B"}
            />
            <p className="text-sm text-muted-foreground">{parsed.rows.length} question(s) ready</p>
            {parsed.rows.length > 0 && (
              <div className="max-h-80 space-y-3 overflow-auto rounded-md border bg-muted/30 p-3">
                {parsed.rows.map((q, qi) => (
                  <div key={qi} className="text-sm">
                    <div className="flex gap-1.5 font-medium">
                      <span className="shrink-0">{qi + 1}.</span>
                      <RichText text={q.text} />
                    </div>
                    <ul className="mt-1 space-y-1">
                      {q.options.map((o, oi) => {
                        const right = q.correct_indices.includes(oi);
                        return (
                          <li
                            key={oi}
                            className={`flex items-start gap-2 ${right ? "font-medium text-emerald-700" : "text-muted-foreground"}`}
                          >
                            <span className="w-4 shrink-0">{String.fromCharCode(65 + oi)}.</span>
                            <RichText text={o} />
                            {right && <Check className="mt-0.5 h-4 w-4 shrink-0" />}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            )}
            {parsed.errors.length > 0 && (
              <ul className="max-h-24 overflow-auto text-sm text-destructive">
                {parsed.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
            <Button disabled={parsed.rows.length === 0 || add.isPending} onClick={() => add.mutate(parsed.rows)}>
              Add {parsed.rows.length || ""} question{parsed.rows.length === 1 ? "" : "s"}
            </Button>
            {add.isError && showBulk && (
              <p className="text-sm text-destructive">{errorMessage(add.error, "Could not add.")}</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------- Student information fields ----------------

function slugKey(label: string, taken: Set<string>): string {
  const base =
    label
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/^[^a-z]+/, "")
      .slice(0, 30) || "field";
  let key = base;
  for (let n = 2; taken.has(key) || key === "name" || key === "email"; n++) key = `${base}_${n}`;
  return key;
}

function InfoFieldsEditor({ fields, onChange }: { fields: InfoField[]; onChange: (f: InfoField[]) => void }) {
  const patch = (index: number, change: Partial<InfoField>) =>
    onChange(fields.map((f, i) => (i === index ? { ...f, ...change } : f)));

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Students always give their name and email. Add whatever else you need to know about them.
      </p>
      {fields.map((f, i) => (
        <div key={f.key} className="space-y-2 rounded-md border p-3">
          <div className="flex items-center gap-2">
            <Input
              value={f.label}
              onChange={(e) => patch(i, { label: e.target.value })}
              placeholder="Question, e.g. College name"
              aria-label="Field label"
            />
            <select
              className="rounded-md border bg-background px-2 py-2 text-sm"
              value={f.type}
              aria-label="Field type"
              onChange={(e) => {
                const type = e.target.value as InfoField["type"];
                patch(i, { type, options: type === "select" ? (f.options.length >= 2 ? f.options : ["", ""]) : [] });
              }}
            >
              <option value="text">Short answer</option>
              <option value="phone">Phone number</option>
              <option value="select">Dropdown</option>
            </select>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              aria-label="Remove field"
              onClick={() => onChange(fields.filter((_, j) => j !== i))}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          {f.type === "select" && (
            <Textarea
              rows={3}
              value={f.options.join("\n")}
              onChange={(e) => patch(i, { options: e.target.value.split("\n") })}
              placeholder={"One choice per line\n1st year\n2nd year"}
              aria-label="Dropdown choices"
            />
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={f.required} onChange={(e) => patch(i, { required: e.target.checked })} />
            Required
          </label>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={fields.length >= 12}
        onClick={() =>
          onChange([
            ...fields,
            { key: slugKey("field", new Set(fields.map((f) => f.key))), label: "", required: true, type: "text", options: [] },
          ])
        }
      >
        <Plus className="h-4 w-4" />
        Add field
      </Button>
    </div>
  );
}

// ---------------- Setup & certificates ----------------

function SetupTab({ exam }: { exam: WorkshopExam }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(exam.title);
  const [description, setDescription] = useState(exam.description ?? "");
  const [duration, setDuration] = useState(String(exam.duration_minutes));
  const [showResult, setShowResult] = useState(exam.show_result);
  const [heading, setHeading] = useState(exam.certificate_heading);
  const [certText, setCertText] = useState(exam.certificate_text ?? "");
  const [release, setRelease] = useState(toLocalInput(exam.certificate_release_at));
  const [fields, setFields] = useState<InfoField[]>(exam.info_fields);

  useEffect(() => {
    setRelease(toLocalInput(exam.certificate_release_at));
  }, [exam.certificate_release_at]);

  const dispatched = !!exam.certificates_dispatched_at;

  // Keys are generated from the label the first time it's typed, then frozen
  // (they name the stored answers), so renaming a label never orphans data.
  const cleanedFields = (): InfoField[] => {
    const taken = new Set<string>();
    return fields.map((f) => {
      const key = /^field(_\d+)?$/.test(f.key) && f.label.trim() ? slugKey(f.label, taken) : f.key;
      taken.add(key);
      return {
        ...f,
        key,
        label: f.label.trim(),
        options: f.type === "select" ? f.options.map((o) => o.trim()).filter(Boolean) : [],
      };
    });
  };
  const fieldsProblem = fields.some((f) => !f.label.trim())
    ? "Give every extra field a label, or remove it."
    : fields.some((f) => f.type === "select" && f.options.map((o) => o.trim()).filter(Boolean).length < 2)
      ? "A dropdown needs at least two choices."
      : null;

  const save = useMutation({
    mutationFn: () =>
      workshopExamsApi.update(exam.id, {
        title: title.trim(),
        description: description.trim() || null,
        duration_minutes: Number(duration),
        show_result: showResult,
        certificate_heading: heading.trim(),
        certificate_text: certText.trim() || null,
        info_fields: cleanedFields(),
        ...(dispatched ? {} : { certificate_release_at: release ? new Date(release).toISOString() : null }),
      }),
    onSuccess: (saved) => {
      setFields(saved.info_fields);
      queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
    },
  });

  return (
    <Card className="max-w-2xl">
      <CardContent className="space-y-4 p-6">
        <div className="space-y-2">
          <Label htmlFor="s-title">Title</Label>
          <Input id="s-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="s-desc">Instructions shown to attendees</Label>
          <Textarea id="s-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="s-dur">Time limit (minutes, counted from when each person starts)</Label>
          <Input id="s-dur" type="number" min={1} max={480} value={duration} onChange={(e) => setDuration(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showResult} onChange={(e) => setShowResult(e.target.checked)} />
          Show each attendee their score after they submit
        </label>

        <div className="space-y-2 border-t pt-4">
          <h3 className="font-medium">Information to collect from students</h3>
          <InfoFieldsEditor fields={fields} onChange={setFields} />
          {fieldsProblem && <p className="text-sm text-destructive">{fieldsProblem}</p>}
        </div>

        <div className="space-y-2 border-t pt-4">
          <h3 className="font-medium">Certificate</h3>
          <CertificateDesigner exam={exam} />
          {!exam.has_certificate_template && (
            <div className="space-y-2 border-t pt-3">
              <p className="text-sm text-muted-foreground">
                No design uploaded - an automatic certificate with this wording is sent instead.
              </p>
              <Label htmlFor="s-head">Heading</Label>
              <Input id="s-head" value={heading} onChange={(e) => setHeading(e.target.value)} />
              <Label htmlFor="s-text">Wording under the name (optional)</Label>
              <Textarea
                id="s-text"
                rows={3}
                value={certText}
                onChange={(e) => setCertText(e.target.value)}
                placeholder={`has participated in the workshop "${exam.title}".`}
              />
            </div>
          )}
          <Label htmlFor="s-release">Send certificates at</Label>
          <Input
            id="s-release"
            type="datetime-local"
            disabled={dispatched}
            value={release}
            onChange={(e) => setRelease(e.target.value)}
          />
          <p className="text-sm text-muted-foreground">
            {dispatched
              ? "Certificates have already been sent."
              : "Everyone who wrote the exam is emailed their certificate within about 5 minutes of this time. Leave empty to send manually from the Live tab."}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button disabled={save.isPending || title.trim().length < 2 || !!fieldsProblem} onClick={() => save.mutate()}>
            {save.isPending ? "Saving..." : "Save"}
          </Button>
          {save.isSuccess && <span className="text-sm text-muted-foreground">Saved.</span>}
          {save.isError && <span className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
