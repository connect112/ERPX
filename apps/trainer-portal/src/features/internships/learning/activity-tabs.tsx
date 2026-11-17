import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { errorText, key, learningApi, useAct, useQ } from "@/features/internships/learning/api";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";

/** Practicals and viva share one shape: an activity with a date, a rubric and marks, and one mark per student. */
export function ActivityTab({ kind, internshipId, courseId, canManage }: { kind: "practicals" | "viva"; internshipId: string; courseId: string | null; canManage: boolean }) {
  const noun = kind === "practicals" ? "practical" : "viva";
  const list = useQ(key(kind, internshipId), () => learningApi.evals(kind, courseId!, internshipId), !!courseId);
  const roster = useQ(key("enrollments", internshipId), () => learningApi.enrollments(internshipId));
  const [open, setOpen] = useState<string | null>(null);
  const results = useQ(key(kind, "results", open ?? ""), () => learningApi.evalResults(kind, courseId!, open!, internshipId), !!open && !!courseId);
  const [form, setForm] = useState({ title: "", date: "", rubric: "" });
  const [student, setStudent] = useState("");
  const [score, setScore] = useState("");
  const [remarks, setRemarks] = useState("");
  const [editing, setEditing] = useState<string | null>(null);

  const create = useAct(
    () => learningApi.createEval(kind, courseId!, { title: form.title.trim(), exam_date: form.date, rubric: form.rubric.trim() || null, internship_id: internshipId }),
    () => setForm({ title: "", date: "", rubric: "" }),
  );
  const save = useAct(
    () =>
      editing
        ? learningApi.correctEval(kind, courseId!, open!, editing, { score: Number(score), remarks: remarks || undefined })
        : learningApi.recordEval(kind, courseId!, open!, { student_id: student, score: Number(score), remarks: remarks || undefined }),
    () => {
      setStudent("");
      setScore("");
      setRemarks("");
      setEditing(null);
    },
  );

  if (!courseId) return <p className="text-sm text-muted-foreground">A {noun} belongs to the LMS course; none is linked to this internship yet.</p>;
  const eligible = (roster.data ?? []).filter((r) => r.lms_status === "granted" && r.lms_student_id);
  const current = list.data?.find((a) => a.id === open);

  return (
    <Card data-testid={`trainer-${kind}`}>
      <CardHeader>
        <CardTitle className="text-base capitalize">{noun}s</CardTitle>
        <p className="text-xs text-muted-foreground">Marks can be recorded for students who currently hold LMS access. A mistake is corrected by editing the mark; nothing is deleted.</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {canManage && (
          <div className="grid gap-2 sm:grid-cols-3">
            <Input aria-label={`New ${noun} title`} placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <Input aria-label="Date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            <Button disabled={create.isPending || form.title.trim().length < 2 || !form.date} onClick={() => create.mutate(undefined)}>
              Add {noun}
            </Button>
            <Textarea aria-label="Rubric" className="sm:col-span-3" rows={2} placeholder="Rubric (optional)" value={form.rubric} onChange={(e) => setForm({ ...form, rubric: e.target.value })} />
          </div>
        )}
        {create.isError && <p className="text-sm text-destructive">{errorText(create.error, "Could not add it.")}</p>}
        {list.isLoading && <Skeleton className="h-16 w-full" />}
        {list.data?.length === 0 && <p className="text-sm text-muted-foreground">No {noun}s yet.</p>}
        {list.data?.map((a) => (
          <div key={a.id} className="rounded-md border p-3" data-testid={`${kind}-${a.title}`}>
            <button type="button" className="flex w-full items-center justify-between text-left text-sm" onClick={() => setOpen(open === a.id ? null : a.id)}>
              <span className="font-medium">
                {a.title} <Badge variant={a.internship_id ? "info" : "secondary"}>{a.internship_id ? "This internship" : "Course-wide"}</Badge>
              </span>
              <span className="text-muted-foreground">{a.exam_date} · out of {a.total_marks}</span>
            </button>
            {open === a.id && (
              <div className="mt-3 space-y-3 border-t pt-3 text-sm">
                {a.rubric && <p className="whitespace-pre-wrap text-xs text-muted-foreground">{a.rubric}</p>}
                <ul className="divide-y">
                  {results.data?.map((r) => (
                    <li key={r.id} className="flex items-center justify-between gap-2 py-1.5">
                      <span>
                        {r.student_name ?? "Student"}
                        {r.access_status === "revoked" && <Badge className="ml-2" variant="warning">Access revoked</Badge>}
                      </span>
                      <span className="flex items-center gap-2 text-muted-foreground">
                        {r.score} / {a.total_marks}
                        {r.remarks ? ` · ${r.remarks}` : ""}
                        {canManage && a.internship_id && (
                          <Button size="sm" variant="ghost" onClick={() => { setEditing(r.student_id); setScore(String(r.score)); setRemarks(r.remarks ?? ""); }}>
                            Edit
                          </Button>
                        )}
                      </span>
                    </li>
                  ))}
                  {results.data?.length === 0 && <li className="py-1 text-xs text-muted-foreground">No marks recorded yet.</li>}
                </ul>
                {canManage && a.internship_id && (
                  <div className="flex flex-wrap items-center gap-2">
                    {!editing && (
                      <select aria-label="Student" className={selectClass} value={student} onChange={(e) => setStudent(e.target.value)}>
                        <option value="">Choose a student</option>
                        {eligible.map((r) => <option key={r.lms_student_id!} value={r.lms_student_id!}>{r.name}</option>)}
                      </select>
                    )}
                    <Input aria-label="Marks" className="w-24" type="number" min={0} max={current?.total_marks} placeholder={`/ ${current?.total_marks ?? ""}`} value={score} onChange={(e) => setScore(e.target.value)} />
                    <Input aria-label="Remarks" className="w-56" placeholder="Remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
                    <Button size="sm" disabled={save.isPending || score === "" || (!editing && !student)} onClick={() => save.mutate(undefined)}>
                      {editing ? "Save correction" : "Record marks"}
                    </Button>
                    {editing && <Button size="sm" variant="ghost" onClick={() => { setEditing(null); setScore(""); setRemarks(""); }}>Cancel</Button>}
                  </div>
                )}
                {save.isError && <p className="text-destructive">{errorText(save.error, "Could not save the marks.")}</p>}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function ThreadRow({ courseId, id, title, body, author, internshipId, locked }: { courseId: string; id: string; title: string; body: string; author: string | null; internshipId: string | null; locked: boolean }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const replies = useQ(key("replies", id), () => learningApi.replies(courseId, id), open);
  const reply = useAct(() => learningApi.reply(courseId, id, text.trim()), () => setText(""));
  return (
    <div className="rounded-md border p-3" data-testid={`thread-${title}`}>
      <button type="button" className="w-full text-left text-sm" onClick={() => setOpen((o) => !o)}>
        <span className="font-medium">{title}</span>
        <Badge className="ml-2" variant={internshipId ? "info" : "secondary"}>{internshipId ? "This internship only" : "Course-wide"}</Badge>
        {locked && <Badge className="ml-1" variant="warning">Locked</Badge>}
        <span className="block text-xs text-muted-foreground">{author ?? "Someone"}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-2 border-t pt-3 text-sm">
          <p className="whitespace-pre-wrap">{body}</p>
          {replies.data?.map((r) => (
            <div key={r.id} className="rounded bg-muted/40 p-2">
              <div className="text-xs text-muted-foreground">{r.author_name ?? "Someone"}</div>
              <p className="whitespace-pre-wrap">{r.body}</p>
            </div>
          ))}
          {!locked && (
            <div className="space-y-2">
              <Textarea aria-label="Your reply" rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Reply as instructor" />
              <Button size="sm" disabled={reply.isPending || !text.trim()} onClick={() => reply.mutate(undefined)}>Reply</Button>
              {reply.isError && <p className="text-destructive">{errorText(reply.error, "Could not post your reply.")}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** The internship's own private threads and the course-wide ones, with instructor participation. */
export function DiscussionsTab({ internshipId, courseId }: { internshipId: string; courseId: string | null }) {
  const threads = useQ(key("threads", internshipId), () => learningApi.threads(courseId!, internshipId), !!courseId);
  const [t, setT] = useState({ title: "", body: "" });
  const create = useAct(() => learningApi.createThread(courseId!, { title: t.title.trim(), body: t.body.trim(), internship_id: internshipId }), () => setT({ title: "", body: "" }));
  if (!courseId) return <p className="text-sm text-muted-foreground">Discussions belong to the LMS course; none is linked to this internship yet.</p>;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Discussions</CardTitle>
        <p className="text-xs text-muted-foreground">Threads started here are private to this internship's students and instructors.</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          <Input aria-label="Thread title" placeholder="Title" value={t.title} onChange={(e) => setT({ ...t, title: e.target.value })} />
          <Textarea aria-label="Thread message" rows={2} placeholder="Message to the cohort" value={t.body} onChange={(e) => setT({ ...t, body: e.target.value })} />
          <Button disabled={create.isPending || t.title.trim().length < 2 || !t.body.trim()} onClick={() => create.mutate(undefined)}>Start discussion</Button>
          {create.isError && <p className="text-sm text-destructive">{errorText(create.error, "Could not post.")}</p>}
        </div>
        {threads.isLoading && <Skeleton className="h-16 w-full" />}
        {threads.data?.length === 0 && <p className="text-sm text-muted-foreground">No discussions yet.</p>}
        {threads.data?.map((x) => (
          <ThreadRow key={x.id} courseId={courseId} id={x.id} title={x.title} body={x.body} author={x.author_name} internshipId={x.internship_id} locked={x.is_locked} />
        ))}
      </CardContent>
    </Card>
  );
}
