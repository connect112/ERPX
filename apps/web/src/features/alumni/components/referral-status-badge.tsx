import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type ReferralStatus, referralStatusLabels } from "@/features/alumni/schemas/event-schemas";

const statusVariants: Record<ReferralStatus, BadgeProps["variant"]> = {
  open: "success",
  closed: "secondary",
};

export function ReferralStatusBadge({ status }: { status: ReferralStatus }) {
  return <Badge variant={statusVariants[status]}>{referralStatusLabels[status]}</Badge>;
}
