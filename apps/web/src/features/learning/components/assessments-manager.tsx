import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type Assessment,
  type Question,
  assessmentKeys,
  assessmentsApi,
  learningKeys,
  useLearningEnrollments,
} from "@/features/learning/api/learning-api";
import { useStudentsList } from "@/features/students/api/students-hooks";
import type { TabProps } from "@/features/learning/components/learning-workspace";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";
const typeLabel = { quiz: "Quiz", mock_test: "Mock test", coding_test: "Coding test" } as const;

function QuestionDialog({ open, onClose, initial, onSave, pending, error }: { open: boolean; onClose: () => void; initial?: Question; onSave: (v: { text: string; options: string[]; correct_indices: number[]; allow_multiple: boolean; marks: number }) => void; pending: boolean; error: unknown }) {
  const [text, setText] = useState(initial?.text ?? "");
  const [options, setOptions] = useState<string[]>(initial?.options ?? ["", ""]);
  const [correct, setCorrect] = useState<number[]>(initial?.correct_indices ?? []);
  const [multiple, setMultiple] = useState(initial?.allow_multiple ?? false);
  const [marks, setMarks] = useState(String(initial?.marks ?? 1));
  const toggle = (i: number) => setCorrect((c) => (multiple ? (c.includes(i) ? c.filter((x) => x !== i) : [...c, i]) : [i]));
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initial ? "Edit question" : "Add a question"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="q-text">Question</Label>
            <Input id="q-text" value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Options (mark the correct {multiple ? "ones" : "one"})</Label>
            {options.map((o, i) => (
              <div key={i} className="flex items-center gap-2">
                <input type={multiple ? "checkbox" : "radio"} name="correct" aria-label={`Option ${i + 1} is correct`} checked={correct.includes(i)} onChange={() => toggle(i)} />
                <Input aria-label={`Option ${i + 1}`} value={o} onChange={(e) => setOptions((all) => all.map((x, j) => (j === i ? e.target.value : x)))} />
                {options.length > 2 && (
                  <Button type="button" variant="ghost" size="icon" aria-label={`Remove option ${i + 1}`} onClick={() => { setOptions((all) => all.filter((_, j) => j !== i)); setCorrect((c) => c.filter((x) => x !== i).map((x) => (x > i ? x - 1 : x))); }}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
            {options.length < 8 && (
              <Button type="button" variant="outline" size="sm" onClick={() => setOptions((o) => [...o, ""])}>
                Add an option
              </Button>
            )}
          </div>
          <div className="flex items-center gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={multiple} onChange={(e) => { setMultiple(e.target.checked); setCorrect((c) => (e.target.checked ? c : c.slice(0, 1))); }} />
              More than one correct answer
            </label>
            <label className="flex items-center gap-2">
              Marks
              <Input className="w-20" type="number" min={1} value={marks} onChange={(e) => setMarks(e.target.value)} />
            </label>
          </div>
          {error != null && <p className="text-sm text-destructive">{errorMessage(error, "Could not save the question.")}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={pending || !text.trim() || correct.length === 0} onClick={() => onSave({ text: text.trim(), options: options.map((o) => o.trim()), correct_indices: [...correct].sort(), allow_multiple: multiple, marks: Number(marks) || 1 })}>
            Save question
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AssessmentCard({ courseId, a, canManage, internshipId }: { courseId: string; a: Assessment; canManage: boolean; internshipId: string | null }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Question | "new" | null>(null);
  const questions = useQuery({ queryKey: assessmentKeys.questions(a.id), queryFn: () => assessmentsApi.questions(courseId, a.id), enabled: open && canManage });
  const attempts = useQuery({ queryKey: assessmentKeys.attempts(a.id, internshipId), queryFn: () => assessmentsApi.attempts(courseId, a.id, internshipId), enabled: open });
  const refresh = () => queryClient.invalidateQueries({ queryKey: learningKeys.all });
  const save = useMutation({
    mutationFn: (v: Parameters<typeof assessmentsApi.addQuestion>[2]) => (editing && editing !== "new" ? assessmentsApi.updateQuestion(courseId, a.id, editing.id, v) : assessmentsApi.addQuestion(courseId, a.id, v)),
    onSuccess: () => { setEditing(null); void refresh(); },
  });
  const remove = useMutation({ mutationFn: (id: string) => assessmentsApi.removeQuestion(courseId, a.id, id), onSuccess: refresh });
  const publish = useMutation({ mutationFn: (v: boolean) => assessmentsApi.update(courseId, a.id, { is_published: v }), onSuccess: refresh });
  const del = useMutation({ mutationFn: () => assessmentsApi.remove(courseId, a.id), onSuccess: refresh });
  const hasQuestions = (questions.data?.length ?? 0) > 0;
  const started = (attempts.data?.length ?? 0) > 0;
  // an assessment with no questions is a score sheet: authorized staff record each student's score by hand (never a student)
  const roster = useLearningEnrollments(a.internship_id ?? undefined);
  const everyone = useStudentsList({ limit: 200 });
  const candidates = a.internship_id
    ? (roster.data?.rows ?? []).filter((r) => r.lms_status === "granted" && r.lms_student_id).map((r) => ({ id: r.lms_student_id!, name: r.name }))
    : (everyone.data?.items ?? []).map((st) => ({ id: st.id, name: st.full_name }));
  const [scoreStudent, setScoreStudent] = useState("");
  const [scoreValue, setScoreValue] = useState("");
  const recordScore = useMutation({
    mutationFn: () => assessmentsApi.recordScore(courseId, a.id, scoreStudent, Number(scoreValue)),
    onSuccess: () => { setScoreStudent(""); setScoreValue(""); void refresh(); },
  });

  return (
    <div className="rounded-md border p-3" data-testid={`assessment-${a.title}`}>
      <div className="flex items-center justify-between gap-2">
        <button type="button" className="flex flex-1 items-center gap-2 text-left" onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
          <span className="text-sm font-medium">{a.title}</span>
          <Badge variant="secondary">{typeLabel[a.assessment_type]}</Badge>
          <Badge variant={a.internship_id ? "info" : "secondary"}>{a.internship_id ? "Internship only" : "Course-wide"}</Badge>
          <Badge variant={a.is_published ? "success" : "warning"}>{a.is_published ? "Published" : "Draft"}</Badge>
        </button>
        <span className="text-xs text-muted-foreground">
          {a.total_marks} marks · pass {a.passing_marks}
          {a.duration_minutes ? ` · ${a.duration_minutes} min` : ""}
        </span>
        {canManage && (
          <>
            <Button size="sm" variant="outline" disabled={publish.isPending} onClick={() => publish.mutate(!a.is_published)}>
              {a.is_published ? "Unpublish" : "Publish"}
            </Button>
            <Button size="icon" variant="ghost" aria-label={`Delete ${a.title}`} disabled={del.isPending} onClick={() => window.confirm("Delete this assessment?") && del.mutate()}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </>
        )}
      </div>
      {(publish.error || del.error) && <p className="mt-2 text-sm text-destructive">{errorMessage(publish.error ?? del.error, "That did not work.")}</p>}
      {open && (
        <div className="mt-3 space-y-4 border-t pt-3">
          {canManage && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Questions</p>
                <Button size="sm" variant="outline" disabled={started} onClick={() => setEditing("new")}>
                  <Plus className="h-3 w-3" /> Add question
                </Button>
              </div>
              {started && <p className="text-xs text-muted-foreground">Students have started this, so its questions can no longer be changed.</p>}
              {questions.isLoading && <Skeleton className="h-8 w-full" />}
              {!questions.isLoading && !hasQuestions && <p className="text-xs text-muted-foreground">No questions: scores for this assessment are recorded by hand.</p>}
              <ol className="space-y-1 text-sm">
                {questions.data?.map((q, i) => (
                  <li key={q.id} className="flex items-start justify-between gap-2 rounded bg-muted/40 p-2">
                    <div>
                      <div>
                        {i + 1}. {q.text} <span className="text-xs text-muted-foreground">({q.marks} {q.marks === 1 ? "mark" : "marks"})</span>
                      </div>
                      <ul className="ml-4 list-disc text-xs text-muted-foreground">
                        {q.options.map((o, j) => (
                          <li key={j} className={q.correct_indices.includes(j) ? "font-medium text-foreground" : ""}>
                            {o}
                            {q.correct_indices.includes(j) ? " ✓" : ""}
                          </li>
                        ))}
                      </ul>
                    </div>
                    {!started && (
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setEditing(q)}>
                          Edit
                        </Button>
                        <Button size="icon" variant="ghost" aria-label={`Remove question ${i + 1}`} onClick={() => remove.mutate(q.id)}>
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Attempts{internshipId ? " (this internship's students)" : ""}</p>
            {attempts.isLoading ? (
              <Skeleton className="h-8 w-full" />
            ) : (attempts.data?.length ?? 0) === 0 ? (
              <p className="text-xs text-muted-foreground">Nobody has attempted this yet.</p>
            ) : (
              <ul className="divide-y text-sm">
                {attempts.data!.map((t) => (
                  <li key={t.id} className="flex items-center justify-between py-1.5">
                    <span>
                      {t.student_name ?? "Student"}
                      {t.access_status === "revoked" && <Badge className="ml-2" variant="warning">Access revoked</Badge>}
                    </span>
                    <span className="text-muted-foreground">
                      {t.status === "in_progress" ? "In progress" : t.score != null ? `${t.score}${t.total_marks ? ` / ${t.total_marks}` : ""}` : "Submitted"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {canManage && questions.isSuccess && !hasQuestions && (
              <div className="flex flex-wrap items-end gap-2 pt-2" data-testid="record-score">
                <div className="space-y-1">
                  <Label htmlFor={`rs-${a.id}`}>Record a score for</Label>
                  <select id={`rs-${a.id}`} className={selectClass} value={scoreStudent} onChange={(e) => setScoreStudent(e.target.value)}>
                    <option value="">Choose a student…</option>
                    {candidates.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`rv-${a.id}`}>Score (of {a.total_marks})</Label>
                  <Input id={`rv-${a.id}`} className="w-24" type="number" min={0} max={a.total_marks} value={scoreValue} onChange={(e) => setScoreValue(e.target.value)} />
                </div>
                <Button size="sm" disabled={recordScore.isPending || !scoreStudent || scoreValue === ""} onClick={() => recordScore.mutate()}>
                  Record
                </Button>
              </div>
            )}
            {recordScore.isError && <p className="text-sm text-destructive">{errorMessage(recordScore.error, "Could not record the score.")}</p>}
          </div>
          {editing && <QuestionDialog open onClose={() => setEditing(null)} initial={editing === "new" ? undefined : editing} onSave={(v) => save.mutate(v)} pending={save.isPending} error={save.error} />}
        </div>
      )}
    </div>
  );
}

function CreateDialog({ courseId, internshipId, canCourse, canInternship, onClose }: { courseId: string; internshipId: string | null; canCourse: boolean; canInternship: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [type, setType] = useState<Assessment["assessment_type"]>("quiz");
  const [total, setTotal] = useState("100");
  const [pass, setPass] = useState("40");
  const [minutes, setMinutes] = useState("");
  const [scope, setScope] = useState<"internship" | "course">(canInternship ? "internship" : "course");
  const create = useMutation({
    mutationFn: () => assessmentsApi.create(courseId, { title: title.trim(), assessment_type: type, total_marks: Number(total) || 100, passing_marks: Number(pass) || 0, duration_minutes: minutes ? Number(minutes) : null, internship_id: scope === "internship" ? internshipId : null }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: learningKeys.all }); onClose(); },
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New assessment</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="a-title">Title</Label>
            <Input id="a-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="a-type">Type</Label>
              <select id="a-type" className={selectClass + " w-full"} value={type} onChange={(e) => setType(e.target.value as Assessment["assessment_type"])}>
                <option value="quiz">Quiz</option>
                <option value="mock_test">Mock test</option>
                <option value="coding_test">Coding test</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="a-min">Time limit (minutes, optional)</Label>
              <Input id="a-min" type="number" min={1} value={minutes} onChange={(e) => setMinutes(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="a-total">Total marks</Label>
              <Input id="a-total" type="number" min={1} value={total} onChange={(e) => setTotal(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="a-pass">Passing marks</Label>
              <Input id="a-pass" type="number" min={0} value={pass} onChange={(e) => setPass(e.target.value)} />
            </div>
          </div>
          {internshipId && canInternship && canCourse && (
            <div className="space-y-1">
              <Label htmlFor="a-scope">Who it is for</Label>
              <select id="a-scope" className={selectClass + " w-full"} value={scope} onChange={(e) => setScope(e.target.value as "internship" | "course")}>
                <option value="internship">This internship only</option>
                <option value="course">Everyone in the course</option>
              </select>
            </div>
          )}
          {create.isError && <p className="text-sm text-destructive">{errorMessage(create.error, "Could not create the assessment.")}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={create.isPending || title.trim().length < 2} onClick={() => create.mutate()}>
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Assessments, quizzes and mock tests. An assessment with questions is a real timed test, scored on the server (a student never supplies a
 * score); one with none keeps working as a score sheet that staff fill in. One that belongs to an internship is reached only through it.
 */
export function AssessmentsManager({ courseId, internship, needsChoice, ctx }: TabProps & { courseId: string }) {
  const internshipId = internship?.id ?? null;
  const [creating, setCreating] = useState(false);
  const list = useQuery({ queryKey: assessmentKeys.list(courseId, internshipId), queryFn: () => assessmentsApi.list(courseId, internshipId), enabled: !needsChoice || !!ctx.course_caps.assessments_view });
  const canCourse = !!ctx.course_caps.assessments_manage;
  const canInternship = !!internship?.can_manage;
  const canCreate = canCourse || canInternship;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Assessments and quizzes</CardTitle>
        {canCreate && !needsChoice && (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New assessment
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {needsChoice && !ctx.course_caps.assessments_view && <p className="text-sm text-muted-foreground">Choose an internship above to see its own assessments.</p>}
        {list.isLoading && <Skeleton className="h-16 w-full" />}
        {list.isError && <p className="text-sm text-destructive">Could not load the assessments.</p>}
        {list.data && list.data.length === 0 && <p className="text-sm text-muted-foreground">No assessments yet.</p>}
        {list.data?.map((a) => (
          <AssessmentCard key={a.id} courseId={courseId} a={a} internshipId={internshipId} canManage={a.internship_id ? canInternship : canCourse} />
        ))}
        {creating && <CreateDialog courseId={courseId} internshipId={internshipId} canCourse={canCourse} canInternship={canInternship} onClose={() => setCreating(false)} />}
      </CardContent>
    </Card>
  );
}
