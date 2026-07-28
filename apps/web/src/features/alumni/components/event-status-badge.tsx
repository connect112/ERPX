import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type EventStatus, eventStatusLabels } from "@/features/alumni/schemas/event-schemas";

const statusVariants: Record<EventStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  published: "success",
  completed: "info",
  cancelled: "destructive",
};

export function EventStatusBadge({ status }: { status: EventStatus }) {
  return <Badge variant={statusVariants[status]}>{eventStatusLabels[status]}</Badge>;
}
