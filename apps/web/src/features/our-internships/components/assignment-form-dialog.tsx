import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Plus, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage, formatBytes } from "@/features/institutions/lib/format";
import {
  type Assignment,
  type AssignmentPayload,
  type AssignmentTask,
  type RubricRule,
  assignmentsApi,
} from "@/features/our-internships/api/learning-api";
import { fromLocalInput, newRowId, rubricTotal, toLocalInput } from "@/features/our-internships/lib/learning";
import { useCanDelete } from "@/features/our-internships/lib/internship-access";

/**
 * Create or edit an assignment: the brief, the tasks, how it is marked (a rubric, or one score out of the maximum), when it
 * opens and closes, and the reference files students can download. Reference files can be added once it is saved.
 */
export function AssignmentFormDialog({
  internshipId,
  assignment,
  onClose,
  onSaved,
}: {
  internshipId: string;
  assignment: Assignment | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const canDelete = useCanDelete();
  const [saved, setSaved] = useState<Assignment | null>(assignment);
  const [title, setTitle] = useState(assignment?.title ?? "");
  const [description, setDescription] = useState(assignment?.description ?? "");
  const [instructions, setInstructions] = useState(assignment?.instructions ?? "");
  const [tasks, setTasks] = useState<AssignmentTask[]>(assignment?.tasks ?? []);
  const [rubric, setRubric] = useState<RubricRule[]>(assignment?.rubric ?? []);
  const [maxMarks, setMaxMarks] = useState(String(assignment?.max_marks ?? 100));
  const [startsAt, setStartsAt] = useState(toLocalInput(assignment?.starts_at ?? null));
  const [deadlineAt, setDeadlineAt] = useState(toLocalInput(assignment?.deadline_at ?? null));
  const [allowLate, setAllowLate] = useState(assignment?.allow_late ?? false);
  const [maxFiles, setMaxFiles] = useState(String(assignment?.max_files ?? 5));
  const [publish, setPublish] = useState(assignment ? assignment.status !== "draft" : false);

  const useRubric = rubric.length > 0;
  const payload = (): AssignmentPayload => ({
    title: title.trim(),
    description: description.trim() || null,
    instructions: instructions.trim() || null,
    tasks: tasks.filter((t) => t.title.trim()).map((t) => ({ ...t, title: t.title.trim(), details: t.details?.trim() || null })),
    rubric: rubric.filter((r) => r.criterion.trim()).map((r) => ({ ...r, criterion: r.criterion.trim() })),
    max_marks: Math.max(1, Math.round(Number(maxMarks) || 100)),
    starts_at: fromLocalInput(startsAt),
    deadline_at: fromLocalInput(deadlineAt),
    allow_late: allowLate,
    max_files: Math.min(20, Math.max(1, Math.round(Number(maxFiles) || 5))),
  });

  const save = useMutation({
    mutationFn: () => {
      const body = payload();
      if (saved) return assignmentsApi.update(internshipId, saved.id, { ...body, ...(saved.status === "closed" ? {} : { status: publish ? "published" : "draft" }) });
      return assignmentsApi.create(internshipId, body).then((created) => (publish ? assignmentsApi.update(internshipId, created.id, { status: "published" }) : created));
    },
    onSuccess: (result) => {
      setSaved(result);
      void queryClient.invalidateQueries({ queryKey: ["our-internships", "assignments", internshipId] });
      onSaved();
    },
  });

  const refreshSaved = (next: Assignment) => {
    setSaved(next);
    void queryClient.invalidateQueries({ queryKey: ["our-internships", "assignments", internshipId] });
  };
  const addFile = useMutation({
    mutationFn: async (file: File) => {
      await assignmentsApi.addFile(internshipId, saved!.id, file);
      return assignmentsApi.list(internshipId).then((all) => all.find((a) => a.id === saved!.id)!);
    },
    onSuccess: refreshSaved,
  });
  const removeFile = useMutation({
    mutationFn: async (fileId: string) => {
      await assignmentsApi.removeFile(internshipId, saved!.id, fileId);
      return assignmentsApi.list(internshipId).then((all) => all.find((a) => a.id === saved!.id)!);
    },
    onSuccess: refreshSaved,
  });

  const valid = title.trim().length > 0 && (!deadlineAt || !startsAt || new Date(deadlineAt) > new Date(startsAt));

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{assignment ? "Edit assignment" : "New assignment"}</DialogTitle>
          <DialogDescription>Students see it on their My Internship page once it is published.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="as-title">Title</Label>
            <Input id="as-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Reconnaissance report" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="as-desc">Description</Label>
            <Textarea id="as-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium leading-none">Tasks / questions</span>
              <Button type="button" size="sm" variant="outline" onClick={() => setTasks([...tasks, { id: newRowId("t", tasks.map((t) => t.id)), title: "", details: "" }])}>
                <Plus className="h-3.5 w-3.5" />
                Add task
              </Button>
            </div>
            {tasks.map((task, index) => (
              <div key={task.id} className="space-y-2 rounded-md border p-3">
                <div className="flex gap-2">
                  <Input
                    aria-label={`Task ${index + 1} title`}
                    placeholder={`Task ${index + 1}`}
                    value={task.title}
                    onChange={(e) => setTasks(tasks.map((t) => (t.id === task.id ? { ...t, title: e.target.value } : t)))}
                  />
                  <Button type="button" size="icon" variant="ghost" aria-label={`Remove task ${index + 1}`} onClick={() => setTasks(tasks.filter((t) => t.id !== task.id))}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                <Textarea
                  aria-label={`Task ${index + 1} details`}
                  rows={2}
                  placeholder="Details (optional)"
                  value={task.details ?? ""}
                  onChange={(e) => setTasks(tasks.map((t) => (t.id === task.id ? { ...t, details: e.target.value } : t)))}
                />
              </div>
            ))}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="as-instr">Instructions</Label>
            <Textarea id="as-instr" rows={3} value={instructions} onChange={(e) => setInstructions(e.target.value)} placeholder="How to prepare and submit the work" />
          </div>

          <div className="space-y-2 rounded-md border p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium leading-none">Marking</span>
              <Button type="button" size="sm" variant="outline" onClick={() => setRubric([...rubric, { id: newRowId("r", rubric.map((r) => r.id)), criterion: "", points: 10 }])}>
                <Plus className="h-3.5 w-3.5" />
                Add rubric criterion
              </Button>
            </div>
            {useRubric ? (
              <>
                {rubric.map((rule, index) => (
                  <div key={rule.id} className="flex gap-2">
                    <Input
                      aria-label={`Criterion ${index + 1}`}
                      placeholder="Criterion"
                      value={rule.criterion}
                      onChange={(e) => setRubric(rubric.map((r) => (r.id === rule.id ? { ...r, criterion: e.target.value } : r)))}
                    />
                    <Input
                      aria-label={`Criterion ${index + 1} points`}
                      className="w-24"
                      type="number"
                      min={1}
                      value={rule.points}
                      onChange={(e) => setRubric(rubric.map((r) => (r.id === rule.id ? { ...r, points: Math.max(1, Math.round(Number(e.target.value) || 1)) } : r)))}
                    />
                    <Button type="button" size="icon" variant="ghost" aria-label={`Remove criterion ${index + 1}`} onClick={() => setRubric(rubric.filter((r) => r.id !== rule.id))}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                <p className="text-xs text-muted-foreground">Total marks: {rubricTotal(rubric)} (the sum of the criteria).</p>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <Label htmlFor="as-max" className="text-sm font-normal">
                  One score out of
                </Label>
                <Input id="as-max" className="w-24" type="number" min={1} max={1000} value={maxMarks} onChange={(e) => setMaxMarks(e.target.value)} />
              </div>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="as-start">Opens</Label>
              <Input id="as-start" type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="as-deadline">Deadline</Label>
              <Input id="as-deadline" type="datetime-local" value={deadlineAt} onChange={(e) => setDeadlineAt(e.target.value)} />
            </div>
          </div>
          {startsAt && deadlineAt && new Date(deadlineAt) <= new Date(startsAt) && <p className="text-sm text-destructive">The deadline must be after the opening time.</p>}
          <div className="flex flex-wrap items-center gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={allowLate} onChange={(e) => setAllowLate(e.target.checked)} />
              Accept late submissions (marked as late)
            </label>
            <div className="flex items-center gap-2">
              <Label htmlFor="as-files" className="text-sm font-normal">
                Files per student
              </Label>
              <Input id="as-files" className="w-20" type="number" min={1} max={20} value={maxFiles} onChange={(e) => setMaxFiles(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2 rounded-md border p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium leading-none">Reference files</span>
              <Button type="button" size="sm" variant="outline" disabled={!saved || addFile.isPending} onClick={() => fileInput.current?.click()}>
                <Plus className="h-3.5 w-3.5" />
                {addFile.isPending ? "Uploading..." : "Add file"}
              </Button>
              <input
                ref={fileInput}
                type="file"
                className="hidden"
                aria-label="Reference file"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (file) addFile.mutate(file);
                }}
              />
            </div>
            {!saved && <p className="text-xs text-muted-foreground">Save the assignment first, then add files (up to 25 MB each).</p>}
            {saved?.files.map((f) => (
              <div key={f.id} className="flex items-center justify-between gap-2 text-sm">
                <a href={f.url ?? "#"} target="_blank" rel="noreferrer" className="inline-flex min-w-0 items-center gap-1.5 hover:underline">
                  <FileText className="h-4 w-4 shrink-0" />
                  <span className="truncate">{f.filename}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{formatBytes(f.size_bytes)}</span>
                </a>
                {canDelete && (
                  <Button type="button" size="icon" variant="ghost" aria-label={`Remove ${f.filename}`} disabled={removeFile.isPending} onClick={() => removeFile.mutate(f.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
            {(addFile.isError || removeFile.isError) && <p className="text-sm text-destructive">{errorMessage(addFile.error ?? removeFile.error, "That file could not be changed.")}</p>}
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={publish} disabled={saved?.status === "closed"} onChange={(e) => setPublish(e.target.checked)} />
            Published (visible to students)
          </label>

          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the assignment.")}</p>}
          {save.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">Saved.</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              {saved ? "Close" : "Cancel"}
            </Button>
            <Button disabled={!valid || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving..." : saved ? "Save changes" : "Create assignment"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
