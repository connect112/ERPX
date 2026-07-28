import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type EventType, eventTypeLabels } from "@/features/events/schemas/event-schemas";

const typeVariants: Record<EventType, BadgeProps["variant"]> = {
  holiday: "success",
  meeting: "info",
  announcement: "warning",
  other: "secondary",
};

export function EventTypeBadge({ type }: { type: EventType }) {
  return <Badge variant={typeVariants[type]}>{eventTypeLabels[type]}</Badge>;
}
