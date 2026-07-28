import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type WorkshopStatus,
  workshopStatusLabels,
} from "@/features/workshops/schemas/workshop-schemas";

const statusVariants: Record<WorkshopStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  published: "info",
  ongoing: "success",
  completed: "secondary",
  cancelled: "destructive",
};

export function WorkshopStatusBadge({ status }: { status: WorkshopStatus }) {
  return <Badge variant={statusVariants[status]}>{workshopStatusLabels[status]}</Badge>;
}
