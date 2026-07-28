import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type HackathonStatus,
  hackathonStatusLabels,
} from "@/features/hackathons/schemas/hackathon-schemas";

const statusVariants: Record<HackathonStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  registration_open: "info",
  ongoing: "success",
  completed: "secondary",
  cancelled: "destructive",
};

export function HackathonStatusBadge({ status }: { status: HackathonStatus }) {
  return <Badge variant={statusVariants[status]}>{hackathonStatusLabels[status]}</Badge>;
}
