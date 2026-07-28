import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type LandingPageStatus,
  landingPageStatusLabels,
} from "@/features/marketing/landing-pages/schemas/landing-page-schemas";

const statusVariants: Record<LandingPageStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  published: "success",
  archived: "destructive",
};

export function LandingPageStatusBadge({ status }: { status: LandingPageStatus }) {
  return <Badge variant={statusVariants[status]}>{landingPageStatusLabels[status]}</Badge>;
}
