import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Plus, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage, formatBytes } from "@/features/institutions/lib/format";
import { type Project, type ProjectPayload, type ReferenceLink, projectsApi } from "@/features/our-internships/api/projects-api";
import { fromLocalInput, newRowId, toLocalInput } from "@/features/our-internships/lib/learning";
import { submissionProblem } from "@/features/our-internships/lib/projects";

function FileList({
  title,
  hint,
  files,
  disabled,
  pending,
  onAdd,
  onRemove,
}: {
  title: string;
  hint: string;
  files: Project["documents"];
  disabled: boolean;
  pending: boolean;
  onAdd: (file: File) => void;
  onRemove: (id: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium leading-none">{title}</span>
        <Button type="button" size="sm" variant="outline" disabled={disabled || pending} onClick={() => input.current?.click()}>
          <Plus className="h-3.5 w-3.5" />
          {pending ? "Uploading..." : "Add file"}
        </Button>
        <input
          ref={input}
          type="file"
          className="hidden"
          aria-label={title}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) onAdd(file);
          }}
        />
      </div>
      <p className="text-xs text-muted-foreground">{disabled ? "Save the project first, then add files (up to 25 MB each)." : hint}</p>
      {files.map((f) => (
        <div key={f.id} className="flex items-center justify-between gap-2 text-sm">
          <a href={f.url ?? "#"} target="_blank" rel="noreferrer" className="inline-flex min-w-0 items-center gap-1.5 hover:underline">
            <FileText className="h-4 w-4 shrink-0" />
            <span className="truncate">{f.filename}</span>
            <span className="shrink-0 text-xs text-muted-foreground">{formatBytes(f.size_bytes)}</span>
          </a>
          <Button type="button" size="icon" variant="ghost" aria-label={`Remove ${f.filename}`} onClick={() => onRemove(f.id)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  );
}

/**
 * Create or edit a project: the brief, the rules, how students may hand it in (files, an email, a repository link, or any
 * mix), a limit on how many students can pick it, dates, reference links, and the documents and templates students get.
 */
export function ProjectFormDialog({
  internshipId,
  project,
  onClose,
  onSaved,
}: {
  internshipId: string;
  project: Project | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState<Project | null>(project);
  const [title, setTitle] = useState(project?.title ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [objectives, setObjectives] = useState(project?.objectives ?? "");
  const [rules, setRules] = useState(project?.rules ?? "");
  const [instructions, setInstructions] = useState(project?.submission_instructions ?? "");
  const [links, setLinks] = useState<ReferenceLink[]>(project?.reference_links ?? []);
  const [allowFile, setAllowFile] = useState(project?.allow_file ?? true);
  const [allowEmail, setAllowEmail] = useState(project?.allow_email ?? false);
  const [allowRepo, setAllowRepo] = useState(project?.allow_repository ?? false);
  const [email, setEmail] = useState(project?.submission_email ?? "");
  const [maxFiles, setMaxFiles] = useState(String(project?.max_files ?? 5));
  const [capacity, setCapacity] = useState(project?.capacity ? String(project.capacity) : "");
  const [startsAt, setStartsAt] = useState(toLocalInput(project?.starts_at ?? null));
  const [deadlineAt, setDeadlineAt] = useState(toLocalInput(project?.deadline_at ?? null));
  const [allowLate, setAllowLate] = useState(project?.allow_late ?? false);
  const [publish, setPublish] = useState(project ? project.status !== "draft" : false);

  const problem = submissionProblem({ allowFile, allowEmail, allowRepo, email, startsAt, deadlineAt });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["our-internships", "projects", internshipId] });

  const payload = (): ProjectPayload => ({
    title: title.trim(),
    description: description.trim() || null,
    objectives: objectives.trim() || null,
    rules: rules.trim() || null,
    submission_instructions: instructions.trim() || null,
    reference_links: links.filter((l) => l.title.trim() && l.url.trim()).map((l) => ({ ...l, title: l.title.trim(), url: l.url.trim() })),
    allow_file: allowFile,
    allow_email: allowEmail,
    allow_repository: allowRepo,
    submission_email: allowEmail ? email.trim() || null : null,
    max_files: Math.min(20, Math.max(1, Math.round(Number(maxFiles) || 5))),
    capacity: capacity.trim() ? Math.max(1, Math.round(Number(capacity) || 1)) : null,
    starts_at: fromLocalInput(startsAt),
    deadline_at: fromLocalInput(deadlineAt),
    allow_late: allowLate,
  });

  const save = useMutation({
    mutationFn: () => {
      const body = payload();
      if (saved) return projectsApi.update(internshipId, saved.id, { ...body, ...(saved.status === "closed" ? {} : { status: publish ? "published" : "draft" }) });
      return projectsApi.create(internshipId, body).then((created) => (publish ? projectsApi.update(internshipId, created.id, { status: "published" }) : created));
    },
    onSuccess: (result) => {
      setSaved(result);
      void invalidate();
      onSaved();
    },
  });

  const reload = async () => {
    const next = (await projectsApi.list(internshipId)).find((p) => p.id === saved!.id)!;
    setSaved(next);
    void invalidate();
  };
  const addFile = useMutation({
    mutationFn: (v: { kind: "document" | "template"; file: File }) => projectsApi.addFile(internshipId, saved!.id, v.kind, v.file),
    onSuccess: reload,
  });
  const removeFile = useMutation({ mutationFn: (fileId: string) => projectsApi.removeFile(internshipId, saved!.id, fileId), onSuccess: reload });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{project ? "Edit project" : "New project"}</DialogTitle>
          <DialogDescription>Students choose one project and hand it in the way you allow below.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="pr-title">Title</Label>
            <Input id="pr-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Network vulnerability scanner" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pr-desc">Description</Label>
            <Textarea id="pr-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pr-obj">Objectives</Label>
            <Textarea id="pr-obj" rows={2} value={objectives} onChange={(e) => setObjectives(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pr-rules">Rules</Label>
            <Textarea id="pr-rules" rows={3} value={rules} onChange={(e) => setRules(e.target.value)} placeholder="What is allowed, what is not, what a submission must contain" />
          </div>

          <div className="space-y-2 rounded-md border p-3">
            <span className="text-sm font-medium leading-none">How students hand it in</span>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={allowFile} onChange={(e) => setAllowFile(e.target.checked)} />
              Upload files
            </label>
            {allowFile && (
              <div className="ml-6 flex items-center gap-2">
                <Label htmlFor="pr-files" className="text-sm font-normal">
                  Files per student
                </Label>
                <Input id="pr-files" className="w-20" type="number" min={1} max={20} value={maxFiles} onChange={(e) => setMaxFiles(e.target.value)} />
              </div>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={allowEmail} onChange={(e) => setAllowEmail(e.target.checked)} />
              Send by email
            </label>
            {allowEmail && (
              <div className="ml-6 flex items-center gap-2">
                <Label htmlFor="pr-email" className="text-sm font-normal">
                  Send to
                </Label>
                <Input id="pr-email" className="max-w-xs" type="email" placeholder="projects@pentrix.in" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={allowRepo} onChange={(e) => setAllowRepo(e.target.checked)} />
              Share a repository link
            </label>
            <Textarea aria-label="Submission instructions" rows={2} placeholder="Instructions for handing in (optional)" value={instructions} onChange={(e) => setInstructions(e.target.value)} />
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="pr-start">Opens</Label>
              <Input id="pr-start" type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pr-deadline">Deadline</Label>
              <Input id="pr-deadline" type="datetime-local" value={deadlineAt} onChange={(e) => setDeadlineAt(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pr-cap">Student limit</Label>
              <Input id="pr-cap" type="number" min={1} placeholder="No limit" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={allowLate} onChange={(e) => setAllowLate(e.target.checked)} />
            Accept late submissions (marked as late)
          </label>

          <div className="space-y-2 rounded-md border p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium leading-none">Reference links</span>
              <Button type="button" size="sm" variant="outline" onClick={() => setLinks([...links, { id: newRowId("l", links.map((l) => l.id)), title: "", url: "" }])}>
                <Plus className="h-3.5 w-3.5" />
                Add link
              </Button>
            </div>
            {links.map((link, index) => (
              <div key={link.id} className="flex gap-2">
                <Input aria-label={`Link ${index + 1} title`} className="w-40" placeholder="Title" value={link.title} onChange={(e) => setLinks(links.map((l) => (l.id === link.id ? { ...l, title: e.target.value } : l)))} />
                <Input aria-label={`Link ${index + 1} address`} placeholder="https://..." value={link.url} onChange={(e) => setLinks(links.map((l) => (l.id === link.id ? { ...l, url: e.target.value } : l)))} />
                <Button type="button" size="icon" variant="ghost" aria-label={`Remove link ${index + 1}`} onClick={() => setLinks(links.filter((l) => l.id !== link.id))}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>

          <FileList
            title="Project documents"
            hint="Briefs, specifications and reading material students can download."
            files={saved?.documents ?? []}
            disabled={!saved}
            pending={addFile.isPending && addFile.variables?.kind === "document"}
            onAdd={(file) => addFile.mutate({ kind: "document", file })}
            onRemove={(id) => removeFile.mutate(id)}
          />
          <FileList
            title="Templates"
            hint="Report or code templates students start from."
            files={saved?.templates ?? []}
            disabled={!saved}
            pending={addFile.isPending && addFile.variables?.kind === "template"}
            onAdd={(file) => addFile.mutate({ kind: "template", file })}
            onRemove={(id) => removeFile.mutate(id)}
          />
          {(addFile.isError || removeFile.isError) && <p className="text-sm text-destructive">{errorMessage(addFile.error ?? removeFile.error, "That file could not be changed.")}</p>}

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={publish} disabled={saved?.status === "closed"} onChange={(e) => setPublish(e.target.checked)} />
            Published (students can choose it)
          </label>

          {problem && <p className="text-sm text-destructive">{problem}</p>}
          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the project.")}</p>}
          {save.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">Saved.</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              {saved ? "Close" : "Cancel"}
            </Button>
            <Button disabled={!title.trim() || !!problem || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving..." : saved ? "Save changes" : "Create project"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
