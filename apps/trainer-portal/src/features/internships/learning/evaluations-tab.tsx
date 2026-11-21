import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type ResultRow, errorText, key, learningApi, useAct, useQ } from "@/features/internships/learning/api";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";

function Exams({ internshipId }: { internshipId: string }) {
  const exams = useQ(key("exams", internshipId), () => learningApi.exams(internshipId));
  const [open, setOpen] = useState<string | null>(null);
  const results = useQ(key("exam-results", open ?? ""), () => learningApi.examResults(internshipId, open!), !!open);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Internship exams</CardTitle>
        <p className="text-xs text-muted-foreground">Students take these through their personal link; the link stops working if their LMS access is withdrawn.</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {exams.isLoading && <Skeleton className="h-16 w-full" />}
        {exams.data?.length === 0 && <p className="text-sm text-muted-foreground">No exams on this internship yet.</p>}
        {exams.data?.map((e) => (
          <div key={e.id} className="rounded-md border p-3" data-testid={`exam-${e.title}`}>
            <button type="button" className="flex w-full items-center justify-between text-left text-sm" onClick={() => setOpen(open === e.id ? null : e.id)}>
              <span className="font-medium">{e.title} <Badge variant="secondary">{e.status}</Badge></span>
              <span className="text-muted-foreground">{e.submitted_count}/{e.attendee_count} submitted{e.average_percent != null ? ` · avg ${e.average_percent}%` : ""}</span>
            </button>
            {open === e.id && (
              <ul className="mt-2 divide-y text-sm">
                {results.data?.map((r) => (
                  <li key={r.selection_id} className="flex justify-between py-1">
                    <span>{r.student_name}{r.access_status === "revoked" && <Badge className="ml-2" variant="warning">Access revoked</Badge>}</span>
                    <span className="text-muted-foreground">{r.state === "submitted" && r.score != null ? `${r.score} / ${r.total_marks} (${r.percent}%)` : r.state.replace("_", " ")}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Assignments({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const list = useQ(key("assignments", internshipId), () => learningApi.assignments(internshipId));
  const [open, setOpen] = useState<string | null>(null);
  const subs = useQ(key("submissions", open ?? ""), () => learningApi.submissions(internshipId, open!), !!open);
  const [drafts, setDrafts] = useState<Record<string, { score: string; feedback: string }>>({});
  const grade = useAct((v: { sel: string; score: number; feedback?: string }) => learningApi.grade(internshipId, open!, v.sel, { score: v.score, feedback: v.feedback }));
  const current = list.data?.find((a) => a.id === open);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Internship assignments</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {list.isLoading && <Skeleton className="h-16 w-full" />}
        {list.data?.length === 0 && <p className="text-sm text-muted-foreground">No assignments on this internship yet.</p>}
        {list.data?.map((a) => (
          <div key={a.id} className="rounded-md border p-3" data-testid={`assignment-${a.title}`}>
            <button type="button" className="flex w-full items-center justify-between text-left text-sm" onClick={() => setOpen(open === a.id ? null : a.id)}>
              <span className="font-medium">{a.title} <Badge variant="secondary">{a.status}</Badge></span>
              <span className="text-muted-foreground">{a.submitted_count} submitted · {a.graded_count} graded of {a.enrolled_count}</span>
            </button>
            {open === a.id && (
              <div className="mt-3 space-y-2">
                {subs.data?.map((s) => {
                  const d = drafts[s.selection_id] ?? { score: s.score != null ? String(s.score) : "", feedback: s.feedback ?? "" };
                  return (
                    <div key={s.selection_id} className="rounded bg-muted/40 p-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{s.student_name}{s.access_status === "revoked" && <Badge className="ml-2" variant="warning">Access revoked</Badge>}</span>
                        <span className="text-xs text-muted-foreground">{s.submitted ? `Submitted ${s.submitted_at ? new Date(s.submitted_at).toLocaleString("en-GB") : ""}${s.is_late ? " (late)" : ""}` : "Not submitted"}</span>
                      </div>
                      {s.note && <p className="mt-1 whitespace-pre-wrap text-xs">{s.note}</p>}
                      {s.files.length > 0 && <p className="mt-1 text-xs text-muted-foreground">Files: {s.files.map((f) => f.filename).join(", ")}</p>}
                      {s.submitted && canManage && (
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <Input aria-label={`Marks for ${s.student_name}`} className="w-24" type="number" min={0} max={current?.max_marks} placeholder={`/ ${current?.max_marks ?? ""}`} value={d.score} onChange={(e) => setDrafts((x) => ({ ...x, [s.selection_id]: { ...d, score: e.target.value } }))} />
                          <Input aria-label={`Feedback for ${s.student_name}`} className="w-64" placeholder="Feedback" value={d.feedback} onChange={(e) => setDrafts((x) => ({ ...x, [s.selection_id]: { ...d, feedback: e.target.value } }))} />
                          <Button size="sm" disabled={grade.isPending || d.score === ""} onClick={() => grade.mutate({ sel: s.selection_id, score: Number(d.score), feedback: d.feedback || undefined })}>
                            {s.reviewed_at ? "Update grade" : "Grade"}
                          </Button>
                        </div>
                      )}
                    </div>
                  );
                })}
                {grade.isError && <p className="text-sm text-destructive">{errorText(grade.error, "Could not save the grade.")}</p>}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Assessments({ internshipId, courseId, canManage }: { internshipId: string; courseId: string | null; canManage: boolean }) {
  const list = useQ(key("assessments", internshipId), () => learningApi.assessments(courseId!, internshipId), !!courseId);
  const [open, setOpen] = useState<string | null>(null);
  const questions = useQ(key("aq", open ?? ""), () => learningApi.questions(courseId!, open!), !!open && canManage);
  const attempts = useQ(key("aa", open ?? ""), () => learningApi.attempts(courseId!, open!, internshipId), !!open);
  const [title, setTitle] = useState("");
  const [q, setQ] = useState({ text: "", options: "", correct: "1" });
  const create = useAct(() => learningApi.createAssessment(courseId!, { title: title.trim(), assessment_type: "quiz", total_marks: 100, passing_marks: 40, internship_id: internshipId }), () => setTitle(""));
  const publish = useAct((v: { id: string; on: boolean }) => learningApi.setPublished(courseId!, v.id, v.on));
  const addQ = useAct(() => {
    const options = q.options.split("\n").map((o) => o.trim()).filter(Boolean);
    return learningApi.addQuestion(courseId!, open!, { text: q.text.trim(), options, correct_indices: [Number(q.correct) - 1], allow_multiple: false, marks: 1 });
  }, () => setQ({ text: "", options: "", correct: "1" }));
  if (!courseId) return <p className="text-sm text-muted-foreground">Assessments belong to the LMS course; none is linked to this internship yet.</p>;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assessments and quizzes</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {canManage && (
          <div className="flex gap-2">
            <Input aria-label="New assessment title" placeholder="New quiz for this internship" value={title} onChange={(e) => setTitle(e.target.value)} />
            <Button disabled={create.isPending || title.trim().length < 2} onClick={() => create.mutate(undefined)}>Create quiz</Button>
          </div>
        )}
        {create.isError && <p className="text-sm text-destructive">{errorText(create.error, "Could not create it.")}</p>}
        {list.data?.length === 0 && <p className="text-sm text-muted-foreground">No assessments yet.</p>}
        {list.data?.map((a) => (
          <div key={a.id} className="rounded-md border p-3" data-testid={`assessment-${a.title}`}>
            <div className="flex items-center justify-between gap-2 text-sm">
              <button type="button" className="text-left font-medium" onClick={() => setOpen(open === a.id ? null : a.id)}>
                {a.title} <Badge variant={a.internship_id ? "info" : "secondary"}>{a.internship_id ? "Internship only" : "Course-wide"}</Badge> <Badge variant={a.is_published ? "success" : "warning"}>{a.is_published ? "Published" : "Draft"}</Badge>
              </button>
              {canManage && a.internship_id && (
                <Button size="sm" variant="outline" onClick={() => publish.mutate({ id: a.id, on: !a.is_published })}>{a.is_published ? "Unpublish" : "Publish"}</Button>
              )}
            </div>
            {open === a.id && (
              <div className="mt-3 space-y-3 border-t pt-3 text-sm">
                {canManage && a.internship_id && (
                  <>
                    <ol className="list-decimal pl-5">
                      {questions.data?.map((x) => <li key={x.id}>{x.text} <span className="text-xs text-muted-foreground">({x.options.length} options)</span></li>)}
                    </ol>
                    <div className="space-y-2">
                      <Input aria-label="Question" placeholder="Question" value={q.text} onChange={(e) => setQ({ ...q, text: e.target.value })} />
                      <textarea aria-label="Options, one per line" className="w-full rounded-md border bg-background p-2 text-sm" rows={3} placeholder={"Options, one per line"} value={q.options} onChange={(e) => setQ({ ...q, options: e.target.value })} />
                      <label className="flex items-center gap-2">Correct option number <Input className="w-16" type="number" min={1} value={q.correct} onChange={(e) => setQ({ ...q, correct: e.target.value })} /></label>
                      <Button size="sm" disabled={addQ.isPending || !q.text.trim() || q.options.split("\n").filter((o) => o.trim()).length < 2} onClick={() => addQ.mutate(undefined)}>Add question</Button>
                      {addQ.isError && <p className="text-destructive">{errorText(addQ.error, "Could not add the question.")}</p>}
                    </div>
                  </>
                )}
                <ul className="divide-y">
                  {attempts.data?.map((t) => (
                    <li key={t.id} className="flex justify-between py-1">
                      <span>{t.student_name}{t.access_status === "revoked" && <Badge className="ml-2" variant="warning">Access revoked</Badge>}</span>
                      <span className="text-muted-foreground">{t.status === "in_progress" ? "In progress" : t.score != null ? `${t.score}${t.total_marks ? ` / ${t.total_marks}` : ""}` : "Submitted"}</span>
                    </li>
                  ))}
                  {attempts.data?.length === 0 && <li className="py-1 text-xs text-muted-foreground">Nobody has attempted this yet.</li>}
                </ul>
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Results({ internshipId }: { internshipId: string }) {
  const [kind, setKind] = useState("");
  const rows = useQ(key("results", internshipId, kind), () => learningApi.results(internshipId, kind));
  return (
    <Card data-testid="trainer-results">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Results</CardTitle>
        <select aria-label="Kind of activity" className={selectClass} value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">All kinds</option>
          {["exam", "assignment", "assessment", "project", "practical", "viva"].map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
      </CardHeader>
      <CardContent>
        <p className="mb-2 text-xs text-muted-foreground">Each activity is shown in its own marks; there is no combined score.</p>
        {rows.isLoading ? <Skeleton className="h-24 w-full" /> : (
          <ul className="divide-y text-sm">
            {rows.data?.map((r: ResultRow) => (
              <li key={`${r.kind}-${r.activity_id}-${r.student_key}`} className="flex justify-between gap-2 py-1.5">
                <span>{r.student_name}{r.access_status === "revoked" && <Badge className="ml-2" variant="warning">Access revoked</Badge>}<span className="ml-2 text-muted-foreground">{r.activity_title} ({r.kind})</span></span>
                <span className="text-muted-foreground">{r.score != null ? `${r.score} / ${r.total_marks}` : r.state.replace("_", " ")}</span>
              </li>
            ))}
            {rows.data?.length === 0 && <li className="py-2 text-muted-foreground">No results yet.</li>}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function EvaluationsTab({ internshipId, courseId, canManage }: { internshipId: string; courseId: string | null; canManage: boolean }) {
  return (
    <Tabs defaultValue="exams">
      <TabsList>
        <TabsTrigger value="exams">Exams</TabsTrigger>
        <TabsTrigger value="assignments">Assignments</TabsTrigger>
        <TabsTrigger value="assessments">Assessments / Quizzes</TabsTrigger>
        <TabsTrigger value="results">Results</TabsTrigger>
      </TabsList>
      <TabsContent value="exams"><Exams internshipId={internshipId} /></TabsContent>
      <TabsContent value="assignments"><Assignments internshipId={internshipId} canManage={canManage} /></TabsContent>
      <TabsContent value="assessments"><Assessments internshipId={internshipId} courseId={courseId} canManage={canManage} /></TabsContent>
      <TabsContent value="results"><Results internshipId={internshipId} /></TabsContent>
    </Tabs>
  );
}

export function ProjectsTab({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const projects = useQ(key("projects", internshipId), () => learningApi.projects(internshipId));
  const rows = useQ(key("project-rows", internshipId), () => learningApi.projectRows(internshipId));
  const [drafts, setDrafts] = useState<Record<string, { marks: string; feedback: string }>>({});
  const final = useAct((v: { pid: string; sel: string; marks: number; feedback?: string }) => learningApi.finalMarks(internshipId, v.pid, v.sel, { final_marks: v.marks, feedback: v.feedback }));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Projects</CardTitle>
        <p className="text-xs text-muted-foreground">{projects.data?.length ?? 0} project(s) on this internship. Final marks are published to the student.</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.isLoading && <Skeleton className="h-16 w-full" />}
        {rows.data?.filter((r) => r.project_id).map((r) => {
          const max = projects.data?.find((p) => p.id === r.project_id)?.max_marks;
          const d = drafts[r.selection_id] ?? { marks: "", feedback: "" };
          return (
            <div key={r.selection_id} className="rounded-md border p-3 text-sm" data-testid={`project-row-${r.student_name}`}>
              <div className="flex items-center justify-between">
                <span className="font-medium">{r.student_name}{r.access_status === "revoked" && <Badge className="ml-2" variant="warning">Access revoked</Badge>}</span>
                <span className="text-muted-foreground">{r.project_title} · {r.submitted ? `submitted by ${r.method}` : "not submitted"}</span>
              </div>
              {r.repository_url && <a className="text-xs text-primary hover:underline" href={r.repository_url} target="_blank" rel="noreferrer">{r.repository_url}</a>}
              {r.submitted && canManage && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Input aria-label={`Final marks for ${r.student_name}`} className="w-24" type="number" min={0} max={max} placeholder={`/ ${max ?? ""}`} value={d.marks} onChange={(e) => setDrafts((x) => ({ ...x, [r.selection_id]: { ...d, marks: e.target.value } }))} />
                  <Input aria-label={`Feedback for ${r.student_name}`} className="w-64" placeholder="Feedback" value={d.feedback} onChange={(e) => setDrafts((x) => ({ ...x, [r.selection_id]: { ...d, feedback: e.target.value } }))} />
                  <Button size="sm" disabled={final.isPending || d.marks === ""} onClick={() => final.mutate({ pid: r.project_id!, sel: r.selection_id, marks: Number(d.marks), feedback: d.feedback || undefined })}>Publish final marks</Button>
                </div>
              )}
            </div>
          );
        })}
        {rows.data && rows.data.filter((r) => r.project_id).length === 0 && <p className="text-sm text-muted-foreground">No student has chosen a project yet.</p>}
        {final.isError && <p className="text-sm text-destructive">{errorText(final.error, "Could not publish the marks.")}</p>}
      </CardContent>
    </Card>
  );
}
