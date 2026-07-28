import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type CommunicationStatus,
  statusLabels,
} from "@/features/communication/schemas/communication-schemas";

const statusVariants: Record<CommunicationStatus, BadgeProps["variant"]> = {
  sent: "success",
  failed: "destructive",
};

export function CommunicationStatusBadge({ status }: { status: CommunicationStatus }) {
  return <Badge variant={statusVariants[status]}>{statusLabels[status]}</Badge>;
}
