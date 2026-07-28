import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type PostingStatus,
  postingStatusLabels,
} from "@/features/placements/schemas/posting-schemas";

const statusVariants: Record<PostingStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  open: "success",
  closed: "destructive",
};

export function PostingStatusBadge({ status }: { status: PostingStatus }) {
  return <Badge variant={statusVariants[status]}>{postingStatusLabels[status]}</Badge>;
}
