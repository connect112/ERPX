import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type ProjectStatus, projectStatusLabels } from "@/features/corporate/projects/schemas/project-schemas";

const statusVariants: Record<ProjectStatus, BadgeProps["variant"]> = {
  planned: "secondary",
  in_progress: "info",
  on_hold: "warning",
  completed: "success",
  cancelled: "destructive",
};

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return <Badge variant={statusVariants[status]}>{projectStatusLabels[status]}</Badge>;
}
