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
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { type EvalActivity, type EvalKind, evalKeys, evaluationsApi, learningKeys, useLearningEnrollments } from "@/features/learning/api/learning-api";
import type { TabProps } from "@/features/learning/components/learning-workspace";
import { useStudentsList } from "@/features/students/api/students-hooks";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";
const COPY = {
  practicals: { title: "Practicals", one: "practical", detail: "Instructions / rubric", empty: "No practicals yet." },
  viva: { title: "Viva", one: "viva", detail: "Panel members", empty: "No viva evaluations yet." },
} as const;

function Results({ kind, courseId, activity, internshipId, canManage }: { kind: EvalKind; courseId: string; activity: EvalActivity; internshipId: string | null; canManage: boolean }) {
  const queryClient = useQueryClient();
  const results = useQuery({ queryKey: evalKeys.results(kind, activity.id, internshipId), queryFn: () => evaluationsApi.results(kind, courseId, activity.id, internshipId) });
  // who can be graded: an internship's granted students for its own activity, the course's students otherwise (the server checks eligibility too)
  const scoped = !!activity.internship_id;
  const roster = useLearningEnrollments(scoped ? activity.internship_id! : undefined);
  const everyone = useStudentsList({ limit: 200 });
  const options = scoped
    ? (roster.data?.rows ?? []).filter((r) => r.lms_status === "granted" && r.lms_student_id).map((r) => ({ id: r.lms_student_id!, name: r.name }))
    : (everyone.data?.items ?? []).map((s) => ({ id: s.id, name: s.full_name }));
  const [student, setStudent] = useState("");
  const [score, setScore] = useState("");
  const [remarks, setRemarks] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: learningKeys.all });
  const record = useMutation({
    mutationFn: () =>
      editing
        ? evaluationsApi.correct(kind, courseId, activity.id, editing, { score: Number(score), remarks: remarks || undefined })
        : evaluationsApi.record(kind, courseId, activity.id, { student_id: student, score: Number(score), remarks: remarks || undefined }),
    onSuccess: () => { setStudent(""); setScore(""); setRemarks(""); setEditing(null); void refresh(); },
  });
  return (
    <div className="space-y-3 border-t pt-3">
      {results.isLoading ? (
        <Skeleton className="h-8 w-full" />
      ) : (results.data?.length ?? 0) === 0 ? (
        <p className="text-xs text-muted-foreground">No results recorded yet.</p>
      ) : (
        <ul className="divide-y text-sm">
          {results.data!.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-2 py-1.5">
              <span>
                {r.student_name ?? "Student"}
                {r.access_status === "revoked" && <Badge className="ml-2" variant="warning">Access revoked</Badge>}
                {r.remarks && <span className="ml-2 text-xs text-muted-foreground">“{r.remarks}”</span>}
              </span>
              <span className="flex items-center gap-2">
                {r.score} / {activity.total_marks}
                <Badge variant={r.score >= activity.passing_marks ? "success" : "destructive"}>{r.score >= activity.passing_marks ? "Pass" : "Fail"}</Badge>
                {canManage && (
                  <Button size="sm" variant="ghost" onClick={() => { setEditing(r.student_id); setScore(String(r.score)); setRemarks(r.remarks ?? ""); }}>
                    Correct
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {canManage && (
        <div className="flex flex-wrap items-end gap-2">
          {!editing && (
            <div className="space-y-1">
              <Label htmlFor={`st-${activity.id}`}>Student</Label>
              <select id={`st-${activity.id}`} className={selectClass} value={student} onChange={(e) => setStudent(e.target.value)}>
                <option value="">Choose…</option>
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="space-y-1">
            <Label htmlFor={`sc-${activity.id}`}>Marks (of {activity.total_marks})</Label>
            <Input id={`sc-${activity.id}`} className="w-28" type="number" min={0} max={activity.total_marks} value={score} onChange={(e) => setScore(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`rm-${activity.id}`}>Feedback</Label>
            <Input id={`rm-${activity.id}`} className="w-64" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
          </div>
          <Button size="sm" disabled={record.isPending || score === "" || (!editing && !student)} onClick={() => record.mutate()}>
            {editing ? "Save correction" : "Record result"}
          </Button>
          {editing && (
            <Button size="sm" variant="ghost" onClick={() => { setEditing(null); setScore(""); setRemarks(""); }}>
              Cancel
            </Button>
          )}
        </div>
      )}
      {record.isError && <p className="text-sm text-destructive">{errorMessage(record.error, "Could not save the result.")}</p>}
    </div>
  );
}

function CreateDialog({ kind, courseId, internshipId, canCourse, canInternship, onClose }: { kind: EvalKind; courseId: string; internshipId: string | null; canCourse: boolean; canInternship: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const c = COPY[kind];
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [total, setTotal] = useState(kind === "viva" ? "50" : "100");
  const [pass, setPass] = useState(kind === "viva" ? "20" : "40");
  const [detail, setDetail] = useState("");
  const [scope, setScope] = useState<"internship" | "course">(canInternship ? "internship" : "course");
  const create = useMutation({
    mutationFn: () =>
      evaluationsApi.create(kind, courseId, {
        title: title.trim(), exam_date: date, total_marks: Number(total) || 100, passing_marks: Number(pass) || 0,
        ...(kind === "practicals" ? { rubric: detail || undefined } : { panel_members: detail || undefined }),
        internship_id: scope === "internship" ? internshipId : null,
      }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: learningKeys.all }); onClose(); },
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New {c.one}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="ev-title">Title</Label>
            <Input id="ev-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label htmlFor="ev-date">Date</Label>
              <Input id="ev-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ev-total">Total marks</Label>
              <Input id="ev-total" type="number" min={1} value={total} onChange={(e) => setTotal(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ev-pass">Passing marks</Label>
              <Input id="ev-pass" type="number" min={0} value={pass} onChange={(e) => setPass(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="ev-detail">{c.detail}</Label>
            <Textarea id="ev-detail" rows={3} value={detail} onChange={(e) => setDetail(e.target.value)} />
          </div>
          {internshipId && canInternship && canCourse && (
            <div className="space-y-1">
              <Label htmlFor="ev-scope">Who it is for</Label>
              <select id="ev-scope" className={selectClass + " w-full"} value={scope} onChange={(e) => setScope(e.target.value as "internship" | "course")}>
                <option value="internship">This internship only</option>
                <option value="course">Everyone in the course</option>
              </select>
            </div>
          )}
          {create.isError && <p className="text-sm text-destructive">{errorMessage(create.error, "Could not create it.")}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={create.isPending || title.trim().length < 2 || !date} onClick={() => create.mutate()}>
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Practicals and viva: the same engine and screen for both. Each is the course's own, or one internship's (explicitly scoped). */
export function ActivityTab({ kind, courseId, internship, needsChoice, ctx }: TabProps & { kind: EvalKind }) {
  const queryClient = useQueryClient();
  const c = COPY[kind];
  const internshipId = internship?.id ?? null;
  const canCourse = !!ctx.course_caps[`${kind}_manage`];
  const canCourseView = !!ctx.course_caps[`${kind}_view`];
  const canInternship = !!internship?.can_manage;
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const enabled = !!courseId && (!!internship || canCourseView);
  const list = useQuery({ queryKey: evalKeys.list(kind, courseId ?? "", internshipId), queryFn: () => evaluationsApi.list(kind, courseId!, internshipId), enabled });
  const remove = useMutation({
    mutationFn: (id: string) => evaluationsApi.remove(kind, courseId!, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: learningKeys.all }),
  });

  if (!courseId) return <p className="text-sm text-muted-foreground">{c.title} belong to the LMS course; link one to this internship to use them.</p>;
  if (!enabled) return <p className="text-sm text-muted-foreground">{needsChoice ? `Choose an internship above to see its ${c.title.toLowerCase()}.` : `You do not have access to ${c.title.toLowerCase()}.`}</p>;
  const canCreate = (canCourse || canInternship) && !needsChoice;

  return (
    <Card data-testid={`${kind}-tab`}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{c.title}</CardTitle>
        {canCreate && (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New {c.one}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {needsChoice && <p className="text-sm text-muted-foreground">Showing the course-wide {c.title.toLowerCase()}. Choose an internship above to add its own.</p>}
        {list.isLoading && <Skeleton className="h-16 w-full" />}
        {list.isError && <p className="text-sm text-destructive">Could not load them.</p>}
        {list.data && list.data.length === 0 && <p className="text-sm text-muted-foreground">{c.empty}</p>}
        {list.data?.map((a) => {
          const canManage = a.internship_id ? canInternship : canCourse;
          const isOpen = open === a.id;
          return (
            <div key={a.id} className="rounded-md border p-3" data-testid={`${kind}-${a.title}`}>
              <div className="flex items-center justify-between gap-2">
                <button type="button" className="flex flex-1 items-center gap-2 text-left" onClick={() => setOpen(isOpen ? null : a.id)}>
                  {isOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                  <span className="text-sm font-medium">{a.title}</span>
                  <Badge variant={a.internship_id ? "info" : "secondary"}>{a.internship_id ? "Internship only" : "Course-wide"}</Badge>
                </button>
                <span className="text-xs text-muted-foreground">
                  {a.exam_date} · {a.total_marks} marks · pass {a.passing_marks}
                </span>
                {canManage && (
                  <Button size="icon" variant="ghost" aria-label={`Delete ${a.title}`} onClick={() => window.confirm("Delete this? It must have no recorded results.") && remove.mutate(a.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
              {(a.rubric || a.panel_members) && isOpen && <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{a.rubric ?? a.panel_members}</p>}
              {isOpen && <Results kind={kind} courseId={courseId} activity={a} internshipId={internshipId} canManage={canManage} />}
            </div>
          );
        })}
        {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not delete it.")}</p>}
        {creating && <CreateDialog kind={kind} courseId={courseId} internshipId={internshipId} canCourse={canCourse} canInternship={canInternship} onClose={() => setCreating(false)} />}
      </CardContent>
    </Card>
  );
}
