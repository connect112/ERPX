import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type TicketStatus, ticketStatusLabels } from "@/features/corporate/tickets/schemas/ticket-schemas";

const statusVariants: Record<TicketStatus, BadgeProps["variant"]> = {
  open: "info",
  in_progress: "warning",
  on_hold: "secondary",
  resolved: "success",
  closed: "secondary",
};

export function TicketStatusBadge({ status }: { status: TicketStatus }) {
  return <Badge variant={statusVariants[status]}>{ticketStatusLabels[status]}</Badge>;
}
