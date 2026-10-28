import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Link2, Plus, Send, Unlink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/features/institutions/lib/format";
import { type ExamSummary, examsApi, learningKeys } from "@/features/our-internships/api/learning-api";
import { EXAM_STATE_LABELS, formatDateTime } from "@/features/our-internships/lib/learning";
import { useCanDelete } from "@/features/our-internships/lib/internship-access";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";
const examVariant = { draft: "secondary", open: "success", closed: "warning" } as const;

/**
 * The internship's exams. They are ordinary Workshop Exams (same builder, same exam page for students), attached to this
 * internship. Assigning puts every student who has LMS access on the exam, each with their own personal link.
 */
export function ExamsTab({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const canDelete = useCanDelete();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [linking, setLinking] = useState(false);
  const [resultsFor, setResultsFor] = useState<ExamSummary | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const exams = useQuery({ queryKey: learningKeys.exams(internshipId), queryFn: () => examsApi.list(internshipId) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["our-internships", "exams", internshipId] });

  const assign = useMutation({
    mutationFn: (v: { examId: string; invite: boolean }) => examsApi.assign(internshipId, v.examId, v.invite),
    onSuccess: (r) => {
      setNotice(
        r.added === 0 && r.invited === 0
          ? "Everyone with LMS access is already on this exam."
          : `${r.added} student${r.added === 1 ? "" : "s"} added${r.invited ? `, ${r.invited} invite${r.invited === 1 ? "" : "s"} queued` : ""}.`,
      );
      void refresh();
    },
  });
  const unlink = useMutation({ mutationFn: (examId: string) => examsApi.unlink(internshipId, examId), onSuccess: refresh });

  if (exams.isLoading) return <Skeleton className="h-40 w-full" />;
  if (exams.isError) return <p className="text-sm text-destructive">Could not load the exams.</p>;
  const items = exams.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Exams are built in the exam builder, the same one used for workshops. Students who have LMS access take them from their My Internship page.
        </p>
        {canManage && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setLinking(true)}>
              <Link2 className="h-4 w-4" />
              Add an existing exam
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              New exam
            </Button>
          </div>
        )}
      </div>

      {notice && <p className="text-sm text-emerald-700 dark:text-emerald-400">{notice}</p>}
      {(assign.isError || unlink.isError) && (
        <p className="text-sm text-destructive">{errorMessage(assign.error ?? unlink.error, "That did not work.")}</p>
      )}

      {items.length === 0 ? (
        <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No exams on this internship yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Exam</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Questions</TableHead>
                <TableHead className="text-right">Assigned</TableHead>
                <TableHead className="text-right">Submitted</TableHead>
                <TableHead className="text-right">Average</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((exam) => (
                <TableRow key={exam.id}>
                  <TableCell>
                    <Link to={`/workshop-exams/${exam.id}`} className="inline-flex items-center gap-1 font-medium hover:underline">
                      {exam.title}
                      <ExternalLink className="h-3 w-3 text-muted-foreground" />
                    </Link>
                    <div className="text-xs text-muted-foreground">{exam.duration_minutes} minutes</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={examVariant[exam.status]} className="capitalize">
                      {exam.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">{exam.question_count}</TableCell>
                  <TableCell className="text-right">{exam.attendee_count}</TableCell>
                  <TableCell className="text-right">{exam.submitted_count}</TableCell>
                  <TableCell className="text-right">{exam.average_percent === null ? "-" : `${exam.average_percent}%`}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={() => setResultsFor(exam)}>
                        Results
                      </Button>
                      {canManage && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={assign.isPending}
                            onClick={() => {
                              setNotice(null);
                              assign.mutate({ examId: exam.id, invite: true });
                            }}
                          >
                            <Send className="h-3.5 w-3.5" />
                            Assign &amp; invite
                          </Button>
                          {canDelete && (
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={`Remove ${exam.title} from this internship`}
                            disabled={unlink.isPending}
                            onClick={() => {
                              if (window.confirm(`Remove "${exam.title}" from this internship? The exam and its results are kept.`)) unlink.mutate(exam.id);
                            }}
                          >
                            <Unlink className="h-3.5 w-3.5" />
                          </Button>
                          )}
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {creating && <NewExamDialog internshipId={internshipId} onClose={() => setCreating(false)} onChanged={refresh} />}
      {linking && <LinkExamDialog internshipId={internshipId} onClose={() => setLinking(false)} onChanged={refresh} />}
      {resultsFor && <ResultsDialog internshipId={internshipId} exam={resultsFor} onClose={() => setResultsFor(null)} />}
    </div>
  );
}

function NewExamDialog({ internshipId, onClose, onChanged }: { internshipId: string; onClose: () => void; onChanged: () => void }) {
  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState("30");
  const create = useMutation({
    mutationFn: () => examsApi.create(internshipId, title.trim(), Math.min(480, Math.max(1, Number(minutes) || 30))),
    onSuccess: () => {
      onChanged();
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New exam</DialogTitle>
          <DialogDescription>Create it here, then add its questions in the exam builder.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="exam-title">Title</Label>
            <Input id="exam-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Week 1 assessment" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="exam-minutes">Duration (minutes)</Label>
            <Input id="exam-minutes" type="number" min={1} max={480} value={minutes} onChange={(e) => setMinutes(e.target.value)} />
          </div>
          {create.isError && <p className="text-sm text-destructive">{errorMessage(create.error, "Could not create the exam.")}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={title.trim().length < 2 || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Creating..." : "Create exam"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function LinkExamDialog({ internshipId, onClose, onChanged }: { internshipId: string; onClose: () => void; onChanged: () => void }) {
  const [examId, setExamId] = useState("");
  const available = useQuery({ queryKey: learningKeys.availableExams(internshipId), queryFn: () => examsApi.available(internshipId) });
  const link = useMutation({
    mutationFn: () => examsApi.link(internshipId, examId),
    onSuccess: () => {
      onChanged();
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add an existing exam</DialogTitle>
          <DialogDescription>Only exams that do not belong to a workshop, event or another internship are listed.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <select aria-label="Exam" className={selectClass} value={examId} onChange={(e) => setExamId(e.target.value)}>
            <option value="">Choose an exam...</option>
            {available.data?.map((e) => (
              <option key={e.id} value={e.id}>
                {e.title} ({e.status})
              </option>
            ))}
          </select>
          {available.data?.length === 0 && <p className="text-xs text-muted-foreground">There are no unattached exams. Create a new one instead.</p>}
          {link.isError && <p className="text-sm text-destructive">{errorMessage(link.error, "Could not add the exam.")}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={!examId || link.isPending} onClick={() => link.mutate()}>
              Add exam
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ResultsDialog({ internshipId, exam, onClose }: { internshipId: string; exam: ExamSummary; onClose: () => void }) {
  const results = useQuery({ queryKey: learningKeys.results(internshipId, exam.id), queryFn: () => examsApi.results(internshipId, exam.id) });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{exam.title}: results</DialogTitle>
          <DialogDescription>Every student with LMS access on this internship.</DialogDescription>
        </DialogHeader>
        {results.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : results.isError ? (
          <p className="text-sm text-destructive">Could not load the results.</p>
        ) : results.data?.length === 0 ? (
          <p className="rounded-md border p-6 text-center text-sm text-muted-foreground">No students have LMS access yet. Grant it under Onboarding.</p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead>Submitted</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.data?.map((row) => (
                  <TableRow key={row.selection_id}>
                    <TableCell>
                      <div className="font-medium">{row.student_name}</div>
                      <div className="text-xs text-muted-foreground">{row.student_email}</div>
                    </TableCell>
                    <TableCell>{EXAM_STATE_LABELS[row.state]}</TableCell>
                    <TableCell className="text-right">
                      {row.score === null ? "-" : `${row.score}/${row.total_marks} (${row.percent}%)`}
                    </TableCell>
                    <TableCell>{formatDateTime(row.submitted_at)}</TableCell>
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
