import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type ClientStatus, clientStatusLabels } from "@/features/corporate/clients/schemas/client-schemas";

const statusVariants: Record<ClientStatus, BadgeProps["variant"]> = {
  prospect: "info",
  active: "success",
  inactive: "secondary",
  churned: "destructive",
};

export function ClientStatusBadge({ status }: { status: ClientStatus }) {
  return <Badge variant={statusVariants[status]}>{clientStatusLabels[status]}</Badge>;
}
