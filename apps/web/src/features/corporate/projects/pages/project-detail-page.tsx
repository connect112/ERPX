import { ArrowLeft, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useClient } from "@/features/corporate/clients/api/clients-hooks";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import {
  useChangeProjectStatus,
  useProject,
  useUpdateProject,
} from "@/features/corporate/projects/api/projects-hooks";
import { ProjectStatusBadge } from "@/features/corporate/projects/components/project-status-badge";
import {
  type ProjectStatus,
  projectStatusLabels,
  projectStatusValues,
  projectTypeLabels,
} from "@/features/corporate/projects/schemas/project-schemas";
import { VAPTPanel } from "@/features/corporate/vapt/components/vapt-panel";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: project, isLoading } = useProject(projectId);
  const { data: client } = useClient(project?.client_id);
  const { data: employees } = useEmployeesList({ limit: 200 });
  const changeStatus = useChangeProjectStatus(projectId ?? "");
  const updateProject = useUpdateProject(projectId ?? "");

  const [editOpen, setEditOpen] = useState(false);
  const [notes, setNotes] = useState("");

  if (isLoading || !project) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const managerName = employees?.items.find((e) => e.id === project.project_manager_employee_id)?.full_name;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate(`/corporate/clients/${project.client_id}`)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{project.project_code}</span>
              <ProjectStatusBadge status={project.status} />
            </div>
          </div>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            setNotes(project.notes ?? "");
            setEditOpen(true);
          }}
        >
          <Pencil className="h-4 w-4" />
          Edit
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Project details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Client" value={client?.name || "—"} />
              <DetailRow label="Type" value={projectTypeLabels[project.project_type]} />
              <DetailRow label="Project manager" value={managerName || "—"} />
              <DetailRow label="Start date" value={new Date(project.start_date).toLocaleDateString()} />
              <DetailRow
                label="End date"
                value={project.end_date ? new Date(project.end_date).toLocaleDateString() : "—"}
              />
              <DetailRow
                label="Budget"
                value={project.budget_amount != null ? project.budget_amount.toLocaleString() : "—"}
              />
              {project.description && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Description</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{project.description}</p>
                </div>
              )}
              {project.notes && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Notes</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{project.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change status</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={project.status}
                onValueChange={(value) => changeStatus.mutate(value as ProjectStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {projectStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {projectStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      {project.project_type === "vapt" && <VAPTPanel projectId={project.id} />}

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit project notes</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                updateProject.mutate({ notes }, { onSuccess: () => setEditOpen(false) })
              }
              disabled={updateProject.isPending}
            >
              {updateProject.isPending ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
