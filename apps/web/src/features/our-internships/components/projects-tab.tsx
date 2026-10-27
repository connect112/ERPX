import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage, formatBytes } from "@/features/institutions/lib/format";
import { type Project, type ProjectSelectionRow, projectKeys, projectsApi } from "@/features/our-internships/api/projects-api";
import { ProjectFormDialog } from "@/features/our-internships/components/project-form-dialog";
import { formatDateTime } from "@/features/our-internships/lib/learning";
import { METHOD_LABELS, PROJECT_STATUS, allowedMethods } from "@/features/our-internships/lib/projects";

/** The internship's projects, and which project each enrolled student chose and handed in. */
export function ProjectsTab({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Project | "new" | null>(null);
  const projects = useQuery({ queryKey: projectKeys.list(internshipId), queryFn: () => projectsApi.list(internshipId) });
  const selections = useQuery({ queryKey: projectKeys.selections(internshipId), queryFn: () => projectsApi.selections(internshipId) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["our-internships", "projects", internshipId] });
  const remove = useMutation({ mutationFn: (id: string) => projectsApi.remove(internshipId, id), onSuccess: refresh });
  const received = useMutation({
    mutationFn: (v: { row: ProjectSelectionRow; received: boolean }) => projectsApi.markReceived(internshipId, v.row.project_id!, v.row.selection_id, v.received),
    onSuccess: refresh,
  });

  if (projects.isLoading) return <Skeleton className="h-40 w-full" />;
  if (projects.isError) return <p className="text-sm text-destructive">Could not load the projects.</p>;
  const items = projects.data ?? [];
  const rows = selections.data ?? [];

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-2xl text-sm text-muted-foreground">
            Each student with LMS access chooses one project and hands it in the way you allow: files, an email, or a repository link.
          </p>
          {canManage && (
            <Button onClick={() => setEditing("new")}>
              <Plus className="h-4 w-4" />
              New project
            </Button>
          )}
        </div>
        {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not delete the project.")}</p>}

        {items.length === 0 ? (
          <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No projects on this internship yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Project</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Hand in by</TableHead>
                  <TableHead>Deadline</TableHead>
                  <TableHead className="text-right">Chosen</TableHead>
                  <TableHead className="text-right">Submitted</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((p) => {
                  const status = PROJECT_STATUS[p.status];
                  return (
                    <TableRow key={p.id}>
                      <TableCell>
                        <div className="font-medium">{p.title}</div>
                        <div className="text-xs text-muted-foreground">
                          {p.documents.length + p.templates.length} file{p.documents.length + p.templates.length === 1 ? "" : "s"}
                          {p.reference_links.length ? ` · ${p.reference_links.length} link${p.reference_links.length === 1 ? "" : "s"}` : ""}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={status.variant}>{status.label}</Badge>
                      </TableCell>
                      <TableCell>{allowedMethods(p)}</TableCell>
                      <TableCell>
                        {formatDateTime(p.deadline_at)}
                        {p.allow_late && <div className="text-xs text-muted-foreground">late allowed</div>}
                      </TableCell>
                      <TableCell className="text-right">
                        {p.chosen_count}
                        {p.capacity ? ` / ${p.capacity}` : ""}
                      </TableCell>
                      <TableCell className="text-right">{p.submitted_count}</TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-2">
                          {canManage && (
                            <>
                              <Button size="sm" variant="ghost" aria-label={`Edit ${p.title}`} onClick={() => setEditing(p)}>
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                aria-label={`Delete ${p.title}`}
                                disabled={remove.isPending}
                                onClick={() => {
                                  if (window.confirm(`Delete "${p.title}", the choices made for it and every submission and file? This cannot be undone.`)) remove.mutate(p.id);
                                }}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
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
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">Student selections and submissions</h2>
        {selections.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : selections.isError ? (
          <p className="text-sm text-destructive">Could not load the selections.</p>
        ) : rows.length === 0 ? (
          <p className="rounded-md border p-6 text-center text-sm text-muted-foreground">No students have LMS access yet. Grant it under Onboarding.</p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Project</TableHead>
                  <TableHead>Submission</TableHead>
                  <TableHead>Handed in</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.selection_id}>
                    <TableCell>
                      <div className="font-medium">{row.student_name}</div>
                      <div className="text-xs text-muted-foreground">{row.student_email}</div>
                    </TableCell>
                    <TableCell>{row.project_title ?? <span className="text-muted-foreground">Not chosen yet</span>}</TableCell>
                    <TableCell>
                      {!row.project_id ? (
                        "-"
                      ) : !row.submitted ? (
                        <span className="text-muted-foreground">Nothing handed in</span>
                      ) : (
                        <div className="space-y-1 text-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="info">{METHOD_LABELS[row.method!]}</Badge>
                            {row.is_late && <Badge variant="warning">Late</Badge>}
                            {row.method === "email" && (
                              <Badge variant={row.received_at ? "success" : "warning"}>{row.received_at ? "Received" : "Awaiting email"}</Badge>
                            )}
                          </div>
                          {row.repository_url && (
                            <a href={row.repository_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
                              <ExternalLink className="h-3.5 w-3.5" />
                              <span className="max-w-xs truncate">{row.repository_url}</span>
                            </a>
                          )}
                          {row.files.map((f) => (
                            <a key={f.id} href={f.url ?? "#"} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 hover:underline">
                              <FileText className="h-3.5 w-3.5 shrink-0" />
                              <span className="truncate">{f.filename}</span>
                              <span className="text-xs text-muted-foreground">{formatBytes(f.size_bytes)}</span>
                            </a>
                          ))}
                          {row.note && <p className="max-w-md whitespace-pre-wrap text-xs text-muted-foreground">{row.note}</p>}
                          {canManage && row.method === "email" && (
                            <Button size="sm" variant="outline" disabled={received.isPending} onClick={() => received.mutate({ row, received: !row.received_at })}>
                              {row.received_at ? "Mark as not received" : "Mark email as received"}
                            </Button>
                          )}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      {formatDateTime(row.submitted_at)}
                      {row.resubmission_count > 0 && <div className="text-xs text-muted-foreground">changed {row.resubmission_count}x</div>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        {received.isError && <p className="text-sm text-destructive">{errorMessage(received.error, "Could not update that.")}</p>}
      </section>

      {editing && <ProjectFormDialog internshipId={internshipId} project={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => void refresh()} />}
    </div>
  );
}
