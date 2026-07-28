import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type ContractStatus,
  contractStatusLabels,
} from "@/features/corporate/contracts/schemas/contract-schemas";

const statusVariants: Record<ContractStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  active: "success",
  expired: "destructive",
  terminated: "destructive",
  renewed: "info",
};

export function ContractStatusBadge({ status }: { status: ContractStatus }) {
  return <Badge variant={statusVariants[status]}>{contractStatusLabels[status]}</Badge>;
}
