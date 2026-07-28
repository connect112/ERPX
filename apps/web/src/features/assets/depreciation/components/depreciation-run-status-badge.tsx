import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type DepreciationRunStatus,
  depreciationRunStatusLabels,
} from "@/features/assets/depreciation/schemas/depreciation-schemas";

const statusVariants: Record<DepreciationRunStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  posted: "success",
  cancelled: "destructive",
};

export function DepreciationRunStatusBadge({ status }: { status: DepreciationRunStatus }) {
  return <Badge variant={statusVariants[status]}>{depreciationRunStatusLabels[status]}</Badge>;
}
