import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type ReferralStatus,
  referralStatusLabels,
} from "@/features/marketing/referrals/schemas/referral-schemas";

const statusVariants: Record<ReferralStatus, BadgeProps["variant"]> = {
  pending: "warning",
  converted: "info",
  rewarded: "success",
  expired: "secondary",
  rejected: "destructive",
};

export function ReferralStatusBadge({ status }: { status: ReferralStatus }) {
  return <Badge variant={statusVariants[status]}>{referralStatusLabels[status]}</Badge>;
}
