import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import type { Project } from "@/features/our-internships/api/projects-api";
import { type Review, type ReviewRow, reviewKeys, reviewsApi } from "@/features/our-internships/api/reviews-api";
import { formatDateTime, sumScores } from "@/features/our-internships/lib/learning";
import { useCanDelete } from "@/features/our-internships/lib/internship-access";

/** Reviews of a project: who handed in, the reviews written for each, and publishing the final marks. */
export function ReviewsDialog({ internshipId, project, canManage, onClose }: { internshipId: string; project: Project; canManage: boolean; onClose: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const rows = useQuery({ queryKey: reviewKeys.rows(internshipId, project.id), queryFn: () => reviewsApi.rows(internshipId, project.id) });
  const current = rows.data?.find((r) => r.selection_id === open) ?? null;

  return (
    <Dialog open onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{project.title}: reviews</DialogTitle>
          <DialogDescription>Out of {project.max_marks} marks. Students see reviews and marks only after you publish their final result.</DialogDescription>
        </DialogHeader>
        {rows.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : rows.isError ? (
          <p className="text-sm text-destructive">Could not load the reviews.</p>
        ) : rows.data?.length === 0 ? (
          <p className="rounded-md border p-6 text-center text-sm text-muted-foreground">Nobody has handed this project in yet.</p>
        ) : current ? (
          <StudentReviews internshipId={internshipId} project={project} row={current} canManage={canManage} onBack={() => setOpen(null)} />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Handed in</TableHead>
                  <TableHead className="text-right">Reviews</TableHead>
                  <TableHead className="text-right">Average</TableHead>
                  <TableHead>Final result</TableHead>
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
                      {formatDateTime(row.submitted_at)}
                      {row.is_late && (
                        <Badge variant="warning" className="ml-2">
                          Late
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">{row.reviews.length}</TableCell>
                    <TableCell className="text-right">{row.average === null ? "-" : `${row.average}/${row.max_marks}`}</TableCell>
                    <TableCell>
                      {row.final_published_at ? <Badge variant="success">{row.final_marks}/{row.max_marks} published</Badge> : <span className="text-muted-foreground">Not published</span>}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" onClick={() => setOpen(row.selection_id)}>
                        Review
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

function StudentReviews({ internshipId, project, row, canManage, onBack }: { internshipId: string; project: Project; row: ReviewRow; canManage: boolean; onBack: () => void }) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["our-internships", "projects", internshipId] });
  const [editing, setEditing] = useState<Review | "new" | null>(null);
  const published = !!row.final_published_at;
  const canDelete = useCanDelete();
  const [finalMarks, setFinalMarks] = useState(row.final_marks !== null ? String(row.final_marks) : "");
  const [finalFeedback, setFinalFeedback] = useState(row.final_feedback ?? "");

  const remove = useMutation({ mutationFn: (id: string) => reviewsApi.remove(internshipId, project.id, id), onSuccess: refresh });
  const publish = useMutation({
    mutationFn: () => reviewsApi.publish(internshipId, project.id, row.selection_id, { final_marks: finalMarks.trim() === "" ? null : Number(finalMarks), feedback: finalFeedback.trim() || null }),
    onSuccess: refresh,
  });
  const withdraw = useMutation({ mutationFn: () => reviewsApi.unpublish(internshipId, project.id, row.selection_id), onSuccess: refresh });
  const finalInvalid = finalMarks.trim() !== "" && (Number(finalMarks) < 0 || Number(finalMarks) > row.max_marks || Number.isNaN(Number(finalMarks)));
  const nothingToPublish = finalMarks.trim() === "" && row.reviews.length === 0;
  const error = remove.error ?? publish.error ?? withdraw.error;

  return (
    <div className="space-y-5">
      <Button variant="ghost" size="sm" onClick={onBack}>
        Back to all students
      </Button>
      <div>
        <div className="font-medium">{row.student_name}</div>
        <div className="text-xs text-muted-foreground">{row.student_email} · handed in {formatDateTime(row.submitted_at)}</div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Reviews ({row.reviews.length})</h3>
          {canManage && !published && !editing && (
            <Button size="sm" onClick={() => setEditing("new")}>
              Add review
            </Button>
          )}
        </div>
        {published && <p className="text-xs text-muted-foreground">The result is published. Withdraw it below to add or change reviews.</p>}
        {row.reviews.map((review) => (
          <div key={review.id} className="space-y-1 rounded-md border p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="font-medium">{review.label}</span>
                <span className="ml-2 text-sm">{review.total}/{review.max_total}</span>
                <div className="text-xs text-muted-foreground">{review.reviewer_name ?? "Unknown reviewer"} · {formatDateTime(review.updated_at)}</div>
              </div>
              {canManage && !published && (
                <div className="flex gap-1">
                  <Button size="icon" variant="ghost" aria-label={`Edit ${review.label}`} onClick={() => setEditing(review)}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  {canDelete && (
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Delete ${review.label}`}
                    disabled={remove.isPending}
                    onClick={() => {
                      if (window.confirm(`Delete the review "${review.label}"?`)) remove.mutate(review.id);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                  )}
                </div>
              )}
            </div>
            {review.factor_scores && (
              <ul className="text-sm text-muted-foreground">
                {project.review_factors.map((f) => (
                  <li key={f.id} className="flex justify-between gap-3">
                    <span>{f.name}</span>
                    <span>{review.factor_scores?.[f.id] ?? 0} / {f.max_marks}</span>
                  </li>
                ))}
              </ul>
            )}
            {review.feedback && <p className="whitespace-pre-wrap text-sm">{review.feedback}</p>}
          </div>
        ))}
        {editing && (
          <ReviewForm
            internshipId={internshipId}
            project={project}
            selectionId={row.selection_id}
            review={editing === "new" ? null : editing}
            suggestion={`Review ${row.reviews.length + 1}`}
            onDone={() => {
              setEditing(null);
              void refresh();
            }}
            onCancel={() => setEditing(null)}
          />
        )}
      </div>

      {canManage && (
        <div className="space-y-3 rounded-md border p-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">Final result</h3>
            {published ? <Badge variant="success">Published {formatDateTime(row.final_published_at)}</Badge> : <Badge variant="secondary">Not published</Badge>}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="final-marks" className="text-sm">
              Final marks <span className="text-xs text-muted-foreground">(max {row.max_marks})</span>
            </label>
            <Input id="final-marks" className="w-28" type="number" min={0} max={row.max_marks} step="0.5" placeholder={row.average === null ? "" : String(row.average)} value={finalMarks} onChange={(e) => setFinalMarks(e.target.value)} />
            {row.average !== null && <span className="text-xs text-muted-foreground">Left empty, the average of the reviews ({row.average}) is used.</span>}
          </div>
          <Textarea aria-label="Final feedback" rows={3} placeholder="Overall feedback the student will see" value={finalFeedback} onChange={(e) => setFinalFeedback(e.target.value)} />
          {finalInvalid && <p className="text-sm text-destructive">Marks must be between 0 and {row.max_marks}.</p>}
          {error && <p className="text-sm text-destructive">{errorMessage(error, "That did not work.")}</p>}
          <div className="flex justify-end gap-2">
            {published && (
              <Button variant="outline" disabled={withdraw.isPending} onClick={() => withdraw.mutate()}>
                Withdraw result
              </Button>
            )}
            <Button disabled={publish.isPending || finalInvalid || nothingToPublish} onClick={() => publish.mutate()}>
              {publish.isPending ? "Publishing..." : published ? "Update published result" : "Publish result"}
            </Button>
          </div>
          {nothingToPublish && <p className="text-xs text-muted-foreground">Write a review or enter the final marks first.</p>}
        </div>
      )}
    </div>
  );
}

function ReviewForm({
  internshipId,
  project,
  selectionId,
  review,
  suggestion,
  onDone,
  onCancel,
}: {
  internshipId: string;
  project: Project;
  selectionId: string;
  review: Review | null;
  suggestion: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const hasFactors = project.review_factors.length > 0;
  const [label, setLabel] = useState(review?.label ?? suggestion);
  const [scores, setScores] = useState<Record<string, string>>(
    Object.fromEntries(project.review_factors.map((f) => [f.id, review?.factor_scores?.[f.id] !== undefined ? String(review.factor_scores[f.id]) : ""])),
  );
  const [single, setSingle] = useState(review && !hasFactors ? String(review.total) : "");
  const [feedback, setFeedback] = useState(review?.feedback ?? "");

  const total = hasFactors ? sumScores(scores) : Number(single) || 0;
  const out = hasFactors ? project.review_factors.some((f) => Number(scores[f.id]) > f.max_marks || Number(scores[f.id]) < 0) : Number(single) > project.max_marks || Number(single) < 0;
  const save = useMutation({
    mutationFn: () => {
      const payload = hasFactors
        ? { label: label.trim(), factor_scores: Object.fromEntries(project.review_factors.map((f) => [f.id, Number(scores[f.id]) || 0])), feedback: feedback.trim() || null }
        : { label: label.trim(), score: Number(single), feedback: feedback.trim() || null };
      return review ? reviewsApi.update(internshipId, project.id, review.id, payload) : reviewsApi.add(internshipId, project.id, selectionId, payload);
    },
    onSuccess: onDone,
  });

  return (
    <div className="space-y-3 rounded-md border bg-muted/30 p-3">
      <Input aria-label="Review name" placeholder="Mid-way review" value={label} onChange={(e) => setLabel(e.target.value)} />
      {hasFactors ? (
        project.review_factors.map((f) => (
          <div key={f.id} className="flex items-center justify-between gap-3">
            <label htmlFor={`rf-${f.id}`} className="text-sm">
              {f.name} <span className="text-xs text-muted-foreground">(max {f.max_marks})</span>
            </label>
            <Input id={`rf-${f.id}`} className="w-24" type="number" min={0} max={f.max_marks} step="0.5" value={scores[f.id]} onChange={(e) => setScores({ ...scores, [f.id]: e.target.value })} />
          </div>
        ))
      ) : (
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="rf-single" className="text-sm">
            Marks <span className="text-xs text-muted-foreground">(max {project.max_marks})</span>
          </label>
          <Input id="rf-single" className="w-24" type="number" min={0} max={project.max_marks} step="0.5" value={single} onChange={(e) => setSingle(e.target.value)} />
        </div>
      )}
      <div className="text-right text-sm font-medium">
        Total: {total} / {project.max_marks}
      </div>
      <Textarea aria-label="Review feedback" rows={3} placeholder="Feedback for this review" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
      {out && <p className="text-sm text-destructive">Marks must be between 0 and the maximum.</p>}
      {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the review.")}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button disabled={!label.trim() || out || save.isPending || (!hasFactors && single === "")} onClick={() => save.mutate()}>
          {save.isPending ? "Saving..." : review ? "Update review" : "Save review"}
        </Button>
      </div>
    </div>
  );
}
