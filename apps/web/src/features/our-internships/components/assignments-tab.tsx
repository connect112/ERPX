import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Pencil, Plus, Trash2, Users } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage, formatBytes } from "@/features/institutions/lib/format";
import { type Assignment, type SubmissionRow, assignmentsApi, learningKeys } from "@/features/our-internships/api/learning-api";
import { AssignmentFormDialog } from "@/features/our-internships/components/assignment-form-dialog";
import { ASSIGNMENT_STATUS, formatDateTime, sumScores } from "@/features/our-internships/lib/learning";
import { useCanDelete } from "@/features/our-internships/lib/internship-access";

/** The internship's assignments: write them, publish them, and mark what the enrolled students hand in. */
export function AssignmentsTab({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Assignment | "new" | null>(null);
  const canDelete = useCanDelete();
  const [marking, setMarking] = useState<Assignment | null>(null);
  const assignments = useQuery({ queryKey: learningKeys.assignments(internshipId), queryFn: () => assignmentsApi.list(internshipId) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["our-internships", "assignments", internshipId] });
  const remove = useMutation({ mutationFn: (id: string) => assignmentsApi.remove(internshipId, id), onSuccess: refresh });

  if (assignments.isLoading) return <Skeleton className="h-40 w-full" />;
  if (assignments.isError) return <p className="text-sm text-destructive">Could not load the assignments.</p>;
  const items = assignments.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Assignments go to the students who have LMS access. They hand in files before the deadline and you mark them here, by rubric or with one score.
        </p>
        {canManage && (
          <Button onClick={() => setEditing("new")}>
            <Plus className="h-4 w-4" />
            New assignment
          </Button>
        )}
      </div>
      {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not delete the assignment.")}</p>}

      {items.length === 0 ? (
        <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No assignments on this internship yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Assignment</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Deadline</TableHead>
                <TableHead className="text-right">Marks</TableHead>
                <TableHead className="text-right">Submitted</TableHead>
                <TableHead className="text-right">Marked</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((a) => {
                const status = ASSIGNMENT_STATUS[a.status];
                return (
                  <TableRow key={a.id}>
                    <TableCell>
                      <div className="font-medium">{a.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {a.rubric.length ? `${a.rubric.length} rubric criteria` : "Single score"}
                        {a.files.length ? ` · ${a.files.length} file${a.files.length === 1 ? "" : "s"}` : ""}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell>
                      {formatDateTime(a.deadline_at)}
                      {a.allow_late && <div className="text-xs text-muted-foreground">late allowed</div>}
                    </TableCell>
                    <TableCell className="text-right">{a.max_marks}</TableCell>
                    <TableCell className="text-right">
                      {a.submitted_count}/{a.enrolled_count}
                    </TableCell>
                    <TableCell className="text-right">{a.graded_count}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="outline" onClick={() => setMarking(a)}>
                          <Users className="h-3.5 w-3.5" />
                          Submissions
                        </Button>
                        {canManage && (
                          <>
                            <Button size="sm" variant="ghost" aria-label={`Edit ${a.title}`} onClick={() => setEditing(a)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            {canDelete && (
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label={`Delete ${a.title}`}
                              disabled={remove.isPending}
                              onClick={() => {
                                if (window.confirm(`Delete "${a.title}" with all its submissions and files? This cannot be undone.`)) remove.mutate(a.id);
                              }}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                            )}
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {editing && (
        <AssignmentFormDialog
          internshipId={internshipId}
          assignment={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => void refresh()}
        />
      )}
      {marking && <SubmissionsDialog internshipId={internshipId} assignment={marking} canManage={canManage} onClose={() => setMarking(null)} />}
    </div>
  );
}

function SubmissionsDialog({
  internshipId,
  assignment,
  canManage,
  onClose,
}: {
  internshipId: string;
  assignment: Assignment;
  canManage: boolean;
  onClose: () => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const rows = useQuery({
    queryKey: learningKeys.submissions(internshipId, assignment.id),
    queryFn: () => assignmentsApi.submissions(internshipId, assignment.id),
  });
  const current = rows.data?.find((r) => r.selection_id === open) ?? null;

  return (
    <Dialog open onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{assignment.title}: submissions</DialogTitle>
          <DialogDescription>
            Out of {assignment.max_marks} marks{assignment.deadline_at ? ` · deadline ${formatDateTime(assignment.deadline_at)}` : ""}.
          </DialogDescription>
        </DialogHeader>
        {rows.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : rows.isError ? (
          <p className="text-sm text-destructive">Could not load the submissions.</p>
        ) : rows.data?.length === 0 ? (
          <p className="rounded-md border p-6 text-center text-sm text-muted-foreground">No students have LMS access yet. Grant it under Onboarding.</p>
        ) : current ? (
          <MarkingPanel internshipId={internshipId} assignment={assignment} row={current} canManage={canManage} onBack={() => setOpen(null)} />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Files</TableHead>
                  <TableHead className="text-right">Marks</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.data?.map((row) => (
                  <TableRow key={row.selection_id}>
                    <TableCell>
                      <div className="font-medium">{row.student_name}</div>
                      <div className="text-xs text-muted-foreground">{row.student_email}</div>
                    </TableCell>
                    <TableCell>
                      {row.submitted ? (
                        <>
                          {formatDateTime(row.submitted_at)}
                          {row.is_late && (
                            <Badge variant="warning" className="ml-2">
                              Late
                            </Badge>
                          )}
                        </>
                      ) : (
                        <span className="text-muted-foreground">Not submitted</span>
                      )}
                    </TableCell>
                    <TableCell>{row.files.length || "-"}</TableCell>
                    <TableCell className="text-right">{row.reviewed_at ? `${row.score}/${assignment.max_marks}` : "-"}</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" disabled={!row.submitted} onClick={() => setOpen(row.selection_id)}>
                        {row.reviewed_at ? "Review" : "Mark"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function MarkingPanel({
  internshipId,
  assignment,
  row,
  canManage,
  onBack,
}: {
  internshipId: string;
  assignment: Assignment;
  row: SubmissionRow;
  canManage: boolean;
  onBack: () => void;
}) {
  const queryClient = useQueryClient();
  const hasRubric = assignment.rubric.length > 0;
  const [scores, setScores] = useState<Record<string, string>>(
    Object.fromEntries(assignment.rubric.map((r) => [r.id, row.rubric_scores?.[r.id] !== undefined ? String(row.rubric_scores[r.id]) : ""])),
  );
  const [single, setSingle] = useState(row.score !== null && !hasRubric ? String(row.score) : "");
  const [feedback, setFeedback] = useState(row.feedback ?? "");

  const total = hasRubric ? sumScores(scores) : Number(single) || 0;
  const overRubric = hasRubric && assignment.rubric.some((r) => Number(scores[r.id]) > r.points || Number(scores[r.id]) < 0);
  const overMax = !hasRubric && (Number(single) > assignment.max_marks || Number(single) < 0);

  const save = useMutation({
    mutationFn: () =>
      assignmentsApi.grade(
        internshipId,
        assignment.id,
        row.selection_id,
        hasRubric
          ? { rubric_scores: Object.fromEntries(assignment.rubric.map((r) => [r.id, Number(scores[r.id]) || 0])), feedback: feedback.trim() || null }
          : { score: Number(single), feedback: feedback.trim() || null },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["our-internships", "assignments", internshipId] });
      onBack();
    },
  });

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={onBack}>
        Back to all students
      </Button>
      <div>
        <div className="font-medium">{row.student_name}</div>
        <div className="text-xs text-muted-foreground">
          {row.student_email} · submitted {formatDateTime(row.submitted_at)}
          {row.is_late ? " (late)" : ""}
          {row.resubmission_count > 0 ? ` · changed ${row.resubmission_count} time${row.resubmission_count === 1 ? "" : "s"}` : ""}
        </div>
      </div>
      {row.note && <p className="whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm">{row.note}</p>}
      <div className="space-y-1.5">
        {row.files.length === 0 && <p className="text-sm text-muted-foreground">No files, only the note above.</p>}
        {row.files.map((f) => (
          <a key={f.id} href={f.url ?? "#"} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted">
            <FileText className="h-4 w-4" />
            <span className="truncate">{f.filename}</span>
            <span className="text-xs text-muted-foreground">{formatBytes(f.size_bytes)}</span>
          </a>
        ))}
      </div>

      {canManage && (
        <div className="space-y-3 rounded-md border p-3">
          {hasRubric ? (
            assignment.rubric.map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-3">
                <label htmlFor={`score-${r.id}`} className="text-sm">
                  {r.criterion} <span className="text-xs text-muted-foreground">(max {r.points})</span>
                </label>
                <Input
                  id={`score-${r.id}`}
                  className="w-24"
                  type="number"
                  min={0}
                  max={r.points}
                  step="0.5"
                  value={scores[r.id]}
                  onChange={(e) => setScores({ ...scores, [r.id]: e.target.value })}
                />
              </div>
            ))
          ) : (
            <div className="flex items-center justify-between gap-3">
              <label htmlFor="score-single" className="text-sm">
                Marks <span className="text-xs text-muted-foreground">(max {assignment.max_marks})</span>
              </label>
              <Input id="score-single" className="w-24" type="number" min={0} max={assignment.max_marks} step="0.5" value={single} onChange={(e) => setSingle(e.target.value)} />
            </div>
          )}
          <div className="text-right text-sm font-medium">
            Total: {total} / {assignment.max_marks}
          </div>
          <Textarea aria-label="Feedback" rows={3} placeholder="Feedback for the student" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          {(overRubric || overMax) && <p className="text-sm text-destructive">Marks must be between 0 and the maximum.</p>}
          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the marks.")}</p>}
          <div className="flex justify-end">
            <Button disabled={save.isPending || overRubric || overMax || (!hasRubric && single === "")} onClick={() => save.mutate()}>
              {save.isPending ? "Saving..." : row.reviewed_at ? "Update marks" : "Save marks"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
