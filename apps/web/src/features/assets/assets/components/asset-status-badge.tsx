import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type AssetStatus, assetStatusLabels } from "@/features/assets/assets/schemas/asset-schemas";

const statusVariants: Record<AssetStatus, BadgeProps["variant"]> = {
  in_use: "success",
  in_storage: "secondary",
  under_maintenance: "warning",
  disposed: "destructive",
};

export function AssetStatusBadge({ status }: { status: AssetStatus }) {
  return <Badge variant={statusVariants[status]}>{assetStatusLabels[status]}</Badge>;
}
