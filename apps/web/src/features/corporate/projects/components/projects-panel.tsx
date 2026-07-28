import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useProjectsList } from "@/features/corporate/projects/api/projects-hooks";
import { ProjectFormDialog } from "@/features/corporate/projects/components/project-form-dialog";
import { ProjectStatusBadge } from "@/features/corporate/projects/components/project-status-badge";
import { projectTypeLabels } from "@/features/corporate/projects/schemas/project-schemas";

export function ProjectsPanel({ clientId }: { clientId: string }) {
  const navigate = useNavigate();
  const { data, isLoading } = useProjectsList({ client_id: clientId, limit: 50 });
  const [formOpen, setFormOpen] = useState(false);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Projects</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New project
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {!isLoading && (data?.items.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No projects yet.</p>
        )}
        {!isLoading && (data?.items.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Start date</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((project) => (
                <TableRow
                  key={project.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/corporate/projects/${project.id}`)}
                >
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {project.project_code}
                  </TableCell>
                  <TableCell className="font-medium">{project.name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {projectTypeLabels[project.project_type]}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(project.start_date).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <ProjectStatusBadge status={project.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <ProjectFormDialog open={formOpen} onOpenChange={setFormOpen} clientId={clientId} />
    </Card>
  );
}
