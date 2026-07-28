import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type CampaignStatus,
  campaignStatusLabels,
} from "@/features/marketing/campaigns/schemas/campaign-schemas";

const statusVariants: Record<CampaignStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  scheduled: "info",
  active: "success",
  paused: "warning",
  completed: "secondary",
  cancelled: "destructive",
};

export function CampaignStatusBadge({ status }: { status: CampaignStatus }) {
  return <Badge variant={statusVariants[status]}>{campaignStatusLabels[status]}</Badge>;
}
